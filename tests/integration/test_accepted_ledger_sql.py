"""Actual isolated AL SQL tests; unsigned data is never operational authority."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from uuid import UUID, uuid4

import psycopg2
import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs.ledger_repository import (
    AcceptedLedgerRepository,
    accepted_ledger_transaction,
)
from services.scan.occurrence_store.models import RequestInput
from tests import accepted_input_fixtures as af
from tests import occurrence_store_fixtures as of
from tests.unit import test_accepted_ledger_commands as commands

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.occurrence_store_postgres"]


def instant(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class SqlLedger:
    """Private fixture identity/bytes; uses real owners and restricted SQL roles."""

    def __init__(self, pg, *, scope="customer"):
        self.pg = pg
        self.tenant_org, self.codebase = pg.scope()
        self.org = self.tenant_org if scope == "customer" else None
        self.namespace, self.registry = uuid4(), uuid4()
        original = af.bundle_fixture()
        manifest, models = c.decode_spec(original.spec_bytes)
        manifest.update(
            scope=scope,
            org_id=str(self.org) if self.org is not None else None,
            registry_id=str(self.registry),
            bundle_id=str(uuid4()),
        )
        self.bundle = m.AcceptedBundleBytes(
            c.encode_spec(c.encode_document(manifest, s.S_MANIFEST), models),
            original.detector_blobs,
            original.rule_blobs,
        )
        self.expected, self.objects, self.admission = commands.publication(self.bundle)
        self.manifest = manifest
        now = datetime.now(UTC).replace(microsecond=0)
        self.policy = c.decode_document(self.objects["current-policy"], s.POLICY)
        self.policy["valid_from"] = instant(now - timedelta(minutes=1))
        self.policy["expires_at"] = instant(now + timedelta(hours=1))
        self.policy["grants"][0].update(
            not_before=self.policy["valid_from"], not_after=self.policy["expires_at"]
        )
        self.objects["current-policy"] = c.encode_document(self.policy, s.POLICY)
        self.checkpoint = c.decode_document(self.objects["admission-checkpoint"], s.ADMISSION)
        self.checkpoint.update(
            policy_digest=c.domain_digest(s.POLICY, self.objects["current-policy"]),
            issued_at=instant(now - timedelta(seconds=30)),
            expires_at=instant(now + timedelta(minutes=30)),
        )
        self.objects["admission-checkpoint"] = c.encode_document(self.checkpoint, s.ADMISSION)
        adoption = c.decode_document(self.objects["operator-adoption"], s.ADOPTION)
        adoption["decided_at"] = instant(now - timedelta(seconds=1))
        self.objects["operator-adoption"] = c.encode_document(adoption, s.ADOPTION)
        inventory = c.decode_document(self.objects["approval-evidence-inventory"], s.INVENTORY)
        inventory["objects"][0].update(
            length=len(self.objects["operator-adoption"]),
            raw_sha256=c.raw_digest(self.objects["operator-adoption"]),
        )
        self.objects["approval-evidence-inventory"] = c.encode_document(inventory, s.INVENTORY)
        self.approval = c.decode_document(self.objects["approval-statement"], s.APPROVAL)
        self.approval.update(
            issued_at=instant(now),
            trust_policy_digest=self.checkpoint["policy_digest"],
            evidence_inventory_digest=c.domain_digest(
                s.INVENTORY, self.objects["approval-evidence-inventory"]
            ),
        )
        self.objects["approval-statement"] = c.encode_document(self.approval, s.APPROVAL)
        self.admission.update(
            policy_digest=self.checkpoint["policy_digest"],
            checkpoint_digest=c.domain_digest(s.ADMISSION, self.objects["admission-checkpoint"]),
        )
        self.revision = 0
        self.installed = m.InstalledTrust(
            registry_id=self.registry,
            scope=scope,
            org_id=self.org,
            deployment_id=UUID(self.checkpoint["deployment_id"]),
            administrator_actor_id=UUID(self.checkpoint["administrator_actor_id"]),
            root_spki_sha256=c.raw_digest(self.objects["trust-root-spki"]),
        )
        with pg.admin() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE scanipy_accepted_owner")
            repository = AcceptedLedgerRepository(connection, self.namespace, self.org)
            assert repository.initialize_registry_namespace(self.installed) == (
                self.namespace,
                False,
            )
            connection.commit()

    @contextmanager
    def repo(self, role="resolver"):
        with accepted_ledger_transaction(
            lambda: self.pg.connection("accepted_" + role), self.namespace, self.org
        ) as repository:
            yield repository

    def command(self, action, body, roles=(), parts=(), *, key=None, revision=None):
        data, parts = commands.command(action, body, roles, tuple(parts))
        value = c.parse_json(data)
        value.update(
            namespace_id=str(self.namespace),
            operation_key=str(key or uuid4()),
            expected_coordination_revision=self.revision if revision is None else revision,
        )
        return c.canonical_bytes(value), parts

    def activate(self):
        policy_command = self.command(
            "install-policy",
            {"predecessor_policy_digest": None},
            ("policy", "root-signature"),
            (self.objects["current-policy"], self.objects["current-policy-signature"]),
        )
        with self.repo("policy_admin") as repository:
            policy = repository.install_policy(*policy_command)
        self.revision += 1
        checkpoint_command = self.command(
            "record-admission",
            {"predecessor_checkpoint_digest": None},
            ("checkpoint", "root-signature"),
            (self.objects["admission-checkpoint"], self.objects["admission-checkpoint-signature"]),
        )
        with self.repo("policy_admin") as repository:
            checkpoint = repository.record_admission(*checkpoint_command)
        self.revision += 1
        assert policy.record_bytes == self.objects["current-policy"]
        assert checkpoint.record_bytes == self.objects["admission-checkpoint"]
        self.publication_command = self.command(
            "publish-builtin",
            {
                "admission": self.admission,
                "bundle": self.expected,
                "publisher_artifact_digest": "4" * 64,
            },
            ("publication-input", "accepted-spec", "detector", "rule"),
            (
                af.frame(s.PUBLICATION_INPUT, self.expected, self.objects),
                self.bundle.spec_bytes,
                *self.bundle.detector_blobs,
                *self.bundle.rule_blobs,
            ),
        )
        with self.repo("publisher") as repository:
            self.publication = repository.publish_builtin_bundle(*self.publication_command)
        return self

    def create(self, *, null_pin=None):
        requested = of.request_input(self.org, self.codebase, lease=300)
        plan = requested.planned_policy.value
        detector = self.manifest["detectors"][0]
        binding = plan["bindings"][0]
        binding.update(
            key="accepted-detector/0/python/" + s.PROJECTION + "/" + s.SOURCE_SYNTAX,
            detector_id=detector["detector_id"],
            detector_content_digest=detector["detector_sha256"],
            class_id=detector["class_id"],
            engines=["ifds"],
            rules=[
                {
                    "rule_id": rule["rule_id"],
                    "content_digest": rule["raw_sha256"],
                    "semantic_digest": rule["semantic_descriptor_digest"],
                }
                for rule in detector["rules"]
            ],
        )
        if null_pin is not None:
            role, field = null_pin
            (binding if role == "binding" else plan[role])[field] = None
        planned = of.envelope(
            "planned-policy", **{key: value for key, value in plan.items() if key != "schema"}
        )
        request = requested.request.value
        request["requested_policy_digest"] = planned.digest.hex()
        request = of.envelope(
            "request", **{key: value for key, value in request.items() if key != "schema"}
        )
        self.requested = RequestInput(request, planned)
        self.create_command = self.command(
            "create-bound-request",
            {
                "admission": self.admission,
                "bundle": self.expected,
                "approval_event_id": self.approval["event_id"],
                "verifier_artifact_digest": "4" * 64,
            },
            ("request", "planned-policy"),
            (request.data, planned.data),
        )
        with self.repo() as repository:
            self.sealed = repository.create_bound_request(*self.create_command)
        self.sealed_manifest = c.decode_frame(self.sealed.record_bytes, s.SEALED).manifest
        self.request_id = UUID(self.sealed_manifest["request_id"])
        self.work_id = UUID(
            str(
                self.pg.rows(
                    "SELECT active_detection_work_id "
                    "FROM scanipy_execution.scan_requests WHERE id=%s",
                    (str(self.request_id),),
                )[0][0]
            )
        )
        with self.pg.repo("detector", self.org) as repository:
            claim = repository.claim("capture_detection", of.attempt_policy(), self.work_id)
        assert claim is not None
        self.fence = claim.fence
        return self

    def fence_value(self):
        return {
            "work_item_id": str(self.fence.work_item_id),
            "work_attempt_id": str(self.fence.attempt_id),
            "fencing_token": self.fence.token,
            "work_revision": self.fence.revision,
        }

    def sealing_request(self):
        # Reuse only valid legacy source evidence. Its fixed accepted bytes
        # cannot validate the revised AL request's detector/rule bindings.
        controlled = of.capture_seal(
            self.request_id, of.request_input(self.tenant_org, self.codebase)
        )
        content = of.envelope(
            "accepted-content",
            spec_sha256=c.raw_digest(self.bundle.spec_bytes),
            detector_sha256s=[c.raw_digest(raw) for raw in self.bundle.detector_blobs],
            rule_sha256s=[c.raw_digest(raw) for raw in self.bundle.rule_blobs],
        )
        value = controlled.seal.value
        value.update(
            s_version=self.requested.request.value["requested_s_version"],
            planned_policy_digest=self.requested.planned_policy.digest.hex(),
            bindings=self.requested.planned_policy.value["bindings"],
            accepted_content_digest=content.digest.hex(),
            acceptance_evidence_digest=c.raw_digest(self.sealed.record_bytes),
        )
        seal = of.envelope("seal", **{key: item for key, item in value.items() if key != "schema"})
        # Change every coupled field together; the actual occurrence model
        # validates exact raw content and evidence before any AL command exists.
        captured = replace(
            controlled,
            seal=seal,
            accepted_content=content,
            spec=self.bundle.spec_bytes,
            detectors=self.bundle.detector_blobs,
            rules=self.bundle.rule_blobs,
            authority_evidence=self.sealed.record_bytes,
        )
        return self.command(
            "seal-bound-capture",
            {
                "admission": self.admission,
                "fence": self.fence_value(),
                "resolver_artifact_digest": "4" * 64,
            },
            ("seal", "source-inventory", "accepted-content"),
            (captured.seal.data, captured.inventory.data, captured.accepted_content.data),
        )

    def seal(self):
        self.seal_command = self.sealing_request()
        with self.repo() as repository:
            self.seal_authorization = repository.seal_bound_capture(*self.seal_command)
        return self

    def authorization_request(self, *, ordinal=0):
        invocation = of.invocation().value
        invocation["binding_key"] = self.requested.planned_policy.value["bindings"][0]["key"]
        invocation["run_ordinal"] = ordinal
        raw = of.envelope(
            "run-input", **{key: value for key, value in invocation.items() if key != "schema"}
        )
        return self.command(
            "authorize-detector",
            {
                "admission": self.admission,
                "fence": self.fence_value(),
                "resolver_artifact_digest": "4" * 64,
            },
            ("run-input",),
            (raw.data,),
        )

    def authorize(self):
        self.authorize_command = self.authorization_request()
        with self.repo() as repository:
            self.authorization = repository.authorize_detector_run(*self.authorize_command)
        return c.parse_json(self.authorization.record_bytes)

    def renewal_request(self, previous):
        return self.command(
            "renew-detector",
            {
                "admission": self.admission,
                "fence": {**self.fence_value(), "work_revision": previous["work_revision"]},
                "resolver_artifact_digest": "5" * 64,
                "detector_run_id": previous["detector_run_id"],
                "previous_authorization_id": previous["event_id"],
            },
        )

    def rotate_grant(self, status):
        """Real SQL history with unsigned fixture declarations, never key authority."""
        assert status in ("retired", "revoked")
        prior_policy = self.checkpoint["policy_digest"]
        prior_checkpoint = self.admission["checkpoint_digest"]
        now = instant(datetime.now(UTC).replace(microsecond=0))
        self.policy = deepcopy(self.policy)
        self.policy.update(
            event_id=str(uuid4()),
            revision=self.policy["revision"] + 1,
            previous_policy_digest=prior_policy,
        )
        self.policy["grants"][0].update(status=status, status_changed_at=now)
        raw_policy = c.encode_document(self.policy, s.POLICY)
        command = self.command(
            "install-policy",
            {"predecessor_policy_digest": prior_policy},
            ("policy", "root-signature"),
            (raw_policy, self.objects["current-policy-signature"]),
        )
        with self.repo("policy_admin") as repository:
            repository.install_policy(*command)
        self.revision += 1
        self.checkpoint = deepcopy(self.checkpoint)
        self.checkpoint.update(
            event_id=str(uuid4()),
            policy_digest=c.domain_digest(s.POLICY, raw_policy),
            policy_revision=self.policy["revision"],
            generation=self.checkpoint["generation"] + 1,
            previous_checkpoint_digest=prior_checkpoint,
            issued_at=now,
        )
        raw_checkpoint = c.encode_document(self.checkpoint, s.ADMISSION)
        command = self.command(
            "record-admission",
            {"predecessor_checkpoint_digest": prior_checkpoint},
            ("checkpoint", "root-signature"),
            (raw_checkpoint, self.objects["admission-checkpoint-signature"]),
        )
        with self.repo("policy_admin") as repository:
            repository.record_admission(*command)
        self.revision += 1
        self.admission.update(
            policy_digest=self.checkpoint["policy_digest"],
            policy_revision=self.policy["revision"],
            checkpoint_digest=c.domain_digest(s.ADMISSION, raw_checkpoint),
            checkpoint_generation=self.checkpoint["generation"],
        )
        return self


def execution_binding(raw):
    document = c.decode_document(raw, s.EXECUTION)
    fields = {
        name: document["event_id" if name == "authorization_event_id" else name]
        for name in s.EXECUTION_BINDING
        if name != "authorization_digest"
    }
    fields["authorization_digest"] = c.domain_digest(s.EXECUTION, raw)
    return c.decode_record(fields, m.ExecutionBinding, s.EXECUTION_BINDING)


def counts(ledger):
    return ledger.pg.rows(
        "SELECT (SELECT count(*) FROM scanipy_accepted_inputs.authority_events "
        "WHERE namespace_id=%s), (SELECT count(*) FROM scanipy_execution.detector_runs "
        "WHERE request_id=%s)",
        (str(ledger.namespace), str(ledger.request_id)),
    )[0]


def detector_run_snapshot(pg, run_id):
    return [
        (state, bytes(input_bytes))
        for state, input_bytes in pg.rows(
            "SELECT state,input_bytes FROM scanipy_execution.detector_runs WHERE id=%s",
            (run_id,),
        )
    ]


@pytest.fixture
def ledger(accepted_ledger_pg):
    return SqlLedger(accepted_ledger_pg).activate()


def test_fixture_roundtrip_preserves_old_history_definitions_and_isolated_roles(accepted_ledger_pg):
    pg = accepted_ledger_pg
    assert pg.round_trip_verified and pg.accepted_round_trip_verified
    assert pg._execution_definitions() == pg.execution_definitions
    assert "accepted_owner" not in pg.roles


def test_historical_publication_bundle_and_binding_are_exact_owner_bytes(ledger):
    with ledger.repo("publisher") as repository:
        replay = repository.publish_builtin_bundle(*ledger.publication_command)
        assert replay.replayed and replay.record_bytes == ledger.publication.record_bytes
    expected = c.decode_record(ledger.expected, m.BundleExpectation, s.BUNDLE_EXPECTATION)
    with ledger.repo("reader") as repository:
        bundle = repository.read_exact_bundle(expected)
    with ledger.repo("reader") as repository:
        receipt = repository.read_publication_receipt(
            publication_key=UUID(ledger.approval["publication_key"])
        )
    with ledger.repo("reader") as repository:
        approval, support = repository.read_authority_event(
            "approval",
            UUID(ledger.approval["event_id"]),
            c.domain_digest(s.APPROVAL, ledger.objects["approval-statement"]),
        )
    assert bundle == ledger.bundle and receipt == ledger.publication.record_bytes
    assert approval == ledger.objects["approval-statement"]
    assert support == (ledger.publication_command[1][0], receipt)
    ledger.create()
    with ledger.repo("reader") as repository:
        assert (
            repository.read_request_binding(ledger.codebase, ledger.request_id)
            == ledger.sealed.record_bytes
        )


def test_initial_real_run_is_running_and_same_command_replays_without_new_authority(ledger):
    ledger.create().seal()
    document = ledger.authorize()
    assert document["schema"] == s.EXECUTION and document["action"] == "initial"
    assert ledger.pg.rows(
        "SELECT state FROM scanipy_execution.detector_runs WHERE id=%s",
        (document["detector_run_id"],),
    ) == [("running",)]
    with ledger.repo() as repository:
        replay = repository.authorize_detector_run(*ledger.authorize_command)
    assert replay.replayed and replay.record_bytes == ledger.authorization.record_bytes
    assert ledger.pg.rows(
        "SELECT count(*) FROM scanipy_accepted_inputs.authority_events "
        "WHERE namespace_id=%s AND kind='execution-authorization'",
        (str(ledger.namespace),),
    ) == [(1,)]


@pytest.mark.parametrize(
    "role,field",
    [
        ("binding", "expected_tool_digest"),
        ("binding", "expected_code_digest"),
        ("binding", "expected_image_digest"),
        ("capture_detection_runner", "expected_code_digest"),
        ("capture_detection_runner", "expected_image_digest"),
        ("identity_runner", "expected_code_digest"),
        ("identity_runner", "expected_image_digest"),
    ],
)
def test_null_planned_pin_denies_real_run_and_attempt_atomically_without_empty_output_claim(
    ledger, role, field
):
    ledger.create(null_pin=(role, field)).seal()
    document = ledger.authorize()
    assert document["schema"] == s.DENIAL and document["reason"] == "missing-runtime-pin"
    row = ledger.pg.rows(
        "SELECT state,result_bytes,failure_prefix FROM scanipy_execution.detector_runs WHERE id=%s",
        (document["detector_run_id"],),
    )[0]
    failure = of.envelope(
        "run-failure",
        **{key: value for key, value in c.parse_json(bytes(row[1])).items() if key != "schema"},
    )
    assert row[0] == "failed" and bytes(row[2]) == b""
    assert (
        failure.value["observed_byte_count"] is None
        and failure.value["observed_full_sha256"] is None
    )
    assert failure.value["truncated"] is True
    assert ledger.pg.rows(
        "SELECT state FROM scanipy_execution.work_attempts WHERE id=%s",
        (str(ledger.fence.attempt_id),),
    ) == [("failed",)]
    assert ledger.pg.rows(
        "SELECT count(*) FROM scanipy_accepted_inputs.authority_events "
        "WHERE namespace_id=%s AND kind='execution-authorization'",
        (str(ledger.namespace),),
    ) == [(0,)]
    with ledger.repo() as repository:
        replay = repository.authorize_detector_run(*ledger.authorize_command)
    assert replay.replayed and replay.record_bytes == ledger.authorization.record_bytes


def test_changed_original_command_cannot_replay_or_adopt_history(ledger):
    data, parts = ledger.publication_command
    changed = c.parse_json(data)
    changed["body"]["publisher_artifact_digest"] = "f" * 64
    with pytest.raises(s.VerificationError):
        with ledger.repo("publisher") as repository:
            repository.publish_builtin_bundle(c.canonical_bytes(changed), parts)


def test_positive_renewal_advances_actual_revision_and_preserves_current_read_binding(ledger):
    ledger.create().seal()
    initial = ledger.authorize()
    request = ledger.renewal_request(initial)
    with ledger.repo() as repository:
        renewed = repository.renew_authorized_execution(*request)
    document = c.decode_document(renewed.record_bytes, s.EXECUTION)
    assert (
        document["action"] == "renew" and document["work_revision"] == initial["work_revision"] + 1
    )
    assert document["previous_authorization_id"] == initial["event_id"]
    binding = execution_binding(renewed.record_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    with ledger.repo() as repository:
        current, live, reference = repository.read_execution_authority(binding, admission)
    assert current.binding == binding
    with ledger.repo() as repository:
        assert (
            repository.recheck_execution_authority(binding, admission, current, live, reference)
            is None
        )
    stale = replace(binding, work_revision=initial["work_revision"])
    with pytest.raises(s.VerificationError):
        with ledger.repo() as repository:
            repository.read_execution_authority(stale, admission)


@pytest.mark.parametrize("initial", (True, False))
def test_revocation_denies_atomically_and_does_not_renew_or_rewrite_prior_authority(
    ledger, initial
):
    ledger.create().seal()
    previous = None if initial else ledger.authorize()
    prior_bytes = None if initial else ledger.authorization.record_bytes
    old_expiry = ledger.pg.rows(
        "SELECT lease_expires_at FROM scanipy_execution.work_attempts WHERE id=%s",
        (str(ledger.fence.attempt_id),),
    )[0][0]
    ledger.rotate_grant("revoked")
    command = ledger.authorization_request() if initial else ledger.renewal_request(previous)
    method = "authorize_detector_run" if initial else "renew_authorized_execution"
    with ledger.repo() as repository:
        result = getattr(repository, method)(*command)
    denial = c.decode_document(result.record_bytes, s.DENIAL)
    assert denial["reason"] == "grant-revoked"
    assert ledger.pg.rows(
        "SELECT state,lease_expires_at FROM scanipy_execution.work_attempts WHERE id=%s",
        (str(ledger.fence.attempt_id),),
    ) == [("failed", old_expiry)]
    assert ledger.pg.rows(
        "SELECT state FROM scanipy_execution.detector_runs WHERE id=%s",
        (denial["detector_run_id"],),
    ) == [("failed",)]
    if not initial:
        assert (
            bytes(
                ledger.pg.rows(
                    "SELECT record_bytes FROM scanipy_accepted_inputs.authority_events "
                    "WHERE namespace_id=%s AND id=%s",
                    (str(ledger.namespace), previous["event_id"]),
                )[0][0]
            )
            == prior_bytes
        )
    with ledger.repo() as repository:
        replay = getattr(repository, method)(*command)
    assert replay.replayed and replay.record_bytes == result.record_bytes


@pytest.mark.parametrize("failure_table", ("detector_runs", "work_attempts"))
def test_failure_between_denial_and_lower_terminal_writes_rolls_back_every_row(
    ledger, failure_table
):
    ledger.create(null_pin=("binding", "expected_image_digest")).seal()
    command = ledger.authorization_request()
    before = counts(ledger)
    # This transient trigger belongs only to the disposable test database and
    # this transaction. Rollback removes both it and every partially written row.
    with ledger.pg.admin() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE FUNCTION pg_temp.al_terminal_fault() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'controlled terminal fault'; END $$"
            )
            cursor.execute(
                "CREATE TRIGGER al_terminal_fault BEFORE UPDATE ON "
                f"scanipy_execution.{failure_table} FOR EACH ROW WHEN (NEW.state='failed') "
                "EXECUTE FUNCTION pg_temp.al_terminal_fault()"
            )
            cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(psycopg2.Error) as captured:
            repository.authorize_detector_run(*command)
        assert captured.value.diag.message_primary == "controlled terminal fault"
        connection.rollback()
    assert counts(ledger) == before
    assert ledger.pg.rows(
        "SELECT state FROM scanipy_execution.work_attempts WHERE id=%s",
        (str(ledger.fence.attempt_id),),
    ) == [("running",)]
    with ledger.repo() as repository:
        assert (
            c.parse_json(repository.authorize_detector_run(*command).record_bytes)["schema"]
            == s.DENIAL
        )


def test_existing_unbound_lower_run_is_not_adopted_and_remains_unchanged(ledger):
    ledger.create().seal()
    command = ledger.authorization_request()
    value = c.parse_json(command[1][0])
    invocation = of.envelope(
        "run-input", **{key: item for key, item in value.items() if key != "schema"}
    )
    with ledger.pg.repo("detector", ledger.org) as repository:
        lower = repository.begin_detector_run(ledger.fence, invocation)
    row_before = detector_run_snapshot(ledger.pg, lower["run_id"])
    assert row_before == [("running", invocation.data)]
    before = counts(ledger)
    with pytest.raises(s.VerificationError):
        with ledger.repo() as repository:
            repository.authorize_detector_run(*command)
    assert counts(ledger) == before
    assert detector_run_snapshot(ledger.pg, lower["run_id"]) == row_before


@pytest.mark.parametrize("action", ("seal", "authorize", "read", "renew"))
def test_hex_pin_is_local_and_hostile_escape_setting_is_restored(ledger, action):
    ledger.create()
    if action != "seal":
        ledger.seal()
    if action in ("read", "renew"):
        previous = ledger.authorize()
    # Capture the actual facade call under a caller-supplied GUC. The function
    # configuration owns the pin, and PostgreSQL restores the caller afterwards.
    with ledger.pg.connection("accepted_resolver") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET bytea_output='escape'")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        if action == "seal":
            # Build the exact command in a separate transaction, then replay it
            # here: replay paths are also required to restore the hostile GUC.
            ledger.seal()
            repository.seal_bound_capture(*ledger.seal_command)
        elif action == "authorize":
            repository.authorize_detector_run(*ledger.authorization_request())
        elif action == "renew":
            repository.renew_authorized_execution(*ledger.renewal_request(previous))
        else:
            repository.read_execution_authority(
                execution_binding(ledger.authorization.record_bytes),
                c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION),
            )
        with connection.cursor() as cursor:
            cursor.execute("SHOW bytea_output")
            assert cursor.fetchone() == ("escape",)
        connection.commit()


def test_same_operation_key_cannot_cross_command_tables_or_actions(ledger):
    ledger.create()
    data, parts = ledger.create_command
    key = UUID(c.parse_json(data)["operation_key"])
    conflicting = ledger.command(
        "publish-builtin",
        c.parse_json(ledger.publication_command[0])["body"],
        ("publication-input", "accepted-spec", "detector", "rule"),
        ledger.publication_command[1],
        key=key,
    )
    with pytest.raises(s.VerificationError):
        with ledger.repo("publisher") as repository:
            repository.publish_builtin_bundle(*conflicting)
    with ledger.repo() as repository:
        replay = repository.create_bound_request(data, parts)
    assert replay.replayed and replay.record_bytes == ledger.sealed.record_bytes


def test_sql_malformed_part_lower_bounds_cannot_bypass_command_closure(ledger):
    data, _ = ledger.publication_command
    with ledger.pg.connection("accepted_publisher") as connection:
        AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.publish_builtin_bundle_v1(%s,"
                "array_fill('x'::bytea,ARRAY[4],ARRAY[0]))",
                (data,),
            )
        assert captured.value.pgcode == "P0001"
        connection.rollback()


@pytest.mark.parametrize("use_current_read", (False, True))
@pytest.mark.parametrize("extra", (0, 1))
def test_actual_bridge_request_census_n_and_n_plus_one_includes_planned_run(
    ledger, use_current_read, extra
):
    ledger.create().seal()
    if use_current_read:
        ledger.authorize()
    wanted = 65536 + extra - (0 if use_current_read else 1)
    existing = 3 if use_current_read else 2  # one work, one attempt, optional target run
    count = wanted - existing
    command = ledger.authorization_request()
    invocation = command[1][0]
    capture, seal = ledger.pg.rows(
        "SELECT capture_id,id FROM scanipy_execution.scan_seals WHERE request_id=%s",
        (str(ledger.request_id),),
    )[0]
    # Explicit privileged census fixture, not fabricated execution evidence:
    # these rows exercise relational admission only. They are NOT proof that
    # arbitrary owner-injected history meets the ordinary-history induction.
    # Every row is terminal, in one acyclic supersession chain; no active row or
    # accepted event is introduced. No scanner/runtime is invoked by this test.
    # Roll back the entire synthetic census: it is not durable execution history.
    before = counts(ledger)
    with ledger.pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "WITH ids AS (SELECT n,md5(%s||':'||n)::uuid AS id "
            "FROM generate_series(1,%s) n), ordered AS "
            "(SELECT n,id,lag(id) OVER (ORDER BY n) AS prior FROM ids) "
            "INSERT INTO scanipy_execution.detector_runs "
            "(id,org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,"
            "detector_binding_key,run_ordinal,supersedes_run_id,input_schema,input_bytes,input_digest,"
            "state,terminal_at,result_bytes,result_schema,result_digest) "
            "SELECT id,%s,%s,%s,%s,%s,%s,%s,%s,n,prior,'scanipy-execution/run-input/1',"
            "%s,%s,'failed',clock_timestamp(),'{}'::bytea,'scanipy-execution/run-failure/1',"
            "sha256('{}'::bytea) FROM ordered ORDER BY n",
            (
                str(uuid4()),
                count,
                str(ledger.org),
                str(ledger.codebase),
                str(ledger.request_id),
                str(capture),
                str(seal),
                str(ledger.work_id),
                str(ledger.fence.attempt_id),
                ledger.requested.planned_policy.value["bindings"][0]["key"],
                invocation,
                bytes.fromhex(c.domain_digest("scanipy-execution/run-input/1", invocation)),
            ),
        )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)

        def call():
            if use_current_read:
                return repository.read_execution_authority(
                    execution_binding(ledger.authorization.record_bytes),
                    c.decode_record(
                        ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION
                    ),
                )
            return repository.authorize_detector_run(*command)

        if extra:
            with pytest.raises(s.VerificationError):
                call()
        else:
            result = call()
            if use_current_read:
                assert result[0].binding == execution_binding(ledger.authorization.record_bytes)
            else:
                assert c.parse_json(result.record_bytes)["schema"] == s.EXECUTION
        connection.rollback()
    assert counts(ledger) == before


def test_competing_exact_authorizations_serialize_to_one_original_receipt(ledger):
    ledger.create().seal()
    command = ledger.authorization_request()
    started = Event()
    finished = Event()
    results, errors = [], []

    def competing():
        started.set()
        try:
            with ledger.repo() as repository:
                results.append(repository.authorize_detector_run(*command))
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    with ledger.pg.connection("accepted_resolver") as first:
        repository = AcceptedLedgerRepository(first, ledger.namespace, ledger.org)
        original = repository.authorize_detector_run(*command)
        thread = Thread(target=competing, daemon=True)
        thread.start()
        assert started.wait(1)
        assert not finished.wait(0.05)
        first.commit()
    assert finished.wait(5)
    thread.join(1)
    assert not thread.is_alive() and errors == [] and len(results) == 1
    assert results[0].replayed and results[0].record_bytes == original.record_bytes
    assert counts(ledger)[1] == 1


def test_current_read_rechecks_actual_expiry_after_namespace_lock_wait(ledger):
    ledger.create().seal()
    document = ledger.authorize()
    binding = execution_binding(ledger.authorization.record_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    began, finished = Event(), Event()
    errors, results = [], []

    def reader():
        began.set()
        try:
            with ledger.repo() as repository:
                results.append(repository.read_execution_authority(binding, admission))
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    # Deliberately retire the actual lower lease during a held AL parent lock;
    # we do not rewrite immutable EXECUTION bytes or assert a caller timestamp.
    with ledger.pg.admin() as blocker, blocker.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM scanipy_accepted_inputs.registry_namespaces WHERE id=%s FOR UPDATE",
            (str(ledger.namespace),),
        )
        thread = Thread(target=reader, daemon=True)
        thread.start()
        assert began.wait(1) and not finished.wait(0.05)
        cursor.execute(
            "UPDATE scanipy_execution.work_attempts "
            "SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (document["work_attempt_id"],),
        )
        blocker.commit()
    assert finished.wait(5)
    thread.join(1)
    assert not thread.is_alive() and results == []
    assert len(errors) == 1 and isinstance(errors[0], s.VerificationError)


@pytest.mark.parametrize("recheck", (False, True))
def test_current_leaf_advance_is_seen_after_namespace_wait_without_history_row_lock(
    ledger, recheck
):
    ledger.create().seal()
    initial = ledger.authorize()
    original_bytes = ledger.authorization.record_bytes
    binding = execution_binding(original_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    with ledger.repo() as repository:
        prior = repository.read_execution_authority(binding, admission)
    started, finished = Event(), Event()
    results, errors = [], []

    def reader():
        started.set()
        try:
            with ledger.repo() as repository:
                if recheck:
                    results.append(
                        repository.recheck_execution_authority(binding, admission, *prior)
                    )
                else:
                    results.append(repository.read_execution_authority(binding, admission))
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()

    thread = None
    try:
        with ledger.pg.connection("accepted_resolver") as first:
            repository = AcceptedLedgerRepository(first, ledger.namespace, ledger.org)
            renewed = repository.renew_authorized_execution(*ledger.renewal_request(initial))
            # The new immutable leaf exists only in this transaction; its parent
            # namespace lock prevents the competing current read from proceeding.
            thread = Thread(target=reader, daemon=True)
            thread.start()
            assert started.wait(1) and not finished.wait(0.05)
            first.commit()
    finally:
        if thread is not None:
            finished.wait(5)
            thread.join(1)
    assert thread is not None and not thread.is_alive()
    assert results == [] and len(errors) == 1
    assert isinstance(errors[0], s.VerificationError) and errors[0].code == "ledger-mismatch"
    with ledger.repo() as repository:
        current, _live, _reference = repository.read_execution_authority(
            execution_binding(renewed.record_bytes), admission
        )
    assert current.binding == execution_binding(renewed.record_bytes)
    assert (
        bytes(
            ledger.pg.rows(
                "SELECT record_bytes FROM scanipy_accepted_inputs.authority_events "
                "WHERE namespace_id=%s AND id=%s",
                (str(ledger.namespace), initial["event_id"]),
            )[0][0]
        )
        == original_bytes
    )


@pytest.mark.parametrize(
    "field", ("request_binding_digest", "publication_receipt_digest", "policy_event_id")
)
def test_r6_rejects_changed_prior_bytes_instead_of_refreshing_them(ledger, field):
    ledger.create().seal().authorize()
    binding = execution_binding(ledger.authorization.record_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    with ledger.repo() as repository:
        previous, live, moment = repository.read_execution_authority(binding, admission)
    altered = replace(previous, **{field: uuid4() if field.endswith("_id") else "f" * 64})
    before = counts(ledger)
    with pytest.raises(s.VerificationError):
        with ledger.repo() as repository:
            repository.recheck_execution_authority(binding, admission, altered, live, moment)
    assert counts(ledger) == before


@pytest.mark.parametrize(
    "action,bridge,poison_at",
    (
        ("seal", "capture", 1),
        ("seal", "capture", 2),
        ("authorize", "capture", 1),
        ("authorize", "detector", 1),
        ("renew", "detector", 1),
        ("renew", "detector", 2),
        ("read", "detector", 1),
        ("recheck", "detector", 1),
    ),
)
def test_transaction_local_future_bridge_observation_cannot_commit_positive_work(
    ledger, action, bridge, poison_at
):
    ledger.create()
    if action != "seal":
        ledger.seal()
    if action in ("renew", "read", "recheck"):
        previous = ledger.authorize()
        binding = execution_binding(ledger.authorization.record_bytes)
        admission = c.decode_record(
            ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION
        )
    if action == "recheck":
        with ledger.repo() as repository:
            prior = repository.read_execution_authority(binding, admission)
    if action == "seal":
        command = ledger.sealing_request()
    elif action == "authorize":
        command = ledger.authorization_request()
    elif action == "renew":
        command = ledger.renewal_request(previous)
    function = "lock_accepted_" + bridge + "_context_v1"
    original = ledger.pg.rows(
        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='scanipy_execution' AND p.proname=%s",
        (function,),
    )[0][0]
    assert original.count("RETURN result;") == 1
    # Override only the observed return field of this NEW bridge, for one
    # transaction/call. The real bridge still locks/checks the actual rows.
    # This is anomaly injection, not an actual DB-clock observation or runtime.
    injected = original.replace(
        "RETURN result;",
        "PERFORM set_config('scanipy.test_bridge_calls',"
        "(coalesce(nullif(current_setting('scanipy.test_bridge_calls',true),''),'0')::int+1)::text,true);"
        f" IF current_setting('scanipy.test_bridge_calls')::int={poison_at} THEN "
        "result:=result||jsonb_build_object('db_now',to_char("
        "(clock_timestamp()+interval '1 day') AT TIME ZONE 'UTC',"
        '\'YYYY-MM-DD"T"HH24:MI:SS.US"Z"\')); END IF; RETURN result;',
    )
    before = counts(ledger)
    lease_before = ledger.pg.rows(
        "SELECT w.revision,a.lease_expires_at FROM scanipy_execution.work_items w "
        "JOIN scanipy_execution.work_attempts a ON a.id=w.active_attempt_id WHERE w.id=%s",
        (str(ledger.work_id),),
    )
    with ledger.pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(injected)
        cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            if action == "read":
                repository.read_execution_authority(binding, admission)
            elif action == "recheck":
                repository.recheck_execution_authority(binding, admission, *prior)
            else:
                method = {
                    "seal": "seal_bound_capture",
                    "authorize": "authorize_detector_run",
                    "renew": "renew_authorized_execution",
                }[action]
                getattr(repository, method)(*command)
        assert captured.value.code == "fence-stale"
        connection.rollback()
    assert counts(ledger) == before
    assert (
        ledger.pg.rows(
            "SELECT w.revision,a.lease_expires_at FROM scanipy_execution.work_items w "
            "JOIN scanipy_execution.work_attempts a ON a.id=w.active_attempt_id WHERE w.id=%s",
            (str(ledger.work_id),),
        )
        == lease_before
    )
    assert ledger.pg.rows(
        "SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='scanipy_execution' AND p.proname=%s",
        (function,),
    ) == [(original,)]


def test_actual_denial_keeps_fixed_generated_k_precharge_within_original_ceiling(ledger):
    ledger.create(null_pin=("binding", "expected_code_digest")).seal()
    with ledger.repo() as repository:
        result = repository.authorize_detector_run(*ledger.authorization_request())
        with repository.connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('scanipy.accepted_work')::jsonb")
            meter = cursor.fetchone()[0]
    fixed = 2 * (8 * 65537 * 65 + 16 * 65536 + 4096) + (8 * 4097 * 17 + 16 * 4096 + 4096)
    assert c.parse_json(result.record_bytes)["schema"] == s.DENIAL
    assert fixed <= meter["used"][6] <= meter["caps"][6] == 2147483648
    assert meter["used"][5] == 28 * 65537  # two bridges, begin/fail/finish, fixed controls

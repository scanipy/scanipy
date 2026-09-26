"""AL-03 facade diagnostics using private driver doubles, never a database."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import ledger_commands as lc
from services.scan.accepted_inputs import ledger_repository as r
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from tests import accepted_input_fixtures as af
from tests.unit import test_accepted_ledger_commands as commands

pytestmark = pytest.mark.unit
NS, ORG = UUID(af.uid(101)), UUID(af.uid(3))
material = af.material
test_only_keys = af.test_only_keys


class Cursor:
    def __init__(self, connection, setup):
        self.connection, self.setup = connection, setup
        self.rows = [] if setup else list(connection.rows)
        self.closed = 0

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, params))
        if not self.setup and self.connection.query_error is not None:
            raise self.connection.query_error

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed += 1
        if not self.setup and self.connection.close_error is not None:
            raise self.connection.close_error


class Connection:
    autocommit = False

    def __init__(self, rows=()):
        self.rows = rows
        self.calls, self.cursors = [], []
        self.query_error = self.close_error = None
        self.commit_error = self.rollback_error = None
        self.commits = self.rollbacks = self.disposals = 0

    def cursor(self):
        cursor = Cursor(self, not self.cursors)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    @contextmanager
    def factory(self):
        try:
            yield self
        finally:
            self.disposals += 1


@pytest.fixture
def cases():
    # These are the unchanged, explicitly unsigned AL-02 diagnostic records.
    return commands.cases.__wrapped__()


def expect_bundle(bundle=None):
    bundle = af.bundle_fixture() if bundle is None else bundle
    expected, _, _ = commands.publication(bundle)
    return bundle, c.decode_record(expected, m.BundleExpectation, s.BUNDLE_EXPECTATION)


@pytest.mark.parametrize("org", (ORG, None))
def test_exact_local_binding_is_not_a_capability_or_commit(org):
    connection = Connection()
    repository = r.AcceptedLedgerRepository(connection, NS, org)
    assert repository.namespace_id == NS
    assert connection.calls == [
        (
            "SELECT set_config('scanipy.accepted_namespace_id',%s,true),"
            "set_config('app.org_id',%s,true),set_config('statement_timeout',%s,true),"
            "set_config('lock_timeout',%s,true)",
            (str(NS), "" if org is None else str(org), "15000", "2000"),
        )
    ]
    assert connection.commits == connection.rollbacks == 0
    assert connection.cursors[0].closed == 1


@pytest.mark.parametrize("value", (True, 1, "false", None))
def test_non_false_autocommit_is_refused_before_binding(value):
    connection = Connection()
    connection.autocommit = value
    with pytest.raises(s.VerificationError):
        r.AcceptedLedgerRepository(connection, NS, ORG)
    assert connection.calls == []


@pytest.mark.parametrize("action", ("install-policy", "record-admission"))
@pytest.mark.parametrize("replayed", (False, True))
@pytest.mark.parametrize("driver_view", (False, True))
def test_original_unsigned_policy_bytes_and_historical_flag_are_preserved(
    cases, action, replayed, driver_view
):
    data, parts = cases[action]
    result_bytes = memoryview(parts[0]) if driver_view else parts[0]
    connection = Connection([(result_bytes, replayed)])
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    operation = (
        repository.install_policy if action == "install-policy" else repository.record_admission
    )
    result = operation(data, parts)
    assert type(result) is r.LedgerResult
    assert result.record_bytes == parts[0] and type(result.record_bytes) is bytes
    assert result.replayed is replayed
    sql, params = connection.calls[-1]
    expected_function = "install_policy_v1" if action == "install-policy" else "record_admission_v1"
    assert sql == f"SELECT * FROM scanipy_accepted_inputs.{expected_function}(%s,%s)"
    assert params == (data, list(parts))
    assert connection.commits == 0
    assert all(cursor.closed == 1 for cursor in connection.cursors)
    with pytest.raises(s.VerificationError):
        operation(data, parts)
    assert len(connection.calls) == 2


@pytest.mark.parametrize(
    "rows", ([], [(b"x",)], [[b"x", False]], [(b"x", False, None)], [(b"x", False), (b"y", True)])
)
def test_exact_one_driver_row_and_column_shape(cases, rows):
    connection = Connection(rows)
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    with pytest.raises(s.VerificationError) as caught:
        repository.install_policy(*cases["install-policy"])
    assert caught.value.code == "content-mismatch"
    assert connection.cursors[-1].closed == 1


@pytest.mark.parametrize("flag", (0, 1, "true", None))
def test_replay_bool_is_not_coerced(cases, flag):
    data, parts = cases["install-policy"]
    repository = r.AcceptedLedgerRepository(Connection([(parts[0], flag)]), NS, ORG)
    with pytest.raises(s.VerificationError) as caught:
        repository.install_policy(data, parts)
    assert caught.value.code == "content-mismatch"


def test_complete_bundle_returns_actual_owner_and_bytes():
    bundle, expected = expect_bundle()
    connection = Connection(
        [
            (
                memoryview(bundle.spec_bytes),
                list(map(memoryview, bundle.detector_blobs)),
                list(bundle.rule_blobs),
            )
        ]
    )
    result = r.AcceptedLedgerRepository(connection, NS, ORG).read_exact_bundle(expected)
    assert type(result) is m.AcceptedBundleBytes
    assert result.spec_bytes == bundle.spec_bytes
    assert result.detector_blobs == bundle.detector_blobs
    assert result.rule_blobs == bundle.rule_blobs
    sql, params = connection.calls[-1]
    assert sql == "SELECT * FROM scanipy_accepted_inputs.read_exact_bundle_v1(%s,%s,%s)"
    assert params == (
        str(NS),
        str(expected.bundle_id),
        bytes.fromhex(expected.accepted_content_digest),
    )


@pytest.mark.parametrize("field", ("namespace", "organization", "bundle"))
@pytest.mark.parametrize("poison", (True, -1, 2**128, object()))
def test_original_uuid_storage_is_rejected_before_query(field, poison):
    _, expected = expect_bundle()
    namespace, org = UUID(str(NS)), UUID(str(ORG))
    target = (
        namespace
        if field == "namespace"
        else org
        if field == "organization"
        else expected.bundle_id
    )
    object.__setattr__(target, "int", poison)
    connection = Connection()
    with pytest.raises(s.VerificationError):
        repository = r.AcceptedLedgerRepository(connection, namespace, org)
        repository.read_exact_bundle(expected)
    assert len(connection.calls) == (1 if field == "bundle" else 0)


@pytest.mark.parametrize("mode", ("commit", "query"))
def test_ambiguous_commit_or_query_failure_propagates_and_discards(mode):
    failure = OSError("private failure")
    connection = Connection()
    if mode == "commit":
        connection.commit_error = failure
    with pytest.raises(OSError) as caught:
        with r.accepted_ledger_transaction(connection.factory, NS, ORG):
            if mode == "query":
                raise failure
    assert caught.value is failure
    assert connection.commits == (1 if mode == "commit" else 0)
    assert connection.rollbacks == connection.disposals == 1


@pytest.mark.parametrize("place", ("cursor", "rollback"))
@pytest.mark.parametrize("explicit", (False, True))
def test_original_primary_and_earlier_chain_survive_cleanup_failure(place, explicit):
    primary = KeyboardInterrupt()
    earlier, cleanup = ValueError("private prior"), OSError("private close")
    if explicit:
        primary.__cause__ = earlier
    else:
        primary.__context__ = earlier
    connection = Connection()
    with pytest.raises(KeyboardInterrupt) as caught:
        if place == "cursor":
            connection.query_error, connection.close_error = primary, cleanup
            repository = r.AcceptedLedgerRepository(connection, NS, ORG)
            repository.read_publication_receipt(publication_key=UUID(af.uid(19)))
        else:
            connection.rollback_error = cleanup
            with r.accepted_ledger_transaction(connection.factory, NS, ORG):
                raise primary
    assert caught.value is primary
    assert isinstance(primary.__cause__, BaseExceptionGroup)
    assert primary.__cause__.exceptions == (earlier, cleanup)
    assert all(cursor.closed == 1 for cursor in connection.cursors)


def test_success_acknowledgment_occurs_only_after_context_exit():
    connection = Connection()
    with r.accepted_ledger_transaction(connection.factory, NS, ORG):
        assert connection.commits == connection.disposals == 0
    assert connection.commits == connection.disposals == 1
    assert connection.rollbacks == 0


@pytest.mark.parametrize(
    "function,columns,void",
    (
        ("drop_table", 1, False),
        ("read_exact_bundle_v1", 2, False),
        ("read_exact_bundle_v1", 3, True),
    ),
)
def test_private_dispatch_cannot_format_unknown_sql_or_wrong_signature(function, columns, void):
    connection = Connection()
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    with pytest.raises(s.VerificationError):
        repository._call(function, ("x", "y", "z"), columns, void=void)
    assert len(connection.calls) == 1


@pytest.mark.parametrize("kind", ("json", "schema", "frame", "spec"))
def test_stored_malformed_owner_bytes_are_content_mismatch(cases, kind):
    if kind in ("json", "schema"):
        raw = b"{" if kind == "json" else b'{"schema":"not-an-owner-schema"}'
        repository = r.AcceptedLedgerRepository(Connection([(raw,)]), NS, ORG)

        def operation():
            return repository.read_publication_receipt(publication_key=UUID(af.uid(19)))

    elif kind == "frame":
        repository = r.AcceptedLedgerRepository(Connection([(b"malformed",)]), NS, ORG)

        def operation():
            return repository.read_request_binding(UUID(af.uid(4)), UUID(af.uid(20)))

    else:
        bundle, expected = expect_bundle()
        repository = r.AcceptedLedgerRepository(
            Connection([(b"malformed", bundle.detector_blobs, bundle.rule_blobs)]), NS, ORG
        )

        def operation():
            return repository.read_exact_bundle(expected)

    with pytest.raises(s.VerificationError) as caught:
        operation()
    assert caught.value.code == "content-mismatch"


def sql_shape(value):
    if type(value) is dict:
        return {key: sql_shape(child) for key, child in value.items()}
    if type(value) is tuple:
        if value[0] == "nullable":
            return {"$nullable": sql_shape(value[1])}
        if value[0] == "enum":
            return {"$enum": list(value[1])}
        assert value[0] == "array"
        return {"$array": sql_shape(value[1]), "$min": value[2], "$max": value[3]}
    return value


def test_frozen_sql_shape_resource_matches_complete_actual_owners():
    root = Path(__file__).resolve().parents[2]
    resource = json.loads((root / "db/migrations/versions/accepted_v1_shapes.json").read_bytes())
    assert set(resource) == {"format", "documents", "records", "commands", "frames"}
    assert resource["format"] == "scanipy-accepted-sql-shapes/1"
    assert resource["commands"] == sql_shape(lc._BODIES)
    assert resource["frames"] == {
        key: [list(row) for row in rows] for key, rows in s.FRAME_ROLES.items()
    }
    assert resource["records"] == sql_shape(
        {
            "BUNDLE_EXPECTATION": s.BUNDLE_EXPECTATION,
            "ADMISSION_EXPECTATION": s.ADMISSION_EXPECTATION,
            "EXECUTION_BINDING": s.EXECUTION_BINDING,
            "LEDGER_EXPECTATION": s.LEDGER_EXPECTATION,
        }
    )
    expected_documents = (
        s.INSTALLED_TRUST,
        s.S_MANIFEST,
        s.DETECTOR,
        s.SEMANTIC_BINDING,
        s.POLICY,
        s.APPROVAL,
        s.INVENTORY,
        s.ADOPTION,
        s.PUBLICATION,
        s.ADMISSION,
        s.SEALED,
        s.LIVE,
        s.PUBLICATION_INPUT,
        s.SEAL_AUTHORIZATION,
        s.EXECUTION,
        s.DENIAL,
    )
    assert resource["documents"] == {key: sql_shape(s.SHAPES[key]) for key in expected_documents}


@pytest.mark.parametrize("expanded", (False, True))
def test_actual_complete_owner_hash_work_is_reserved_before_every_call(monkeypatch, expanded):
    bundle = commands.expanded_bundle() if expanded else af.bundle_fixture()
    bundle, expected = expect_bundle(bundle)
    connection = Connection([(bundle.spec_bytes, bundle.detector_blobs, bundle.rule_blobs)])
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    real_hash, real_reserve = hashlib.sha256, r._Work.reserve
    state = {"calls": 0, "bytes": 0, "work": None}

    def reserve(work, calls, size):
        real_reserve(work, calls, size)
        state["work"] = work

    def sha256(data=b"", **kwargs):
        state["calls"] += 1
        state["bytes"] += len(data)
        work = state["work"]
        assert work is not None
        assert state["calls"] <= work.calls and state["bytes"] <= work.size
        return real_hash(data, **kwargs)

    monkeypatch.setattr(r._Work, "reserve", reserve)
    monkeypatch.setattr(hashlib, "sha256", sha256)
    assert repository.read_exact_bundle(expected) == bundle
    assert state["calls"] > 0


@pytest.mark.parametrize("field", ("detectors", "rules", "spec"))
def test_driver_aggregate_cap_rejects_before_owner_hash_or_decode(monkeypatch, field):
    bundle, expected = expect_bundle()
    row = [bundle.spec_bytes, list(bundle.detector_blobs), list(bundle.rule_blobs)]
    if field == "spec":
        row[0] = memoryview(bytes(s.MAX_CONTENT + 1))
    else:
        row[1 if field == "detectors" else 2] = [memoryview(bytes(s.MAX_CONTENT))]
    repository = r.AcceptedLedgerRepository(Connection([tuple(row)]), NS, ORG)

    def forbidden(*args, **kwargs):
        raise AssertionError("owner decoder reached before aggregate bounds")

    monkeypatch.setattr(c, "decode_spec", forbidden)
    with pytest.raises(s.VerificationError) as caught:
        repository.read_exact_bundle(expected)
    assert caught.value.code == "content-mismatch"


def migration_module():
    """Load definitions only: none of these controls invokes Alembic or PG."""
    filename = Path(__file__).parents[2] / "db/migrations/versions/20260926_0006_accepted_ledger.py"
    spec = importlib.util.spec_from_file_location("accepted_migration_diagnostic", filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_has_exact_roles_tables_entrypoints_and_legacy_grants():
    migration = migration_module()
    assert migration.down_revision == "20260925_0005"
    assert migration.TABLES == (
        "registry_namespaces",
        "artifact_versions",
        "bundle_versions",
        "authority_events",
        "request_bundle_bindings",
    )
    assert migration.ROLES == tuple(
        "scanipy_accepted_" + name
        for name in ("owner", "policy_admin", "publisher", "resolver", "reader")
    )
    assert sum(map(len, migration.MUTATIONS.values())) == 7
    assert len(migration.READS) == 6
    assert len(migration.LOWER_SIGNATURES) == 6
    assert len(migration.BRIDGE_SIGNATURES) == 2
    for signature in migration.LOWER_SIGNATURES:
        assert signature.split("(", 1)[0] in {
            "create_request_v1",
            "register_capture_and_seal_v1",
            "begin_detector_run_v1",
            "renew_capture_detection_v1",
            "fail_detector_run_v1",
            "finish_capture_detection_v1",
        }


@pytest.mark.parametrize("detector", (False, True))
def test_bridge_rendering_is_closed_control_only_and_has_one_shared_census(detector):
    migration = migration_module()
    bridges = migration._bridges(migration._resource("accepted_v1_execution_bridges.sql"))
    source = bridges[int(detector)]
    assert "__" not in source
    assert source.count("CREATE FUNCTION") == 1
    assert "SECURITY DEFINER" in source
    assert "SET bytea_output='hex'" in source
    assert "SET search_path=pg_catalog,scanipy_execution,pg_temp" in source
    assert source.count("LIMIT (65536-seen+1)") == 4
    assert "seen:=planned;" in source
    assert "NOT is_detector AND sealed THEN 1 ELSE 0" in source
    assert "row_to_json(" not in source and "to_jsonb(" not in source
    assert "v1_lock(" not in source and "v1_hash(" not in source
    for name in (
        "request_bytes",
        "planned_policy_bytes",
        "policy_bytes",
        "input_bytes",
        "inventory_bytes",
        "seal_bytes",
        "result_bytes",
    ):
        assert name not in source
    assert (",p_run uuid,p_lease uuid" in source) is detector
    assert ("d.id,'run_input_digest'" in source) is detector
    assert source.index("INTO r FROM scanipy_execution.scan_requests") < source.index(
        "seen:=planned;"
    )
    assert source.index("FOR run_key IN SELECT id") < source.index(
        "INTO l FROM scanipy_execution.capture_leases"
    )
    assert source.index("INTO l FROM scanipy_execution.capture_leases") < source.index(
        "now_at:=clock_timestamp();"
    )


def test_new_acl_sweep_names_only_accepted_namespace_and_exact_new_bridges():
    migration = migration_module()
    source = migration._resource("accepted_v1_acl.sql")
    assert "scanipy_accepted_inputs" in source and "aclexplode" in source
    assert "lock_accepted_capture_context_v1" in source
    assert "lock_accepted_detector_context_v1" in source
    assert "2950 2950 2950 20 20" in source
    assert "2950 2950 2950 20 20 2950 2950" in source
    assert "ALL TABLES IN SCHEMA scanipy_execution" not in source
    assert "ALL FUNCTIONS IN SCHEMA scanipy_execution" not in source


def test_sql_private_hash_gate_precedes_digest_and_occurrence_work_is_not_20k():
    migration = migration_module()
    source = migration._resource("accepted_v1_validation.sql")
    hash_body = source.split("CREATE FUNCTION scanipy_accepted_inputs.v1_hash(", 1)[1].split(
        "END $$;", 1
    )[0]
    assert hash_body.index("v1_charge(0,1)") < hash_body.index("RETURN pg_catalog.sha256")
    assert hash_body.index("v1_charge(1,") < hash_body.index("RETURN pg_catalog.sha256")
    assert "v1_lexical(payloads[i],1048576,1048576,1048576)" in source
    assert "f:=14*a" in source and "f:=78*a+o" in source
    assert "f:=32*a+4*o+4096" in source
    assert "cost<=2147483648/copies" in source
    assert "8*(n+1)*(values_seen+1)+16*n+4096" in source


def test_history_never_formats_whole_accepted_raw_rows_and_has_no_noop_escape():
    migration = migration_module()
    source = migration._resource("accepted_v1_history.sql")
    body = source.split("CREATE FUNCTION scanipy_accepted_inputs.v1_immutable_history()", 1)[
        1
    ].split("END $$;", 1)[0]
    assert "RAISE EXCEPTION 'immutable accepted history'" in body
    assert "RETURN NEW" not in body and "old_row=new_row" not in body
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("--"))
    assert "to_jsonb(NEW)" not in code and "to_jsonb(OLD)" not in code


def test_sql_frozen_model_rows_are_exact_actual_semantic_owner_rows():
    from analysis.ifds.bound_rules import _initial_model

    source = migration_module()._resource("accepted_v1_validation.sql")
    literal = source.split("$models$", 2)[1]
    models = json.loads(literal)
    assert set(models) == {
        "python.string-concat/1",
        "python.os-system/1",
        "java.string-concat/1",
        "java.jdbc-execute-query/1",
    }
    assert models == {name: _initial_model(name) for name in models}
    assert "v1_json(rule_raw,262144,false,50000,24)" in source
    assert "v1_json(model_raw,524288,false,50000,24)" in source
    assert "path<>'' AND octet_length(path)<=1024" in source


def diagnostic_authority_result(cases, action, *, denial=False):
    """Closed unsigned result bytes, not a signer/installation or DB receipt."""
    data, parts = cases[action]
    header = c.parse_json(data)
    value = {}
    for index, (name, rule) in enumerate(s.AUTHORITY_COMMON.items(), 200):
        if rule == "uuid":
            value[name] = af.uid(index)
        elif rule == "digest":
            value[name] = "a" * 64
        elif rule == "instant":
            value[name] = "2026-09-25T00:01:00.000000Z"
        elif rule in ("positive", "count"):
            value[name] = 1
    value.update(header["body"]["admission"])
    value.update(header["body"]["fence"])
    value.update(
        operation_key=header["operation_key"],
        org_id=str(ORG),
        scope="customer",
        work_kind="capture_detection",
        resolver_artifact_digest=header["body"]["resolver_artifact_digest"],
    )
    if action == "seal-bound-capture":
        seal = json.loads(parts[0])
        value.update(
            request_id=seal["request_id"],
            requested_policy_digest=seal["planned_policy_digest"],
            accepted_content_digest=seal["accepted_content_digest"],
            request_binding_digest=seal["acceptance_evidence_digest"],
            authorized_at="2026-09-25T00:00:10.000000Z",
        )
        schema = s.SEAL_AUTHORIZATION
    else:
        value.update(purpose="detector-run", detector_run_id=af.uid(250), occurrence_id=None)
        value["run_input_digest"] = (
            c.domain_digest("scanipy-execution/run-input/1", parts[0]) if parts else "a" * 64
        )
        value["previous_authorization_id"] = header["body"].get("previous_authorization_id")
        if action == "renew-detector":
            value["detector_run_id"] = header["body"]["detector_run_id"]
        if denial:
            schema = s.DENIAL
            value.update(reason="missing-runtime-pin", observed_at="2026-09-25T00:00:10.000000Z")
        else:
            schema = s.EXECUTION
            value.update(
                action="renew" if action == "renew-detector" else "initial",
                authorized_at="2026-09-25T00:00:10.000000Z",
            )
            if action == "renew-detector":
                value["work_revision"] += 1
    return c.encode_document(dict(value, schema=schema), schema)


@pytest.mark.parametrize("action", ("seal-bound-capture", "authorize-detector", "renew-detector"))
@pytest.mark.parametrize("replayed", (False, True))
def test_authority_results_preserve_actual_owner_bytes_without_grant(cases, action, replayed):
    raw = diagnostic_authority_result(cases, action)
    connection = Connection([(memoryview(raw), replayed)])
    result = r.AcceptedLedgerRepository(connection, NS, ORG)._mutate(action, *cases[action])
    assert result.record_bytes == raw and result.replayed is replayed
    assert connection.commits == 0


@pytest.mark.parametrize("action", ("authorize-detector", "renew-detector"))
def test_metadata_only_denial_is_not_rewritten_as_positive(cases, action):
    raw = diagnostic_authority_result(cases, action, denial=True)
    result = r.AcceptedLedgerRepository(Connection([(raw, True)]), NS, ORG)._mutate(
        action, *cases[action]
    )
    assert result.record_bytes == raw
    assert c.decode_document(raw, s.DENIAL)["reason"] == "missing-runtime-pin"


@pytest.mark.parametrize("action", ("seal-bound-capture", "authorize-detector", "renew-detector"))
@pytest.mark.parametrize(
    "field", ("policy_digest", "checkpoint_digest", "admission_epoch", "resolver_artifact_digest")
)
def test_authority_result_cannot_substitute_command_head_or_service_artifact(cases, action, field):
    value = json.loads(diagnostic_authority_result(cases, action))
    value[field] = af.uid(900) if field == "admission_epoch" else "f" * 64
    raw = c.encode_document(value, value["schema"])
    repository = r.AcceptedLedgerRepository(Connection([(raw, False)]), NS, ORG)
    with pytest.raises(s.VerificationError):
        repository._mutate(action, *cases[action])


def test_authorize_result_cannot_substitute_run_input_digest(cases):
    value = json.loads(diagnostic_authority_result(cases, "authorize-detector"))
    value["run_input_digest"] = "f" * 64
    raw = c.encode_document(value, value["schema"])
    with pytest.raises(s.VerificationError):
        r.AcceptedLedgerRepository(Connection([(raw, False)]), NS, ORG).authorize_detector_run(
            *cases["authorize-detector"]
        )


@pytest.mark.parametrize(
    "field",
    ("request_id", "requested_policy_digest", "accepted_content_digest", "request_binding_digest"),
)
def test_seal_result_cannot_substitute_original_intent(cases, field):
    value = json.loads(diagnostic_authority_result(cases, "seal-bound-capture"))
    value[field] = af.uid(900) if field == "request_id" else "f" * 64
    raw = c.encode_document(value, value["schema"])
    with pytest.raises(s.VerificationError):
        r.AcceptedLedgerRepository(Connection([(raw, False)]), NS, ORG).seal_bound_capture(
            *cases["seal-bound-capture"]
        )


def diagnostic_publication_bytes(cases):
    data, parts = cases["publish-builtin"]
    header = c.parse_json(data)
    frame = c.decode_frame(parts[0], s.PUBLICATION_INPUT)
    approval = frame.document("approval-statement")
    receipt = {
        "schema": s.PUBLICATION,
        **{
            key: approval[key]
            for key in (
                "registry_id",
                "scope",
                "org_id",
                "publication_key",
                "bundle_id",
                "accepted_content_digest",
                "evidence_inventory_digest",
            )
        },
        "approval_event_id": approval["event_id"],
        "approval_statement_digest": c.domain_digest(
            s.APPROVAL, frame.object("approval-statement")
        ),
        "approval_signature_sha256": c.raw_digest(frame.object("approval-signature")),
        **header["body"]["admission"],
        "published_at": "2026-09-25T00:00:20.000000Z",
        "publisher_actor_id": approval["issuer_actor_id"],
        "publisher_artifact_digest": header["body"]["publisher_artifact_digest"],
    }
    return c.encode_document(receipt, s.PUBLICATION)


def diagnostic_sealed_bytes(cases):
    header = c.parse_json(cases["create-bound-request"][0])
    request = json.loads(cases["create-bound-request"][1][0])
    _, objects, admission = commands.publication()
    manifest = {
        "registry_id": header["body"]["bundle"]["registry_id"],
        "bundle_id": header["body"]["bundle"]["bundle_id"],
        "accepted_content_digest": header["body"]["bundle"]["accepted_content_digest"],
        "org_id": request["org_id"],
        "codebase_id": request["codebase_id"],
        "request_id": af.uid(20),
        "approval_event_id": header["body"]["approval_event_id"],
        "publication_policy_digest": admission["policy_digest"],
        "current_policy_digest": admission["policy_digest"],
        "current_policy_revision": admission["policy_revision"],
        "checkpoint_digest": admission["checkpoint_digest"],
        "checkpoint_generation": admission["checkpoint_generation"],
        "admission_epoch": admission["admission_epoch"],
        "resolved_at": "2026-09-25T00:00:21.000000Z",
        "verifier_artifact_digest": header["body"]["verifier_artifact_digest"],
    }
    objects = dict(
        objects,
        **{
            "publication-receipt": diagnostic_publication_bytes(cases),
            "publication-policy": objects["current-policy"],
            "publication-policy-signature": objects["current-policy-signature"],
            "publication-checkpoint": objects["admission-checkpoint"],
            "publication-checkpoint-signature": objects["admission-checkpoint-signature"],
        },
    )
    return af.frame(s.SEALED, manifest, objects)


@pytest.mark.parametrize("action", ("publish-builtin", "create-bound-request"))
@pytest.mark.parametrize("replayed", (False, True))
def test_publication_and_binding_results_are_original_unsigned_owner_bytes(cases, action, replayed):
    raw = (
        diagnostic_publication_bytes(cases)
        if action == "publish-builtin"
        else diagnostic_sealed_bytes(cases)
    )
    connection = Connection([(memoryview(raw), replayed)])
    result = r.AcceptedLedgerRepository(connection, NS, ORG)._mutate(action, *cases[action])
    assert result.record_bytes == raw and result.replayed is replayed
    assert connection.commits == 0


@pytest.mark.parametrize("action", ("publish-builtin", "create-bound-request"))
@pytest.mark.parametrize("field", ("checkpoint_digest", "artifact"))
def test_publication_and_binding_result_links_reject_changed_head_or_artifact(cases, action, field):
    if action == "publish-builtin":
        document = c.decode_document(diagnostic_publication_bytes(cases), s.PUBLICATION)
        document["publisher_artifact_digest" if field == "artifact" else field] = "f" * 64
        raw = c.encode_document(document, s.PUBLICATION)
    else:
        frame = c.decode_frame(diagnostic_sealed_bytes(cases), s.SEALED)
        manifest = dict(frame.manifest)
        manifest["verifier_artifact_digest" if field == "artifact" else field] = "f" * 64
        raw = c.encode_frame(
            s.SEALED,
            c.encode_document(manifest, s.SEALED),
            tuple(frame.object(role) for role, _ in s.FRAME_ROLES[s.SEALED]),
        )
    with pytest.raises(s.VerificationError):
        r.AcceptedLedgerRepository(Connection([(raw, True)]), NS, ORG)._mutate(
            action, *cases[action]
        )


def test_create_result_validation_keeps_actual_wide_occurrence_domain(cases):
    from services.scan.occurrence_store.codec import encode_envelope

    original, parts = cases["create-bound-request"]
    request = json.loads(parts[0])
    request["source_selector"]["value"] = "x" * 17000
    changed = (encode_envelope("request", request).data, parts[1])
    data, changed = commands.command(
        "create-bound-request", json.loads(original)["body"], ("request", "planned-policy"), changed
    )
    altered = dict(cases, **{"create-bound-request": (data, changed)})
    raw = diagnostic_sealed_bytes(altered)
    result = r.AcceptedLedgerRepository(Connection([(raw, False)]), NS, ORG).create_bound_request(
        data, changed
    )
    assert result.record_bytes == raw


def test_occurrence_delegate_is_precharged_before_owner_hash(monkeypatch, cases):
    original = r.decode_envelope
    work = r._Work()
    seen = []

    def checked(name, data):
        seen.append((work.calls, work.size))
        assert work.calls == 1
        assert work.size == len(data) + len("scanipy-execution/" + name + "/1\n")
        return original(name, data)

    monkeypatch.setattr(r, "decode_envelope", checked)
    work.occurrence("request", cases["create-bound-request"][1][0])
    assert len(seen) == 1


def sql_function(source, name):
    """Inspect migration source only; this is not PostgreSQL execution evidence."""
    return source.split("CREATE FUNCTION scanipy_accepted_inputs." + name + "(", 1)[1].split(
        "END $$;", 1
    )[0]


@pytest.mark.parametrize(
    ("name", "helper", "lower", "parse"),
    (
        ("create_bound_request_v1", "create", "create_request_v1", True),
        ("seal_bound_capture_v1", "register", "register_capture_and_seal_v1", True),
        ("authorize_detector_run_v1", "begin", "begin_detector_run_v1", True),
        ("renew_authorized_execution_v1", "renew", "renew_capture_detection_v1", False),
    ),
)
def test_sql_lower_admission_source_order_is_explicit(name, helper, lower, parse):
    body = sql_function(migration_module()._resource("accepted_v1_operations.sql"), name)
    preflight = body.index("v1_lower_preflight('" + helper + "'")
    reserve = body.index("v1_lower_reserve('" + helper + "'")
    delegate = body.index("scanipy_execution." + lower + "(")
    assert preflight < reserve < delegate
    if parse:
        assert preflight < body.index("v1_occurrence(")
    assert body.count("v1_work_begin(") == 1
    assert body.index("v1_replay(") < body.index("v1_fresh_command(") < delegate


def test_sql_lexical_and_lower_reservations_are_split_without_refunds():
    source = migration_module()._resource("accepted_v1_validation.sql")
    preflight = sql_function(source, "v1_lower_preflight")
    lower = sql_function(source, "v1_lower_reserve")
    assert preflight.index("v1_lexical(") < preflight.index("v1_concat_reserve(")
    assert "::json" not in preflight and "v1_work_begin(" not in preflight
    assert "v1_concat_reserve(" not in lower and "v1_work_begin(" not in lower
    for bucket in (0, 1, 2, 3, 4, 5):
        assert f"v1_charge({bucket}," in lower
    assert "v1_charge(6,cost*copies)" in source
    assert "amount>=0" in sql_function(source, "v1_charge")


def test_sql_metadata_denial_uses_real_new_running_row_and_atomic_failed_helpers():
    source = migration_module()._resource("accepted_v1_operations.sql")
    initial = sql_function(source, "authorize_detector_run_v1")
    assert "result->'completed'='false'::jsonb" in initial
    assert "result->'replayed'='false'::jsonb" in initial
    assert "context->>'run_state'='running'" in initial
    assert (
        initial.index("begin_detector_run_v1(")
        < initial.index("lock_accepted_detector_context_v1(")
        < initial.index("moment:=clock_timestamp()")
    )
    assert initial.index("v1_emit_observation(") < initial.index("v1_fail_denied(")
    failed = sql_function(source, "v1_fail_denied")
    assert "'observed_byte_count',NULL,'truncated',true,'observed_full_sha256',NULL" in failed
    assert "'actual_code_digest',NULL,'actual_env_digest',NULL" in failed
    assert "'completed_run_ids','[]'::jsonb,'identity',NULL,'identity_policy_reason',NULL" in failed
    assert "Accepted execution denied." in failed
    assert (
        failed.index("v1_lexical(failure,65536)")
        < failed.index("v1_lower_reserve('fail'")
        < failed.index("fail_detector_run_v1(")
    )
    assert (
        failed.index("v1_lexical(terminal,65536)")
        < failed.index("v1_lower_reserve('finish'")
        < failed.index("finish_capture_detection_v1(")
    )
    assert "WHEN OTHERS" not in failed and "COMMIT" not in failed


def test_sql_renewal_evaluates_denial_before_extending_and_keeps_actual_new_revision():
    body = sql_function(
        migration_module()._resource("accepted_v1_operations.sql"), "renew_authorized_execution_v1"
    )
    assert body.index("v1_fetch_execution(") < body.index("lock_accepted_detector_context_v1(")
    assert body.index("v1_previous_context(") < body.index("v1_denial_reason(")
    assert (
        body.index("v1_denial_reason(")
        < body.index("IF reason IS NULL THEN")
        < body.index("renew_capture_detection_v1(")
    )
    assert body.count("lock_accepted_detector_context_v1(") == 2
    assert "renewed_fence:=fence||jsonb_build_object('work_revision',result->'revision')" in body
    assert "'previous_authorization_id',previous_id" in body
    assert body.index("v1_emit_observation(") < body.index("v1_fail_denied(")


def test_sql_pin_denial_is_last_and_never_compares_service_with_runner_artifacts():
    source = migration_module()._resource("accepted_v1_operations.sql")
    reason = sql_function(source, "v1_denial_reason")
    expected = (
        "RETURN 'policy-expired'",
        "RETURN 'unsupported-authority'",
        "RETURN 'grant-revoked'",
        "RETURN 'grant-expired'",
    )
    positions = [reason.index(value) for value in expected]
    assert positions == sorted(positions)
    assert reason.rindex("RETURN 'unsupported-authority'") < reason.index(
        "RETURN 'missing-runtime-pin'"
    )
    assert reason.index("v1_planned_pins_present(") < reason.index("RETURN 'policy-expired'")
    assert "resolver_artifact_digest" not in reason
    assert "scope-conflict" not in reason


def test_sql_observation_ids_are_volatile_and_private_bundle_returns_real_content_digest():
    migration = migration_module()
    observation = sql_function(
        migration._resource("accepted_v1_operations.sql"), "v1_common_observation"
    )
    assert "LANGUAGE plpgsql VOLATILE" in observation and "gen_random_uuid()" in observation
    bundle = sql_function(migration._resource("accepted_v1_reads.sql"), "v1_fetch_bundle")
    assert "accepted_content_bytes bytea,content_digest bytea" in bundle
    assert "content_digest:=validated.content_digest" in bundle


@pytest.mark.parametrize(
    "profile", (None, True, 1, "", "head", "global", "ACCEPTED", ("accepted",))
)
def test_fixture_profile_is_closed_before_url_or_database_work(profile):
    from tests.occurrence_store_postgres import PrivatePostgres

    with pytest.raises(ValueError, match="profile"):
        PrivatePostgres(object(), profile=profile)


def test_fixture_profile_rejects_string_subclass_without_callback():
    from tests.occurrence_store_postgres import PrivatePostgres

    class Poison(str):
        def __eq__(self, other):
            pytest.fail("caller profile equality callback")

    with pytest.raises(ValueError, match="profile"):
        PrivatePostgres(object(), profile=Poison("accepted"))


@pytest.mark.parametrize(
    "profile,target", (("occurrence", "20260925_0005"), ("accepted", "20260926_0006"))
)
def test_fixture_default_migration_target_is_fixed_child_not_head(monkeypatch, profile, target):
    from types import SimpleNamespace

    from tests import occurrence_store_postgres as pg

    cluster = pg.PrivatePostgres(
        "postgresql://controlled@localhost/only_test_bootstrap", profile=profile
    )
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pg.subprocess, "run", run)
    cluster.migrate()
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[-2:] == ["upgrade", target]
    assert cluster.database in kwargs["env"]["SCANIPY_DATABASE_URL"]
    assert "only_test_bootstrap" not in kwargs["env"]["SCANIPY_DATABASE_URL"]
    assert cluster.reserved == pg.RESERVED + (pg.ACCEPTED_RESERVED if profile == "accepted" else ())
    assert cluster.owned_roles == {} and cluster.database_identity is None


@pytest.mark.parametrize("target", ("head", "base", "20260925_0002", "20260926_0006", "x", 5))
def test_occurrence_fixture_cannot_select_accepted_or_unbounded_migration(monkeypatch, target):
    from tests import occurrence_store_postgres as pg

    cluster = pg.PrivatePostgres("postgresql://controlled@localhost/only_test_bootstrap")
    monkeypatch.setattr(pg.subprocess, "run", lambda *a, **k: pytest.fail("unexpected subprocess"))
    with pytest.raises(ValueError, match="target"):
        cluster.migrate(target)


@pytest.mark.parametrize("required", (None, "1"))
def test_accepted_fixture_never_falls_back_to_occurrence_or_app_url(monkeypatch, required):
    from tests import occurrence_store_postgres as pg

    monkeypatch.delenv("SCANIPY_ACCEPTED_LEDGER_TEST_URL", raising=False)
    monkeypatch.delenv("SCANIPY_ACCEPTED_LEDGER_TEST_REQUIRED", raising=False)
    monkeypatch.setenv("SCANIPY_OCCURRENCE_TEST_URL", "postgresql://unread@localhost/foreign")
    monkeypatch.setenv("SCANIPY_DATABASE_URL", "postgresql://unread@localhost/app")
    if required:
        monkeypatch.setenv("SCANIPY_ACCEPTED_LEDGER_TEST_REQUIRED", required)
    monkeypatch.setattr(
        pg, "PrivatePostgres", lambda *a, **k: pytest.fail("unexpected fixture setup")
    )
    expected = pytest.fail.Exception if required else pytest.skip.Exception
    with pytest.raises(expected):
        next(pg.accepted_ledger_pg.__wrapped__())


def test_both_accepted_modules_will_share_one_plugin_owned_fixture_instance(monkeypatch):
    from tests import occurrence_store_postgres as pg

    calls = []

    class Cluster:
        def __init__(self, url, *, profile):
            calls.append((url, profile))

        def setup(self):
            calls.append("setup")

        def dispose(self):
            calls.append("dispose")

    monkeypatch.setenv("SCANIPY_ACCEPTED_LEDGER_TEST_URL", "explicit-controlled-value")
    monkeypatch.setenv("SCANIPY_OCCURRENCE_TEST_URL", "unread")
    monkeypatch.setattr(pg, "PrivatePostgres", Cluster)
    fixture = pg.accepted_ledger_pg.__wrapped__()
    assert type(next(fixture)) is Cluster
    assert calls == [("explicit-controlled-value", "accepted"), "setup"]
    with pytest.raises(StopIteration):
        next(fixture)
    assert calls[-1] == "dispose"


def test_accepted_fixture_failed_migration_does_not_adopt_racing_reserved_role(monkeypatch):
    from tests import occurrence_store_postgres as pg
    from tests.unit import test_occurrence_repository as existing

    # Reuse the unchanged no-database ownership-race falsifier, selecting the
    # new fixed profile and a new reserved role instead of weakening its check.
    real = pg.PrivatePostgres
    monkeypatch.setattr(existing, "PrivatePostgres", lambda url: real(url, profile="accepted"))
    monkeypatch.setattr(existing, "RESERVED", pg.ACCEPTED_RESERVED)
    existing.test_failed_migration_does_not_adopt_or_dispose_racing_reserved_role(monkeypatch)


def test_sql_all_allocated_public_functions_have_concrete_resource_bodies():
    migration = migration_module()
    source = migration._resource("accepted_v1_operations.sql") + migration._resource(
        "accepted_v1_reads.sql"
    )
    for names in migration.MUTATIONS.values():
        for name in names:
            body = sql_function(source, name)
            assert "SECURITY DEFINER" in body and "v1_work_begin(" in body
            assert "RETURN NEXT" in body
    for signature in migration.READS:
        body = sql_function(source, signature.split("(", 1)[0])
        assert "SECURITY DEFINER" in body and "v1_work_begin(" in body
    installer = sql_function(source, "initialize_registry_namespace_v1")
    assert "SECURITY INVOKER" in installer


@pytest.mark.parametrize("name", ("read_execution_authority_v1", "recheck_execution_authority_v1"))
def test_sql_current_reads_have_one_shared_no_refund_meter_and_private_body(name):
    source = migration_module()._resource("accepted_v1_reads.sql")
    body = sql_function(source, name)
    assert body.count("v1_work_begin(5701632,8519808,131106)") == 1
    assert body.count("v1_read_current(") == 1
    assert "scanipy_accepted_inputs.read_execution_authority_v1(" not in body
    shared = sql_function(source, "v1_read_current")
    assert "v1_work_begin(" not in shared and "v1_lower_" not in shared
    assert shared.count("lock_accepted_detector_context_v1(") == 1
    assert "lock_accepted_capture_context_v1(" not in shared
    assert (
        shared.index("v1_read_bridge_reserve()")
        < shared.index("lock_accepted_detector_context_v1(")
        < shared.index("moment:=clock_timestamp()")
    )


def test_sql_current_reads_reserve_both_bridge_id_passes_and_all_binding_fields():
    migration = migration_module()
    source = migration._resource("accepted_v1_reads.sql")
    reserve = sql_function(source, "v1_read_bridge_reserve")
    assert "v1_charge(3,8454272)" in reserve and "v1_charge(5,131106)" in reserve
    assert "v1_fetch(" not in reserve and "v1_hash(" not in reserve
    body = sql_function(source, "v1_read_current")
    assert (
        "jsonb_object_keys(scanipy_accepted_inputs.v1_shapes()->'records'->'EXECUTION_BINDING')"
        in body
    )
    assert "WHEN key='authorization_event_id' THEN 'event_id'" in body
    assert "binding->>'authorization_digest'=encode(current_execution.record_digest,'hex')" in body
    assert body.index("v1_fetch_execution(") < body.index("lock_accepted_detector_context_v1(")
    assert "v1_policy_time(live.policy,live.checkpoint,issued)" in body
    assert "v1_policy_time(live.policy,live.checkpoint,moment)" in body
    assert "v1_grant_use(grant_row,issued," in body and "v1_grant_use(grant_row,moment," in body


def test_sql_recheck_preserves_prior_context_bytes_and_never_restamps_them():
    source = migration_module()._resource("accepted_v1_reads.sql")
    body = sql_function(source, "recheck_execution_authority_v1")
    assert "current_read.ledger_bytes=prior_ledger_bytes" in body
    assert "current_read.live_bytes=prior_live_bytes" in body
    assert "current_read.reference_time::timestamptz>=prior_reference_time::timestamptz" in body
    assert "RETURNS void" in body and "RETURN QUERY" not in body and "RETURN NEXT" not in body
    assert "v1_emit_observation(" not in body and "renew_capture_detection_v1(" not in body


@pytest.mark.parametrize(
    "name", ("seal_bound_capture_v1", "authorize_detector_run_v1", "renew_authorized_execution_v1")
)
def test_sql_mutation_bridge_schedule_is_two_calls_with_two_tickets_each(name):
    body = sql_function(migration_module()._resource("accepted_v1_operations.sql"), name)
    assert (
        body.count("lock_accepted_capture_context_v1(")
        + body.count("lock_accepted_detector_context_v1(")
        == 2
    )
    assert body.count("v1_relational_reserve(2)") == 2
    assert body.count("v1_relational_reserve(5)") == 1
    assert "v1_relational_reserve(1)" not in body


@pytest.mark.parametrize("kind", ("document", "frame", "bundle", "occurrence"))
def test_stored_sql_wrappers_preserve_private_limit_detail_and_unexpected_failures(kind):
    body = sql_function(migration_module()._resource("accepted_v1_reads.sql"), "v1_stored_" + kind)
    assert body.count("scanipy_accepted_inputs.v1_" + kind + "(") == 1
    assert "EXCEPTION WHEN SQLSTATE 'P0001'" in body
    assert "message='invalid-input' AND detail IS DISTINCT FROM 'accepted-work-limit'" in body
    assert "GET STACKED DIAGNOSTICS message=MESSAGE_TEXT,detail=PG_EXCEPTION_DETAIL" in body
    assert "RAISE EXCEPTION 'content-mismatch'" in body and "  RAISE;" in body
    assert "WHEN OTHERS" not in body and "v1_work_begin(" not in body
    assert "v1_charge(" not in body and "v1_hash(" not in body


def test_sql_work_limit_primary_code_stays_unchanged_with_private_detail():
    body = sql_function(migration_module()._resource("accepted_v1_validation.sql"), "v1_charge")
    assert "IF amount>ceiling-used THEN" in body
    assert (
        "RAISE EXCEPTION 'invalid-input' USING ERRCODE='P0001',DETAIL='accepted-work-limit'" in body
    )
    assert body.index("DETAIL='accepted-work-limit'") < body.index("jsonb_set(")


def test_sql_stored_replay_and_live_fetches_do_not_relabel_caller_material():
    operations = migration_module()._resource("accepted_v1_operations.sql")
    replay = sql_function(operations, "v1_replay")
    assert "v1_stored_frame(original.result," in replay
    assert "v1_stored_document(original.result," in replay
    assert "v1_frame(parts[1]," in replay  # caller parts were independently validated
    for name in ("v1_fetch_binding", "v1_fetch_seal", "v1_fetch_execution"):
        body = sql_function(operations, name)
        assert "v1_stored_occurrence(" in body
    recheck = sql_function(
        migration_module()._resource("accepted_v1_reads.sql"), "recheck_execution_authority_v1"
    )
    assert "v1_frame(prior_live_bytes," in recheck
    assert "v1_stored_frame(prior_live_bytes," not in recheck


def test_generated_denial_k_before_construction_is_prepaid_once():
    body = sql_function(
        migration_module()._resource("accepted_v1_operations.sql"), "v1_fail_denied"
    )
    construction = body.index("failure:=")
    assert body[:construction].count("v1_concat_reserve(65536,64)") == 2
    assert "v1_concat_reserve(4096,16)" in body[:construction]
    assert "v1_lower_preflight(" not in body
    assert body.count("v1_lower_reserve(") == 2
    assert "v1_lexical(failure,65536)<=64" in body
    assert "v1_lexical(terminal,65536)<=64" in body


@pytest.mark.parametrize(
    "name,resource",
    (
        ("seal_bound_capture_v1", "accepted_v1_operations.sql"),
        ("authorize_detector_run_v1", "accepted_v1_operations.sql"),
        ("renew_authorized_execution_v1", "accepted_v1_operations.sql"),
        ("v1_read_current", "accepted_v1_reads.sql"),
    ),
)
def test_fresh_sql_clock_does_not_precede_its_actual_bridge_observation(name, resource):
    body = sql_function(migration_module()._resource(resource), name)
    assert "moment>=(context->>'db_now')::timestamptz" in body
    if name == "v1_read_current":
        assert "issued<=moment" in body
    else:
        assert "(binding.manifest->>'resolved_at')::timestamptz<=moment" in body


@pytest.mark.parametrize("scope", ("customer", "global"))
def test_integration_fixture_publication_and_rotation_use_real_closed_owner_inputs_without_db(
    monkeypatch, scope
):
    from tests.integration.test_accepted_ledger_sql import SqlLedger

    class AdminCursor:
        def execute(self, *_args):
            pass

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Admin:
        autocommit = False

        def cursor(self):
            return AdminCursor()

        def commit(self):
            pass

    class NoDatabase:
        def scope(self):
            return ORG, UUID(af.uid(102))

        @contextmanager
        def admin(self):
            yield Admin()

    observed = []

    class DiagnosticCommands:
        def invoke(self, action, data, parts):
            decoded = lc.decode_ledger_command(data, parts, expected_action=action)
            observed.append(decoded)
            # Input codec control only, deliberately not a forged SQL result.
            return SimpleNamespace(record_bytes=parts[0])

        def install_policy(self, *args):
            return self.invoke("install-policy", *args)

        def record_admission(self, *args):
            return self.invoke("record-admission", *args)

        def publish_builtin_bundle(self, *args):
            return self.invoke("publish-builtin", *args)

    @contextmanager
    def diagnostic_repo(self, role="resolver"):
        yield DiagnosticCommands()

    monkeypatch.setattr(
        r.AcceptedLedgerRepository,
        "initialize_registry_namespace",
        lambda self, installed: (self.namespace_id, False),
    )
    monkeypatch.setattr(SqlLedger, "repo", diagnostic_repo)
    fixture = SqlLedger(NoDatabase(), scope=scope).activate().rotate_grant("revoked")
    assert len(observed) == 5
    assert fixture.manifest["scope"] == scope and fixture.policy["grants"][0]["status"] == "revoked"
    assert fixture.checkpoint["generation"] == 2


def current_inputs(material):
    request = material.request
    assert request.ledger is not None and request.ledger.binding is not None
    return request, request.ledger.binding


@pytest.mark.parametrize("live", (b"", b"not-a-frame", b"scanipy-accepted-live/999\n"))
def test_r6_caller_live_keeps_actual_owner_input_error_before_sql(material, live):
    request, binding = current_inputs(material)
    with pytest.raises(s.VerificationError) as original:
        c.decode_frame(live, s.LIVE)
    connection = Connection([(None,)])
    with pytest.raises(s.VerificationError) as observed:
        r.AcceptedLedgerRepository(connection, NS, ORG).recheck_execution_authority(
            binding, request.admission, request.ledger, live, request.reference_time
        )
    assert observed.value.code == original.value.code
    assert len(connection.calls) == 1


@pytest.mark.parametrize(
    "column,bad",
    (
        (0, b"[]"),
        (0, b"{"),
        (0, b"{}"),
        (1, b"not-a-frame"),
        (1, b"scanipy-accepted-live/999\n"),
        (1, b""),
        (2, None),
        (2, "2026-09-25"),
        (2, True),
    ),
)
def test_r5_malformed_returned_current_material_is_stored_corruption(material, column, bad):
    request, binding = current_inputs(material)
    row = [
        c.canonical_bytes(m.record_dict(request.ledger)),
        request.live_authority_evidence,
        request.reference_time,
    ]
    row[column] = bad
    connection = Connection([tuple(row)])
    with pytest.raises(s.VerificationError) as observed:
        r.AcceptedLedgerRepository(connection, NS, ORG).read_execution_authority(
            binding, request.admission
        )
    assert observed.value.code == "content-mismatch"
    assert len(connection.calls) == 2


@pytest.mark.parametrize("reference", (None, "2026-09-25", True))
def test_r6_caller_reference_keeps_actual_shape_error_before_sql(material, reference):
    request, binding = current_inputs(material)
    with pytest.raises(s.VerificationError) as original:
        s.shape(reference, "instant")
    connection = Connection([(None,)])
    with pytest.raises(s.VerificationError) as observed:
        r.AcceptedLedgerRepository(connection, NS, ORG).recheck_execution_authority(
            binding, request.admission, request.ledger, request.live_authority_evidence, reference
        )
    assert observed.value.code == original.value.code
    assert len(connection.calls) == 1


def test_r5_r6_valid_actual_owner_material_keeps_original_bytes(material):
    request, binding = current_inputs(material)
    row = (
        c.canonical_bytes(m.record_dict(request.ledger)),
        request.live_authority_evidence,
        request.reference_time,
    )
    connection = Connection([row])
    result = r.AcceptedLedgerRepository(connection, NS, ORG).read_execution_authority(
        binding, request.admission
    )
    assert result == (request.ledger, request.live_authority_evidence, request.reference_time)
    assert len(connection.calls) == 2
    connection = Connection([(None,)])
    r.AcceptedLedgerRepository(connection, NS, ORG).recheck_execution_authority(
        binding, request.admission, *result
    )
    assert len(connection.calls) == 2
    assert connection.calls[-1][1][-2:] == (
        request.live_authority_evidence,
        request.reference_time,
    )


@pytest.mark.parametrize("current_read", (False, True))
@pytest.mark.parametrize("limit", ("MAX_HASH_CALLS", "MAX_HASH_BYTES"))
def test_current_local_work_limit_is_not_remapped_as_stored_corruption(
    material, monkeypatch, current_read, limit
):
    request, binding = current_inputs(material)
    monkeypatch.setattr(r, limit, 0)
    row = (
        c.canonical_bytes(m.record_dict(request.ledger)),
        request.live_authority_evidence,
        request.reference_time,
    )
    connection = Connection([row if current_read else (None,)])
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    with pytest.raises(s.VerificationError) as observed:
        if current_read:
            repository.read_execution_authority(binding, request.admission)
        else:
            repository.recheck_execution_authority(
                binding,
                request.admission,
                request.ledger,
                request.live_authority_evidence,
                request.reference_time,
            )
    assert observed.value.code == "invalid-input"
    assert len(connection.calls) == (2 if current_read else 1)


@pytest.mark.parametrize("current_read", (False, True))
@pytest.mark.parametrize("code", ("fence-stale", "policy-stale", "checkpoint-denied"))
def test_current_known_binding_errors_are_not_syntax_corruption(material, current_read, code):
    request, binding = current_inputs(material)
    value = m.record_dict(request.ledger)
    admission = request.admission
    if code == "fence-stale":
        value["binding"]["work_revision"] += 1
    elif code == "policy-stale":
        value["policy_event_id"] = af.uid(900)
    else:
        changed = m.record_dict(admission)
        changed["policy_digest"] = "f" * 64
        admission = c.decode_record(changed, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    ledger = c.decode_record(value, m.LedgerExpectation, s.LEDGER_EXPECTATION)
    row = (c.canonical_bytes(value), request.live_authority_evidence, request.reference_time)
    connection = Connection([row if current_read else (None,)])
    repository = r.AcceptedLedgerRepository(connection, NS, ORG)
    with pytest.raises(s.VerificationError) as observed:
        if current_read:
            repository.read_execution_authority(binding, admission)
        else:
            repository.recheck_execution_authority(
                binding, admission, ledger, request.live_authority_evidence, request.reference_time
            )
    assert observed.value.code == code


@pytest.mark.parametrize("returned", ("", "not-a-uuid", af.uid(901)))
def test_installer_returned_uuid_syntax_and_valid_identity_mismatch_are_distinct(
    material, returned
):
    connection = Connection([(returned, False)])
    with pytest.raises(s.VerificationError) as observed:
        r.AcceptedLedgerRepository(connection, NS, ORG).initialize_registry_namespace(
            material.request.installed_trust
        )
    assert observed.value.code == (
        "ledger-mismatch" if returned == af.uid(901) else "content-mismatch"
    )


def test_publication_frame_provenance_is_explicitly_incoming_after_al02_validation(
    cases, monkeypatch
):
    data, parts = cases["publish-builtin"]
    raw = diagnostic_publication_bytes(cases)
    calls = []
    original = r._Work.frame

    def observed(self, data, schema, *, stored):
        calls.append((schema, stored))
        return original(self, data, schema, stored=stored)

    monkeypatch.setattr(r._Work, "frame", observed)
    r.AcceptedLedgerRepository(Connection([(raw, False)]), NS, ORG).publish_builtin_bundle(
        data, parts
    )
    assert calls == [(s.PUBLICATION_INPUT, False)]


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
def test_migration_literal_submission_has_no_invented_compiler_bind(monkeypatch, direction):
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

    migration = migration_module()
    submitted = []
    monkeypatch.setattr(migration.op, "execute", submitted.append)
    getattr(migration, direction)()
    assert submitted
    for statement in submitted:
        compiled = text(statement).compile(dialect=PGDialect_psycopg2())
        assert compiled.params == {}
        assert compiled.construct_params() == {}


@pytest.mark.parametrize("dialect_style", ("named", "pyformat"))
@pytest.mark.parametrize(
    "statement",
    (
        'SELECT \'{"python":0,"java":1,"value":null}\'::jsonb',
        "SELECT ':name', ':0', ':$', ':n$a', ':a:b', '::', ':', ':é', 'a:word'",
        r"SELECT E'\n', E'\\', '\:name', '\\:name', '\\\:name', '\\::jsonb'",
        r"SELECT '\:', '\\:', '\\\:', '\:a:b', '\::', '::uuid', E'\\x01'::bytea",
        "DO $$ BEGIN RAISE EXCEPTION '%', value; PERFORM format('%s %I %% %(name)s',value); END $$",
        "-- :comment and %(comment)s\nSELECT $body$:value\n\\:value\n%$body$::text",
    ),
)
def test_literal_submission_compiles_exact_colons_casts_backslashes_and_percents(
    monkeypatch, dialect_style, statement
):
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

    migration = migration_module()
    submitted = []
    monkeypatch.setattr(migration.op, "execute", submitted.append)
    migration._execute_literal(statement)
    assert len(submitted) == 1
    compiled = text(submitted[0]).compile(dialect=PGDialect_psycopg2(paramstyle=dialect_style))
    assert compiled.params == compiled.construct_params() == {}
    # psycopg2's parameterized path receives doubled literal percent signs;
    # named offline output has no DBAPI percent-escape layer to remove.
    expected = statement.replace("%", "%%") if dialect_style == "pyformat" else statement
    assert str(compiled) == expected
    assert (str(compiled) % {} if dialect_style == "pyformat" else str(compiled)) == statement


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
@pytest.mark.parametrize("dialect_style", ("named", "pyformat"))
def test_all_generated_migration_statements_have_exact_original_sql_bytes(
    monkeypatch, direction, dialect_style
):
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

    migration = migration_module()
    literal_submit = migration._execute_literal
    original = []
    # Capture complete statement generation before the submission-only escape.
    monkeypatch.setattr(migration.op, "execute", original.append)
    monkeypatch.setattr(migration, "_execute_literal", original.append)
    getattr(migration, direction)()
    submitted = []
    monkeypatch.setattr(migration.op, "execute", submitted.append)
    monkeypatch.setattr(migration, "_execute_literal", literal_submit)
    getattr(migration, direction)()
    assert len(submitted) == len(original) and original
    for raw, escaped in zip(original, submitted, strict=True):
        compiled = text(escaped).compile(dialect=PGDialect_psycopg2(paramstyle=dialect_style))
        assert compiled.params == compiled.construct_params() == {}
        assert str(compiled) == (raw.replace("%", "%%") if dialect_style == "pyformat" else raw)
    if direction == "upgrade":
        for name in ("validation", "tables", "history", "operations", "reads", "acl"):
            assert migration._resource(f"accepted_v1_{name}.sql") in original
        assert set(
            migration._bridges(migration._resource("accepted_v1_execution_bridges.sql"))
        ) <= set(original)
        assert any(migration._resource("accepted_v1_shapes.json") in sql for sql in original)


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
def test_actual_alembic_offline_submission_preserves_literal_migration_statements(
    monkeypatch, direction
):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = migration_module()
    original = []
    literal_submit = migration._execute_literal
    monkeypatch.setattr(migration.op, "execute", original.append)
    monkeypatch.setattr(migration, "_execute_literal", original.append)
    getattr(migration, direction)()
    monkeypatch.setattr(migration, "_execute_literal", literal_submit)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        dialect_opts={"paramstyle": "named"},
        opts={"as_sql": True, "literal_binds": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    getattr(migration, direction)()
    assert output.getvalue() == "".join(
        statement.replace("\t", "    ").strip() + ";\n\n" for statement in original
    )


def diagnostic_login_batch(
    monkeypatch,
    *,
    profile="accepted",
    limit=63,
    mismatch=None,
    commit_error=None,
    grant_error=None,
    create_error=None,
    close_error=None,
):
    from tests import occurrence_store_postgres as pg

    cluster = pg.PrivatePostgres(
        "postgresql://controlled@localhost/only_test_bootstrap", profile=profile
    )
    cluster.owned_roles = {"previous_owned": 99}
    cluster.roles = {"previous": ("previous_owned", "fixture-only")}
    fixed = UUID(af.uid(900))
    monkeypatch.setattr(pg, "uuid4", lambda: fixed)
    driver = SimpleNamespace(
        created=[], granted=[], commits=0, rollbacks=0, closed=0, selected=None
    )

    class LoginCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, parameters=()):
            if type(query) is str:
                if "max_identifier_length" in query:
                    driver.selected = (limit,)
                elif "FROM pg_roles" in query:
                    assert query == (
                        "SELECT rolname::text,oid FROM pg_roles WHERE rolname::text=%s"
                    )
                    name = parameters[0]
                    oid = 1000 + driver.created.index(name)
                    returned = name
                    if mismatch and "accepted_policy_admin" in name:
                        returned = name[:-1] if mismatch == "name" else None
                        if mismatch == "oid":
                            returned, oid = name, True
                    driver.selected = (returned, oid) if "rolname::text" in query else (oid,)
                else:
                    pytest.fail("unexpected diagnostic login query")
                return
            prefix = query.seq[0].string
            identifiers = [
                item.strings[0] for item in query.seq if isinstance(item, pg.sql.Identifier)
            ]
            if prefix.startswith("CREATE ROLE"):
                if create_error is not None and "accepted_policy_admin" in identifiers[0]:
                    raise create_error
                driver.created.append(identifiers[0])
            elif prefix.startswith("GRANT"):
                driver.granted.append(tuple(identifiers))
                if grant_error is not None and "accepted_policy_admin" in identifiers[1]:
                    raise grant_error
            else:
                pytest.fail("unexpected diagnostic login statement")

        def fetchone(self):
            return driver.selected

    class LoginConnection:
        def cursor(self):
            return LoginCursor()

        def commit(self):
            driver.maps_at_commit = (dict(cluster.owned_roles), dict(cluster.roles))
            driver.commits += 1
            if commit_error is not None:
                raise commit_error

    @contextmanager
    def admin():
        try:
            yield LoginConnection()
        except BaseException:
            driver.rollbacks += 1
            raise
        finally:
            driver.closed += 1
            if close_error is not None:
                raise close_error

    monkeypatch.setattr(cluster, "admin", admin)
    return cluster, driver, fixed.hex


@pytest.mark.parametrize("profile", ("occurrence", "accepted"))
def test_login_names_preserve_complete_uuid_and_legacy_format_within_server_bound(
    monkeypatch, profile
):
    cluster, driver, token = diagnostic_login_batch(monkeypatch, profile=profile)
    assert len("occurrence_accepted_policy_admin_" + token) == 65
    cluster._create_logins()
    for suffix, (name, _password) in cluster.roles.items():
        if suffix == "previous":
            continue
        prefix = "altest_" if suffix.startswith("accepted_") else "occurrence_"
        assert name == prefix + suffix + "_" + token
        assert name.isascii() and len(name) <= 63 and name.endswith(token)
    assert driver.commits == 1 and driver.rollbacks == 0 and driver.closed == 1
    assert len(driver.created) == len(driver.granted) == (10 if profile == "accepted" else 6)


def test_login_server_identifier_bound_precedes_first_create(monkeypatch):
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, limit=5)
    with pytest.raises(AssertionError, match="identifier"):
        cluster._create_logins()
    assert driver.created == driver.granted == [] and driver.commits == 0
    assert cluster.owned_roles == {"previous_owned": 99}


@pytest.mark.parametrize("limit", (0, True, "63", None))
def test_invalid_server_identifier_bound_never_creates_login(monkeypatch, limit):
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, limit=limit)
    with pytest.raises(AssertionError, match="identifier"):
        cluster._create_logins()
    assert driver.created == driver.granted == [] and driver.commits == 0


@pytest.mark.parametrize("limit", (60, 61))
def test_accepted_login_exact_server_limit_is_checked_without_truncation(monkeypatch, limit):
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, limit=limit)
    if limit == 61:
        cluster._create_logins()
        assert max(map(len, driver.created)) == 61
    else:
        with pytest.raises(AssertionError, match="identifier"):
            cluster._create_logins()
        assert len(driver.created) == 6
        assert all(name.startswith("occurrence_") for name in driver.created)
        assert cluster.owned_roles == {"previous_owned": 99}
        assert driver.commits == 0


def test_non_ascii_generated_login_is_rejected_before_create(monkeypatch):
    from tests import occurrence_store_postgres as pg

    cluster, driver, _ = diagnostic_login_batch(monkeypatch)
    monkeypatch.setattr(pg, "uuid4", lambda: SimpleNamespace(hex="é" * 32))
    with pytest.raises(AssertionError, match="identifier"):
        cluster._create_logins()
    assert driver.created == driver.granted == []


@pytest.mark.parametrize("stage", ("create", "grant", "close"))
def test_login_batch_failure_does_not_publish_previously_created_batch(monkeypatch, stage):
    failure = OSError("controlled batch failure")
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, **{stage + "_error": failure})
    with pytest.raises(OSError) as observed:
        cluster._create_logins()
    assert observed.value is failure
    assert driver.commits == (1 if stage == "close" else 0)
    assert driver.rollbacks == (0 if stage == "close" else 1)
    assert cluster.owned_roles == {"previous_owned": 99}
    assert cluster.roles == {"previous": ("previous_owned", "fixture-only")}


@pytest.mark.parametrize("mismatch", ("name", "missing", "oid"))
def test_login_readback_mismatch_never_grants_or_adopts_batch(monkeypatch, mismatch):
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, mismatch=mismatch)
    with pytest.raises(AssertionError, match="identity"):
        cluster._create_logins()
    assert "accepted_policy_admin" in driver.created[-1]
    assert not any("accepted_policy_admin" in grant[1] for grant in driver.granted)
    assert driver.commits == 0 and driver.rollbacks == 1
    assert cluster.owned_roles == {"previous_owned": 99}
    assert cluster.roles == {"previous": ("previous_owned", "fixture-only")}


@pytest.mark.parametrize("failure", (None, OSError("controlled ambiguous commit")))
def test_login_ownership_is_promoted_only_after_successful_batch_commit(monkeypatch, failure):
    cluster, driver, _ = diagnostic_login_batch(monkeypatch, commit_error=failure)
    if failure is None:
        cluster._create_logins()
    else:
        with pytest.raises(OSError) as observed:
            cluster._create_logins()
        assert observed.value is failure
    original = ({"previous_owned": 99}, {"previous": ("previous_owned", "fixture-only")})
    assert driver.maps_at_commit == original
    if failure is None:
        assert len(cluster.owned_roles) == len(cluster.roles) == 11
    else:
        assert (cluster.owned_roles, cluster.roles) == original


def test_immutable_reads_rely_on_namespace_lock_without_requiring_history_update_rights():
    migration = migration_module()
    operations = migration._resource("accepted_v1_operations.sql")
    statements = operations.split(";")
    assert not any(
        "FOR UPDATE" in statement
        and (
            "FROM scanipy_accepted_inputs.authority_events" in statement
            or "FROM scanipy_accepted_inputs.request_bundle_bindings" in statement
        )
        for statement in statements
    )
    assert operations.count("FOR UPDATE") == 2
    assert "WHERE id=p_namespace FOR UPDATE" in operations
    assert "ORDER BY id FOR UPDATE" in operations
    assert "WHERE id=NEW.namespace_id FOR UPDATE" in migration._resource("accepted_v1_history.sql")
    assert (
        'rights = "SELECT,INSERT,UPDATE" if table == "registry_namespaces" else "SELECT,INSERT"'
        in Path(migration.__file__).read_text()
    )


def diagnostic_sealing_fixture(*, scope="customer", null_pin=None, mismatch=None):
    from services.scan.occurrence_store.models import Fence, RequestInput
    from tests import occurrence_store_fixtures as of
    from tests.integration.test_accepted_ledger_sql import SqlLedger

    # Invoke only the pure input builder. No constructor/SQL, receipt, global
    # adoption or runtime authority is fabricated by this diagnostic object.
    fixture = SqlLedger.__new__(SqlLedger)
    fixture.tenant_org, fixture.codebase = ORG, UUID(af.uid(102))
    fixture.org = ORG if scope == "customer" else None
    fixture.namespace, fixture.request_id = NS, UUID(af.uid(930))
    fixture.revision = 3
    original = af.bundle_fixture()
    manifest, models = c.decode_spec(original.spec_bytes)
    manifest.update(
        scope=scope, org_id=str(ORG) if scope == "customer" else None, S_version="2.3.4"
    )
    fixture.bundle = m.AcceptedBundleBytes(
        c.encode_spec(c.encode_document(manifest, s.S_MANIFEST), models),
        original.detector_blobs,
        original.rule_blobs,
    )
    _expected, _objects, fixture.admission = commands.publication(fixture.bundle)
    requested = of.request_input(ORG, fixture.codebase)
    plan = requested.planned_policy.value
    binding = plan["bindings"][0]
    detector = manifest["detectors"][0]
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
    if mismatch == "detector":
        binding["detector_content_digest"] = "0" * 64
    elif mismatch == "rule":
        binding["rules"][0]["content_digest"] = "0" * 64
    planned = of.envelope(
        "planned-policy", **{key: value for key, value in plan.items() if key != "schema"}
    )
    request = requested.request.value
    request.update(requested_s_version="2.3.4", requested_policy_digest=planned.digest.hex())
    fixture.requested = RequestInput(
        of.envelope("request", **{key: value for key, value in request.items() if key != "schema"}),
        planned,
    )
    fixture.fence = Fence(UUID(af.uid(931)), UUID(af.uid(932)), "capture_detection", 1, 0)
    fixture.sealed = SimpleNamespace(record_bytes=b"controlled raw authority, not a SQL receipt")
    return fixture


def checked_sealing_input(fixture):
    from services.scan.occurrence_store.codec import decode_envelope, encode_envelope
    from services.scan.occurrence_store.models import CaptureSeal

    command, parts = fixture.sealing_request()
    decoded = lc.decode_ledger_command(command, parts, expected_action="seal-bound-capture")
    assert decoded.validation == "input-structure-only"
    return CaptureSeal(
        *(
            encode_envelope(name, decode_envelope(name, raw))
            for name, raw in zip(
                ("seal", "source-inventory", "accepted-content"), parts, strict=True
            )
        ),
        fixture.bundle.spec_bytes,
        fixture.bundle.detector_blobs,
        fixture.bundle.rule_blobs,
        fixture.sealed.record_bytes,
    )


@pytest.mark.parametrize("scope", ("customer", "global"))
def test_sealing_fixture_uses_actual_accepted_bytes_and_exact_requested_plan(scope):
    from tests import occurrence_store_fixtures as of

    fixture = diagnostic_sealing_fixture(scope=scope)
    requested_before = (fixture.requested.request.data, fixture.requested.planned_policy.data)
    result = checked_sealing_input(fixture)
    seal = result.seal.value
    assert seal["request_id"] == str(fixture.request_id)
    assert seal["s_version"] == "2.3.4"
    assert seal["planned_policy_digest"] == fixture.requested.planned_policy.digest.hex()
    assert seal["bindings"] == fixture.requested.planned_policy.value["bindings"]
    assert seal["accepted_content_digest"] == result.accepted_content.digest.hex()
    assert seal["acceptance_evidence_digest"] == c.raw_digest(fixture.sealed.record_bytes)
    assert result.spec != of.SPEC and result.detectors != (of.DETECTOR,)
    assert result.rules != (of.RULE,) and result.authority_evidence != of.AUTHORITY
    assert requested_before == (
        fixture.requested.request.data,
        fixture.requested.planned_policy.data,
    )


@pytest.mark.parametrize("mismatch", ("detector", "rule"))
def test_sealing_fixture_rejects_changed_requested_content_binding(mismatch):
    from services.scan.occurrence_store.codec import EnvelopeError

    fixture = diagnostic_sealing_fixture(mismatch=mismatch)
    with pytest.raises(EnvelopeError, match=mismatch + " content binding mismatch"):
        fixture.sealing_request()


@pytest.mark.parametrize(
    "role,field",
    (
        ("binding", "expected_tool_digest"),
        ("binding", "expected_code_digest"),
        ("binding", "expected_image_digest"),
        ("capture_detection_runner", "expected_code_digest"),
        ("capture_detection_runner", "expected_image_digest"),
        ("identity_runner", "expected_code_digest"),
        ("identity_runner", "expected_image_digest"),
    ),
)
def test_sealing_fixture_preserves_explicit_null_runtime_pin_intent(role, field):
    fixture = diagnostic_sealing_fixture(null_pin=(role, field))
    before = fixture.requested.planned_policy.data
    result = checked_sealing_input(fixture)
    assert fixture.requested.planned_policy.data == before
    assert result.seal.value["bindings"] == fixture.requested.planned_policy.value["bindings"]
    assert (
        result.seal.value["planned_policy_digest"] == fixture.requested.planned_policy.digest.hex()
    )
    source = fixture.requested.planned_policy.value
    assert (source["bindings"][0] if role == "binding" else source[role])[field] is None


@pytest.mark.parametrize("before_format,after_format", (("c", "B"), ("B", "c")))
@pytest.mark.parametrize("changed", (False, True), ids=("same-bytes", "changed-byte"))
def test_detector_run_snapshot_compares_exact_bytes_across_driver_views(
    before_format, after_format, changed
):
    from tests.integration.test_accepted_ledger_sql import detector_run_snapshot

    payload = b"\x00controlled lower run\xff"
    after_payload = payload[:-1] + b"\xfe" if changed else payload
    before_view = memoryview(payload).cast(before_format)
    after_view = memoryview(after_payload).cast(after_format)
    assert before_view.format == before_format and after_view.format == after_format
    supplied = [[("running", before_view)], [("running", after_view)]]
    calls = []

    def rows(query, parameters):
        calls.append((query, parameters))
        return supplied.pop(0)

    pg = SimpleNamespace(rows=rows)
    run_id = UUID(af.uid(933))
    before = detector_run_snapshot(pg, run_id)
    assert before == [("running", payload)]
    after = detector_run_snapshot(pg, run_id)
    assert after == [("running", after_payload)]
    if changed:
        assert after != before
    else:
        assert after == before
    assert not supplied
    expected_call = (
        "SELECT state,input_bytes FROM scanipy_execution.detector_runs WHERE id=%s",
        (run_id,),
    )
    assert calls == [expected_call, expected_call]


@pytest.mark.parametrize("value", (None, 1, "yes"))
def test_administration_mode_requires_exact_boolean_before_url(monkeypatch, value):
    from tests import occurrence_store_postgres as pg

    monkeypatch.setattr(pg, "make_url", lambda *_: pytest.fail("URL parsing preceded mode gate"))
    with pytest.raises(ValueError, match="administration"):
        pg.PrivatePostgres("not a URL", administration=value)


def test_administration_mode_is_accepted_only_before_url(monkeypatch):
    from tests import occurrence_store_postgres as pg

    monkeypatch.setattr(pg, "make_url", lambda *_: pytest.fail("URL parsing preceded profile gate"))
    with pytest.raises(ValueError, match="administration"):
        pg.PrivatePostgres("not a URL", administration=True)


def test_accepted_migration_allows_explicit_0007_without_changing_default(monkeypatch):
    from tests import occurrence_store_postgres as pg

    cluster = pg.PrivatePostgres("postgresql://controlled@localhost/bootstrap", profile="accepted")
    calls = []

    def recorded(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pg.subprocess, "run", recorded)
    cluster.migrate("20260926_0007")
    cluster.migrate()
    assert [argv[-1] for argv, _ in calls] == ["20260926_0007", "20260926_0006"]


def administration_fixture(monkeypatch):
    """Only private OS/driver doubles; never a root identity or connection."""
    from tests import occurrence_store_postgres as pg

    fake_os = SimpleNamespace(**vars(pg.os))
    fake_os.environ = {}
    fake_os.getresuid = fake_os.getresgid = lambda: (0, 0, 0)
    fake_sys = SimpleNamespace(**vars(pg.sys))
    fake_sys.flags = SimpleNamespace(isolated=1, no_site=1)
    fake_sys.dont_write_bytecode = True
    fake_sys.executable = "/controlled/python"
    monkeypatch.setattr(pg, "os", fake_os)
    monkeypatch.setattr(pg, "sys", fake_sys)
    checked = []
    monkeypatch.setattr(
        pg, "_administration_directory", lambda path, **kw: checked.append((path, kw))
    )
    monkeypatch.setattr(
        pg, "psycopg2", SimpleNamespace(connect=lambda **_: pytest.fail("real connect"))
    )
    monkeypatch.setattr(pg, "uuid4", lambda: UUID(int=933))
    cluster = pg.PrivatePostgres(
        pg.ADMINISTRATION_URL,
        profile="accepted",
        administration=True,
        migration_cwd=Path("/controlled/work"),
        migration_site_packages=Path("/controlled/deps"),
    )
    return pg, cluster, checked


@pytest.mark.parametrize("keyword", ("migration_cwd", "migration_site_packages"))
def test_administration_paths_require_explicit_mode_without_callbacks(monkeypatch, keyword):
    from tests import occurrence_store_postgres as pg

    monkeypatch.setattr(pg, "make_url", lambda *_: pytest.fail("unexpected parse"))
    with pytest.raises(ValueError, match="administration"):
        pg.PrivatePostgres("unused", **{keyword: object()})


@pytest.mark.parametrize(
    "value", (None, "/controlled", Path("relative"), Path("/a/../b"), Path("/"))
)
def test_administration_path_shape_refuses_before_filesystem(value):
    from tests import occurrence_store_postgres as pg

    with pytest.raises(ValueError):
        pg._administration_path(value)


def test_administration_path_snapshot_ignores_caller_cache_and_rejects_custom_storage():
    from tests import occurrence_store_postgres as pg

    value = Path("/controlled/work")
    object.__setattr__(value, "_str", "/wrong/cache")
    assert str(pg._administration_path(value)) == "/controlled/work"
    attribute = "_raw_paths" if hasattr(value, "_raw_paths") else "_parts"

    class Poison(list):
        def __iter__(self):
            pytest.fail("caller iteration")

    object.__setattr__(value, attribute, Poison(["/controlled/work"]))
    with pytest.raises(ValueError):
        pg._administration_path(value)


@pytest.mark.parametrize(
    "field,value",
    (
        ("getresuid", (10001, 10001, 10001)),
        ("getresgid", (10001, 10001, 10001)),
        ("platform", "win32"),
        ("isolated", 0),
        ("no_site", 0),
        ("dont_write_bytecode", False),
    ),
)
def test_administration_runtime_facts_fail_before_more_directory_checks(monkeypatch, field, value):
    pg, cluster, checked = administration_fixture(monkeypatch)
    checked.clear()
    if field.startswith("getres"):
        setattr(pg.os, field, lambda: value)
    elif field in ("isolated", "no_site"):
        setattr(pg.sys.flags, field, value)
    else:
        setattr(pg.sys, field, value)
    with pytest.raises(ValueError, match="root fixture"):
        cluster._administration_runtime()
    assert checked == []


@pytest.mark.parametrize(
    "selector",
    (
        "DATABASE_URL",
        "SCANIPY_DATABASE_URL",
        "SCANIPY_ACCEPTED_LEDGER_TEST_URL",
        "SCANIPY_OCCURRENCE_TEST_REQUIRED",
        "AWS_SESSION_TOKEN",
        "PGPASSFILE",
        "PGOPTIONS",
    ),
)
def test_administration_never_inherits_ambient_database_or_credential_selector(
    monkeypatch, selector
):
    pg, cluster, checked = administration_fixture(monkeypatch)
    checked.clear()
    pg.os.environ[selector] = "public-diagnostic"
    with pytest.raises(ValueError, match="ambient"):
        cluster._administration_runtime()
    assert checked == []


@pytest.mark.parametrize(
    "url",
    (
        "postgresql://a2_fixture_admin@localhost/a2_fixture_bootstrap",
        "postgresql://a2_fixture_admin@:5433/a2_fixture_bootstrap?host=/run/scanipy-a2-postgres",
        "postgresql://other@:5432/a2_fixture_bootstrap?host=/run/scanipy-a2-postgres",
    ),
)
def test_administration_requires_literal_disposable_route(monkeypatch, url):
    pg, _cluster, checked = administration_fixture(monkeypatch)
    checked.clear()
    with pytest.raises(ValueError, match="exact peer"):
        pg.PrivatePostgres(
            url,
            profile="accepted",
            administration=True,
            migration_cwd=Path("/work"),
            migration_site_packages=Path("/deps"),
        )
    assert checked == []


def administration_login_double(monkeypatch, *, fault=None, transform=None):
    pg, cluster, _checked = administration_fixture(monkeypatch)
    state = SimpleNamespace(
        calls=[],
        names=[],
        memberships={},
        closed=0,
        cursor_closed=0,
        commits=0,
        rows=[],
        one=None,
        connects=[],
        encrypted=False,
    )
    previous = ({"previous_owned": 99}, {"previous": ("previous_owned", "public-fixture")})
    cluster.owned_roles, cluster.roles = map(dict, previous)

    def failure(stage):
        if fault and fault[0] == stage:
            raise fault[1]

    class LoginCursor:
        def execute(self, query, parameters=()):
            state.calls.append((query, parameters))
            if type(query) is str:
                if "max_identifier_length" in query:
                    state.one = (63,)
                elif query.startswith("SET LOCAL password_encryption"):
                    state.encrypted = True
                elif query.startswith("SELECT rolname::text,oid"):
                    failure("readback")
                    state.one = (parameters[0], 1000 + state.names.index(parameters[0]))
                elif query == pg._ADMIN_LOGIN_PROOF:
                    failure("proof")
                    groups = (*pg.ACCEPTED_RESERVED[:3], pg.ACCEPTED_RESERVED[4])
                    rows = []
                    for route, (_key, group, prefix) in pg._ADMINISTRATION_ROUTES.items():
                        if prefix is None:
                            prefix = "altest_" + _key + "_"
                        name = next(name for name in state.names if name.startswith(prefix))
                        inherited = route != "owner"
                        rows.append(
                            (
                                name,
                                1000 + state.names.index(name),
                                True,
                                False,
                                inherited,
                                False,
                                False,
                                False,
                                False,
                                True,
                                group,
                                2000 + groups.index(group),
                                10,
                                False,
                                inherited,
                                True,
                                *(candidate == group for candidate in groups),
                                True,
                                inherited,
                            )
                        )
                    state.rows = transform(rows) if transform else rows
                else:
                    pytest.fail("unexpected administration query")
                return
            prefix = query.seq[0].string
            identifiers = [
                item.strings[0] for item in query.seq if isinstance(item, pg.sql.Identifier)
            ]
            if prefix.startswith("CREATE ROLE"):
                failure("create")
                assert state.encrypted
                state.names.append(identifiers[0])
            else:
                assert prefix.startswith("GRANT")
                failure("grant")
                state.memberships.setdefault(identifiers[1], []).append(
                    (identifiers[0], str(query))
                )

        def fetchone(self):
            return state.one

        def fetchmany(self, count):
            assert count == 6
            return state.rows

        def close(self):
            state.cursor_closed += 1
            failure("cursor-close")

    class LoginConnection:
        def cursor(self):
            failure("cursor")
            return LoginCursor()

        def commit(self):
            state.at_commit = (
                dict(cluster.owned_roles),
                dict(cluster.roles),
                dict(cluster.administration_routes),
            )
            state.commits += 1
            failure("commit")

        def close(self):
            state.closed += 1
            failure("close")

    def connect(**kwargs):
        state.connects.append(kwargs)
        failure("connect")
        return LoginConnection()

    pg.psycopg2.connect = connect
    return pg, cluster, state, previous


def test_administration_thirteen_logins_five_routes_exact_fifty_two_executions(monkeypatch):
    pg, cluster, state, previous = administration_login_double(monkeypatch)
    cluster._create_logins()
    assert len(state.calls) == 52 and len(state.names) == 13
    assert len(cluster.roles) == len(cluster.owned_roles) == 14  # plus preexisting diagnostic row
    assert state.at_commit == (*previous, {})
    assert state.commits == state.closed == state.cursor_closed == 1
    assert all(len(name) <= 63 and name.endswith(UUID(int=933).hex) for name in state.names)
    names = [cluster.roles[key][0] for key in cluster.administration_routes.values()]
    assert len(names) == len(set(names)) == 5
    for route, key in cluster.administration_routes.items():
        name, _password = cluster.roles[key]
        memberships = state.memberships[name]
        assert len(memberships) == 3
        assert all(group == pg._ADMINISTRATION_ROUTES[route][1] for group, _ in memberships)
        assert "ADMIN FALSE" in memberships[0][1]
        assert ("INHERIT FALSE" if route == "owner" else "INHERIT TRUE") in memberships[1][1]
        assert "SET TRUE" in memberships[2][1]
    assert state.connects == [
        {
            **cluster.child,
            "connect_timeout": 2,
            "options": pg._ADMIN_OPTIONS,
            "application_name": "scanipy-a2-fixture-setup",
        }
    ]


@pytest.mark.parametrize(
    "stage",
    (
        "connect",
        "cursor",
        "create",
        "readback",
        "grant",
        "proof",
        "cursor-close",
        "commit",
        "close",
    ),
)
@pytest.mark.parametrize("kind", (OSError, KeyboardInterrupt, SystemExit))
def test_administration_failure_never_promotes_login_maps(monkeypatch, stage, kind):
    failure = kind("controlled fixture failure")
    _pg, cluster, state, previous = administration_login_double(monkeypatch, fault=(stage, failure))
    with pytest.raises(kind) as observed:
        cluster._create_logins()
    assert observed.value is failure and failure.__traceback__ is not None
    assert (cluster.owned_roles, cluster.roles) == previous and cluster.administration_routes == {}
    assert state.closed == (0 if stage == "connect" else 1)
    assert state.cursor_closed == (0 if stage in ("connect", "cursor") else 1)


@pytest.mark.parametrize("column", tuple(range(2, 10)) + tuple(range(13, 22)))
def test_administration_each_login_flag_and_membership_option_is_independent(monkeypatch, column):
    def mutate(rows):
        row = list(rows[0])
        row[column] = not row[column]
        return [tuple(row), *rows[1:]]

    _pg, cluster, state, previous = administration_login_double(monkeypatch, transform=mutate)
    with pytest.raises(AssertionError, match="privilege proof"):
        cluster._create_logins()
    assert (cluster.owned_roles, cluster.roles) == previous and state.commits == 0


@pytest.mark.parametrize("mutation", ("missing", "extra", "duplicate", "oid", "shape", "oversize"))
def test_administration_login_proof_is_complete_exact_and_bounded(monkeypatch, mutation):
    def mutate(rows):
        if mutation == "missing":
            return rows[:-1]
        if mutation == "extra":
            return rows + rows[:1]
        if mutation == "duplicate":
            return [rows[0], rows[0], *rows[2:]]
        row = list(rows[0])
        if mutation == "oid":
            row[1] = True
        elif mutation == "shape":
            row.pop()
        else:
            row[0] = "x" * 4097
        return [tuple(row), *rows[1:]]

    _pg, cluster, state, previous = administration_login_double(monkeypatch, transform=mutate)
    with pytest.raises(AssertionError):
        cluster._create_logins()
    assert (cluster.owned_roles, cluster.roles) == previous and state.commits == 0


def administration_process_outcome(argv, env, cwd, *, returncode=0, stderr=b""):
    from tools.worker import bounded_process as bp

    def output(data):
        evidence = bp.StreamEvidence(
            len(data), len(data), hashlib.sha256(data).digest(), True, False
        )
        return bp.MemoryOutput(evidence, data)

    invocation = bp.FrozenInvocation(
        argv, tuple(sorted(env.items())), str(cwd), 0, hashlib.sha256(b"").digest()
    )
    return bp.ProcessOutcome(
        invocation, "exited", 321, 321, returncode, 0, output(b""), output(stderr), 1, "completed"
    )


def administration_transport(monkeypatch, *, transform=None, failure=None):
    from tools.worker import bounded_process as bp

    pg, cluster, _checked = administration_fixture(monkeypatch)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if failure:
            raise failure
        outcome = administration_process_outcome(argv, kwargs["env"], kwargs["cwd"])
        return transform(outcome) if transform else outcome

    monkeypatch.setattr(bp, "run_bounded_process", run)
    monkeypatch.setattr(pg.subprocess, "run", lambda *_a, **_kw: pytest.fail("unbounded runner"))
    return pg, cluster, calls


def test_administration_migration_uses_actual_owner_fixed_limits_and_no_environment_fallback(
    monkeypatch,
):
    pg, cluster, calls = administration_transport(monkeypatch)
    result = cluster.migrate()
    argv, kwargs = calls[0]
    assert argv[:5] == ("/controlled/python", "-I", "-S", "-B", "-c")
    assert argv[5:] == (
        pg._MIGRATION_BOOTSTRAP,
        str(pg.ROOT),
        "/controlled/deps",
        "upgrade",
        "20260926_0006",
    )
    assert len(argv[5].encode()) <= 8192
    assert kwargs["stdin"] is None and kwargs["cwd"] == Path("/controlled/work")
    assert vars(kwargs["limits"]) == {
        "stdin_bytes": 0,
        "stdout_bytes": 1048576,
        "stderr_bytes": 1048576,
        "combined_output_bytes": 1048576,
        "wall_ms": 60000,
        "cleanup_reserve_ms": 5000,
    }
    assert set(kwargs["env"]) == {
        "LANG",
        "LC_ALL",
        "PGPASSFILE",
        "PGCONNECT_TIMEOUT",
        "PGOPTIONS",
        "SCANIPY_DATABASE_URL",
    }
    assert kwargs["env"]["PGPASSFILE"] == "/dev/null"
    assert kwargs["env"]["PGOPTIONS"] == pg._ADMIN_OPTIONS
    assert cluster.database in kwargs["env"]["SCANIPY_DATABASE_URL"]
    assert result.returncode == 0 and result.stdout == result.stderr == ""
    assert len(cluster.migration_evidence) == 1 and cluster._migration_calls == 1


def test_administration_migration_ten_tickets_no_refund_or_implicit_0007(monkeypatch):
    _pg, cluster, calls = administration_transport(monkeypatch)
    for _ in range(10):
        cluster.migrate()
    with pytest.raises(AssertionError, match="exhausted"):
        cluster.migrate()
    assert len(calls) == len(cluster.migration_evidence) == 10
    assert {argv[-1] for argv, _ in calls} == {"20260926_0006"}


@pytest.mark.parametrize(
    "field,value",
    (
        ("reason", "timeout"),
        ("cleanup", "incomplete"),
        ("returncode", None),
        ("returncode", True),
        ("returncode", -9),
        ("stdout", None),
        ("stdin_sent_bytes", 1),
    ),
)
def test_administration_incomplete_outcome_poisoning_prevents_more_migrations(
    monkeypatch, field, value
):
    def mutate(outcome):
        object.__setattr__(outcome, field, value)
        return outcome

    _pg, cluster, calls = administration_transport(monkeypatch, transform=mutate)
    with pytest.raises(AssertionError):
        cluster.migrate()
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate()
    assert len(calls) == len(cluster.migration_evidence) == 1


@pytest.mark.parametrize(
    "field,value",
    (("eof", False), ("truncated", True), ("observed_bytes", 1), ("retained_bytes", None)),
)
def test_administration_never_accepts_partial_stream_evidence(monkeypatch, field, value):
    def mutate(outcome):
        object.__setattr__(outcome.stdout.evidence, field, value)
        return outcome

    _pg, cluster, calls = administration_transport(monkeypatch, transform=mutate)
    with pytest.raises(AssertionError):
        cluster.migrate()
    assert len(calls) == 1 and cluster._migration_failed


@pytest.mark.parametrize("kind", (OSError, KeyboardInterrupt, SystemExit))
def test_administration_transport_primary_is_exact_and_no_retry(monkeypatch, kind):
    failure = kind("private transport diagnostic")
    prior = ValueError("private earlier failure")
    failure.__context__ = prior
    _pg, cluster, calls = administration_transport(monkeypatch, failure=failure)
    with pytest.raises(kind) as observed:
        cluster.migrate()
    assert observed.value is failure and observed.value.__context__ is prior
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate()
    assert len(calls) == 1


def test_administration_expected_refusal_requires_completed_exact_nonzero(monkeypatch):
    def mutate(outcome):
        object.__setattr__(outcome, "returncode", 1)
        return outcome

    _pg, cluster, calls = administration_transport(monkeypatch, transform=mutate)
    assert cluster.migrate("20260926_0006", expect_success=False).returncode == 1
    with pytest.raises(AssertionError, match="exit differs"):
        cluster.migrate("20260926_0006")
    assert len(calls) == 2 and cluster._migration_failed


@pytest.mark.parametrize("context_only", (False, True))
@pytest.mark.parametrize("kind", (KeyboardInterrupt, SystemExit, ValueError))
def test_administration_cursor_keeps_primary_prior_and_one_uncertain_close(context_only, kind):
    from tests import occurrence_store_postgres as pg

    primary, prior, cleanup = kind("primary"), ValueError("prior"), OSError("close")
    if context_only:
        primary.__context__ = prior
    else:
        primary.__cause__ = prior
    closed = []

    def close():
        closed.append(1)
        raise cleanup

    connection = SimpleNamespace(cursor=lambda: SimpleNamespace(close=close))
    with pytest.raises(kind) as observed:
        with pg._administration_cursor(connection):
            raise primary
    assert observed.value is primary and closed == [1]
    assert isinstance(primary.__cause__, BaseExceptionGroup)
    assert primary.__cause__.exceptions == (prior, cleanup)


@pytest.mark.parametrize("context_only", (False, True))
def test_administration_connection_is_close_only_and_keeps_primary_context(
    monkeypatch, context_only
):
    pg, cluster, _ = administration_fixture(monkeypatch)
    primary, prior, cleanup = KeyboardInterrupt("primary"), ValueError("prior"), OSError("close")
    if context_only:
        primary.__context__ = prior
    else:
        primary.__cause__ = prior
    closed = []

    def close():
        closed.append(1)
        raise cleanup

    pg.psycopg2.connect = lambda **_: SimpleNamespace(close=close)
    with pytest.raises(KeyboardInterrupt) as observed:
        with cluster.admin():
            raise primary
    assert observed.value is primary and closed == [1]
    assert primary.__cause__.exceptions == (prior, cleanup)


def administration_directory_double(
    monkeypatch, *, mode=0o700, uid=0, entry=None, close_fault=None
):
    from tests import occurrence_store_postgres as pg

    os_local = SimpleNamespace(**vars(pg.os))
    state = SimpleNamespace(opened=[], closed=[], scan_closed=0, scan_calls=0)

    def opened(name, flags, **kwargs):
        assert flags & pg.os.O_NOFOLLOW and flags & pg.os.O_CLOEXEC
        fd = 10 + len(state.opened)
        state.opened.append((fd, name, flags, kwargs))
        return fd

    def closed(fd):
        assert fd not in state.closed
        state.closed.append(fd)
        if close_fault == fd:
            raise OSError("uncertain close")

    class Scan:
        def __iter__(self):
            return self

        def __next__(self):
            state.scan_calls += 1
            if entry is None:
                raise StopIteration
            return entry

        def close(self):
            state.scan_closed += 1

    os_local.open, os_local.close = opened, closed
    os_local.fstat = lambda _: SimpleNamespace(st_mode=0o040000 | mode, st_uid=uid)
    os_local.scandir = lambda _: Scan()
    monkeypatch.setattr(pg, "os", os_local)
    return pg, state


@pytest.mark.parametrize(
    "mode,uid,entry,accepted",
    (
        (0o700, 0, None, True),
        (0o755, 0, None, False),
        (0o700, 1000, None, False),
        (0o700, 0, "existing", False),
    ),
)
def test_administration_directory_checks_and_closes_every_acknowledged_slot(
    monkeypatch, mode, uid, entry, accepted
):
    pg, state = administration_directory_double(monkeypatch, mode=mode, uid=uid, entry=entry)
    if accepted:
        pg._administration_directory(Path("/controlled/work"), private=True, empty=True)
    else:
        with pytest.raises(ValueError):
            pg._administration_directory(Path("/controlled/work"), private=True, empty=True)
    assert sorted(state.closed) == [fd for fd, *_ in state.opened]
    assert state.scan_closed == state.scan_calls <= 1


@pytest.mark.parametrize(
    "mode,accepted", ((0o755, True), (0o555, True), (0o775, False), (0o777, False))
)
def test_administration_dependency_directory_never_accepts_group_world_write(
    monkeypatch, mode, accepted
):
    pg, state = administration_directory_double(monkeypatch, mode=mode)
    if accepted:
        pg._administration_directory(Path("/deps"))
    else:
        with pytest.raises(ValueError):
            pg._administration_directory(Path("/deps"))
    assert sorted(state.closed) == [10, 11]


@pytest.mark.parametrize("close_fd", (10, 11, 12))
def test_administration_directory_uncertain_close_is_not_retried(monkeypatch, close_fd):
    pg, state = administration_directory_double(monkeypatch, close_fault=close_fd)
    with pytest.raises(OSError, match="uncertain close"):
        pg._administration_directory(Path("/controlled/work"), private=True, empty=True)
    assert len(state.closed) == len(set(state.closed)) == len(state.opened)


@pytest.mark.parametrize("kind", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("acknowledged", (1, 2))
def test_administration_directory_acquisition_is_already_guarded(monkeypatch, kind, acknowledged):
    import sys as real_sys

    pg, state = administration_directory_double(monkeypatch)
    prior_trace = real_sys.gettrace()
    primary = kind("acknowledged acquisition")
    fired = []

    def trace(frame, event, _arg):
        if (
            frame.f_code is pg._administration_directory.__code__
            and event == "line"
            and len(state.opened) == acknowledged
            and not fired
        ):
            fired.append(frame.f_lineno)
            raise primary
        return trace

    try:
        real_sys.settrace(trace)
        with pytest.raises(kind) as observed:
            pg._administration_directory(Path("/controlled/work"), private=True)
    finally:
        real_sys.settrace(prior_trace)
    assert fired and observed.value is primary and primary.__traceback__ is not None
    assert sorted(state.closed) == [fd for fd, *_ in state.opened]


def administration_cluster_rows():
    return [
        [
            (
                160009,
                "",
                "scram-sha-256",
                "a2_fixture_admin",
                "a2_fixture_admin",
                True,
                True,
                "15s",
                "2s",
            )
        ],
        [
            (
                "local",
                ["all"],
                ["a2_fixture_admin"],
                None,
                None,
                "peer",
                ["map=a2_root_setup"],
                None,
            ),
            ("local", ["all"], ["all"], None, None, "scram-sha-256", None, None),
            ("host", ["all"], ["all"], "0.0.0.0", "0.0.0.0", "reject", None, None),
            ("host", ["all"], ["all"], "::", "::", "reject", None, None),
        ],
        [("a2_root_setup", "root", "a2_fixture_admin", None)],
    ]


def test_administration_cluster_qualification_is_three_fixed_bounded_reads(monkeypatch):
    pg, cluster, _ = administration_fixture(monkeypatch)
    rows, calls, closed = administration_cluster_rows(), [], []

    class Catalog:
        def execute(self, query, parameters=()):
            calls.append((query, parameters))

        def fetchmany(self, count):
            assert count == (2, 5, 2)[len(calls) - 1]
            return rows.pop(0)

        def close(self):
            closed.append("cursor")

    pg.psycopg2.connect = lambda **_: SimpleNamespace(
        cursor=Catalog, close=lambda: closed.append("connection")
    )
    cluster._check_administration_cluster()
    assert not rows and closed == ["cursor", "connection"] and len(calls) == 3
    assert all(query.startswith("SELECT") and not parameters for query, parameters in calls)
    assert "left(" in calls[0][0] and "LIMIT 5" in calls[1][0] and "LIMIT 2" in calls[2][0]
    assert "invalid-rule" in calls[1][0] and "invalid-map" in calls[2][0]


@pytest.mark.parametrize(
    "which,column,value",
    (
        (0, 0, 170000),
        (0, 1, "*"),
        (0, 2, "md5"),
        (0, 3, "postgres"),
        (0, 5, 1),
        (0, 6, False),
        (0, 7, "0"),
        (0, 8, "0"),
        (1, 5, "trust"),
        (1, 6, ["map=other"]),
        (1, 7, "invalid-rule"),
        (2, 1, "anyone"),
        (2, 2, "other"),
        (2, 3, "invalid-map"),
    ),
)
def test_administration_cluster_mismatch_refuses_before_any_mutation(
    monkeypatch, which, column, value
):
    pg, cluster, _ = administration_fixture(monkeypatch)
    rows = administration_cluster_rows()
    changed = list(rows[which][0])
    changed[column] = value
    rows[which][0] = tuple(changed)
    calls = []
    cursor = SimpleNamespace(
        execute=lambda query, _p=(): calls.append(query),
        fetchmany=lambda _n: rows.pop(0),
        close=lambda: None,
    )
    pg.psycopg2.connect = lambda **_: SimpleNamespace(cursor=lambda: cursor, close=lambda: None)
    with pytest.raises(AssertionError):
        cluster.setup()
    assert calls and all(query.startswith("SELECT") for query in calls)
    assert cluster.database_identity is None and cluster.owned_roles == {}


@pytest.mark.parametrize("which", (0, 1, 2))
def test_administration_cluster_extra_rows_never_hide_behind_limit(monkeypatch, which):
    pg, cluster, _ = administration_fixture(monkeypatch)
    rows = administration_cluster_rows()
    rows[which].append(rows[which][0])
    cursor = SimpleNamespace(
        execute=lambda *_: None, fetchmany=lambda _n: rows.pop(0), close=lambda: None
    )
    pg.psycopg2.connect = lambda **_: SimpleNamespace(cursor=lambda: cursor, close=lambda: None)
    with pytest.raises(AssertionError, match="row bound"):
        cluster._check_administration_cluster()


def test_administration_catalog_aggregate_budget_does_not_reset_between_reads():
    from tests import occurrence_store_postgres as pg

    row = ("a" * 4000,) * 4
    cursor = SimpleNamespace(execute=lambda *_: None, fetchmany=lambda _: [row])
    budget = [0]
    pg._administration_rows(cursor, "controlled", maximum=1, columns=4, budget=budget)
    with pytest.raises(AssertionError, match="byte bound"):
        pg._administration_rows(cursor, "controlled", maximum=1, columns=4, budget=budget)


@pytest.mark.parametrize("length,accepted", ((1048576, True), (1048577, False)))
def test_administration_combined_raw_output_exact_cap(monkeypatch, length, accepted):
    from tools.worker import bounded_process as bp

    def mutate(outcome):
        data = b"x" * length
        stream = bp.MemoryOutput(
            bp.StreamEvidence(length, length, hashlib.sha256(data).digest(), True, False), data
        )
        object.__setattr__(outcome, "stdout", stream)
        return outcome

    _pg, cluster, calls = administration_transport(monkeypatch, transform=mutate)
    if accepted:
        assert len(cluster.migrate().stdout) == length
    else:
        with pytest.raises(AssertionError, match="transport incomplete"):
            cluster.migrate()
    assert len(calls) == len(cluster.migration_evidence) == 1


@pytest.mark.parametrize("interrupt", (False, True))
def test_administration_retains_actual_owner_partial_outcome(monkeypatch, interrupt):
    from tools.worker import bounded_process as bp

    _pg, cluster, calls = administration_transport(monkeypatch)
    saved = []

    def failed(argv, **kwargs):
        outcome = administration_process_outcome(argv, kwargs["env"], kwargs["cwd"])
        transport_error = bp.ProcessTransportError(outcome)
        error = KeyboardInterrupt("primary") if interrupt else transport_error
        if interrupt:
            error.__cause__ = transport_error
        saved.extend((outcome, error))
        raise error

    monkeypatch.setattr(bp, "run_bounded_process", failed)
    with pytest.raises(KeyboardInterrupt if interrupt else bp.ProcessTransportError) as observed:
        cluster.migrate()
    assert observed.value is saved[1] and cluster.migration_evidence == saved[:1]
    assert cluster._migration_failed and calls == []


@pytest.mark.parametrize("kind", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("resource", ("cursor", "connection"))
def test_administration_acknowledged_driver_acquisition_has_active_cleanup(
    monkeypatch, kind, resource
):
    import sys as real_sys

    pg, cluster, _ = administration_fixture(monkeypatch)
    acknowledged, closed, fired = [], [], []
    primary = kind("acknowledged driver resource")

    def acquire(*_args, **_kwargs):
        acknowledged.append(1)
        return SimpleNamespace(close=lambda: closed.append(1))

    if resource == "cursor":

        def manager():
            return pg._administration_cursor(SimpleNamespace(cursor=acquire))

        code = pg._administration_cursor.__wrapped__.__code__
    else:
        pg.psycopg2.connect = acquire
        manager = cluster._administration_admin
        code = pg.PrivatePostgres._administration_admin.__wrapped__.__code__

    def trace(frame, event, _arg):
        if frame.f_code is code and event == "line" and acknowledged and not fired:
            fired.append(frame.f_lineno)
            raise primary
        return trace

    previous = real_sys.gettrace()
    try:
        real_sys.settrace(trace)
        with pytest.raises(kind) as observed, manager():
            pytest.fail("interruption did not precede yield")
    finally:
        real_sys.settrace(previous)
    assert observed.value is primary and len(fired) == 1 and closed == [1]


def test_administration_bootstrap_literal_has_no_site_or_plugin_activation():
    import ast

    from tests import occurrence_store_postgres as pg

    tree = ast.parse(pg._MIGRATION_BOOTSTRAP)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {"os", "sys"}
    from_imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert from_imports == {"alembic", "alembic.config"}
    assert "site.addsitedir" not in pg._MIGRATION_BOOTSTRAP
    assert (
        "script_location" in pg._MIGRATION_BOOTSTRAP
        and "prepend_sys_path" in pg._MIGRATION_BOOTSTRAP
    )
    assert "SCRAM-SHA-256$%%" in pg._ADMIN_LOGIN_PROOF
    assert pg._ADMIN_LOGIN_PROOF.count("%s") == 1


@pytest.mark.parametrize("target", ("20260926_0007", "head", "base"))
def test_occurrence_still_refuses_new_or_unbounded_target(monkeypatch, target):
    from tests import occurrence_store_postgres as pg

    cluster = pg.PrivatePostgres("postgresql://controlled@localhost/bootstrap")
    monkeypatch.setattr(pg.subprocess, "run", lambda *_a, **_kw: pytest.fail("unexpected launch"))
    with pytest.raises(ValueError, match="unsupported"):
        cluster.migrate(target)


def test_administration_does_not_change_fixed_setup_migration_census():
    import ast
    import inspect
    import textwrap

    from tests import occurrence_store_postgres as pg

    calls = []
    for function in (pg.PrivatePostgres.setup, pg.PrivatePostgres._setup_accepted):
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "migrate"
            ):
                calls.append(node.args[0].value)
    assert len(calls) == 10 and set(calls) == {
        "20260925_0003",
        "20260925_0004",
        "20260925_0005",
        "20260926_0006",
    }


def test_administration_profile_exact_type_precedes_caller_comparison(monkeypatch):
    from tests import occurrence_store_postgres as pg

    class Poison(str):
        def __ne__(self, _other):
            pytest.fail("caller profile comparison")

    monkeypatch.setattr(pg, "make_url", lambda *_: pytest.fail("unexpected URL parser"))
    with pytest.raises(ValueError):
        pg.PrivatePostgres("unused", profile=Poison("accepted"), administration=True)


@pytest.mark.parametrize("keyword", ("action", "expect_success"))
def test_administration_migration_primitives_precede_work_and_callbacks(monkeypatch, keyword):
    _pg, cluster, calls = administration_transport(monkeypatch)

    class Poison:
        def __eq__(self, _other):
            pytest.fail("caller migration comparison")

        def __bool__(self):
            pytest.fail("caller migration truthiness")

    with pytest.raises(ValueError):
        cluster.migrate(**{keyword: Poison()})
    assert calls == [] and cluster._migration_calls == 0 and not cluster._migration_failed


_ADMINISTRATION_TEN = (
    ("upgrade", "20260925_0003"),
    ("upgrade", "20260925_0004"),
    ("upgrade", "20260925_0005"),
    ("upgrade", "20260925_0005"),
    ("downgrade", "20260925_0003"),
    ("upgrade", "20260925_0005"),
    ("upgrade", "20260926_0006"),
    ("upgrade", "20260926_0006"),
    ("downgrade", "20260925_0005"),
    ("upgrade", "20260926_0006"),
)


def administration_complete_setup(monkeypatch, *, login_fault=None, migration_fault=None):
    """Real setup/migrate/login methods; fixed-query DB and owner-transport doubles only."""
    from contextlib import contextmanager

    from tools.worker import bounded_process as bp

    pg, cluster, login, _previous = administration_login_double(monkeypatch, fault=login_fault)
    cluster.owned_roles.clear()
    cluster.roles.clear()
    state = SimpleNamespace(calls=[], events=[], roles={}, one=None, many=[], login=False)

    class SetupCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

        def close(self):
            state.events.append("setup-cursor-close")

        def execute(self, query, parameters=()):
            if type(query) is not str:
                prefix = query.seq[0].string
                identifiers = [
                    item.strings[0] for item in query.seq if isinstance(item, pg.sql.Identifier)
                ]
                if prefix.startswith("CREATE ROLE"):
                    assert identifiers[0] not in state.roles
                    state.roles[identifiers[0]] = 7000 + len(state.roles)
                else:
                    assert prefix.startswith(("CREATE DATABASE", "ALTER DEFAULT PRIVILEGES"))
                return
            if query == "SELECT rolname FROM pg_roles WHERE rolname=ANY(%s)":
                state.many = [(name,) for name in parameters[0] if name in state.roles]
            elif query == "SELECT oid,datdba FROM pg_database WHERE datname=%s":
                state.one = (8001, 10)
            elif query == "SELECT oid FROM pg_roles WHERE rolname=%s":
                oid = state.roles.get(parameters[0])
                state.one = (oid,) if oid is not None else None
            elif query.startswith("SELECT oid FROM pg_roles WHERE rolname='"):
                state.one = (state.roles[query.split("'")[1]],)
            elif query == "SELECT rolname,oid FROM pg_roles WHERE rolname=ANY(%s)":
                state.many = [(name, state.roles[name]) for name in parameters[0]]
            elif query.startswith("CREATE ROLE "):
                name = query.split()[2]
                assert name not in state.roles
                state.roles[name] = 9000
            elif query.startswith("DROP ROLE "):
                del state.roles[query.split()[2]]
            else:
                pytest.fail("unexpected fixed setup query")

        def fetchone(self):
            return state.one

        def fetchall(self):
            return state.many

    class SetupConnection:
        def cursor(self):
            return SetupCursor()

        def commit(self):
            state.events.append("setup-commit")

        def close(self):
            state.events.append("setup-close")

    @contextmanager
    def admin(*, bootstrap=False):
        if state.login:
            with cluster._administration_admin(bootstrap=bootstrap) as connection:
                yield connection
        else:
            connection = SetupConnection()
            try:
                yield connection
            finally:
                connection.close()

    original_connect = pg.psycopg2.connect

    def login_connect(**kwargs):
        connection = original_connect(**kwargs)
        original_commit, original_close = connection.commit, connection.close

        def commit():
            state.events.append(("login-commit", cluster._administration_setup_complete))
            original_commit()

        def close():
            state.events.append(("login-close", cluster._administration_setup_complete))
            original_close()

        connection.commit, connection.close = commit, close
        return connection

    pg.psycopg2.connect = login_connect
    original_logins = cluster._create_logins

    def logins():
        state.events.append(("login-entry", cluster._migration_calls))
        state.login = True
        original_logins()
        state.login = False
        state.events.append(("login-return", cluster._administration_setup_complete))

    def rows(query, parameters=()):
        if "SELECT rolname,oid" in query:
            return [(name, state.roles[name]) for name in parameters[0]]
        assert query.startswith("SELECT count(*)")
        if "FROM pg_roles" in query:
            return [(sum(name in state.roles for name in parameters[0]),)]
        return [(0,)]  # Fixed empty round-trip schema/ACL observations, not a SQL interpreter.

    def run(argv, **kwargs):
        state.calls.append((argv, kwargs))
        ordinal = len(state.calls)
        expected = (
            _ADMINISTRATION_TEN[ordinal - 1] if ordinal <= 10 else ("upgrade", "20260926_0007")
        )
        assert argv[-2:] == expected
        assert cluster._migration_calls == ordinal and cluster._migration_failed
        if migration_fault and ordinal == migration_fault[0]:
            raise migration_fault[1]
        refused = ordinal in (3, 7)
        if not refused:
            if argv[-2:] == ("downgrade", "20260925_0003"):
                for name in pg.RESERVED:
                    del state.roles[name]
            elif argv[-2:] == ("downgrade", "20260925_0005"):
                for name in pg.ACCEPTED_RESERVED:
                    del state.roles[name]
            elif argv[-1] == "20260925_0005":
                state.roles.update({name: ordinal * 100 + i for i, name in enumerate(pg.RESERVED)})
            elif argv[-1] == "20260926_0006":
                state.roles.update(
                    {name: ordinal * 100 + i for i, name in enumerate(pg.ACCEPTED_RESERVED)}
                )
        stderr = (
            b"reserved execution role already exists"
            if ordinal == 3
            else b"reserved accepted role already exists"
            if ordinal == 7
            else b""
        )
        return administration_process_outcome(
            argv, kwargs["env"], kwargs["cwd"], returncode=int(refused), stderr=stderr
        )

    monkeypatch.setattr(cluster, "admin", admin)
    monkeypatch.setattr(cluster, "rows", rows)
    monkeypatch.setattr(
        cluster, "_check_administration_cluster", lambda: state.events.append("cluster")
    )
    monkeypatch.setattr(cluster, "_seed_legacy_history", lambda: None)
    monkeypatch.setattr(cluster, "_legacy_history", lambda: [("inert legacy row",)])
    monkeypatch.setattr(cluster, "_legacy_acl", lambda: [("inert legacy ACL",)])
    monkeypatch.setattr(cluster, "_execution_definitions", lambda: [("inert execution body",)])
    monkeypatch.setattr(cluster, "_execution_acl", lambda: [("inert execution ACL",)])
    monkeypatch.setattr(cluster, "_create_logins", logins)
    monkeypatch.setattr(bp, "run_bounded_process", run)
    monkeypatch.setattr(pg.subprocess, "run", lambda *_a, **_kw: pytest.fail("unbounded process"))
    return pg, cluster, state, login


def test_final_ticket_real_setup_sequence_arms_only_after_login_close(monkeypatch):
    pg, cluster, state, login = administration_complete_setup(monkeypatch)
    assert cluster._administration_setup_complete is False
    cluster.setup()
    assert [argv[-2:] for argv, _ in state.calls] == list(_ADMINISTRATION_TEN)
    assert cluster._migration_calls == len(cluster.migration_evidence) == 10
    assert cluster._administration_setup_complete and not cluster._migration_failed
    assert cluster.round_trip_verified and cluster.accepted_round_trip_verified
    assert state.events[-4:] == [
        ("login-entry", 10),
        ("login-commit", False),
        ("login-close", False),
        ("login-return", False),
    ]
    assert login.commits == login.closed == 1 and len(login.names) == 13
    assert set(cluster.administration_routes) == set(pg._ADMINISTRATION_ROUTES)
    assert cluster.migrate("20260926_0007").returncode == 0
    assert cluster._migration_calls == len(cluster.migration_evidence) == 11
    assert cluster.migration_target == "20260926_0006"
    assert not cluster._migration_failed
    for argv, kwargs in state.calls:
        assert kwargs["limits"].wall_ms == 60000 and kwargs["limits"].cleanup_reserve_ms == 5000
        assert kwargs["limits"].combined_output_bytes == 1048576
        assert kwargs["cwd"] == Path("/controlled/work") and kwargs["stdin"] is None
        assert argv[5] == pg._MIGRATION_BOOTSTRAP
    assert sum(kwargs["limits"].wall_ms for _, kwargs in state.calls) == 660000
    assert sum(kwargs["limits"].combined_output_bytes for _, kwargs in state.calls) == 11534336


@pytest.mark.parametrize("ordinal", range(1, 11))
def test_final_ticket_setup_migration_failure_never_arms(monkeypatch, ordinal):
    primary = OSError("controlled migration failure")
    _pg, cluster, state, login = administration_complete_setup(
        monkeypatch, migration_fault=(ordinal, primary)
    )
    with pytest.raises(OSError) as observed:
        cluster.setup()
    assert observed.value is primary and cluster._migration_failed
    assert len(state.calls) == cluster._migration_calls == ordinal
    assert not cluster._administration_setup_complete and not login.commits
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == ordinal


@pytest.mark.parametrize("stage", ("proof", "cursor-close", "commit", "close"))
@pytest.mark.parametrize("kind", (OSError, KeyboardInterrupt, SystemExit))
def test_final_ticket_login_failure_never_arms_or_promotes(monkeypatch, stage, kind):
    primary = kind("controlled login cleanup failure")
    _pg, cluster, state, _login = administration_complete_setup(
        monkeypatch, login_fault=(stage, primary)
    )
    with pytest.raises(kind) as observed:
        cluster.setup()
    assert observed.value is primary and len(state.calls) == cluster._migration_calls == 10
    assert not cluster._administration_setup_complete
    assert cluster.roles == {} and cluster.administration_routes == {}
    with pytest.raises(AssertionError, match="exhausted"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 10


@pytest.mark.parametrize("count", range(11))
def test_final_ticket_arbitrary_calls_do_not_establish_setup(monkeypatch, count):
    _pg, cluster, calls = administration_transport(monkeypatch)
    for _ in range(count):
        cluster.migrate()
    with pytest.raises(AssertionError, match="exhausted"):
        cluster.migrate("20260926_0007")
    assert len(calls) == cluster._migration_calls == count
    assert not cluster._migration_failed and not cluster._administration_setup_complete


@pytest.mark.parametrize(
    "kwargs",
    (
        {},
        {"target": None},
        {"target": "20260926_0006"},
        {"target": "20260926_0007", "action": "downgrade"},
        {"target": "20260926_0007", "expect_success": False},
        {"target": "head"},
        {"target": "base"},
    ),
)
def test_final_ticket_only_explicit_successful_upgrade_then_never_twelfth(monkeypatch, kwargs):
    _pg, cluster, state, _login = administration_complete_setup(monkeypatch)
    cluster.setup()
    with pytest.raises((AssertionError, ValueError)):
        cluster.migrate(**kwargs)
    assert len(state.calls) == cluster._migration_calls == 10 and not cluster._migration_failed
    cluster.migrate("20260926_0007")
    for request in (kwargs, {"target": "20260926_0007"}, {}):
        with pytest.raises((AssertionError, ValueError)):
            cluster.migrate(**request)
    assert len(state.calls) == cluster._migration_calls == 11 and not cluster._migration_failed


@pytest.mark.parametrize("kind", (OSError, KeyboardInterrupt, SystemExit))
def test_final_ticket_transport_failure_is_spent_and_cannot_retry(monkeypatch, kind):
    primary = kind("controlled final transport")
    prior = ValueError("controlled previous context")
    primary.__context__ = prior
    _pg, cluster, state, _login = administration_complete_setup(
        monkeypatch, migration_fault=(11, primary)
    )
    cluster.setup()
    with pytest.raises(kind) as observed:
        cluster.migrate("20260926_0007")
    assert observed.value is primary and primary.__context__ is prior
    assert len(state.calls) == cluster._migration_calls == 11 and cluster._migration_failed
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 11


@pytest.mark.parametrize(
    "field,value",
    (
        ("reason", "timeout"),
        ("cleanup", "incomplete"),
        ("returncode", None),
        ("returncode", 1),
        ("returncode", True),
        ("stdin_sent_bytes", 1),
    ),
)
def test_final_ticket_incomplete_outcome_remains_evidence_not_success(monkeypatch, field, value):
    from tools.worker import bounded_process as bp

    _pg, cluster, state, _login = administration_complete_setup(monkeypatch)
    cluster.setup()
    original = bp.run_bounded_process
    retained = []

    def corrupt(argv, **kwargs):
        outcome = original(argv, **kwargs)
        object.__setattr__(outcome, field, value)
        retained.append(outcome)
        return outcome

    monkeypatch.setattr(bp, "run_bounded_process", corrupt)
    with pytest.raises(AssertionError):
        cluster.migrate("20260926_0007")
    assert cluster.migration_evidence[-1] is retained[0]
    assert len(cluster.migration_evidence) == len(state.calls) == 11 and cluster._migration_failed
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 11


@pytest.mark.parametrize("stream", ("stdout", "stderr"))
@pytest.mark.parametrize(
    "field,value", (("eof", False), ("truncated", True), ("retained_bytes", 1))
)
def test_final_ticket_partial_stream_is_retained_without_retry(monkeypatch, stream, field, value):
    from tools.worker import bounded_process as bp

    _pg, cluster, state, _login = administration_complete_setup(monkeypatch)
    cluster.setup()
    original = bp.run_bounded_process

    def corrupt(argv, **kwargs):
        outcome = original(argv, **kwargs)
        object.__setattr__(getattr(outcome, stream).evidence, field, value)
        return outcome

    monkeypatch.setattr(bp, "run_bounded_process", corrupt)
    with pytest.raises(AssertionError, match="transport incomplete"):
        cluster.migrate("20260926_0007")
    assert len(cluster.migration_evidence) == len(state.calls) == 11
    assert getattr(getattr(cluster.migration_evidence[-1], stream).evidence, field) == value
    assert cluster._migration_failed
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 11


@pytest.mark.parametrize("interrupt", (None, KeyboardInterrupt, SystemExit))
def test_final_ticket_owner_partial_exception_retains_exact_outcome(monkeypatch, interrupt):
    from tools.worker import bounded_process as bp

    _pg, cluster, state, _login = administration_complete_setup(monkeypatch)
    cluster.setup()
    original, retained = bp.run_bounded_process, []

    def fail(argv, **kwargs):
        outcome = original(argv, **kwargs)
        carrier = bp.ProcessTransportError(outcome)
        primary = carrier if interrupt is None else interrupt("controlled final interruption")
        if primary is not carrier:
            primary.__cause__ = carrier
        retained.extend((outcome, primary))
        raise primary

    monkeypatch.setattr(bp, "run_bounded_process", fail)
    with pytest.raises(bp.ProcessTransportError if interrupt is None else interrupt) as observed:
        cluster.migrate("20260926_0007")
    assert observed.value is retained[1] and cluster.migration_evidence[-1] is retained[0]
    assert len(cluster.migration_evidence) == len(state.calls) == 11
    with pytest.raises(AssertionError, match="unavailable"):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 11


@pytest.mark.parametrize("corruption", ("nine", "eleven", "failed"))
def test_final_ticket_setup_final_consistency_check_cannot_arm(monkeypatch, corruption):
    _pg, cluster, state, _login = administration_complete_setup(monkeypatch)
    original_logins = cluster._create_logins

    def corrupt_after_logins():
        original_logins()
        # Explicit private-state fault injection, not evidence of real database state.
        if corruption == "failed":
            cluster._migration_failed = True
        else:
            cluster._migration_calls = 9 if corruption == "nine" else 11

    monkeypatch.setattr(cluster, "_create_logins", corrupt_after_logins)
    with pytest.raises(AssertionError, match="schedule is incomplete"):
        cluster.setup()
    assert not cluster._administration_setup_complete and len(state.calls) == 10
    with pytest.raises(AssertionError):
        cluster.migrate("20260926_0007")
    assert len(state.calls) == 10

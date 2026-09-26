"""Explicit disposable-PG 0007 tests; never operational authority or real keys.

Requires the separately reviewed accepted-profile literal0007 harness allowlist.
The session's existing owned child is upgraded explicitly, then restored to0006.
No second cluster/session fixture, ambient target, head or adoption is used.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import psycopg2
import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import ledger_repository as r
from services.scan.accepted_inputs import schemas as s
from tests.integration.test_accepted_ledger_security import material_history_snapshot
from tests.integration.test_accepted_ledger_sql import SqlLedger
from tests.unit.test_accepted_historical_reads import migration

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.occurrence_store_postgres"]
MISSING = "accepted-historical-row-missing"


def functions(pg):
    return pg.rows(
        "SELECT p.oid,p.proowner,p.proacl::text,p.proconfig,p.prosrc,"
        "p.proname,p.proargtypes::text,p.proallargtypes::text,p.proargmodes::text,"
        "p.proargnames,p.prorettype,p.prolang,p.prosecdef,p.proleakproof,p.proisstrict,"
        "p.proretset,p.provolatile,p.proparallel,p.procost,p.prorows,p.prosupport,"
        "p.provariadic,p.pronargdefaults,p.proargdefaults::text,p.protrftypes::text,"
        "p.probin,p.prosqlbody::text FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') "
        "ORDER BY n.nspname,p.proname,p.oid"
    )


def same_except_bodies(before, after):
    assert len(before) == len(after)
    changed = []
    for old, new in zip(before, after, strict=True):
        assert old[:4] == new[:4] and old[5:] == new[5:]
        if old[4] != new[4]:
            changed.append(old[5])
    assert sorted(changed) == ["read_authority_event_v1", "read_publication_receipt_v1"]


@pytest.fixture(scope="module")
def pg7(accepted_ledger_pg):
    pg = accepted_ledger_pg
    assert pg.migration_target == "20260926_0006"
    before = functions(pg)
    pg.migrate("20260926_0007")
    same_except_bodies(before, functions(pg))
    try:
        yield pg
    finally:
        pg.migrate("20260926_0006", action="downgrade")
        assert functions(pg) == before


def original_driver(captured, code, detail=None):
    assert type(captured.value) is s.VerificationError and captured.value.code == code
    original = captured.value.__cause__
    assert type(original) is psycopg2.errors.RaiseException
    assert original.pgcode == "P0001"
    assert original.diag.message_primary == code
    assert original.diag.message_detail == detail
    return original


@pytest.mark.parametrize("selector", ("publication_key", "approval_event_id"))
def test_missing_publication_has_private_marker_but_original_public_error(pg7, selector):
    ledger = SqlLedger(pg7)
    with pytest.raises(s.VerificationError) as captured, ledger.repo("reader") as repository:
        repository.read_publication_receipt(**{selector: uuid4()})
    assert (
        r._historical_read_failure_kind(original_driver(captured, "ledger-mismatch", MISSING))
        == "missing"
    )


@pytest.mark.parametrize(
    "kind",
    (
        "policy",
        "admission",
        "approval",
        "seal-authorization",
        "execution-authorization",
        "execution-denial",
    ),
)
def test_missing_typed_authority_has_private_marker(pg7, kind):
    ledger = SqlLedger(pg7)
    with pytest.raises(s.VerificationError) as captured, ledger.repo("reader") as repository:
        repository.read_authority_event(kind, uuid4(), "a" * 64)
    assert (
        r._historical_read_failure_kind(original_driver(captured, "ledger-mismatch", MISSING))
        == "missing"
    )


@pytest.mark.parametrize("kind", ("policy", "admission", "approval"))
def test_present_event_wrong_requested_digest_is_unmarked(pg7, kind):
    ledger = SqlLedger(pg7).activate()
    event = (
        ledger.policy
        if kind == "policy"
        else ledger.checkpoint
        if kind == "admission"
        else ledger.approval
    )
    with pytest.raises(s.VerificationError) as captured, ledger.repo("reader") as repository:
        repository.read_authority_event(kind, UUID(event["event_id"]), "a" * 64)
    assert r._historical_read_failure_kind(original_driver(captured, "ledger-mismatch")) is None


def test_populated_up_down_preserves_oids_acl_history_and_exact_reads(pg7):
    ledger = SqlLedger(pg7).activate()
    tables = ("artifact_versions", "bundle_versions", "authority_events", "request_bundle_bindings")
    history = {table: material_history_snapshot(pg7, table, ledger.namespace) for table in tables}
    after = functions(pg7)
    pg7.migrate("20260926_0006", action="downgrade")
    before = functions(pg7)
    same_except_bodies(before, after)
    # Old SQL is deliberately not inferred as missing by the new client helper.
    with pytest.raises(s.VerificationError) as captured, ledger.repo("reader") as repository:
        repository.read_publication_receipt(publication_key=uuid4())
    assert r._historical_read_failure_kind(original_driver(captured, "ledger-mismatch")) is None
    pg7.migrate("20260926_0007")
    assert functions(pg7) == after
    for table in tables:
        assert material_history_snapshot(pg7, table, ledger.namespace) == history[table]
    with ledger.repo("reader") as repository:
        assert (
            repository.read_publication_receipt(
                publication_key=UUID(ledger.approval["publication_key"])
            )
            == ledger.publication.record_bytes
        )
    for kind, row, role, schema in (
        ("policy", ledger.policy, "current-policy", s.POLICY),
        ("admission", ledger.checkpoint, "admission-checkpoint", s.ADMISSION),
        ("approval", ledger.approval, "approval-statement", s.APPROVAL),
    ):
        with ledger.repo("reader") as repository:
            raw, support = repository.read_authority_event(
                kind, UUID(row["event_id"]), c.domain_digest(schema, ledger.objects[role])
            )
        assert raw == ledger.objects[role] and support


@pytest.mark.parametrize("read", ("publication", "approval", "admission"))
@pytest.mark.parametrize("failure", ("length", "syntax", "link"))
def test_stored_failures_do_not_acquire_missing_marker(pg7, read, failure):
    if read == "admission" and failure == "link":
        # Its event-ID/raw hash validation is content-mismatch, not publication links.
        expected = "content-mismatch"
    else:
        expected = "ledger-mismatch" if failure != "syntax" else "content-mismatch"
    ledger = SqlLedger(pg7).activate()
    kind = "admission" if read == "admission" else "approval"
    row = ledger.checkpoint if kind == "admission" else ledger.approval
    schema = s.ADMISSION if kind == "admission" else s.APPROVAL
    role = "admission-checkpoint" if kind == "admission" else "approval-statement"
    with pg7.admin() as connection, connection.cursor() as cursor:
        # Deliberate privileged corruption, entirely rolled back. Ordinary owner
        # immutable-history routes neither produce nor permit this state.
        cursor.execute("ALTER TABLE scanipy_accepted_inputs.authority_events DISABLE TRIGGER USER")
        if failure in ("length", "syntax"):
            cursor.execute(
                "UPDATE scanipy_accepted_inputs.authority_events SET record_bytes=%s "
                "WHERE namespace_id=%s AND kind=%s",
                (b" " * 65537 if failure == "length" else b"{", str(ledger.namespace), kind),
            )
        elif kind == "admission":
            changed = {**row, "event_id": str(uuid4())}
            cursor.execute(
                "UPDATE scanipy_accepted_inputs.authority_events SET record_bytes=%s "
                "WHERE namespace_id=%s AND kind='admission'",
                (c.encode_document(changed, s.ADMISSION), str(ledger.namespace)),
            )
        else:
            receipt = c.decode_document(ledger.publication.record_bytes, s.PUBLICATION)
            receipt["publisher_actor_id"] = str(uuid4())
            raw = c.encode_document(receipt, s.PUBLICATION)
            cursor.execute(
                "UPDATE scanipy_accepted_inputs.authority_events SET publication_receipt_bytes=%s,"
                "publication_receipt_digest=%s WHERE namespace_id=%s AND kind='approval'",
                (raw, bytes.fromhex(c.domain_digest(s.PUBLICATION, raw)), str(ledger.namespace)),
            )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_reader")
        repository = r.AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            if read == "publication":
                repository.read_publication_receipt(
                    publication_key=UUID(ledger.approval["publication_key"])
                )
            else:
                repository.read_authority_event(
                    kind, UUID(row["event_id"]), c.domain_digest(schema, ledger.objects[role])
                )
        assert r._historical_read_failure_kind(original_driver(captured, expected)) is None
        connection.rollback()


@pytest.mark.parametrize("index", (0, 1))
@pytest.mark.parametrize(
    "drift", ("missing", "body", "owner", "security", "search_path", "cost", "volatility")
)
def test_migration_refuses_target_drift_before_either_replacement(pg7, index, drift):
    m, before = migration(), functions(pg7)
    signature = "scanipy_accepted_inputs." + m.FUNCTIONS[index][0]
    with pg7.admin() as connection, connection.cursor() as cursor:
        # Reversible transaction-local test of predecessor admission; Alembic's
        # durable version is not modified by these deliberately rolled-back DOs.
        cursor.execute(m._replacement(forward=False))
        if drift == "missing":
            cursor.execute("DROP FUNCTION " + signature)
        elif drift == "body":
            altered = m.FUNCTIONS[index][5].replace(
                "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
            )
            cursor.execute(
                altered.replace("DECLARE namespace", "-- test-only drift\nDECLARE namespace", 1)
            )
        else:
            clause = {
                "owner": "OWNER TO scanipy_accepted_reader",
                "security": "SECURITY INVOKER",
                "search_path": "SET search_path TO pg_catalog",
                "cost": "COST 101",
                "volatility": "STABLE",
            }[drift]
            cursor.execute("ALTER FUNCTION " + signature + " " + clause)
        with pytest.raises(psycopg2.errors.RaiseException, match="accepted read migration target"):
            cursor.execute(m._replacement(forward=True))
        connection.rollback()
    assert functions(pg7) == before


def test_actual_owner_work_and_scope_errors_are_not_missing(pg7):
    ledger = SqlLedger(pg7)
    with (
        pytest.raises(s.VerificationError) as captured,
        r.accepted_ledger_transaction(
            lambda: pg7.connection("accepted_reader"), uuid4(), ledger.org
        ) as repository,
    ):
        repository.read_publication_receipt(publication_key=uuid4())
    assert captured.value.code == "scope-mismatch"
    assert r._historical_read_failure_kind(captured.value.__cause__) is None
    with pg7.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE scanipy_accepted_owner")
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(0)")
        with pytest.raises(psycopg2.errors.RaiseException) as work:
            cursor.execute("SELECT scanipy_accepted_inputs.v1_charge(0,100001)")
        assert work.value.diag.message_primary == "invalid-input"
        assert work.value.diag.message_detail == "accepted-work-limit"
        assert r._historical_read_failure_kind(work.value) is None
        connection.rollback()


@pytest.mark.parametrize("kind", ("policy", "admission"))
def test_existing_signature_constraint_refuses_invalid_length_before_read(pg7, kind):
    ledger = SqlLedger(pg7).activate()
    with pg7.admin() as connection, connection.cursor() as cursor:
        cursor.execute("ALTER TABLE scanipy_accepted_inputs.authority_events DISABLE TRIGGER USER")
        # The table itself prevents constructing this invalid R3 signature row.
        # This is a constraint refusal, not an executed R3 decoding assertion.
        with pytest.raises(psycopg2.errors.CheckViolation) as captured:
            cursor.execute(
                "UPDATE scanipy_accepted_inputs.authority_events SET signature_bytes=%s "
                "WHERE namespace_id=%s AND kind=%s",
                (b"bad", str(ledger.namespace), kind),
            )
        assert r._historical_read_failure_kind(captured.value) is None
        connection.rollback()

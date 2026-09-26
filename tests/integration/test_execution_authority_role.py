"""Actual effective-role SQL qualification, NOT login/authentication/escape testing.

Collected without effects. Execution requires the dedicated accepted-PG grant.
Existing session fixtures/owners are reused; no operator or key is installed.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg2
import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs.ledger_repository import AcceptedLedgerRepository
from tests.integration.test_accepted_historical_reads import functions
from tests.integration.test_accepted_ledger_security import material_history_snapshot
from tests.integration.test_accepted_ledger_sql import SqlLedger, execution_binding
from tests.unit.test_execution_authority_role import migration, original_definition

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.occurrence_store_postgres"]
EXECUTION_READER = migration().ROLE


def catalog(pg):
    """Exclude ONLY this new role's ACL entries; compare every original entry."""
    definitions = [row[:2] + row[3:] for row in functions(pg)]
    grants = pg.rows(
        "SELECT p.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid=p.pronamespace CROSS JOIN LATERAL "
        "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
        "WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') "
        "AND a.grantee::bigint<>coalesce((SELECT oid::bigint FROM pg_roles WHERE rolname=%s),-1) "
        "ORDER BY p.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable",
        (EXECUTION_READER,),
    )
    schemas = pg.rows(
        "SELECT n.oid,n.nspowner,a.grantor,a.grantee,a.privilege_type,a.is_grantable "
        "FROM pg_namespace n CROSS JOIN LATERAL "
        "aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a "
        "WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') "
        "AND a.grantee::bigint<>coalesce((SELECT oid::bigint FROM pg_roles WHERE rolname=%s),-1) "
        "ORDER BY n.oid,a.grantor,a.grantee,a.privilege_type,a.is_grantable",
        (EXECUTION_READER,),
    )
    tables = pg.rows(
        "SELECT c.oid,c.relname,c.relowner,c.relacl::text,c.relrowsecurity,c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') "
        "ORDER BY c.oid"
    )
    return definitions, grants, schemas, tables


def history(ledger):
    rows = tuple(
        material_history_snapshot(ledger.pg, table, ledger.namespace)
        for table in (
            "artifact_versions",
            "bundle_versions",
            "authority_events",
            "request_bundle_bindings",
        )
    )
    return (*rows, ledger.pg._legacy_history())


@pytest.fixture(scope="module")
def role_pg(accepted_ledger_pg):
    pg = accepted_ledger_pg
    assert pg.profile == "accepted" and not pg.administration
    assert pg.migration_target == "20260926_0006"
    original = functions(pg)
    pg.migrate("20260926_0007")
    before = catalog(pg)
    pg.migrate("20260926_0008")
    assert catalog(pg) == before
    try:
        yield pg
    finally:
        # No retry after unknown transition. The session's dispose also refuses it.
        pg._drop_reader_probe_database()
        before = catalog(pg)
        pg.migrate("20260926_0007", action="downgrade")
        assert catalog(pg) == before
        pg.migrate("20260926_0006", action="downgrade")
        assert functions(pg) == original


@contextmanager
def reader_transaction(ledger):
    with ledger.pg.admin() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout='15s'")
                cursor.execute("SET LOCAL lock_timeout='2s'")
                cursor.execute("SELECT session_user::text")
                session = cursor.fetchone()[0]
                cursor.execute("SET LOCAL ROLE scanipy_accepted_execution_reader")
                cursor.execute(
                    "SELECT current_user::text,session_user::text,rolsuper,rolcanlogin "
                    "FROM pg_roles WHERE rolname=current_user"
                )
                assert cursor.fetchone() == (EXECUTION_READER, session, False, False)
                assert session != EXECUTION_READER  # Deliberately NOT an authenticated reader.
            yield AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        finally:
            connection.rollback()


def current_inputs(ledger):
    return (
        execution_binding(ledger.authorization.record_bytes),
        c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION),
    )


def test_exact_reader_role_and_seven_owner_issued_grants(role_pg):
    oid = role_pg.owned_roles[EXECUTION_READER]
    assert role_pg.rows(
        "SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,"
        "rolbypassrls,rolconnlimit FROM pg_roles WHERE oid=%s",
        (oid,),
    ) == [(*(False,) * 7, -1)]
    assert role_pg.rows(
        "SELECT count(*) FROM pg_auth_members WHERE roleid=%s OR member=%s OR grantor=%s",
        (oid, oid, oid),
    ) == [(0,)]
    grants = role_pg.rows(
        "SELECT p.oid::regprocedure::text,a.grantor=p.proowner,a.privilege_type,a.is_grantable "
        "FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE a.grantee=%s "
        "UNION ALL SELECT n.nspname,a.grantor=n.nspowner,a.privilege_type,a.is_grantable "
        "FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a WHERE a.grantee=%s",
        (oid, oid),
    )
    expected = [("scanipy_accepted_inputs", True, "USAGE", False)]
    expected.extend(
        ("scanipy_accepted_inputs." + target[0], True, "EXECUTE", False)
        for target in migration().TARGETS
    )
    assert sorted(grants) == sorted(expected)


@pytest.mark.parametrize(
    "read", ("publication", "bundle", "event", "binding", "current", "recheck")
)
def test_six_actual_reads_with_explicit_effective_role(role_pg, read):
    ledger = SqlLedger(role_pg).activate().create().seal()
    ledger.authorize()
    binding, admission = current_inputs(ledger)
    with reader_transaction(ledger) as repository:
        if read == "publication":
            assert (
                repository.read_publication_receipt(
                    publication_key=UUID(ledger.approval["publication_key"])
                )
                == ledger.publication.record_bytes
            )
        elif read == "bundle":
            expected = c.decode_record(ledger.expected, m.BundleExpectation, s.BUNDLE_EXPECTATION)
            assert repository.read_exact_bundle(expected) == ledger.bundle
        elif read == "event":
            raw, support = repository.read_authority_event(
                "policy",
                UUID(ledger.policy["event_id"]),
                c.domain_digest(s.POLICY, ledger.objects["current-policy"]),
            )
            assert raw == ledger.objects["current-policy"]
            assert support == (ledger.objects["current-policy-signature"],)
        elif read == "binding":
            assert (
                repository.read_request_binding(ledger.codebase, ledger.request_id)
                == ledger.sealed.record_bytes
            )
        else:
            prior = repository.read_execution_authority(binding, admission)
            assert prior[0].binding == binding and type(prior[1]) is bytes and prior[2]
    if read == "recheck":
        with reader_transaction(ledger) as repository:
            assert repository.recheck_execution_authority(binding, admission, *prior) is None


@pytest.mark.parametrize("changed", ("binding", "policy", "namespace"))
def test_current_read_does_not_gain_authority_from_role(role_pg, changed):
    ledger = SqlLedger(role_pg).activate().create().seal()
    ledger.authorize()
    binding, admission = current_inputs(ledger)
    with reader_transaction(ledger) as repository:
        prior = repository.read_execution_authority(binding, admission)
    if changed == "binding":
        binding = replace(binding, work_revision=binding.work_revision + 1)
    elif changed == "policy":
        ledger.rotate_grant("revoked")
    else:
        ledger.namespace = uuid4()
    with pytest.raises(s.VerificationError), reader_transaction(ledger) as repository:
        repository.recheck_execution_authority(binding, admission, *prior)


DENIED = (
    "SELECT * FROM scanipy_accepted_inputs.authority_events",
    "SELECT id FROM scanipy_accepted_inputs.authority_events",
    "INSERT INTO scanipy_accepted_inputs.registry_namespaces(id) VALUES(gen_random_uuid())",
    "UPDATE scanipy_accepted_inputs.registry_namespaces "
    "SET coordination_revision=coordination_revision",
    "DELETE FROM scanipy_accepted_inputs.authority_events",
    "TRUNCATE scanipy_accepted_inputs.authority_events",
    "CREATE TABLE scanipy_accepted_inputs.forbidden(id integer)",
    "SELECT scanipy_accepted_inputs.v1_work_begin(0)",
    "SELECT * FROM scanipy_accepted_inputs.initialize_registry_namespace_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.install_policy_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.record_admission_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.publish_builtin_bundle_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.create_bound_request_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.seal_bound_capture_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.authorize_detector_run_v1(NULL,NULL)",
    "SELECT * FROM scanipy_accepted_inputs.renew_authorized_execution_v1(NULL,NULL)",
    "SELECT * FROM scanipy_execution.lock_accepted_capture_context_v1(NULL,NULL,NULL,1,1)",
    "SELECT * FROM scanipy_execution.lock_accepted_detector_context_v1("
    "NULL,NULL,NULL,1,1,NULL,NULL)",
)


@pytest.mark.parametrize("statement", DENIED)
def test_effective_role_permission_denials_not_login_escape(role_pg, statement):
    ledger = SqlLedger(role_pg)
    with reader_transaction(ledger) as repository:
        with repository.connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(statement)
        assert captured.value.pgcode == "42501"


def test_populated_inverse_preserves_all_original_bytes_oids_acl_and_history(role_pg):
    ledger = SqlLedger(role_pg).activate().create().seal()
    ledger.authorize()
    before, records = catalog(role_pg), history(ledger)
    old_oid = role_pg.owned_roles[EXECUTION_READER]
    role_pg.migrate("20260926_0007", action="downgrade")
    assert EXECUTION_READER not in role_pg.owned_roles
    assert catalog(role_pg) == before and history(ledger) == records
    role_pg.migrate("20260926_0008")
    assert role_pg.owned_roles[EXECUTION_READER] != old_oid
    assert catalog(role_pg) == before and history(ledger) == records


DRIFTS = (
    "ALTER ROLE scanipy_accepted_execution_reader LOGIN",
    "ALTER ROLE scanipy_accepted_execution_reader INHERIT",
    "ALTER ROLE scanipy_accepted_execution_reader SUPERUSER",
    "ALTER ROLE scanipy_accepted_execution_reader CREATEDB",
    "ALTER ROLE scanipy_accepted_execution_reader CREATEROLE",
    "ALTER ROLE scanipy_accepted_execution_reader REPLICATION",
    "ALTER ROLE scanipy_accepted_execution_reader BYPASSRLS",
    "ALTER ROLE scanipy_accepted_execution_reader CONNECTION LIMIT 1",
    "ALTER ROLE scanipy_accepted_execution_reader VALID UNTIL '2099-01-01'",
    "ALTER ROLE scanipy_accepted_execution_reader SET statement_timeout='1s'",
    "COMMENT ON ROLE scanipy_accepted_execution_reader IS 'controlled foreign metadata'",
    "GRANT scanipy_accepted_execution_reader TO scanipy_accepted_reader",
    "GRANT scanipy_accepted_reader TO scanipy_accepted_execution_reader",
    "GRANT USAGE ON SCHEMA scanipy_execution TO scanipy_accepted_execution_reader",
    "GRANT USAGE ON SCHEMA scanipy_execution TO PUBLIC",
    "GRANT CREATE ON SCHEMA scanipy_accepted_inputs TO scanipy_accepted_execution_reader",
    "GRANT SELECT ON scanipy_accepted_inputs.authority_events TO scanipy_accepted_execution_reader",
    "GRANT SELECT(id) ON scanipy_accepted_inputs.authority_events "
    "TO scanipy_accepted_execution_reader",
    "ALTER TABLE scanipy_accepted_inputs.authority_events "
    "OWNER TO scanipy_accepted_execution_reader",
    "GRANT EXECUTE ON FUNCTION scanipy_accepted_inputs.v1_work_begin(bigint,bigint,bigint) "
    "TO PUBLIC",
    "GRANT EXECUTE ON FUNCTION scanipy_accepted_inputs.v1_work_begin(bigint,bigint,bigint) "
    "TO scanipy_accepted_execution_reader",
    "GRANT EXECUTE ON FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(uuid,uuid,uuid) "
    "TO scanipy_accepted_execution_reader WITH GRANT OPTION",
    "ALTER FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(uuid,uuid,uuid) COST 2",
    "ALTER FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(uuid,uuid,uuid) "
    "SET statement_timeout='1s'",
    "ALTER FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(uuid,uuid,uuid) "
    "OWNER TO scanipy_accepted_reader",
    "ALTER FUNCTION scanipy_accepted_inputs.read_publication_receipt_v1(uuid,uuid,uuid) "
    "RENAME TO controlled_wrong_name",
    "ALTER SCHEMA scanipy_accepted_inputs OWNER TO scanipy_accepted_reader",
    "UPDATE public.alembic_version SET version_num='20260926_0006'",
)


@pytest.mark.parametrize("statement", DRIFTS)
def test_actual_inverse_guard_rejects_rolled_back_foreign_state(role_pg, statement):
    before, identity = catalog(role_pg), role_pg._reader_state()
    with role_pg.admin() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout='15s'")
                cursor.execute("SET LOCAL lock_timeout='2s'")
                cursor.execute("SET LOCAL search_path='public,pg_catalog'")
                cursor.execute(statement)
                cursor.execute("SHOW search_path")
                path = cursor.fetchone()
                cursor.execute("SAVEPOINT reader_guard")
                with pytest.raises(psycopg2.Error) as captured:
                    cursor.execute(migration()._migration_sql(forward=False))
                assert captured.value.pgcode == "P0001"
                cursor.execute("ROLLBACK TO SAVEPOINT reader_guard")
                cursor.execute("SHOW search_path")
                assert cursor.fetchone() == path
        finally:
            connection.rollback()
    assert catalog(role_pg) == before and role_pg._reader_state() == identity


@pytest.mark.parametrize("fault", ("collision", "body", "superuser", "predecessor"))
def test_actual_forward_guard_and_transaction_rollback(role_pg, fault):
    before, identity = catalog(role_pg), role_pg._reader_state()
    owner = migration()
    with role_pg.admin() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout='15s'")
                cursor.execute("SET LOCAL lock_timeout='2s'")
                cursor.execute(owner._migration_sql(forward=False))
                cursor.execute("UPDATE public.alembic_version SET version_num='20260926_0007'")
                if fault == "collision":
                    cursor.execute("CREATE ROLE scanipy_accepted_execution_reader NOLOGIN")
                elif fault == "body":
                    definition = original_definition(0).replace(
                        "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
                    )
                    assert definition.count("DECLARE namespace jsonb;") == 1
                    cursor.execute(
                        definition.replace(
                            "DECLARE namespace jsonb;",
                            "DECLARE /* controlled drift */ namespace jsonb;",
                            1,
                        )
                    )
                elif fault == "superuser":
                    cursor.execute("SET LOCAL ROLE scanipy_accepted_owner")
                else:
                    cursor.execute("UPDATE public.alembic_version SET version_num='20260926_0006'")
                with pytest.raises(psycopg2.Error) as captured:
                    cursor.execute(owner._migration_sql(forward=True))
                assert captured.value.pgcode == "P0001"
        finally:
            connection.rollback()
    assert catalog(role_pg) == before and role_pg._reader_state() == identity


def test_successful_owner_do_restores_search_path_and_rollback_restores_original_role(role_pg):
    before, identity = catalog(role_pg), role_pg._reader_state()
    with role_pg.admin() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout='15s'")
                cursor.execute("SET LOCAL lock_timeout='2s'")
                cursor.execute("SET LOCAL search_path=public,pg_catalog")
                cursor.execute("SHOW search_path")
                path = cursor.fetchone()
                cursor.execute(migration()._migration_sql(forward=False))
                cursor.execute("SHOW search_path")
                assert cursor.fetchone() == path
                cursor.execute("UPDATE public.alembic_version SET version_num='20260926_0007'")
                cursor.execute(migration()._migration_sql(forward=True))
                cursor.execute("SHOW search_path")
                assert cursor.fetchone() == path
        finally:
            connection.rollback()
    assert catalog(role_pg) == before and role_pg._reader_state() == identity


@contextmanager
def probe_connection(pg, name):
    assert pg._reader_probe_database[0] == name
    connection = None
    try:
        connection = psycopg2.connect(**{**pg.base, "dbname": name})
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout='15s'")
                cursor.execute("SET LOCAL lock_timeout='2s'")
            yield connection
    finally:
        if connection is not None:
            connection.close()


def test_committed_sidecar_dependency_refuses_alembic_inverse_without_adoption(role_pg):
    before, identity = catalog(role_pg), role_pg._reader_state()
    name = role_pg._create_reader_probe_database()
    try:
        with probe_connection(role_pg, name) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA reader_probe")
                cursor.execute(
                    "GRANT USAGE ON SCHEMA reader_probe TO scanipy_accepted_execution_reader"
                )
        failed = role_pg.migrate("20260926_0007", action="downgrade", expect_success=False)
        assert "execution reader foreign dependency" in failed.stderr
        assert catalog(role_pg) == before and role_pg._reader_state() == identity
        with probe_connection(role_pg, name) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "REVOKE USAGE ON SCHEMA reader_probe FROM scanipy_accepted_execution_reader"
                )
    finally:
        role_pg._drop_reader_probe_database()
    assert catalog(role_pg) == before and role_pg._reader_state() == identity

"""Restricted-role AL controls on the separately opted-in disposable cluster."""

from __future__ import annotations

from uuid import UUID, uuid4

import psycopg2
import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs.ledger_repository import AcceptedLedgerRepository
from tests import accepted_input_fixtures as af
from tests import occurrence_store_fixtures as of
from tests.integration.test_accepted_ledger_sql import SqlLedger

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.occurrence_store_postgres"]


@pytest.mark.parametrize("role", ("policy_admin", "publisher", "resolver", "reader"))
@pytest.mark.parametrize(
    "statement",
    (
        "SELECT * FROM scanipy_accepted_inputs.authority_events",
        "INSERT INTO scanipy_accepted_inputs.registry_namespaces(id) VALUES(gen_random_uuid())",
        "UPDATE scanipy_accepted_inputs.registry_namespaces "
        "SET coordination_revision=coordination_revision",
        "DELETE FROM scanipy_accepted_inputs.authority_events",
        "TRUNCATE scanipy_accepted_inputs.authority_events",
        "CREATE TABLE scanipy_accepted_inputs.forbidden(id integer)",
        "SET ROLE scanipy_accepted_owner",
        "SET ROLE scanipy_exec_owner",
        "SELECT scanipy_accepted_inputs.v1_work_begin(0)",
    ),
)
def test_restricted_roles_cannot_bypass_function_fence(accepted_ledger_pg, role, statement):
    with accepted_ledger_pg.connection("accepted_" + role) as connection:
        with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(statement)
        assert captured.value.pgcode == "42501"
        connection.rollback()


@pytest.mark.parametrize("role", ("policy_admin", "publisher", "resolver", "reader"))
def test_runtime_roles_cannot_install_namespaces(accepted_ledger_pg, role):
    with accepted_ledger_pg.connection("accepted_" + role) as connection:
        with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.initialize_registry_namespace_v1(%s,%s)",
                (str(uuid4()), b"{}"),
            )
        assert captured.value.pgcode == "42501"
        connection.rollback()


def test_hostile_default_acl_grantee_gets_no_new_schema_table_or_private_function_rights(
    accepted_ledger_pg,
):
    pg = accepted_ledger_pg
    assert pg.rows(
        "SELECT count(*) FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a "
        "WHERE n.nspname='scanipy_accepted_inputs' AND a.grantee IN "
        "(0,(SELECT oid FROM pg_roles WHERE rolname=%s))",
        (pg.hostile,),
    ) == [(0,)]
    assert pg.rows(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE n.nspname='scanipy_accepted_inputs' "
        "AND a.grantee IN (0,(SELECT oid FROM pg_roles WHERE rolname=%s))",
        (pg.hostile,),
    ) == [(0,)]
    assert pg.rows(
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE n.nspname='scanipy_accepted_inputs' "
        "AND a.grantee IN (0,(SELECT oid FROM pg_roles WHERE rolname=%s))",
        (pg.hostile,),
    ) == [(0,)]


def test_all_five_tables_are_forced_rls_and_owner_has_no_administrative_role_flags(
    accepted_ledger_pg,
):
    pg = accepted_ledger_pg
    assert pg.rows(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='scanipy_accepted_inputs' AND c.relkind='r' "
        "AND c.relrowsecurity AND c.relforcerowsecurity"
    ) == [(5,)]
    assert pg.rows(
        "SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,"
        "rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname='scanipy_accepted_owner'"
    ) == [(False,) * 7]


def test_al_owner_has_exact_cross_owner_function_grants_but_no_table_rights(accepted_ledger_pg):
    pg = accepted_ledger_pg
    names = pg.rows(
        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='scanipy_execution' AND "
        "has_function_privilege('scanipy_accepted_owner',p.oid,'EXECUTE') ORDER BY p.proname"
    )
    assert names == [
        (name,)
        for name in sorted(
            (
                "create_request_v1",
                "register_capture_and_seal_v1",
                "begin_detector_run_v1",
                "renew_capture_detection_v1",
                "fail_detector_run_v1",
                "finish_capture_detection_v1",
                "lock_accepted_capture_context_v1",
                "lock_accepted_detector_context_v1",
            )
        )
    ]
    assert pg.rows(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='scanipy_execution' AND c.relkind='r' "
        "AND has_table_privilege('scanipy_accepted_owner',c.oid,"
        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES')"
    ) == [(0,)]


@pytest.mark.parametrize(
    "table", ("artifact_versions", "bundle_versions", "authority_events", "request_bundle_bindings")
)
def test_material_history_owner_noop_update_delete_and_truncate_are_refused(
    accepted_ledger_pg, table
):
    ledger = SqlLedger(accepted_ledger_pg).activate().create()
    # Identifiers are the closed parametrization above, never caller text.
    queries = (
        (
            "update",
            f"UPDATE scanipy_accepted_inputs.{table} "
            "SET namespace_id=namespace_id WHERE namespace_id=%s",
        ),
        ("delete", f"DELETE FROM scanipy_accepted_inputs.{table} WHERE namespace_id=%s"),
        ("truncate", f"TRUNCATE scanipy_accepted_inputs.{table}"),
    )
    external_referrers = {
        "bundle_versions": ("authority_events", "request_bundle_bindings"),
        "authority_events": ("registry_namespaces", "request_bundle_bindings"),
        "request_bundle_bindings": ("authority_events",),
    }
    for operation, query in queries:
        before = material_history_snapshot(accepted_ledger_pg, table, ledger.namespace)
        assert before
        with accepted_ledger_pg.admin() as connection:
            with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
                cursor.execute(query, (str(ledger.namespace),) if "%s" in query else ())
            if operation == "truncate" and table in external_referrers:
                # RESTRICT checks incoming foreign keys before firing this
                # table's guard. This is refusal evidence, not guard execution.
                assert captured.value.pgcode == "0A000"
                assert captured.value.diag.message_primary == (
                    "cannot truncate a table referenced in a foreign key constraint"
                )
                assert captured.value.diag.message_detail in tuple(
                    f'Table "{referrer}" references "{table}".'
                    for referrer in external_referrers[table]
                )
            else:
                assert captured.value.pgcode in ("55000", "P0001")
                assert "immutable accepted history" in str(captured.value)
            connection.rollback()
        assert material_history_snapshot(accepted_ledger_pg, table, ledger.namespace) == before


def material_history_snapshot(pg, table, namespace):
    keys = {
        "artifact_versions": "id",
        "bundle_versions": "id",
        "authority_events": "id",
        "request_bundle_bindings": "request_id",
    }
    # Complete logical rows, including bytea fields rendered as JSONB text:
    # never compare driver memoryview formats or only row counts/digests.
    return pg.rows(
        f"SELECT to_jsonb(h)::text FROM scanipy_accepted_inputs.{table} AS h "
        f"WHERE namespace_id=%s ORDER BY {keys[table]}",
        (str(namespace),),
    )


def test_all_truncate_guards_bind_exact_unconditional_runtime_function(accepted_ledger_pg):
    pg = accepted_ledger_pg
    assert pg.rows("SELECT current_setting('session_replication_role')") == [("origin",)]
    [guard] = pg.rows(
        "SELECT p.oid,l.lanname,p.prorettype='pg_catalog.trigger'::regtype,"
        "p.proconfig,p.prosrc FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang "
        "WHERE p.oid='scanipy_accepted_inputs.v1_immutable_history()'::regprocedure"
    )
    guard_oid, language, returns_trigger, configuration, body = guard
    assert (language, returns_trigger, configuration, body) == (
        "plpgsql",
        True,
        ["search_path=pg_catalog, scanipy_accepted_inputs, pg_temp"],
        "\nBEGIN\n  RAISE EXCEPTION 'immutable accepted history' USING ERRCODE='P0001';\nEND ",
    )
    actual = pg.rows(
        "SELECT c.relname,t.tgname,t.tgenabled,t.tgtype,t.tgisinternal,t.tgnargs,"
        "octet_length(t.tgargs),t.tgqual IS NULL,t.tgfoid "
        "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='scanipy_accepted_inputs' AND (t.tgtype & 32)<>0 "
        "ORDER BY c.relname,t.tgname"
    )
    # PG16 tgtype34 is BEFORE(2) | TRUNCATE(32), with no ROW/other-event bits.
    # This verifies every binding, not individual execution of FK-blocked ones.
    assert actual == [
        (
            table,
            "accepted_namespace_no_truncate"
            if table == "registry_namespaces"
            else "accepted_history_no_truncate",
            "O",
            34,
            False,
            0,
            0,
            True,
            guard_oid,
        )
        for table in (
            "artifact_versions",
            "authority_events",
            "bundle_versions",
            "registry_namespaces",
            "request_bundle_bindings",
        )
    ]


@pytest.mark.parametrize(
    "table", ("artifact_versions", "bundle_versions", "authority_events", "request_bundle_bindings")
)
def test_immutable_history_never_grants_owner_table_or_column_update(accepted_ledger_pg, table):
    assert accepted_ledger_pg.rows(
        "SELECT has_table_privilege('scanipy_accepted_owner',c.oid,'UPDATE'),"
        "bool_or(has_column_privilege('scanipy_accepted_owner',c.oid,a.attnum,'UPDATE')) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped "
        "WHERE n.nspname='scanipy_accepted_inputs' AND c.relname=%s GROUP BY c.oid",
        (table,),
    ) == [(False, False)]


def test_installer_replay_after_admission_does_not_reset_heads(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg).activate()
    with accepted_ledger_pg.admin() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE scanipy_accepted_owner")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        assert repository.initialize_registry_namespace(ledger.installed) == (
            ledger.namespace,
            True,
        )
        connection.commit()
    assert accepted_ledger_pg.rows(
        "SELECT coordination_revision,policy_revision,checkpoint_generation "
        "FROM scanipy_accepted_inputs.registry_namespaces WHERE id=%s",
        (str(ledger.namespace),),
    ) == [(2, 1, 1)]


def test_same_role_foreign_scope_cannot_read_exact_publication(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg).activate()
    publication_key = UUID(ledger.approval["publication_key"])
    with ledger.repo("reader") as repository:
        assert (
            repository.read_publication_receipt(publication_key=publication_key)
            == ledger.publication.record_bytes
        )
    with accepted_ledger_pg.connection("accepted_reader") as connection:
        repository = AcceptedLedgerRepository(connection, ledger.namespace, uuid4())
        with pytest.raises(s.VerificationError) as captured:
            repository.read_publication_receipt(publication_key=publication_key)
        assert captured.value.code == "scope-mismatch"
        connection.rollback()


def test_malformed_sql_commands_fail_before_any_namespace_or_authority_insert(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg)
    data = (
        b'{"schema":"scanipy-accepted-ledger-command/1",'
        b'"action":"install-policy","action":"install-policy"}'
    )
    with accepted_ledger_pg.connection("accepted_policy_admin") as connection:
        AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.install_policy_v1(%s,%s::bytea[])",
                (data, []),
            )
        assert captured.value.pgcode == "P0001"
        connection.rollback()
    assert accepted_ledger_pg.rows(
        "SELECT count(*) FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=%s",
        (str(ledger.namespace),),
    ) == [(0,)]


@pytest.mark.parametrize(
    "bucket,ceiling",
    (
        (0, 100000),
        (1, 134217728),
        (2, 100),
        (3, 200),
        (4, 536870912),
        (5, 300),
        (6, 2147483648),
        (7, 65536),
        (8, 100),
    ),
)
def test_sql_shared_work_meter_exact_limit_and_next_unit_have_no_refund(
    accepted_ledger_pg, bucket, ceiling
):
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(100,200,300)")
        cursor.execute("SELECT scanipy_accepted_inputs.v1_charge(%s,%s)", (bucket, ceiling))
        cursor.execute("SAVEPOINT work_boundary")
        with pytest.raises(psycopg2.Error) as captured:
            cursor.execute("SELECT scanipy_accepted_inputs.v1_charge(%s,1)", (bucket,))
        assert captured.value.pgcode == "P0001"
        cursor.execute("ROLLBACK TO SAVEPOINT work_boundary")
        cursor.execute(
            "SELECT current_setting('scanipy.accepted_work')::jsonb->'used'->>%s", (bucket,)
        )
        assert int(cursor.fetchone()[0]) == ceiling
        connection.rollback()


@pytest.mark.parametrize("helper", ("create", "register", "begin", "renew", "fail", "finish"))
def test_lower_reservation_charges_exact_approved_fixed_work_before_any_delegate(
    accepted_ledger_pg, helper
):
    a = 1048576
    o, h, small = 65536, 16384, 4096
    expected = {
        "create": (8 * a, 4 * a + 4 * h, 40 * a + 4 * h, 1),
        "register": (14 * a, 4 * a + 8 * h, 84 * a + 11 * h, 2),
        "begin": (78 * a + o, 5 * a + 8 * h, 61 * a + 9 * h, 5),
        "renew": (14 * a, 5 * a + 12 * h, 108 * a + 21 * h, 3),
        "fail": (23 * a + o, 11 * a + 17 * h, 192 * a + 4 * o + 26 * h, 6),
        "finish": (
            32 * a + 4 * o + small,
            12 * a + 24 * h,
            208 * a + 8 * o + 4 * small + 34 * h,
            8,
        ),
    }[helper]
    # A helper's fixed logical accounting can be checked without manufacturing
    # a lower state transition. These are actual SQL counters, not RSS claims.
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(150994944,167772160)")
        cursor.execute(
            "SELECT scanipy_accepted_inputs.v1_lower_reserve(%s,%s::bytea[],0,0)",
            (
                helper,
                [b"{}"]
                * (
                    2
                    if helper == "create"
                    else 3
                    if helper == "register"
                    else 0
                    if helper == "renew"
                    else 1
                ),
            ),
        )
        cursor.execute("SELECT current_setting('scanipy.accepted_work')::jsonb->'used'")
        used = cursor.fetchone()[0]
        raw, scalar, images, tickets = expected
        assert used[2] == raw and used[3] == scalar + 64 * tickets * 65537
        assert used[4] == images and used[5] == tickets * 65537
        assert used[6] == 0 and used[7] == 0 and used[8] == 0
        connection.rollback()


def test_read_bridge_reserves_two_passes_without_resetting_prior_direct_work(accepted_ledger_pg):
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(5701632,8519808,131106)")
        cursor.execute("SELECT scanipy_accepted_inputs.v1_control(65536)")
        cursor.execute("SELECT scanipy_accepted_inputs.v1_read_bridge_reserve()")
        cursor.execute("SELECT current_setting('scanipy.accepted_work')::jsonb->'used'")
        used = cursor.fetchone()[0]
        assert used == [0, 0, 0, 8519808, 0, 131106, 0, 65536, 0]
        cursor.execute("SAVEPOINT already_reserved")
        with pytest.raises(psycopg2.Error):
            cursor.execute("SELECT scanipy_accepted_inputs.v1_read_bridge_reserve()")
        cursor.execute("ROLLBACK TO SAVEPOINT already_reserved")
        cursor.execute("SELECT current_setting('scanipy.accepted_work')::jsonb->'used'")
        assert cursor.fetchone()[0] == used
        connection.rollback()


@pytest.mark.parametrize(
    "schema,key",
    (
        (s.POLICY, "current-policy"),
        (s.ADMISSION, "admission-checkpoint"),
        (s.APPROVAL, "approval-statement"),
    ),
)
def test_sql_document_codec_matches_actual_owner_canonical_bytes(accepted_ledger_pg, schema, key):
    ledger = SqlLedger(accepted_ledger_pg)
    raw = ledger.objects[key]
    expected = c.decode_document(raw, schema)
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_document(%s,%s)", (raw, schema))
        assert cursor.fetchone()[0] == expected
        cursor.execute(
            "SELECT scanipy_accepted_inputs.v1_bytes(scanipy_accepted_inputs.v1_document(%s,%s))",
            (raw, schema),
        )
        assert bytes(cursor.fetchone()[0]) == raw


@pytest.mark.parametrize(
    "raw",
    (
        b'{"x":1,"x":2}',
        b'{"x":1.0}',
        b'{"x":true,"extra":0}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\u0000"}',
        b'{"x":"\\ud800"}',
        b'{"x": 1}',
        b'{"x":NaN}',
        b'{"x":1} trailing',
        b"[" * 33 + b"0" + b"]" * 33,
    ),
)
def test_sql_wire_negative_vectors_fail_closed_before_owner_record_use(accepted_ledger_pg, raw):
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        with pytest.raises(psycopg2.Error):
            cursor.execute(
                "SELECT scanipy_accepted_inputs.v1_document(%s,'scanipy-accepted-trust-policy/1')",
                (raw,),
            )
        connection.rollback()


def test_complete_sql_bundle_matches_actual_owner_and_rejects_last_raw_mismatch(accepted_ledger_pg):
    bundle = af.bundle_fixture()
    expected = c.accepted_content_digest(bundle)
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(1048576,167772160)")
        cursor.execute(
            "SELECT content_digest FROM "
            "scanipy_accepted_inputs.v1_bundle(%s,%s::bytea[],%s::bytea[])",
            (bundle.spec_bytes, list(bundle.detector_blobs), list(bundle.rule_blobs)),
        )
        assert bytes(cursor.fetchone()[0]).hex() == expected
        cursor.execute("SAVEPOINT late_invalid_rule")
        with pytest.raises(psycopg2.Error):
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.v1_bundle(%s,%s::bytea[],%s::bytea[])",
                (bundle.spec_bytes, list(bundle.detector_blobs), [*bundle.rule_blobs[:-1], b"{}"]),
            )
        cursor.execute("ROLLBACK TO SAVEPOINT late_invalid_rule")
        connection.rollback()


def test_wide_original_occurrence_domain_rejects_as_unsupported_work_not_new_20k_schema(
    accepted_ledger_pg,
):
    value = of.invocation().value
    value["argv"] = ["x"] * 30000
    raw = of.envelope(
        "run-input", **{key: item for key, item in value.items() if key != "schema"}
    ).data
    assert len(raw) < 1048576
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT scanipy_accepted_inputs.v1_occurrence(%s,'scanipy-execution/run-input/1')",
            (raw,),
        )
        assert len(cursor.fetchone()[0]["argv"]) == 30000
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(150994944,167772160)")
        with pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT scanipy_accepted_inputs.v1_lower_preflight('begin',ARRAY[%s]::bytea[])",
                (raw,),
            )
        assert captured.value.pgcode == "P0001"
        connection.rollback()


def test_old_sql_definitions_and_configs_remain_exact_after_new_calls(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg).activate().create().seal()
    ledger.authorize()
    assert accepted_ledger_pg._execution_definitions() == accepted_ledger_pg.execution_definitions


@pytest.mark.parametrize("kind", ("execution-authorization", "seal-authorization"))
def test_malformed_stored_authority_is_content_mismatch_not_input_error(accepted_ledger_pg, kind):
    from services.scan.accepted_inputs import models as m
    from tests.integration.test_accepted_ledger_sql import execution_binding

    ledger = SqlLedger(accepted_ledger_pg).activate().create().seal()
    ledger.authorize()
    binding = execution_binding(ledger.authorization.record_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        # Controlled corruption inside one rolled-back privileged test
        # transaction. No production mutation capability is being granted.
        cursor.execute("ALTER TABLE scanipy_accepted_inputs.authority_events DISABLE TRIGGER USER")
        cursor.execute(
            "UPDATE scanipy_accepted_inputs.authority_events SET record_bytes='{'::bytea "
            "WHERE namespace_id=%s AND kind=%s",
            (str(ledger.namespace), kind),
        )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            repository.read_execution_authority(binding, admission)
        assert captured.value.code == "content-mismatch"
        connection.rollback()


def test_malformed_stored_sealed_frame_is_content_mismatch(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg).activate().create()
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE scanipy_accepted_inputs.request_bundle_bindings DISABLE TRIGGER USER"
        )
        cursor.execute(
            "UPDATE scanipy_accepted_inputs.request_bundle_bindings "
            "SET sealed_bytes='{'::bytea,sealed_sha256=sha256('{'::bytea) "
            "WHERE namespace_id=%s AND request_id=%s",
            (str(ledger.namespace), str(ledger.request_id)),
        )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_reader")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            repository.read_request_binding(ledger.codebase, ledger.request_id)
        assert captured.value.code == "content-mismatch"
        connection.rollback()


@pytest.mark.parametrize("bucket,ceiling", ((0, 100000), (1, 134217728)))
@pytest.mark.parametrize("kind", ("frame", "bundle"))
def test_exhausted_hash_budget_inside_stored_wrapper_stays_invalid_input(
    accepted_ledger_pg, bucket, ceiling, kind
):
    ledger = SqlLedger(accepted_ledger_pg).activate().create()
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(1048576,167772160)")
        cursor.execute("SELECT scanipy_accepted_inputs.v1_charge(%s,%s)", (bucket, ceiling))
        cursor.execute(
            "SELECT set_config('scanipy.accepted_namespace_id',%s,true),"
            "set_config('app.org_id',%s,true)",
            (str(ledger.namespace), str(ledger.org)),
        )
        with pytest.raises(psycopg2.Error) as captured:
            if kind == "frame":
                cursor.execute(
                    "SELECT scanipy_accepted_inputs.v1_stored_frame("
                    "%s,'scanipy-sealed-acceptance/1')",
                    (ledger.sealed.record_bytes,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM scanipy_accepted_inputs.v1_stored_bundle("
                    "%s,%s::bytea[],%s::bytea[])",
                    (
                        ledger.bundle.spec_bytes,
                        list(ledger.bundle.detector_blobs),
                        list(ledger.bundle.rule_blobs),
                    ),
                )
        assert captured.value.pgcode == "P0001"
        assert captured.value.diag.message_primary == "invalid-input"
        assert captured.value.diag.message_detail == "accepted-work-limit"
        connection.rollback()


@pytest.mark.parametrize("bucket,ceiling", ((2, 1048576), (7, 65536)))
def test_stored_fetch_does_not_mask_cumulative_raw_or_control_exhaustion(
    accepted_ledger_pg, bucket, ceiling
):
    ledger = SqlLedger(accepted_ledger_pg).activate().create()
    with accepted_ledger_pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT scanipy_accepted_inputs.v1_work_begin(1048576,167772160)")
        cursor.execute(
            "SELECT set_config('scanipy.accepted_namespace_id',%s,true),"
            "set_config('app.org_id',%s,true)",
            (str(ledger.namespace), str(ledger.org)),
        )
        cursor.execute("SELECT scanipy_accepted_inputs.v1_namespace(%s)", (str(ledger.namespace),))
        namespace = cursor.fetchone()[0]
        cursor.execute(
            "SELECT current_setting('scanipy.accepted_work')::jsonb->'used'->>%s", (bucket,)
        )
        already = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT scanipy_accepted_inputs.v1_charge(%s,%s)", (bucket, ceiling - already)
        )
        with pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.v1_fetch_binding(%s::jsonb,%s)",
                (c.canonical_bytes(namespace).decode("utf-8"), str(ledger.request_id)),
            )
        assert captured.value.pgcode == "P0001"
        assert captured.value.diag.message_primary == "invalid-input"
        assert captured.value.diag.message_detail == "accepted-work-limit"
        connection.rollback()


def test_global_publication_is_historical_only_not_customer_execution_adoption(accepted_ledger_pg):
    from services.scan.accepted_inputs import models as m

    ledger = SqlLedger(accepted_ledger_pg, scope="global").activate()
    expected = c.decode_record(ledger.expected, m.BundleExpectation, s.BUNDLE_EXPECTATION)
    with ledger.repo("reader") as repository:
        assert repository.read_exact_bundle(expected) == ledger.bundle
    request = of.request_input(ledger.tenant_org, ledger.codebase)
    command = ledger.command(
        "create-bound-request",
        {
            "admission": ledger.admission,
            "bundle": ledger.expected,
            "approval_event_id": ledger.approval["event_id"],
            "verifier_artifact_digest": "4" * 64,
        },
        ("request", "planned-policy"),
        (request.request.data, request.planned_policy.data),
    )
    with ledger.pg.connection("accepted_resolver") as connection:
        AcceptedLedgerRepository(connection, ledger.namespace, None)
        with connection.cursor() as cursor, pytest.raises(psycopg2.Error) as captured:
            cursor.execute(
                "SELECT * FROM scanipy_accepted_inputs.create_bound_request_v1(%s,%s::bytea[])",
                (command[0], list(command[1])),
            )
        assert captured.value.pgcode in ("42501", "P0001")
        connection.rollback()
    assert ledger.pg.rows(
        "SELECT count(*) FROM scanipy_accepted_inputs.request_bundle_bindings "
        "WHERE namespace_id=%s",
        (str(ledger.namespace),),
    ) == [(0,)]


@pytest.mark.parametrize("role", ("planned-policy", "run-input", "seal-material"))
def test_canonical_retained_occurrence_change_cannot_match_original_lower_commitment(
    accepted_ledger_pg, role
):
    from services.scan.accepted_inputs import models as m
    from tests.integration.test_accepted_ledger_sql import execution_binding

    ledger = SqlLedger(accepted_ledger_pg).activate().create().seal()
    execution = ledger.authorize()
    binding = execution_binding(ledger.authorization.record_bytes)
    admission = c.decode_record(ledger.admission, m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    if role == "planned-policy":
        table, part_index = "request_bundle_bindings", 2
        raw = ledger.create_command[1][1]
        selector, target = "request_id", str(ledger.request_id)
    elif role == "run-input":
        table, part_index = "authority_events", 1
        raw = ledger.authorize_command[1][0]
        selector, target = "id", execution["event_id"]
    else:
        table, part_index = "authority_events", 1
        raw = ledger.seal_command[1][0]
        selector, target = "id", c.parse_json(ledger.seal_authorization.record_bytes)["event_id"]
    value = c.parse_json(raw)
    if role == "run-input":
        value["argv"].append("different-observed-input")
    else:
        value["bindings"][0]["tool_policy_digest"] = "f" * 64
    altered = of.envelope(
        "seal" if role == "seal-material" else role,
        **{key: item for key, item in value.items() if key != "schema"},
    ).data
    with ledger.pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE scanipy_accepted_inputs.{table} DISABLE TRIGGER USER")
        cursor.execute(
            f"UPDATE scanipy_accepted_inputs.{table} SET command_parts[{part_index}]=%s "
            f"WHERE namespace_id=%s AND {selector}=%s",
            (altered, str(ledger.namespace), target),
        )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            repository.read_execution_authority(binding, admission)
        assert captured.value.code == "content-mismatch"
        connection.rollback()


def test_historical_replay_malformed_original_result_uses_stored_error_classification(
    accepted_ledger_pg,
):
    ledger = SqlLedger(accepted_ledger_pg).activate().create()
    with ledger.pg.admin() as connection, connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE scanipy_accepted_inputs.request_bundle_bindings DISABLE TRIGGER USER"
        )
        cursor.execute(
            "UPDATE scanipy_accepted_inputs.request_bundle_bindings "
            "SET sealed_bytes='{'::bytea,sealed_sha256=sha256('{'::bytea) "
            "WHERE namespace_id=%s AND request_id=%s",
            (str(ledger.namespace), str(ledger.request_id)),
        )
        cursor.execute("SET LOCAL ROLE scanipy_accepted_resolver")
        repository = AcceptedLedgerRepository(connection, ledger.namespace, ledger.org)
        with pytest.raises(s.VerificationError) as captured:
            repository.create_bound_request(*ledger.create_command)
        assert captured.value.code == "content-mismatch"
        connection.rollback()


def test_raw_domain_hashes_remain_distinct_in_real_ledger(accepted_ledger_pg):
    ledger = SqlLedger(accepted_ledger_pg).activate().create().seal()
    document = ledger.authorize()
    domain = c.domain_digest(s.EXECUTION, ledger.authorization.record_bytes)
    raw = c.raw_digest(ledger.authorization.record_bytes)
    assert domain != raw
    assert accepted_ledger_pg.rows(
        "SELECT encode(record_digest,'hex'),encode(request_binding_digest,'hex') "
        "FROM scanipy_accepted_inputs.authority_events WHERE namespace_id=%s AND id=%s",
        (str(ledger.namespace), document["event_id"]),
    ) == [(domain, c.raw_digest(ledger.sealed.record_bytes))]

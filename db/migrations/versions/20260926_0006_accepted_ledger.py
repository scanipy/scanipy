"""Accepted ledger v1: five tables, seven writes, six reads, private installer.

The SQL and shape resources are frozen migration inputs. No runtime owner import,
operator key installation, external verifier or DB-BAR authority is performed.
"""

import re
from pathlib import Path

from alembic import op

revision = "20260926_0006"
down_revision = "20260925_0005"
branch_labels = None
depends_on = None

TABLES = (
    "registry_namespaces",
    "artifact_versions",
    "bundle_versions",
    "authority_events",
    "request_bundle_bindings",
)
ROLES = tuple(
    "scanipy_accepted_" + name
    for name in ("owner", "policy_admin", "publisher", "resolver", "reader")
)
LOWER_SIGNATURES = (
    "create_request_v1(uuid,uuid,bytea,bytea,bytea,bytea)",
    "register_capture_and_seal_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea,bytea,bytea,bytea,bytea,bytea,bytea[],bytea[],bytea)",
    "begin_detector_run_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)",
    "renew_capture_detection_v1(uuid,uuid,uuid,bigint,bigint)",
    "fail_detector_run_v1(uuid,uuid,uuid,bigint,bigint,uuid,bytea,bytea,bytea)",
    "finish_capture_detection_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)",
)
BRIDGE_SIGNATURES = (
    "lock_accepted_capture_context_v1(uuid,uuid,uuid,bigint,bigint)",
    "lock_accepted_detector_context_v1(uuid,uuid,uuid,bigint,bigint,uuid,uuid)",
)
MUTATIONS = {
    "policy_admin": ("install_policy_v1", "record_admission_v1"),
    "publisher": ("publish_builtin_bundle_v1",),
    "resolver": (
        "create_bound_request_v1",
        "seal_bound_capture_v1",
        "authorize_detector_run_v1",
        "renew_authorized_execution_v1",
    ),
}
READS = {
    "read_publication_receipt_v1(uuid,uuid,uuid)": ("publisher", "reader", "resolver"),
    "read_exact_bundle_v1(uuid,uuid,bytea)": ("reader", "resolver"),
    "read_authority_event_v1(uuid,text,uuid,bytea)": ("reader", "resolver"),
    "read_request_binding_v1(uuid,uuid,uuid,uuid)": ("reader", "resolver"),
    "read_execution_authority_v1(uuid,bytea,bytea)": ("resolver",),
    "recheck_execution_authority_v1(uuid,bytea,bytea,bytea,bytea,text)": ("resolver",),
}


def _resource(name: str) -> str:
    return Path(__file__).with_name(name).read_text(encoding="utf-8")


def _execute_literal(statement: str) -> None:
    """Escape Alembic's text-bind syntax, not the underlying PostgreSQL SQL.

    Its compiler removes this one added backslash per colon, preserving existing
    backslashes and casts. Percent handling remains with the dialect compiler.
    """
    op.execute(statement.replace(":", r"\:"))


def _bridges(template: str) -> tuple[str, str]:
    """Two fixed signatures, never a generic target/live selector on SQL wire."""
    common = template.replace("__BRIDGE_NAME__", "lock_accepted_capture_context_v1")
    capture = (
        common.replace("__TARGET_PARAMETERS__", "")
        .replace("__IS_DETECTOR__", "false")
        .replace(
            "__TARGET_CHECK__",
            "IF cardinality(active_ids)<>0 THEN "
            "RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001'; END IF;",
        )
        .replace("__CONSUMER_CHECK__", "")
        .replace("__TARGET_RESULT__", "")
    )
    detector = (
        template.replace("__BRIDGE_NAME__", "lock_accepted_detector_context_v1")
        .replace("__TARGET_PARAMETERS__", ",p_run uuid,p_lease uuid")
        .replace("__IS_DETECTOR__", "true")
        .replace(
            "__TARGET_CHECK__",
            """IF p_run IS NULL OR p_lease IS NULL OR cardinality(active_ids)<>1
              OR active_ids[1]<>p_run THEN
                RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
              END IF;
              SELECT id,org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,
                work_attempt_id,input_digest,state INTO d FROM scanipy_execution.detector_runs
                WHERE org_id=p_org AND id=p_run FOR UPDATE;
              IF NOT FOUND OR d.codebase_id<>r.codebase_id OR d.request_id<>request_key
                OR d.capture_id IS DISTINCT FROM capture_key OR d.seal_id IS DISTINCT FROM s.id
                OR d.work_item_id<>p_work OR d.work_attempt_id<>p_attempt
                OR d.state NOT IN ('pending','running') THEN
                RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001';
              END IF;""",
        )
        .replace(
            "__CONSUMER_CHECK__",
            "IF l.id<>p_lease THEN RAISE EXCEPTION 'fence-stale' USING ERRCODE='P0001'; END IF;",
        )
        .replace(
            "__TARGET_RESULT__",
            "result:=result||jsonb_build_object('detector_run_id',d.id,"
            "'run_input_digest',encode(d.input_digest,'hex'),'run_state',d.state);",
        )
    )
    return capture, detector


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF current_setting('server_encoding')<>'UTF8' OR
         current_setting('server_version_num')::integer<160000 THEN
        RAISE EXCEPTION 'accepted ledger requires PostgreSQL 16+ UTF8';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='scanipy_accepted_inputs') THEN
        RAISE EXCEPTION 'reserved accepted schema already exists';
      END IF;
    END $$""")
    # Check the complete reserved set before creating any role. Transactional
    # failure never establishes ownership of a racing/preexisting role.
    for role in ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles "  # noqa: S608 -- frozen role identifiers
            f"WHERE rolname='{role}') THEN RAISE EXCEPTION "
            "'reserved accepted role already exists'; END IF; END $$"
        )
    for role in ROLES:
        op.execute(
            f"CREATE ROLE {role} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
    op.execute("CREATE SCHEMA scanipy_accepted_inputs")
    registry = _resource("accepted_v1_shapes.json")
    _execute_literal(f"""CREATE FUNCTION scanipy_accepted_inputs.v1_shapes() RETURNS jsonb
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp
      AS $body$ SELECT $registry${registry}$registry$::jsonb $body$""")
    for filename in (
        "accepted_v1_validation.sql",
        "accepted_v1_tables.sql",
        "accepted_v1_history.sql",
        "accepted_v1_operations.sql",
        "accepted_v1_reads.sql",
    ):
        _execute_literal(_resource(filename))
    for bridge in _bridges(_resource("accepted_v1_execution_bridges.sql")):
        _execute_literal(bridge)
    # Scrub inherited/default privileges only on new objects; never execute the
    # old execution ACL resource against its now populated namespace.
    _execute_literal(_resource("accepted_v1_acl.sql"))
    op.execute("""DO $$ DECLARE f record; BEGIN
      FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='scanipy_accepted_inputs'
      LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO scanipy_accepted_owner',f.signature);
      END LOOP;
    END $$""")
    for signature in BRIDGE_SIGNATURES:
        op.execute(f"ALTER FUNCTION scanipy_execution.{signature} OWNER TO scanipy_exec_owner")
    for role in ROLES:
        op.execute(f"GRANT USAGE ON SCHEMA scanipy_accepted_inputs TO {role}")
    op.execute("GRANT USAGE ON SCHEMA scanipy_execution TO scanipy_accepted_owner")
    for signature in LOWER_SIGNATURES + BRIDGE_SIGNATURES:
        op.execute(
            f"GRANT EXECUTE ON FUNCTION scanipy_execution.{signature} TO scanipy_accepted_owner"
        )
    for table in TABLES:
        op.execute(f"ALTER TABLE scanipy_accepted_inputs.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE scanipy_accepted_inputs.{table} FORCE ROW LEVEL SECURITY")
        if table == "registry_namespaces":
            predicate = """id=NULLIF(current_setting('scanipy.accepted_namespace_id',true),'')::uuid
              AND ((scope='customer' AND org_id=NULLIF(current_setting('app.org_id',true),'')::uuid)
              OR (scope='global' AND org_id IS NULL AND current_setting('app.org_id',true)=''))"""
        else:
            extra = (
                f" AND n.org_id IS NOT DISTINCT FROM {table}.org_id"
                if table == "authority_events"
                else f" AND n.scope='customer' AND n.org_id={table}.org_id"
                if table == "request_bundle_bindings"
                else ""
            )
            predicate = (
                "namespace_id="  # noqa: S608 -- frozen table and RLS expression only
                "NULLIF(current_setting('scanipy.accepted_namespace_id',true),'')::uuid "
                "AND EXISTS(SELECT 1 FROM scanipy_accepted_inputs.registry_namespaces n "
                f"WHERE n.id={table}.namespace_id{extra})"
            )
        op.execute(
            f"CREATE POLICY accepted_scope ON scanipy_accepted_inputs.{table} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        rights = "SELECT,INSERT,UPDATE" if table == "registry_namespaces" else "SELECT,INSERT"
        op.execute(f"GRANT {rights} ON scanipy_accepted_inputs.{table} TO scanipy_accepted_owner")
    for role, names in MUTATIONS.items():
        for name in names:
            op.execute(
                f"GRANT EXECUTE ON FUNCTION scanipy_accepted_inputs.{name}(bytea,bytea[]) "
                f"TO scanipy_accepted_{role}"
            )
    for signature, roles in READS.items():
        for role in roles:
            op.execute(
                f"GRANT EXECUTE ON FUNCTION scanipy_accepted_inputs.{signature} "
                f"TO scanipy_accepted_{role}"
            )


def downgrade() -> None:
    op.execute("SET LOCAL row_security=off")
    functions = ["v1_shapes"]
    for filename in (
        "accepted_v1_validation.sql",
        "accepted_v1_history.sql",
        "accepted_v1_operations.sql",
        "accepted_v1_reads.sql",
    ):
        functions.extend(
            re.findall(
                r"CREATE FUNCTION scanipy_accepted_inputs\.([a-z0-9_]+)\(", _resource(filename)
            )
        )
    expected_functions = ",".join("'" + name + "'" for name in sorted(functions))
    expected_tables = ",".join("'" + name + "'" for name in sorted(TABLES))
    op.execute(f"""DO $$ BEGIN
      IF (SELECT array_agg(p.proname::text ORDER BY p.proname::text COLLATE "C")
          FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='scanipy_accepted_inputs') IS DISTINCT FROM
          ARRAY[{expected_functions}]::text[]
        OR (SELECT array_agg(c.relname::text ORDER BY c.relname::text COLLATE "C")
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname='scanipy_accepted_inputs' AND c.relkind IN ('r','p','v','m','f','S'))
          IS DISTINCT FROM ARRAY[{expected_tables}]::text[] THEN
        RAISE EXCEPTION 'unexpected objects in accepted namespace';
      END IF;
    END $$""")  # noqa: S608 -- regex-restricted migration identifiers and fixed tables
    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN IF EXISTS(SELECT 1 FROM scanipy_accepted_inputs.{table}) "  # noqa: S608 -- closed five-table inventory
            "THEN RAISE EXCEPTION 'cannot remove nonempty accepted history'; END IF; END $$"
        )
    # Refuse outside dependent FKs (e.g. a later barrier), never CASCADE them.
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM pg_catalog.pg_constraint fk
        JOIN pg_catalog.pg_class target ON target.oid=fk.confrelid
        JOIN pg_catalog.pg_namespace target_ns ON target_ns.oid=target.relnamespace
        JOIN pg_catalog.pg_class source ON source.oid=fk.conrelid
        JOIN pg_catalog.pg_namespace source_ns ON source_ns.oid=source.relnamespace
        WHERE fk.contype='f' AND target_ns.nspname='scanipy_accepted_inputs'
          AND source_ns.nspname<>'scanipy_accepted_inputs') THEN
        RAISE EXCEPTION 'accepted history has external dependents';
      END IF;
    END $$""")
    for signature in LOWER_SIGNATURES:
        op.execute(
            f"REVOKE EXECUTE ON FUNCTION scanipy_execution.{signature} FROM scanipy_accepted_owner"
        )
    for signature in BRIDGE_SIGNATURES:
        op.execute(f"DROP FUNCTION scanipy_execution.{signature}")
    # Break only internal new-table FK cycles before explicit no-CASCADE drops.
    op.execute("""DO $$ DECLARE fk record; BEGIN
      FOR fk IN SELECT c.conname,t.relname FROM pg_catalog.pg_constraint c
        JOIN pg_catalog.pg_class t ON t.oid=c.conrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='scanipy_accepted_inputs' AND c.contype='f'
      LOOP
        EXECUTE format('ALTER TABLE scanipy_accepted_inputs.%I DROP CONSTRAINT %I',
          fk.relname,fk.conname);
      END LOOP;
    END $$""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE scanipy_accepted_inputs.{table}")
    op.execute(
        "ALTER TABLE scanipy_execution.detector_runs DROP CONSTRAINT accepted_detector_scope_key"
    )
    op.execute(
        "ALTER TABLE scanipy_execution.capture_leases DROP CONSTRAINT accepted_consumer_scope_key"
    )
    op.execute("""DO $$ DECLARE f record; BEGIN
      FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='scanipy_accepted_inputs'
      LOOP EXECUTE format('DROP FUNCTION %s',f.signature); END LOOP;
    END $$""")
    op.execute("DROP SCHEMA scanipy_accepted_inputs")
    op.execute("REVOKE USAGE ON SCHEMA scanipy_execution FROM scanipy_accepted_owner")
    for role in reversed(ROLES):
        op.execute(f"DROP ROLE {role}")

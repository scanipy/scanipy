"""Occurrence protocol v1: roles, forced RLS, function-only mutation boundary.

Frozen SQL/shape resources belong to this migration version, not runtime imports.
"""

from pathlib import Path

from alembic import op

revision = "20260925_0005"
down_revision = "20260925_0004"
branch_labels = None
depends_on = None

TABLES = (
    "scan_requests",
    "source_captures",
    "scan_seals",
    "work_items",
    "work_attempts",
    "detector_runs",
    "detection_occurrences",
    "capture_leases",
)
ROLES = tuple(
    "scanipy_exec_" + suffix
    for suffix in ("owner", "request", "detector", "identity", "cleanup", "read")
)
DIRECT = {
    "request": [
        "create_request_v1(uuid,uuid,bytea,bytea,bytea,bytea)",
        "cancel_request_v1(uuid,uuid,bigint,bytea,bytea)",
    ],
    "detector": [
        "register_capture_and_seal_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea,bytea,bytea,bytea,bytea,bytea,bytea[],bytea[],bytea)",
        "begin_detector_run_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)",
        "retain_detection_batch_v1(uuid,uuid,uuid,bigint,bigint,uuid,bytea,bytea,bytea,bytea,bytea[],bytea[])",
        "fail_detector_run_v1(uuid,uuid,uuid,bigint,bigint,uuid,bytea,bytea,bytea)",
    ],
    "cleanup": [
        "claim_retirement_v1(uuid,uuid,bigint)",
        "finish_retirement_v1(uuid,uuid,bigint,bytea,bytea)",
    ],
}


def _wrapper(name: str, params: str, body: str, role: str) -> None:
    op.execute(f"""CREATE FUNCTION scanipy_execution.{name}({params}) RETURNS jsonb
      LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,scanipy_execution,pg_temp
      AS $$ SELECT {body} $$""")
    signature = ",".join(item.strip().split(" ", 1)[1] for item in params.split(","))
    DIRECT.setdefault(role, []).append(f"{name}({signature})")


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF current_setting('server_encoding')<>'UTF8' THEN "
        "RAISE EXCEPTION 'execution envelopes require UTF8 database'; END "
        "IF; END $$"
    )
    for role in ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles "  # noqa: S608 -- fixed role constants
            f"WHERE rolname='{role}') THEN RAISE EXCEPTION "
            "'reserved execution role already exists'; END IF; END $$"
        )
        op.execute(
            f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB "
            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
    registry = Path(__file__).with_name("execution_v1_shapes.json").read_text(encoding="utf-8")
    op.execute(f"""CREATE FUNCTION scanipy_execution.v1_shapes() RETURNS jsonb
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp
      AS $body$ SELECT $registry${registry}$registry$::jsonb $body$""")
    for filename in ("execution_v1_validation.sql", "execution_v1_operations.sql"):
        op.execute(Path(__file__).with_name(filename).read_text(encoding="utf-8"))
    common = "p_org uuid,p_work uuid,p_attempt uuid,p_token bigint,p_revision bigint"
    values = "p_org,'{kind}',p_work,p_attempt,p_token,p_revision"
    for kind, role in (("capture_detection", "detector"), ("identity", "identity")):
        _wrapper(
            f"claim_{kind}_v1",
            "p_org uuid,p_work uuid,data bytea,digest bytea",
            f"scanipy_execution.v1_claim(p_org,'{kind}',p_work,data,digest)",
            role,
        )
        _wrapper(
            f"renew_{kind}_v1",
            common,
            f"scanipy_execution.v1_renew({values.format(kind=kind)})",
            role,
        )
        for action, expired in (("finish", "false"), ("expire", "true")):
            _wrapper(
                f"{action}_{kind}_v1",
                common + ",data bytea,digest bytea",
                f"scanipy_execution.v1_finish({values.format(kind=kind)},data,digest,{expired})",
                role,
            )
        for action in ("acquire", "renew", "release"):
            extra = ",data bytea,digest bytea" if action == "release" else ""
            evidence = "data,digest" if action == "release" else "NULL::bytea,NULL::bytea"
            _wrapper(
                f"{action}_{kind}_capture_lease_v1",
                common + extra,
                f"scanipy_execution.v1_capture_lease({values.format(kind=kind)},'{action}',{evidence})",
                role,
            )
    # Remove PUBLIC AND explicit non-PUBLIC default ACL grants on NEW objects.
    op.execute(Path(__file__).with_name("execution_v1_acl.sql").read_text(encoding="utf-8"))
    op.execute("""DO $$ DECLARE f record; BEGIN
      FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='scanipy_execution' AND p.proname<>'immutable_history_guard'
      LOOP EXECUTE format('ALTER FUNCTION %s OWNER TO scanipy_exec_owner',f.signature); END LOOP;
    END $$""")
    for role in ROLES:
        op.execute(f"GRANT USAGE ON SCHEMA scanipy_execution TO {role}")
    for table in TABLES:
        op.execute(f"ALTER TABLE scanipy_execution.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE scanipy_execution.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY execution_tenant ON scanipy_execution.{table}
          USING (org_id=NULLIF(pg_catalog.current_setting('app.org_id',true),'')::uuid)
          WITH CHECK (org_id=NULLIF(pg_catalog.current_setting('app.org_id',true),'')::uuid)""")
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON scanipy_execution.{table} TO scanipy_exec_owner")
        op.execute(
            f"GRANT SELECT ON scanipy_execution.{table} "
            "TO scanipy_exec_read,scanipy_exec_detector,scanipy_exec_identity"
        )
    for role in ("request", "cleanup"):
        for table in (
            "scan_requests",
            "source_captures",
            "work_items",
            "work_attempts",
            "capture_leases",
        ):
            op.execute(f"GRANT SELECT ON scanipy_execution.{table} TO scanipy_exec_{role}")
    for role, signatures in DIRECT.items():
        for signature in set(signatures):
            op.execute(
                f"GRANT EXECUTE ON FUNCTION scanipy_execution.{signature} TO scanipy_exec_{role}"
            )


def downgrade() -> None:
    op.execute("SET LOCAL row_security=off")
    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN IF EXISTS(SELECT 1 FROM scanipy_execution.{table}) "  # noqa: S608 -- fixed migration identifiers
            "THEN RAISE EXCEPTION 'cannot remove security from nonempty execution history'; "
            "END IF; END $$"
        )
    op.execute("""DO $$ DECLARE f record; BEGIN
      FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='scanipy_execution' AND p.proname<>'immutable_history_guard'
      LOOP EXECUTE format('DROP FUNCTION %s',f.signature); END LOOP;
    END $$""")
    for table in TABLES:
        op.execute(f"DROP POLICY execution_tenant ON scanipy_execution.{table}")
        op.execute(f"ALTER TABLE scanipy_execution.{table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE scanipy_execution.{table} DISABLE ROW LEVEL SECURITY")
    for role in ROLES:
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA scanipy_execution FROM {role}")
        op.execute(f"REVOKE ALL ON SCHEMA scanipy_execution FROM {role}")
        op.execute(f"DROP ROLE {role}")

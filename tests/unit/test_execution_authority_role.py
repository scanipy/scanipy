"""Role-only migration structure and real offline codecs, never live PostgreSQL.

SQL guards below are checked as generated source, not simulated catalog results.
Actual role/ACL/dependency/transaction behavior needs the separately granted PG lane.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import re
from io import StringIO
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "db/migrations/versions"
ROLE = "scanipy_accepted_execution_reader"
SCHEMA = "scanipy_accepted_inputs"
SIGNATURES = (
    "read_publication_receipt_v1(uuid,uuid,uuid)",
    "read_exact_bundle_v1(uuid,uuid,bytea)",
    "read_authority_event_v1(uuid,text,uuid,bytea)",
    "read_request_binding_v1(uuid,uuid,uuid,uuid)",
    "read_execution_authority_v1(uuid,bytea,bytea)",
    "recheck_execution_authority_v1(uuid,bytea,bytea,bytea,bytea,text)",
)


def migration():
    spec = importlib.util.spec_from_file_location(
        "execution_reader_role_migration", VERSIONS / "20260926_0008_execution_reader.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def original_definition(index):
    if index in (0, 2):
        name = "UPDATED_R1" if index == 0 else "UPDATED_R3"
        source = ast.parse((VERSIONS / "20260926_0007_accepted_read_outcomes.py").read_text())
        for node in source.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in node.targets
            ):
                return ast.literal_eval(node.value)
        raise AssertionError(name)
    source = (VERSIONS / "accepted_v1_reads.sql").read_text()
    name = SIGNATURES[index].split("(", 1)[0]
    start = source.index("CREATE FUNCTION " + SCHEMA + "." + name + "(")
    return source[start : source.index("$$;", start) + 3]


def ddl(sql):
    return [
        match.replace("''", "'")
        for match in re.findall(r"^\s*EXECUTE '((?:[^']|'')*)';", sql, re.MULTILINE)
    ]


def test_exact_migration_identity_and_no_other_target():
    m = migration()
    assert (m.revision, m.down_revision, m.branch_labels, m.depends_on) == (
        "20260926_0008",
        "20260926_0007",
        None,
        None,
    )
    assert (m.ROLE, m.SCHEMA) == (ROLE, SCHEMA)
    assert tuple(item[0] for item in m.TARGETS) == SIGNATURES
    assert len(set(SIGNATURES)) == 6


@pytest.mark.parametrize(
    ("path", "digest"),
    (
        (
            "accepted_v1_reads.sql",
            # Public frozen source identity, not credential material.
            # pragma: allowlist nextline secret
            "c7cead1435acf3f2c35c7a24979f10bcf964809b890c17fdac2ed2ff09340e18",
        ),
        (
            "20260926_0007_accepted_read_outcomes.py",
            # pragma: allowlist nextline secret
            "804fc7a047cb1006eca0b0c93382aa4c6b57110dcdf88253d95d0b03f4b62f3a",
        ),
    ),
)
def test_original_owning_resources_are_frozen(path, digest):
    assert hashlib.sha256((VERSIONS / path).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("index", range(6))
def test_exact_owner_body_and_declaration_not_reconstructed(index):
    m = migration()
    signature, inputs, outputs, names, result, retset, body = m.TARGETS[index]
    original = original_definition(index)
    assert original.split(" AS $$", 1)[1].removesuffix("$$;") == body
    match = re.search(r"FUNCTION [^(]+\((.*?)\)\s*RETURNS", original, re.DOTALL)
    assert match
    parameters = [tuple(item.split()) for item in match.group(1).split(",")]
    assert tuple(item[1] for item in parameters) == inputs
    assert tuple(item[0] for item in parameters) == names[: len(inputs)]
    assert signature == signature.split("(", 1)[0] + "(" + ",".join(inputs) + ")"
    if retset:
        match = re.search(r"RETURNS TABLE\((.*?)\)", original, re.DOTALL)
        assert match
        fields = [tuple(item.split()) for item in match.group(1).split(",")]
        assert tuple(item[1] for item in fields) == outputs
        assert tuple(item[0] for item in fields) == names[len(inputs) :]
        assert result == (outputs[0] if len(outputs) == 1 else "record")
    else:
        assert outputs == () and result == "void" and "RETURNS void" in original
    assert "LANGUAGE plpgsql SECURITY DEFINER" in original
    assert "SET search_path=pg_catalog,scanipy_accepted_inputs,pg_temp" in original
    assert "SET bytea_output='hex'" in original


@pytest.mark.parametrize("index", range(6))
def test_body_delimiters_and_expected_properties_are_fixed_per_target(index):
    m = migration()
    guard = m._function_guard(index, remember=True)
    label = f"$ear_body_{index}$"
    assert label not in m.TARGETS[index][-1]
    assert guard.count(label) == 2
    assert f"f.prosrc IS DISTINCT FROM {label}{m.TARGETS[index][-1]}{label}" in guard
    assert f"f.pronargs<>{len(m.TARGETS[index][1])}" in guard
    assert f"f.prorows<>{1000 if m.TARGETS[index][5] else 0}" in guard
    assert "target_oids:=array_append(target_oids,f.oid);" in guard
    assert f"f.oid IS DISTINCT FROM target_oids[{index + 1}]" in m._function_guard(
        index, remember=False
    )


@pytest.mark.parametrize(
    "property_name",
    (
        "oid",
        "proowner",
        "pronamespace",
        "prolang",
        "prokind",
        "prosecdef",
        "proleakproof",
        "proisstrict",
        "proretset",
        "provolatile",
        "proparallel",
        "procost",
        "prorows",
        "prosupport",
        "pronargs",
        "pronargdefaults",
        "provariadic",
        "proargdefaults",
        "protrftypes",
        "probin",
        "prosqlbody",
        "proargtypes",
        "proallargtypes",
        "proargmodes",
        "proargnames",
        "prorettype",
        "proconfig",
        "prosrc",
        "proacl",
    ),
)
def test_each_function_property_is_admitted_or_snapshot_preserved(property_name):
    m = migration()
    for index in range(6):
        assert "f." + property_name in m._function_guard(index, remember=True)


@pytest.mark.parametrize("forward", (True, False))
def test_all_six_targets_and_two_schemas_checked_before_first_ddl(forward):
    m = migration()
    sql = m._migration_sql(forward=forward)
    first = sql.index("EXECUTE '")
    before, after = sql[:first], sql[first:]
    assert before.count("execution reader target missing") == 6
    assert before.count("execution reader target drift") == 6
    assert "jsonb_array_length(before_objects)<>8" in before
    assert "jsonb_array_length(after_objects)<>8" in after
    assert after.count("execution reader target identity changed") == 6
    for index in range(6):
        assert m._function_guard(index, remember=True) in before
        assert m._function_guard(index, remember=False) in after
    assert "IF after_objects IS DISTINCT FROM before_objects THEN" in after


@pytest.mark.parametrize("forward", (True, False))
def test_fixed_predecessor_server_superuser_and_closed_schema_preflight(forward):
    sql = migration()._migration_sql(forward=forward)
    first = sql.index("EXECUTE '")
    before = sql[:first]
    predecessor = "20260926_0007" if forward else "20260926_0008"
    assert f"ARRAY['{predecessor}']::text[]" in before
    for guard in (
        "ORDER BY version_num LIMIT 2",
        "server_encoding')<>'UTF8'",
        "NOT BETWEEN 160000 AND 169999",
        "standard_conforming_strings')<>'on'",
        "rolname=current_user AND rolsuper",
        "accepted_schema_oid IS NULL",
        "execution_schema_oid IS NULL",
        "accepted_schema_oid=execution_schema_oid",
        "rolname='scanipy_accepted_owner' AND NOT rolcanlogin AND NOT rolinherit",
    ):
        assert guard in before
    if forward:
        assert "execution reader role collision" in before
    else:
        assert "execution reader role missing" in before


def test_only_closed_seven_grants_and_guarded_inverse_ddl():
    m = migration()
    upgrade = ddl(m._migration_sql(forward=True))
    downgrade = ddl(m._migration_sql(forward=False))
    create = " ".join(upgrade[0].split())
    assert create == (
        f"CREATE ROLE {ROLE} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB "
        "NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT -1 PASSWORD NULL"
    )
    grants = [f"USAGE ON SCHEMA {SCHEMA}"] + [
        f"EXECUTE ON FUNCTION {SCHEMA}.{signature}" for signature in SIGNATURES
    ]
    assert upgrade[1:] == [f"GRANT {target} TO {ROLE}" for target in grants]
    assert downgrade[:-1] == [f"REVOKE {target} FROM {ROLE} RESTRICT" for target in grants]
    assert downgrade[-1] == f"DROP ROLE {ROLE}"
    assert len(upgrade) == len(downgrade) == 8
    for statement in upgrade + downgrade:
        assert not any(
            word in statement
            for word in (
                "CASCADE",
                "DROP OWNED",
                "ALTER",
                "CREATE FUNCTION",
                "CREATE TABLE",
                "REPLACE",
                "INSERT",
                "DELETE",
                "UPDATE",
                "WITH GRANT",
                "WITH ADMIN",
            )
        )


def test_inverse_dependency_and_metadata_checks_precede_any_revoke():
    m = migration()
    sql = m._migration_sql(forward=False)
    first, drop = sql.index("EXECUTE 'REVOKE"), sql.index("EXECUTE 'DROP ROLE")
    assert m._role_guard(granted=True) in sql[:first]
    assert m._role_guard(granted=False) in sql[first:drop]
    assert "execution reader role removal failed" in sql[drop:]
    assert "EXCEPTION WHEN" not in sql  # No compensation/retry swallowing a guard failure.


@pytest.mark.parametrize("granted", (True, False))
def test_dependency_census_counts_class_oid_kind_and_cross_database(granted):
    sql = migration()._role_guard(granted=granted)
    count = 7 if granted else 0
    for predicate in (
        "WITH dependencies AS MATERIALIZED",
        "refclassid='pg_catalog.pg_authid'::regclass",
        "refobjid=role_oid LIMIT 8",
        "dbid=database_oid",
        "objsubid=0 AND deptype='a'",
        "classid='pg_catalog.pg_proc'::regclass AND objid=ANY(target_oids)",
        "classid='pg_catalog.pg_namespace'::regclass AND objid=accepted_schema_oid",
        f"dependency_count<>{count}",
        "count(DISTINCT (object_kind,object_oid))",
        f"entry_count<>{count} OR object_count<>{count}",
        "grantor=owner AND privilege_type=expected AND NOT is_grantable",
    ):
        assert predicate in sql
    assert "deptype IN" not in sql and "LIMIT 7" not in sql


@pytest.mark.parametrize(
    "predicate",
    (
        "reader.oid IS DISTINCT FROM role_oid",
        "reader.rolsuper",
        "reader.rolinherit",
        "reader.rolcreaterole",
        "reader.rolcreatedb",
        "reader.rolcanlogin",
        "reader.rolreplication",
        "reader.rolbypassrls",
        "reader.rolconnlimit<>-1",
        "NOT reader.no_password",
        "NOT reader.no_expiry",
        "roleid=role_oid OR member=role_oid OR grantor=role_oid",
        "pg_catalog.pg_db_role_setting WHERE setrole=role_oid",
        "pg_catalog.pg_shdescription",
        "pg_catalog.pg_shseclabel",
    ),
)
def test_role_drift_guards_are_present_before_revoke(predicate):
    sql = migration()._migration_sql(forward=False)
    assert predicate in sql[: sql.index("EXECUTE 'REVOKE")]


def test_password_only_absence_not_material_and_no_catalog_escape_output():
    sql = migration()._migration_sql(forward=False)
    assert sql.count("r.rolpassword") == 2
    assert sql.count("r.rolpassword IS NULL AS no_password") == 2
    assert not re.search(r"SELECT\s+(?:r\.\*)?\*\s+.*pg_authid", sql)
    assert "RAISE NOTICE" not in sql and "RAISE LOG" not in sql
    assert not re.search(r"RAISE EXCEPTION '[^']*%", sql)


@pytest.mark.parametrize("granted", (True, False))
def test_effective_privileges_include_public_inheritance_and_grant_options(granted):
    sql = migration()._role_guard(granted=granted)
    for predicate in (
        "has_schema_privilege(role_oid,n.oid,'CREATE')",
        "has_schema_privilege(role_oid,n.oid,'USAGE WITH GRANT OPTION')",
        "has_function_privilege(role_oid,p.oid,'EXECUTE WITH GRANT OPTION')",
        "has_sequence_privilege(role_oid,c.oid,'USAGE,SELECT,UPDATE')",
        "has_table_privilege(role_oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
        "role_oid,c.oid,'SELECT,INSERT,UPDATE,REFERENCES'",
        "n.nspowner=role_oid",
        "p.proowner=role_oid",
        "c.relowner=role_oid",
    ):
        assert predicate in sql
    expected_functions = "p.oid=ANY(target_oids)" if granted else "false"
    assert f"IS DISTINCT FROM ({expected_functions})" in sql
    assert f"n.oid=accepted_schema_oid AND {str(granted).lower()}" in sql


@pytest.mark.parametrize("remember", (True, False))
def test_bounded_snapshots_exclude_only_new_grantee_not_old_acl_entries(remember):
    m = migration()
    sql = m._objects(remember=remember)
    assert sql.count("WHERE a.grantee IS DISTINCT FROM role_oid") == 7
    assert sql.count("coalesce(cardinality(f.proacl),0)>64") == 6
    assert "coalesce(cardinality(n.nspacl),0)>64" in sql
    assert sql.count("WHERE a.grantee=0") == 7
    assert "to_jsonb(f)-'proacl'" in sql and "to_jsonb(n)-'nspacl'" in sql
    assert "ORDER BY oid" in sql and "'kind','schema'" in sql
    assert "a.grantor,a.grantee,a.privilege_type,a.is_grantable" in sql
    assert 'ORDER BY a.grantor,a.grantee,a.privilege_type COLLATE "C",a.is_grantable' in sql
    assert "a.grantor IS DISTINCT FROM role_oid" not in sql


@pytest.mark.parametrize("forward", (True, False))
def test_safe_search_path_local_restore_and_finite_generated_sql(forward):
    sql = migration()._migration_sql(forward=forward)
    safe = "PERFORM pg_catalog.set_config('search_path','pg_catalog,pg_temp',true);"
    restore = "PERFORM pg_catalog.set_config('search_path',prior_search_path,true);"
    assert sql.index(safe) < sql.index("IF current_setting") < sql.index("EXECUTE '")
    assert sql.index(restore) > sql.index("execution reader original objects changed")
    assert "prior_search_path pg_catalog.text:=pg_catalog.current_setting('search_path')" in sql
    assert sql.count("set_config(") == 2
    assert len(sql.encode()) < 131072
    assert sql.count("$execution_reader_migration$") == 2


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
@pytest.mark.parametrize("style", ("named", "pyformat"))
def test_actual_sqlalchemy_dialect_has_no_bindings_or_changed_literal(
    monkeypatch, direction, style
):
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

    m, submitted = migration(), []
    monkeypatch.setattr(m.op, "execute", submitted.append)
    getattr(m, direction)()
    assert len(submitted) == 1
    compiled = text(submitted[0]).compile(dialect=PGDialect_psycopg2(paramstyle=style))
    assert compiled.params == {} and compiled.construct_params() == {}
    output = str(compiled) % {} if style == "pyformat" else str(compiled)
    assert output == m._migration_sql(forward=direction == "upgrade")


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
def test_actual_alembic_offline_literal_no_server(monkeypatch, direction):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    m, output = migration(), StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        dialect_opts={"paramstyle": "named"},
        opts={"as_sql": True, "literal_binds": True, "output_buffer": output},
    )
    monkeypatch.setattr(m, "op", Operations(context))
    getattr(m, direction)()
    assert output.getvalue() == m._migration_sql(forward=direction == "upgrade").strip() + ";\n\n"


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
@pytest.mark.parametrize("error_type", (RuntimeError, KeyboardInterrupt, SystemExit))
def test_single_submission_preserves_failure_without_retry(monkeypatch, direction, error_type):
    m, calls, primary = migration(), [], error_type("controlled offline failure")

    def fail(statement):
        calls.append(statement)
        raise primary

    monkeypatch.setattr(m.op, "execute", fail)
    with pytest.raises(error_type) as observed:
        getattr(m, direction)()
    assert observed.value is primary and len(calls) == 1


def test_existing_runtime_stays_unsupported_and_no_new_provider_is_imported():
    source = (VERSIONS / "20260926_0008_execution_reader.py").read_text()
    imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    assert len(imports) == 1 and imports[0].module == "alembic"
    verifier = (ROOT / "services/scan/accepted_inputs/verify.py").read_text()
    assert '"runtime-unsupported"' in verifier
    assert ROLE not in verifier

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
    assert "coalesce(cardinality(v_n.nspacl),0)>64" in sql
    assert sql.count("WHERE a.grantee=0") == 7
    assert "to_jsonb(f)-'proacl'" in sql and "to_jsonb(v_n)-'nspacl'" in sql
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


@pytest.mark.parametrize("forward", (True, False))
def test_outer_row_variables_do_not_shadow_catalog_relation_aliases(forward):
    # The embedded predecessor bodies are quoted comparison data, not part of
    # the outer DO statement's variable scope. This is a source invariant, not
    # a PostgreSQL parser or proof of successful migration execution.
    sql = migration()._migration_sql(forward=forward)
    outer, bodies = re.subn(r"(\$ear_body_[0-5]\$).*?\1", "''", sql, flags=re.DOTALL)
    assert bodies == 12  # Six targets, both before and after the fixed DDL.
    variables = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s+pg_catalog\.[a-z_]+%ROWTYPE\b", outer))
    aliases = set(
        re.findall(r"\b(?:FROM|JOIN)\s+pg_catalog\.[a-z_]+\s+([a-z_][a-z0-9_]*)\b", outer)
    )
    assert len(variables) == 2
    assert {"p", "r", "n", "c"} <= aliases
    assert variables.isdisjoint(aliases), variables & aliases


@pytest.mark.parametrize("read", ("current", "recheck"))
@pytest.mark.parametrize("fail_first_close", (False, True))
def test_actual_role_read_body_uses_closed_distinct_single_use_transactions(read, fail_first_close):
    from types import SimpleNamespace

    source = ROOT / "tests/integration/test_execution_authority_role.py"
    name = "test_six_actual_reads_with_explicit_effective_role"
    functions = [
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(functions) == 1
    body = functions[0]
    body.decorator_list = []  # Never import/activate the integration plugin or fixture.
    binding, admission, role_pg = object(), object(), object()
    prior = (
        SimpleNamespace(binding=binding),
        bytes(bytearray(b"controlled original LIVE bytes")),
        "2026-09-26T00:00:00Z",
    )
    events, transactions = [], []
    close_error = RuntimeError("controlled first transaction close")
    previous = ValueError("controlled prior cause")
    close_error.__cause__ = previous

    class Ledger:
        def __init__(self, pg):
            assert pg is role_pg

        def activate(self):
            events.append("activate")
            return self

        def create(self):
            events.append("create")
            return self

        def seal(self):
            events.append("seal")
            return self

        def authorize(self):
            events.append("authorize")

    def inputs(ledger):
        assert type(ledger) is Ledger
        return binding, admission

    class Transaction:
        def __init__(self, ledger):
            assert type(ledger) is Ledger
            assert len(transactions) < 2
            assert all(item.closed for item in transactions)
            self.index, self.used, self.closed = len(transactions), False, False
            transactions.append(self)

        def __enter__(self):
            events.append(("enter", self.index))
            return self

        def __exit__(self, kind, value, traceback):
            self.closed = True
            events.append(("close", self.index))
            if fail_first_close and self.index == 0:
                assert value is None
                raise close_error

        def use(self, expected_binding, expected_admission):
            assert not self.closed
            assert not self.used, "single-use repository reused"
            assert expected_binding is binding and expected_admission is admission
            self.used = True

        def read_execution_authority(self, expected_binding, expected_admission):
            self.use(expected_binding, expected_admission)
            assert self.index == 0
            events.append("R5")
            return prior

        def recheck_execution_authority(self, expected_binding, expected_admission, *original):
            self.use(expected_binding, expected_admission)
            assert self.index == 1 and transactions[0].closed
            assert len(original) == 3
            assert all(actual is expected for actual, expected in zip(original, prior, strict=True))
            events.append("R6")
            return None

    namespace = {
        "SqlLedger": Ledger,
        "current_inputs": inputs,
        "reader_transaction": Transaction,
    }
    exec(compile(ast.Module(body=[body], type_ignores=[]), str(source), "exec"), namespace)
    if fail_first_close:
        with pytest.raises(RuntimeError) as observed:
            namespace[name](role_pg, read)
        assert observed.value is close_error and observed.value.__cause__ is previous
    else:
        namespace[name](role_pg, read)
    expected = ["activate", "create", "seal", "authorize", ("enter", 0), "R5", ("close", 0)]
    if read == "recheck" and not fail_first_close:
        expected.extend((("enter", 1), "R6", ("close", 1)))
    assert events == expected
    assert len(transactions) == (2 if read == "recheck" and not fail_first_close else 1)
    assert all(item.closed and item.used for item in transactions)


_SCHEMA_SERVICE_ROLES = (
    "scanipy_exec_owner",
    "scanipy_exec_request",
    "scanipy_exec_detector",
    "scanipy_exec_identity",
    "scanipy_exec_cleanup",
    "scanipy_exec_read",
    "scanipy_accepted_owner",
    "scanipy_accepted_policy_admin",
    "scanipy_accepted_publisher",
    "scanipy_accepted_resolver",
    "scanipy_accepted_reader",
    "scanipy_accepted_execution_reader",
)
_PROTECTED_SCHEMAS = ("accepted_schema_oid", "execution_schema_oid")


def _schema_service_owner_guard(sql):
    """Admit the literal SQL shape, not a replacement PostgreSQL executor."""
    match = re.search(
        r"IF EXISTS\(SELECT 1 FROM pg_catalog\.pg_roles AS protected_owner\s+"
        r"WHERE protected_owner\.oid=v_n\.nspowner AND protected_owner\.rolname IN \("
        r"(?P<names>.*?)\)\) THEN\s+"
        r"RAISE EXCEPTION 'execution reader protected schema service owner'; END IF;",
        sql,
        flags=re.DOTALL,
    )
    assert match is not None, "missing exact protected-schema owner eligibility predicate"
    literals = match.group("names")
    names = tuple(re.findall(r"'([a-z_]+)'", literals))
    assert re.sub(r"'[a-z_]+'", "", literals).replace(",", "").strip() == ""
    assert len(names) == len(set(names)) == 12
    return match.group(), names


def test_schema_service_owner_set_matches_both_original_role_creators():
    roles = []
    for filename in ("20260925_0005_execution_security.py", "20260926_0006_accepted_ledger.py"):
        declarations = [
            node.value
            for node in ast.parse((VERSIONS / filename).read_text()).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "ROLES" for target in node.targets
            )
        ]
        assert len(declarations) == 1
        # Only the two trusted, fixed tuple expressions; no migration import/DDL.
        values = eval(
            compile(ast.Expression(declarations[0]), filename, "eval"),
            {"__builtins__": {}, "tuple": tuple},
        )
        assert type(values) is tuple and all(type(value) is str for value in values)
        roles.extend(values)
    assert (*roles, ROLE) == _SCHEMA_SERVICE_ROLES
    for remember in (True, False):
        _, names = _schema_service_owner_guard(migration()._objects(remember=remember))
        assert names == _SCHEMA_SERVICE_ROLES


@pytest.mark.parametrize("forward", (True, False))
def test_schema_owner_eligibility_precedes_effects_and_final_snapshot(forward):
    m = migration()
    sql = m._migration_sql(forward=forward)
    guards = []
    for remember in (True, False):
        objects = m._objects(remember=remember)
        guard, _ = _schema_service_owner_guard(objects)
        guards.append(guard)
        loop = objects.index("FOR v_n IN SELECT * FROM pg_catalog.pg_namespace")
        selected = objects.index("WHERE oid IN (accepted_schema_oid,execution_schema_oid)", loop)
        admitted = objects.index(guard, selected)
        snapshot = objects.index("'kind','schema','properties',to_jsonb(v_n)-'nspacl'", admitted)
        assert loop < selected < admitted < objects.index("schema ACL overflow") < snapshot
    assert guards[0] == guards[1] and sql.count(guards[0]) == 2
    effects = list(re.finditer(r"^\s*EXECUTE '", sql, re.MULTILINE))
    assert effects
    assert sql.index(guards[0]) < effects[0].start()
    assert effects[-1].start() < sql.rindex(guards[0])
    assert sql.rindex(guards[0]) < sql.index("IF after_objects IS DISTINCT FROM before_objects")


@pytest.mark.parametrize("schema", _PROTECTED_SCHEMAS)
@pytest.mark.parametrize("role", _SCHEMA_SERVICE_ROLES)
def test_closed_schema_owner_predicate_refuses_each_service_role(schema, role):
    # Finite truth table for the admitted equality/IN predicate, not a SQL test.
    objects = migration()._objects(remember=True)
    _, names = _schema_service_owner_guard(objects)
    assert f"WHERE oid IN ({','.join(_PROTECTED_SCHEMAS)})" in objects
    assert schema in _PROTECTED_SCHEMAS
    catalog = tuple((100 + index, name) for index, name in enumerate(_SCHEMA_SERVICE_ROLES))
    owner_oid = {name: oid for oid, name in catalog}[role]
    assert any(oid == owner_oid and name in names for oid, name in catalog)


@pytest.mark.parametrize("schema", _PROTECTED_SCHEMAS)
@pytest.mark.parametrize(
    "owner", ("migration_admin_a", "migration_admin_b", "scanipy_exec_owner_other", "custom_owner")
)
def test_schema_owner_policy_does_not_invent_an_administrator_identity(schema, owner):
    objects = migration()._objects(remember=False)
    guard, names = _schema_service_owner_guard(objects)
    assert schema in _PROTECTED_SCHEMAS
    catalog = ((999, owner), *((100 + index, name) for index, name in enumerate(names)))
    assert not any(oid == 999 and name in names for oid, name in catalog)
    assert "LIKE" not in guard and "current_user" not in guard and "rolsuper" not in guard
    assert "pg_database" not in guard and "to_regrole" not in guard
    assert "protected_owner.oid=v_n.nspowner" in guard

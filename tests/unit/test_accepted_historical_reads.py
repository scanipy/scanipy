"""Historical read classifiers/migration controls; no live server or authority."""

from __future__ import annotations

import ast
import builtins
import hashlib
import importlib.util
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import psycopg2
import pytest

from services.scan.accepted_inputs import ledger_repository as r

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
STATES = ("08000", "08001", "08003", "08004", "08006", "08007", "08P01")


def migration():
    path = ROOT / "db/migrations/versions/20260926_0007_accepted_read_outcomes.py"
    spec = importlib.util.spec_from_file_location("historical_read_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("error_type", (psycopg2.OperationalError, psycopg2.InterfaceError))
def test_exact_base_driver_without_server_state_is_transport(error_type):
    error = error_type("private diagnostic")
    assert error.pgcode is None
    assert r._historical_read_failure_kind(error) == "transport"


@pytest.mark.parametrize(
    "error_type",
    (psycopg2.errors.InsufficientPrivilege, psycopg2.errors.UndefinedTable, psycopg2.DataError),
)
def test_unmapped_server_class_is_not_transport(error_type):
    assert r._historical_read_failure_kind(error_type("private diagnostic")) is None


@pytest.mark.parametrize("state", STATES)
def test_exact_native_driver_type_and_native_sqlstate_descriptor(state):
    # Driver-supported restoration sets the actual native pgcode member. No
    # server response or cryptographic authority is being simulated as real.
    error = psycopg2.errors.lookup(state)("private")
    error.__setstate__({"pgcode": state})
    assert r._historical_read_failure_kind(error) == "transport"


@pytest.mark.parametrize("state", STATES)
def test_native_driver_type_must_match_state(state):
    error = psycopg2.errors.lookup("08003" if state != "08003" else "08006")("private")
    error.__setstate__({"pgcode": state})
    assert r._historical_read_failure_kind(error) is None


@pytest.mark.parametrize("error_type", (psycopg2.OperationalError, psycopg2.InterfaceError))
@pytest.mark.parametrize("state", ("08006", "57014", "P0001", ""))
def test_base_driver_with_any_server_state_is_not_the_no_state_case(error_type, state):
    error = error_type("private")
    error.__setstate__({"pgcode": state})
    assert r._historical_read_failure_kind(error) is None


@pytest.mark.parametrize(
    "state", ("42501", "42P01", "22000", "57014", "55P03", "53100", "57P01", "P0001")
)
def test_genuine_other_server_states_are_fatal_classification(state):
    error = psycopg2.errors.lookup(state)("private")
    error.__setstate__({"pgcode": state})
    assert r._historical_read_failure_kind(error) is None


@pytest.mark.parametrize("parent", (psycopg2.OperationalError, psycopg2.errors.RaiseException))
def test_custom_driver_subclass_properties_and_formatting_are_never_called(parent):
    class Custom(parent):
        @property
        def pgcode(self):
            pytest.fail("untrusted pgcode property")

        @property
        def diag(self):
            pytest.fail("untrusted diagnostic property")

        def __str__(self):
            pytest.fail("untrusted formatting")

    assert r._historical_read_failure_kind(Custom()) is None


def controlled_diagnostics(
    monkeypatch,
    error,
    *,
    code="P0001",
    primary="ledger-mismatch",
    detail="accepted-historical-row-missing",
    wrong_type=False,
):
    """Descriptor-path oracle only; actual PG diagnostic tests are separate.

    Exact exception types stay the installed driver's types. Fake descriptor
    owners stand in for the sealed native diagnostic result, not a SQL server.
    """
    calls = []

    class Descriptor:
        def __init__(self, name, value):
            self.name, self.value = name, value

        def __get__(self, instance, owner):
            calls.append(self.name)
            return self.value

    class Diagnostic:
        message_primary = Descriptor("primary", primary)
        message_detail = Descriptor("detail", detail)

    diagnostic = object() if wrong_type else Diagnostic()

    class ErrorFields:
        pgcode = Descriptor("pgcode", code)
        diag = Descriptor("diag", diagnostic)

    replacement = SimpleNamespace(
        Error=ErrorFields,
        OperationalError=psycopg2.OperationalError,
        InterfaceError=psycopg2.InterfaceError,
        errors=psycopg2.errors,
        extensions=SimpleNamespace(Diagnostics=Diagnostic),
    )
    monkeypatch.setitem(sys.modules, "psycopg2", replacement)
    return calls


@pytest.mark.parametrize(
    "primary,detail,expected",
    (
        ("ledger-mismatch", "accepted-historical-row-missing", "missing"),
        ("ledger-mismatch", None, None),
        ("ledger-mismatch", "accepted-historical-row-missing-extra", None),
        ("ledger-mismatch", " accepted-historical-row-missing", None),
        ("ledger-mismatch", "accepted-work-limit", None),
        ("content-mismatch", "accepted-historical-row-missing", None),
        ("invalid-input", "accepted-historical-row-missing", None),
        (None, "accepted-historical-row-missing", None),
        (b"ledger-mismatch", "accepted-historical-row-missing", None),
        ("ledger-mismatch", b"accepted-historical-row-missing", None),
    ),
)
def test_missing_requires_exact_three_native_fields(monkeypatch, primary, detail, expected):
    error = psycopg2.errors.RaiseException("private")
    calls = controlled_diagnostics(monkeypatch, error, primary=primary, detail=detail)
    assert r._historical_read_failure_kind(error) == expected
    assert calls == ["pgcode", "diag", "primary", "detail"]


@pytest.mark.parametrize("code", (None, "42501", "P0002", "08006", 1, b"P0001"))
def test_missing_requires_exact_state_and_class(monkeypatch, code):
    error = psycopg2.errors.RaiseException("private")
    calls = controlled_diagnostics(monkeypatch, error, code=code)
    assert r._historical_read_failure_kind(error) is None
    assert calls == ["pgcode"]


def test_diagnostic_lookalike_is_rejected_before_fields(monkeypatch):
    error = psycopg2.errors.RaiseException("private")
    calls = controlled_diagnostics(monkeypatch, error, wrong_type=True)
    assert r._historical_read_failure_kind(error) is None
    assert calls == ["pgcode", "diag"]


@pytest.mark.parametrize("field", ("code", "primary", "detail"))
def test_diagnostic_string_subclass_cannot_supply_equality_or_hash(monkeypatch, field):
    class Poison(str):
        def __eq__(self, other):
            pytest.fail("custom diagnostic equality")

        def __hash__(self):
            pytest.fail("custom diagnostic hash")

    values = {
        "code": "P0001",
        "primary": "ledger-mismatch",
        "detail": "accepted-historical-row-missing",
    }
    values[field] = Poison(values[field])
    error = psycopg2.errors.RaiseException("private")
    controlled_diagnostics(monkeypatch, error, **values)
    assert r._historical_read_failure_kind(error) is None


def test_driver_absence_fails_closed(monkeypatch):
    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "psycopg2":
            raise ImportError("controlled absent optional driver")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    assert r._historical_read_failure_kind(ValueError()) is None


def test_no_public_mapper_rewrite_or_consumer_origin_claim():
    error = psycopg2.errors.RaiseException("private")
    error.__setstate__({"pgcode": "P0001"})
    assert r._driver_code(error) is None
    assert r._historical_read_failure_kind(error) is None
    # The helper never reads exception causal links or invents an origin token.
    body = ast.parse(Path(r.__file__).read_text())
    helper = next(
        node
        for node in body.body
        if isinstance(node, ast.FunctionDef) and node.name == "_historical_read_failure_kind"
    )
    assert not any(
        isinstance(node, ast.Attribute)
        and node.attr in ("__cause__", "__context__", "execute", "fetchone", "commit", "rollback")
        for node in ast.walk(helper)
    )


def test_migration_predecessors_and_historical_resources_are_byte_exact():
    m = migration()
    original = (ROOT / "db/migrations/versions/accepted_v1_reads.sql").read_bytes()
    assert hashlib.sha256(original).hexdigest() == (
        # pragma: allowlist nextline secret
        "c7cead1435acf3f2c35c7a24979f10bcf964809b890c17fdac2ed2ff09340e18"
    )
    assert m.ORIGINAL_R1.encode() in original and m.ORIGINAL_R3.encode() in original
    old_migration = ROOT / "db/migrations/versions/20260926_0006_accepted_ledger.py"
    assert hashlib.sha256(old_migration.read_bytes()).hexdigest() == (
        # pragma: allowlist nextline secret
        "e72cd56841dfe001958f03356f0366b03b2a63ac9bea3c0f7c7c8652f9957842"
    )
    assert (m.revision, m.down_revision) == ("20260926_0007", "20260926_0006")


def test_exact_authorized_r1_r3_delta_and_no_extra_query():
    m = migration()
    marker = (
        "  IF NOT FOUND THEN\n"
        "    RAISE EXCEPTION 'ledger-mismatch' USING ERRCODE='P0001',\n"
        "      DETAIL='accepted-historical-row-missing';\n"
        "  END IF;\n"
    )
    first = m.UPDATED_R1.replace("CREATE OR REPLACE FUNCTION", "CREATE FUNCTION", 1)
    first = first.replace(marker, "", 1).replace(
        "v1_require(row.record_length<=65536", "v1_require(FOUND AND row.record_length<=65536", 1
    )
    assert first == m.ORIGINAL_R1
    third = m.UPDATED_R3.replace("CREATE OR REPLACE FUNCTION", "CREATE FUNCTION", 1)
    third = (
        third.replace(marker, "", 1)
        .replace(
            "  PERFORM scanipy_accepted_inputs.v1_require("
            "row.record_digest=p_record_digest,'ledger-mismatch');\n",
            "",
            1,
        )
        .replace("SELECT record_digest,record_length,", "SELECT record_length,", 1)
        .replace("AND id=p_event_id;", "AND id=p_event_id AND record_digest=p_record_digest;", 1)
        .replace("v1_require(row.record_length<=", "v1_require(FOUND AND row.record_length<=", 1)
    )
    assert third == m.ORIGINAL_R3
    assert m.UPDATED_R3.index(marker) < m.UPDATED_R3.index("row.record_digest=p_record_digest")
    for old, new in ((m.ORIGINAL_R1, m.UPDATED_R1), (m.ORIGINAL_R3, m.UPDATED_R3)):
        assert old.count("SELECT ") == new.count("SELECT ") == 2
        assert new.count("v1_control(512)") == 1


@pytest.mark.parametrize("forward", (True, False))
def test_preflight_both_targets_before_ddl_and_exact_postread(forward):
    m = migration()
    sql = m._replacement(forward=forward)
    first_ddl = sql.index("EXECUTE $definition$")
    assert sql[:first_ddl].count("accepted read migration target missing") == 2
    assert sql[:first_ddl].count("accepted read migration target drift") == 2
    assert sql.count("EXECUTE $definition$CREATE OR REPLACE FUNCTION") == 2
    assert sql.count("accepted read migration identity drift") == 2
    assert "DROP FUNCTION" not in sql and "GRANT " not in sql and "CREATE TABLE" not in sql
    for index, item in enumerate(m.FUNCTIONS):
        before, after = item[5 if forward else 6], item[6 if forward else 5]
        assert m._guard(index, before, remember=True) in sql[:first_ddl]
        assert m._guard(index, after, remember=False) in sql[first_ddl:]


@pytest.mark.parametrize(
    "property_name",
    (
        "proowner",
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
        "oid",
    ),
)
def test_catalog_admission_or_preservation_names_every_changed_property(property_name):
    m = migration()
    for index, item in enumerate(m.FUNCTIONS):
        assert "target." + property_name in m._guard(index, item[5], remember=True)


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
@pytest.mark.parametrize("style", ("named", "pyformat"))
def test_actual_sqlalchemy_compilation_retains_exact_literal_sql(monkeypatch, direction, style):
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2

    m, submitted = migration(), []
    monkeypatch.setattr(m.op, "execute", submitted.append)
    getattr(m, direction)()
    assert len(submitted) == 1
    compiled = text(submitted[0]).compile(dialect=PGDialect_psycopg2(paramstyle=style))
    assert compiled.params == {} and compiled.construct_params() == {}
    output = str(compiled) % {} if style == "pyformat" else str(compiled)
    assert output == m._replacement(forward=direction == "upgrade")


@pytest.mark.parametrize("direction", ("upgrade", "downgrade"))
def test_real_alembic_offline_literal_submission(monkeypatch, direction):
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
    assert output.getvalue() == m._replacement(forward=direction == "upgrade").strip() + ";\n\n"

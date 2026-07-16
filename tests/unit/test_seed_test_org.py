"""CLAR-CP-01-02 — tests for scripts/seed_test_org.py.

Covers the hard fail-closed requirement ("MUST refuse to run if ENV/
SCANIPY_ENV is 'prod'") with a real assertion (not prose), plus the seed
logic's idempotency shape against hermetic in-memory doubles — no real
Postgres or AWS connection is opened by this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from scripts.seed_test_org import (
    TEST_ORG_ID,
    TEST_ORG_NAME,
    TEST_ORG_ROLE,
    SeedProdRefusalError,
    generate_api_key,
    refuse_if_prod,
    seed,
)

# ---------------------------------------------------------------------------
# refuse_if_prod — the hard ENV/SCANIPY_ENV=prod gate (CLAR-CP-01-02)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("var_name", ["ENV", "SCANIPY_ENV"])
@pytest.mark.parametrize("value", ["prod", "Prod", "PROD", " prod ", "PROD\n"])
def test_refuse_if_prod_blocks_both_var_names_case_insensitive(var_name: str, value: str) -> None:
    with pytest.raises(SeedProdRefusalError, match=var_name):
        refuse_if_prod({var_name: value})


@pytest.mark.unit
@pytest.mark.parametrize(
    "env",
    [
        {},
        {"ENV": "dev"},
        {"SCANIPY_ENV": "staging"},
        {"ENV": "dev", "SCANIPY_ENV": "test"},
        # "production" is NOT the literal "prod" — the gate is exact-match,
        # not a substring check, matching the literal instruction. Documented
        # here so a future edit that loosens/tightens the match is deliberate.
        {"ENV": "production"},
    ],
)
def test_refuse_if_prod_allows_non_prod(env: dict[str, str]) -> None:
    refuse_if_prod(env)  # must not raise


@pytest.mark.unit
def test_refuse_if_prod_checked_before_any_db_or_aws_call() -> None:
    """main() calls refuse_if_prod() before touching SCANIPY_DATABASE_URL.

    Regression guard for the "MUST refuse to run" hard requirement: even with
    no database configured at all, ENV=prod must raise the refusal — not a
    later, different error about a missing database URL.
    """
    import scripts.seed_test_org as mod

    old_environ = dict(mod.os.environ)
    try:
        mod.os.environ["ENV"] = "prod"
        mod.os.environ.pop("SCANIPY_DATABASE_URL", None)
        with pytest.raises(SeedProdRefusalError):
            mod.main([])
    finally:
        mod.os.environ.clear()
        mod.os.environ.update(old_environ)


# ---------------------------------------------------------------------------
# generate_api_key
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_api_key_is_high_entropy_and_prefixed() -> None:
    a = generate_api_key()
    b = generate_api_key()
    assert a != b
    assert a.startswith("scanipy_test_")
    assert len(a) > 40


# ---------------------------------------------------------------------------
# seed() — hermetic in-memory doubles (Protocol-based DI, repo precedent)
# ---------------------------------------------------------------------------


@dataclass
class _FakeCursor:
    log: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.log.append((sql, params))

    def fetchone(self) -> None:
        return None

    def close(self) -> None:
        pass


@dataclass
class _FakeConnection:
    cursor_log: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)
    committed: bool = False
    rolled_back: bool = False

    def cursor(self) -> _FakeCursor:
        cur = _FakeCursor(self.cursor_log)
        return cur

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class ResourceNotFoundException(Exception):  # noqa: N818 — name fixed verbatim to match boto3's real exception class
    """Name matches boto3's dynamic ClientError subclass (see _secret_exists)."""


@dataclass
class _FakeSecretsClient:
    """A minimal boto3 secretsmanager-client double.

    ``existing`` pre-seeds secret names that already exist, so tests can
    exercise both the create and the already-exists (no rotation) branches.
    """

    existing: set[str] = field(default_factory=set)
    created: dict[str, Any] = field(default_factory=dict)

    def describe_secret(self, SecretId: str) -> dict[str, object]:  # noqa: N803
        if SecretId in self.existing:
            return {"Name": SecretId}
        raise ResourceNotFoundException()

    def create_secret(self, **kwargs: object) -> None:
        name = kwargs["Name"]
        assert isinstance(name, str)
        self.created[name] = kwargs
        self.existing.add(name)


def _patch_resource_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # _secret_exists matches on type(exc).__name__ == "ResourceNotFoundException"
    # (mirrors boto3's dynamic ClientError-subclass shape) — the fake's
    # exception class already carries that name, so no patch is needed. This
    # helper exists so a future botocore-exact double can slot in here.
    _ = monkeypatch


@pytest.mark.unit
def test_seed_upserts_org_row_and_creates_secret_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_resource_not_found(monkeypatch)
    conn = _FakeConnection()
    client = _FakeSecretsClient()

    result = seed(
        database_url="postgresql://unused/for-this-fake",
        region="us-east-1",
        secret_name="scanipy/test-org/api-key",
        connection=conn,
        boto3_client=client,
    )

    assert result.org_id == TEST_ORG_ID
    assert result.org_name == TEST_ORG_NAME
    assert result.api_key_created is True
    assert conn.committed is True
    assert conn.rolled_back is False

    # The org upsert used ON CONFLICT (idempotent), addressed the fixed id.
    (sql, params) = conn.cursor_log[0]
    assert "ON CONFLICT" in sql
    assert params == (str(TEST_ORG_ID), TEST_ORG_NAME)

    # The secret payload carries org_id + role + a generated api_key, never
    # the org name or any other PII-adjacent field.
    payload = client.created["scanipy/test-org/api-key"]["SecretString"]
    import json

    body = json.loads(payload)
    assert body["org_id"] == str(TEST_ORG_ID)
    assert body["role"] == TEST_ORG_ROLE
    assert body["api_key"].startswith("scanipy_test_")


@pytest.mark.unit
def test_seed_does_not_rotate_an_existing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_resource_not_found(monkeypatch)
    conn = _FakeConnection()
    client = _FakeSecretsClient(existing={"scanipy/test-org/api-key"})

    result = seed(
        database_url="postgresql://unused/for-this-fake",
        region="us-east-1",
        secret_name="scanipy/test-org/api-key",
        connection=conn,
        boto3_client=client,
    )

    assert result.api_key_created is False
    assert client.created == {}  # create_secret was never called


@pytest.mark.unit
def test_seed_rolls_back_org_insert_on_db_error() -> None:
    class _FailingCursor(_FakeCursor):
        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            raise RuntimeError("simulated DB failure")

    @dataclass
    class _FailingConnection(_FakeConnection):
        def cursor(self) -> _FailingCursor:  # type: ignore[override]
            return _FailingCursor()

    conn = _FailingConnection()
    client = _FakeSecretsClient()

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        seed(
            database_url="postgresql://unused/for-this-fake",
            region="us-east-1",
            connection=conn,
            boto3_client=client,
        )

    assert conn.rolled_back is True
    assert conn.committed is False

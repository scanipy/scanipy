"""Hermetic unit tests for CMP-ORCH-01's real SQL-backed adapters (Track 1D).

``services/scan/sql_adapters.py`` — no real Postgres, no real AWS. Every test
here injects a fake DB-API2 connection factory or a fake boto3-Secrets-Manager
client, mirroring ``tests/unit/test_substrate.py``'s ``_FakeBoto3S3Client``
pattern. The real-Postgres / real-moto conformance suite for the SAME adapters
lives in ``tests/integration/test_orch01_sql_adapters.py`` (skips when
``SCANIPY_DATABASE_URL`` is unset), including the concurrency falsifier for
:class:`~services.scan.sql_adapters.SqlJobStateStore`'s row lock that this
hermetic file cannot exercise (a fake has no real transaction isolation).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from services.scan.api import HmacKeyIssuer, JobStateStore, SnapshotPort, SpecRegistryPort
from services.scan.sql_adapters import (
    SecretsManagerHmacKeyIssuer,
    SqlJobStateStore,
    SqlSnapshotPort,
    SqlSpecRegistryPort,
)
from services.snapshot.service import SnapshotService

pytestmark = pytest.mark.unit

_FAKE_ENV_DIGEST = "sha256:" + "c" * 64
_ORG_A = "11111111-1111-1111-1111-111111111111"
_ORG_B = "22222222-2222-2222-2222-222222222222"


# --------------------------------------------------------------------------- #
# A minimal DB-API2 fake: records every executed statement, dispatches
# fetchone() results through an injected callback. Good enough to drive
# db/session.py's acquire_for_request (cursor/commit/rollback only).
# --------------------------------------------------------------------------- #


@dataclass
class _RecordedCall:
    sql: str
    params: tuple[object, ...]


@dataclass
class _FakeCursor:
    _conn: _FakeConnection

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._conn.calls.append(_RecordedCall(sql=sql, params=params))
        self._conn._pending = self._conn.on_execute(sql, params)

    def fetchone(self) -> tuple[object, ...] | None:
        return self._conn._pending

    def close(self) -> None:
        pass


@dataclass
class _FakeConnection:
    """Injected in place of a real psycopg2 connection.

    ``on_execute`` decides what the NEXT ``fetchone()`` returns for a given
    executed statement — the test wires the exact query-shape → row mapping it
    wants to assert against.
    """

    on_execute: Callable[[str, tuple[object, ...]], tuple[object, ...] | None]
    calls: list[_RecordedCall] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    _pending: tuple[object, ...] | None = None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _factory_for(conn: Any) -> Callable[[], Iterator[Any]]:
    """Wrap any fake connection (this file defines three shapes) as a
    ``ConnectionFactory``. Not type-checked in CI (tests/ is excluded from the
    mypy-strict scope — see ``.pre-commit-config.yaml``), so a loose ``Any``
    here is the pragmatic choice over three near-duplicate typed overloads.
    """

    @contextmanager
    def _factory() -> Iterator[Any]:
        yield conn

    return _factory


# --------------------------------------------------------------------------- #
# SqlSnapshotPort
# --------------------------------------------------------------------------- #


def test_sql_snapshot_port_is_structural_snapshot_port() -> None:
    port = SqlSnapshotPort(
        connection_factory=_factory_for(_FakeConnection(on_execute=lambda sql, p: None)),
        snapshot_service=SnapshotService(),
    )
    assert isinstance(port, SnapshotPort)


def test_sql_snapshot_port_dedup_returns_existing_row_without_creating() -> None:
    """A matching (org_id, codebase_id, commit_sha, CURRENT env_digest) row
    short-circuits: no new SnapshotService.create_snapshot job is enqueued
    (dedup, per the SnapshotPort docstring "if absent dedup is the port's
    responsibility")."""
    existing_id = uuid4()
    codebase_id = uuid4()

    def on_execute(sql: str, params: tuple[object, ...]) -> tuple[object, ...] | None:
        if sql.strip().startswith("SELECT id, env_digest FROM snapshots"):
            assert params == (_ORG_A, str(codebase_id), "a" * 40, _FAKE_ENV_DIGEST)
            return (str(existing_id), _FAKE_ENV_DIGEST)
        return None

    conn = _FakeConnection(on_execute=on_execute)
    service = SnapshotService(  # would enqueue+mint if wrongly invoked
        env_digest_provider=lambda: _FAKE_ENV_DIGEST
    )
    port = SqlSnapshotPort(connection_factory=_factory_for(conn), snapshot_service=service)

    resolution = port.resolve_or_create(org_id=_ORG_A, codebase_id=codebase_id, commit_sha="a" * 40)

    assert resolution.snapshot_id == existing_id
    assert resolution.env_digest == _FAKE_ENV_DIGEST
    # Dedup path never touched the queue: SnapshotService's default StandardQueue
    # is empty (no create_snapshot job was enqueued).
    assert service.queue.receive() is None
    assert conn.commits == 1  # acquire_for_request committed the read transaction
    assert conn.rollbacks == 0


def test_sql_snapshot_port_env_rollover_never_dedups_onto_a_stale_env_row() -> None:
    """A row seeded under an OLD env_digest is invisible to a lookup under a
    NEW (current) env_digest — an Env rollover must mint a fresh snapshot, not
    silently reuse a snapshot built under a superseded toolchain."""
    existing_id = uuid4()
    codebase_id = uuid4()
    old_env_digest = "sha256:" + "0" * 64

    def on_execute(sql: str, params: tuple[object, ...]) -> tuple[object, ...] | None:
        if sql.strip().startswith("SELECT id, env_digest FROM snapshots"):
            # The adapter must filter on the CURRENT env_digest, not just
            # (org, codebase, commit) — this row under the OLD digest is
            # correctly never matched by that filter.
            if params == (_ORG_A, str(codebase_id), "a" * 40, old_env_digest):
                return (str(existing_id), old_env_digest)
            return None
        return None

    conn = _FakeConnection(on_execute=on_execute)
    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)  # NEW/current digest
    port = SqlSnapshotPort(connection_factory=_factory_for(conn), snapshot_service=service)

    resolution = port.resolve_or_create(org_id=_ORG_A, codebase_id=codebase_id, commit_sha="a" * 40)

    assert resolution.snapshot_id != existing_id  # freshly minted, not the stale row
    assert resolution.env_digest == _FAKE_ENV_DIGEST
    received = service.queue.receive()
    assert received is not None  # the create path genuinely ran


def test_sql_snapshot_port_creates_via_snapshot_service_when_absent() -> None:
    """No matching row: delegates to SnapshotService.create_snapshot (mint +
    enqueue) and returns ITS (snapshot_id, env_digest), never writing a row
    itself (the snapshots row cannot exist until the SNAP-05 worker completes
    it — see SqlSnapshotPort's docstring)."""
    codebase_id = uuid4()
    conn = _FakeConnection(on_execute=lambda sql, p: None)  # no existing row
    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)
    port = SqlSnapshotPort(connection_factory=_factory_for(conn), snapshot_service=service)

    resolution = port.resolve_or_create(org_id=_ORG_A, codebase_id=codebase_id, commit_sha="b" * 40)

    assert resolution.env_digest == _FAKE_ENV_DIGEST
    # SnapshotService enqueued exactly one job for the minted snapshot_id.
    received = service.queue.receive()
    assert received is not None
    assert received.message.body["snapshot_id"] == str(resolution.snapshot_id)
    assert received.message.body["codebase_id"] == str(codebase_id)
    assert service.queue.receive() is None  # exactly one job, not more


def test_sql_snapshot_port_binds_org_id_before_the_select() -> None:
    """The three SET LOCAL set_config binds (acquire_for_request) precede the
    adapter's own SELECT, and the SELECT is explicitly scoped to org_id — the
    RLS-binding + explicit-predicate belt-and-suspenders the module documents."""
    codebase_id = uuid4()
    conn = _FakeConnection(on_execute=lambda sql, p: None)
    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)
    port = SqlSnapshotPort(connection_factory=_factory_for(conn), snapshot_service=service)

    port.resolve_or_create(org_id=_ORG_A, codebase_id=codebase_id, commit_sha="c" * 40)

    set_config_calls = [c for c in conn.calls if "set_config" in c.sql]
    assert len(set_config_calls) == 3  # app.org_id, app.user_id, app.role
    assert set_config_calls[0].params[0] == "app.org_id"
    assert set_config_calls[0].params[1] == _ORG_A
    select_calls = [c for c in conn.calls if c.sql.strip().startswith("SELECT id, env_digest")]
    assert len(select_calls) == 1
    assert select_calls[0].params[0] == _ORG_A
    # The three binds happened strictly BEFORE the SELECT (index order).
    assert conn.calls.index(set_config_calls[-1]) < conn.calls.index(select_calls[0])


def test_sql_snapshot_port_two_orgs_never_cross_read() -> None:
    """A row seeded under org A is never returned for an org-B lookup — the
    fake's on_execute enforces the org_id predicate exactly like real RLS
    would; this pins the adapter actually THREADS org_id into the WHERE
    clause (not just the RLS bind)."""
    codebase_id = uuid4()
    rows = {
        (_ORG_A, str(codebase_id), "d" * 40, _FAKE_ENV_DIGEST): (str(uuid4()), _FAKE_ENV_DIGEST)
    }

    def on_execute(sql: str, params: tuple[object, ...]) -> tuple[object, ...] | None:
        if sql.strip().startswith("SELECT id, env_digest FROM snapshots"):
            return rows.get(params)
        return None

    conn = _FakeConnection(on_execute=on_execute)
    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)
    port = SqlSnapshotPort(connection_factory=_factory_for(conn), snapshot_service=service)

    org_b_resolution = port.resolve_or_create(
        org_id=_ORG_B, codebase_id=codebase_id, commit_sha="d" * 40
    )

    # org B got a FRESH snapshot (service-minted), not org A's row.
    assert str(org_b_resolution.snapshot_id) not in {v[0] for v in rows.values()}


# --------------------------------------------------------------------------- #
# SqlSpecRegistryPort
# --------------------------------------------------------------------------- #


def test_sql_spec_registry_is_structural_spec_registry_port() -> None:
    conn = _FakeConnection(on_execute=lambda s, p: None)
    port = SqlSpecRegistryPort(connection_factory=_factory_for(conn))
    assert isinstance(port, SpecRegistryPort)


def test_sql_spec_registry_resolve_latest_returns_none_when_empty() -> None:
    conn = _FakeConnection(on_execute=lambda sql, p: None)
    port = SqlSpecRegistryPort(connection_factory=_factory_for(conn))
    assert port.resolve_latest() is None
    assert conn.commits == 1


def test_sql_spec_registry_resolve_latest_returns_row_value() -> None:
    conn = _FakeConnection(on_execute=lambda sql, p: ("2.7.0",))
    port = SqlSpecRegistryPort(connection_factory=_factory_for(conn))
    assert port.resolve_latest() == "2.7.0"


def test_sql_spec_registry_is_registered_true_and_false() -> None:
    def on_execute(sql: str, params: tuple[object, ...]) -> tuple[object, ...] | None:
        return (1,) if params == ("2.7.0",) else None

    conn = _FakeConnection(on_execute=on_execute)
    port = SqlSpecRegistryPort(connection_factory=_factory_for(conn))
    assert port.is_registered("2.7.0") is True
    assert port.is_registered("9.9.9") is False


def test_sql_spec_registry_queries_are_scoped_to_global() -> None:
    conn = _FakeConnection(on_execute=lambda sql, p: None)
    port = SqlSpecRegistryPort(connection_factory=_factory_for(conn))
    port.resolve_latest()
    port.is_registered("1.0.0")
    assert all("scope = 'global'" in c.sql for c in conn.calls)


# --------------------------------------------------------------------------- #
# SecretsManagerHmacKeyIssuer
# --------------------------------------------------------------------------- #


class _FakeSecretsManagerExceptions:
    class ResourceNotFoundException(Exception):  # noqa: N818 — mirrors the boto3 exception name
        pass


@dataclass
class _FakeSecretsManagerClient:
    """Minimal boto3-secretsmanager-shaped fake: create_secret/get_secret_value."""

    exceptions: Any = field(default_factory=lambda: _FakeSecretsManagerExceptions())
    _secrets: dict[str, bytes] = field(default_factory=dict)

    def create_secret(self, *, Name: str, SecretBinary: bytes, **_kw: object) -> None:  # noqa: N803
        self._secrets[Name] = SecretBinary

    def get_secret_value(self, *, SecretId: str) -> dict[str, bytes]:  # noqa: N803
        if SecretId not in self._secrets:
            raise self.exceptions.ResourceNotFoundException()
        return {"SecretBinary": self._secrets[SecretId]}


def test_secrets_manager_hmac_issuer_is_structural_hmac_key_issuer() -> None:
    issuer = SecretsManagerHmacKeyIssuer(client=_FakeSecretsManagerClient())
    assert isinstance(issuer, HmacKeyIssuer)


def test_secrets_manager_hmac_issuer_round_trip() -> None:
    client = _FakeSecretsManagerClient()
    issuer = SecretsManagerHmacKeyIssuer(client=client)
    job_id, scan_id = uuid4(), uuid4()

    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)

    assert len(secret) == 32
    looked_up = issuer.lookup(job_id=job_id, key_id=key_id)
    assert looked_up == secret


def test_secrets_manager_hmac_issuer_unknown_key_id_returns_none_fail_closed() -> None:
    client = _FakeSecretsManagerClient()
    issuer = SecretsManagerHmacKeyIssuer(client=client)
    job_id, scan_id = uuid4(), uuid4()
    issuer.issue(job_id=job_id, scan_id=scan_id)

    assert issuer.lookup(job_id=job_id, key_id="k-not-a-real-key") is None
    assert issuer.lookup(job_id=uuid4(), key_id="k-not-a-real-key") is None


def test_secrets_manager_hmac_issuer_two_jobs_get_independent_secrets() -> None:
    client = _FakeSecretsManagerClient()
    issuer = SecretsManagerHmacKeyIssuer(client=client)
    scan_id = uuid4()
    job_a, job_b = uuid4(), uuid4()

    key_a, secret_a = issuer.issue(job_id=job_a, scan_id=scan_id)
    key_b, secret_b = issuer.issue(job_id=job_b, scan_id=scan_id)

    assert secret_a != secret_b
    # job A's key_id does not resolve under job B's namespace (fail closed).
    assert issuer.lookup(job_id=job_b, key_id=key_a) is None
    assert issuer.lookup(job_id=job_a, key_id=key_b) is None


# --------------------------------------------------------------------------- #
# SqlJobStateStore — DOC-API §4.5 state machine parity with InMemoryJobStateStore
# --------------------------------------------------------------------------- #


@dataclass
class _FakeJobsConnection:
    """Simulates the (not-yet-shipped) ``jobs`` table well enough to drive
    SqlJobStateStore's exact three statement shapes: ``SELECT ... FOR UPDATE``,
    ``INSERT``, ``UPDATE``. A real lock/isolation falsifier needs real
    Postgres — see tests/integration/test_orch01_sql_adapters.py.
    """

    rows: dict[str, tuple[str, str]] = field(default_factory=dict)
    calls: list[_RecordedCall] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    _pending: tuple[object, ...] | None = None

    def cursor(self) -> _FakeJobsCursor:
        return _FakeJobsCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


@dataclass
class _FakeJobsCursor:
    _conn: _FakeJobsConnection

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._conn.calls.append(_RecordedCall(sql=sql, params=params))
        text = sql.strip()
        if text.startswith("SELECT status FROM jobs"):
            (job_id,) = params
            row = self._conn.rows.get(job_id)
            self._conn._pending = row if row is None else (row[0],)
        elif text.startswith("INSERT INTO jobs"):
            job_id, status, sha = params
            self._conn.rows[job_id] = (status, sha)
        elif text.startswith("UPDATE jobs"):
            status, sha, job_id = params
            self._conn.rows[job_id] = (status, sha)
        else:
            raise AssertionError(f"unexpected SQL in fake jobs table: {sql!r}")

    def fetchone(self) -> tuple[object, ...] | None:
        return self._conn._pending

    def close(self) -> None:
        pass


def test_sql_job_state_store_is_structural_job_state_store() -> None:
    store = SqlJobStateStore(connection_factory=_factory_for(_FakeJobsConnection()))
    assert isinstance(store, JobStateStore)


def test_sql_job_state_store_no_prior_state_is_applied() -> None:
    conn = _FakeJobsConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))
    job_id = uuid4()

    outcome = store.transition(job_id=job_id, status="running", body_sha256="sha-1")

    assert outcome == "applied"
    assert conn.rows[str(job_id)] == ("running", "sha-1")
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_sql_job_state_store_same_status_replay_is_duplicate_and_not_overwritten() -> None:
    conn = _FakeJobsConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))
    job_id = uuid4()
    store.transition(job_id=job_id, status="done", body_sha256="sha-1")

    outcome = store.transition(job_id=job_id, status="done", body_sha256="sha-1-replay")

    assert outcome == "duplicate"
    # NOT overwritten — the original body_sha256 is still recorded.
    assert conn.rows[str(job_id)] == ("done", "sha-1")


def test_sql_job_state_store_running_to_done_is_applied() -> None:
    conn = _FakeJobsConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))
    job_id = uuid4()
    store.transition(job_id=job_id, status="running", body_sha256="sha-0")

    outcome = store.transition(job_id=job_id, status="done", body_sha256="sha-1")

    assert outcome == "applied"
    assert conn.rows[str(job_id)] == ("done", "sha-1")


def test_sql_job_state_store_running_to_failed_is_applied() -> None:
    conn = _FakeJobsConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))
    job_id = uuid4()
    store.transition(job_id=job_id, status="running", body_sha256="sha-0")

    outcome = store.transition(job_id=job_id, status="failed", body_sha256="sha-1")

    assert outcome == "applied"
    assert conn.rows[str(job_id)] == ("failed", "sha-1")


def test_sql_job_state_store_terminal_to_different_status_is_conflict() -> None:
    conn = _FakeJobsConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))
    job_id = uuid4()
    store.transition(job_id=job_id, status="done", body_sha256="sha-1")

    outcome = store.transition(job_id=job_id, status="failed", body_sha256="sha-2")

    assert outcome == "conflict"
    # Never overwritten — "done" (the original, correct terminal state) stands.
    assert conn.rows[str(job_id)] == ("done", "sha-1")


@pytest.mark.parametrize(
    "sequence",
    [
        [("running", "s0")],
        [("running", "s0"), ("running", "s0")],
        [("running", "s0"), ("done", "s1"), ("done", "s1")],
        [("running", "s0"), ("done", "s1"), ("failed", "s2")],
        [("done", "s1")],
        [("done", "s1"), ("failed", "s2")],
    ],
)
def test_sql_job_state_store_matches_in_memory_state_machine_contract(
    sequence: list[tuple[str, str]],
) -> None:
    """SqlJobStateStore and InMemoryJobStateStore (services/scan/api.py) must
    produce IDENTICAL outcome sequences for the same input — they implement
    the same DOC-API §4.5 state machine over two different storage engines."""
    from services.scan.api import InMemoryJobStateStore

    in_memory = InMemoryJobStateStore()
    sql_store = SqlJobStateStore(connection_factory=_factory_for(_FakeJobsConnection()))
    job_id = uuid4()

    in_memory_outcomes = [
        in_memory.transition(job_id=job_id, status=status, body_sha256=sha)  # type: ignore[arg-type]
        for status, sha in sequence
    ]
    sql_outcomes = [
        sql_store.transition(job_id=job_id, status=status, body_sha256=sha)  # type: ignore[arg-type]
        for status, sha in sequence
    ]

    assert sql_outcomes == in_memory_outcomes


def test_sql_job_state_store_rolls_back_on_error_never_commits_partial_state() -> None:
    """A failure mid-transaction rolls back rather than leaving a half-applied
    row (fail-closed, mirrors acquire_for_request's own except/rollback)."""

    class _BoomCursor:
        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            raise RuntimeError("boom")

        def fetchone(self) -> None:
            return None

        def close(self) -> None:
            pass

    @dataclass
    class _BoomConnection:
        rollbacks: int = 0
        commits: int = 0

        def cursor(self) -> _BoomCursor:
            return _BoomCursor()

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

    conn = _BoomConnection()
    store = SqlJobStateStore(connection_factory=_factory_for(conn))

    with pytest.raises(RuntimeError, match="boom"):
        store.transition(job_id=uuid4(), status="running", body_sha256="x")

    assert conn.rollbacks == 1
    assert conn.commits == 0

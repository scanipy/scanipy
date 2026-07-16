"""Live-PostgreSQL / live-moto conformance for CMP-ORCH-01's SQL adapters.

Complements ``tests/unit/test_orch01_sql_adapters.py`` (fully hermetic, fake
DB-API2 / fake boto3). This file drives the SAME production adapters
(``services/scan/sql_adapters.py``) against:

  * a real PostgreSQL 16 at ``upgrade head`` (the shipped CP-03 Alembic
    schema — ``orgs``/``codebases``/``snapshots``/``spec_versions``) — proving
    the RLS-scoped SQL actually round-trips and actually isolates orgs, not
    just that the adapter calls the right Python methods on a fake;
  * a real ``moto`` Secrets Manager backend for
    :class:`~services.scan.sql_adapters.SecretsManagerHmacKeyIssuer`.

SCHEMA GAP (see ``services/scan/sql_adapters.py`` module docstring): the
``jobs`` table :class:`~services.scan.sql_adapters.SqlJobStateStore` targets
does not exist in ``db/migrations/versions/`` yet. The two ``SqlJobStateStore``
tests below create/drop a **test-local** table matching
``PROPOSED_JOBS_TABLE_DDL`` directly (plain ``CREATE TABLE`` / ``DROP TABLE``
in the test body) — this is NOT an Alembic migration and touches nothing under
``db/migrations/versions/`` (RULE-4: no migration authored without a CLAR).

Environment: every Postgres-backed test requires a live PostgreSQL 16 via
``SCANIPY_DATABASE_URL`` (mirrors ``tests/integration/test_cp_specs.py``'s
``test_cp01b_...`` pattern — same skip guard, same ``SET ROLE scanipy_app``
anti-vacuity discipline, since the CI/local superuser connection BYPASSES RLS
unconditionally and a test run as that superuser would be vacuous). When the
URL is absent (local sandbox with no Postgres) these tests SKIP rather than
asserting a false pass.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import pytest
from moto import mock_aws

from services.scan.sql_adapters import (
    PROPOSED_JOBS_TABLE_DDL,
    SecretsManagerHmacKeyIssuer,
    SqlJobStateStore,
    SqlSnapshotPort,
    SqlSpecRegistryPort,
    psycopg2_connection_factory,
)
from services.snapshot.service import SnapshotService

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FAKE_ENV_DIGEST = "sha256:" + "e" * 64
_REGION = "us-east-1"


def _alembic(command: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "SCANIPY_DATABASE_URL": database_url}
    return subprocess.run(
        ["alembic", *command],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_database_url() -> str:
    database_url = os.environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "SCANIPY_DATABASE_URL not configured — live PostgreSQL 16 integration "
            "env gap; this suite runs in the CI integration-tests job."
        )
    return database_url


def _app_role_connection_factory(dsn: str) -> Any:
    """A test-only connection factory: opens as the DB owner/superuser (the CI
    integration job's connection identity) then ``SET ROLE scanipy_app`` —
    the NOBYPASSRLS request-path role — so RLS is actually enforced. Without
    this, every query would run as the superuser, which unconditionally
    BYPASSes RLS regardless of FORCE ROW LEVEL SECURITY, making any isolation
    assertion vacuous (identical anti-vacuity rationale as
    ``test_cp01b_acquire_for_request_rebinds_recycled_pooled_connection`` /
    ``test_cp03b_*`` in ``tests/integration/test_cp_specs.py``).
    """
    import psycopg2

    @contextmanager
    def _factory() -> Iterator[Any]:
        conn = psycopg2.connect(dsn)
        with conn.cursor() as cur:
            cur.execute("SET ROLE scanipy_app;")
        conn.commit()  # persist SET ROLE at session scope (it is not transaction-local)
        try:
            yield conn
        finally:
            conn.close()

    return _factory


@pytest.fixture()
def live_pg_schema() -> Iterator[str]:
    """Fresh ``upgrade head`` schema on the live Postgres, torn down after."""
    database_url = _require_database_url()
    base = _alembic(["downgrade", "base"], database_url)
    assert base.returncode == 0, f"pre-test downgrade failed:\n{base.stderr}"
    up = _alembic(["upgrade", "head"], database_url)
    assert up.returncode == 0, f"alembic upgrade head failed:\n{up.stderr}"
    try:
        yield database_url
    finally:
        _alembic(["downgrade", "base"], database_url)


def _seed_org(database_url: str, *, org_id: str) -> None:
    import psycopg2

    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO orgs (id, name) VALUES (%s, %s);", (org_id, f"org-{org_id[:8]}")
            )
    conn.close()


def _seed_codebase(database_url: str, *, org_id: str, codebase_id: str) -> None:
    import psycopg2

    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO codebases (id, org_id, name, scm_provider, scm_repo_url) "
                "VALUES (%s, %s, %s, 'github', %s);",
                (
                    codebase_id,
                    org_id,
                    f"cb-{codebase_id[:8]}",
                    f"https://github.com/x/{codebase_id[:8]}",
                ),
            )
    conn.close()


def _seed_org_and_codebase(database_url: str, *, org_id: str, codebase_id: str) -> None:
    _seed_org(database_url, org_id=org_id)
    _seed_codebase(database_url, org_id=org_id, codebase_id=codebase_id)


def _seed_snapshot(
    database_url: str,
    *,
    org_id: str,
    codebase_id: str,
    commit_sha: str,
    env_digest: str,
) -> str:
    """Seed a fully-populated ``snapshots`` row (as the SNAP-05 worker would
    via ``record_completion``) — returns the minted snapshot id."""
    import psycopg2

    snapshot_id = str(uuid4())
    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO snapshots (
                    id, org_id, codebase_id, commit_sha, env_digest,
                    precondition_status, cpg_tarball_uri, reverse_symbol_index_uri,
                    dynamic_call_graph_uri, precondition_status_record_uri
                ) VALUES (%s, %s, %s, %s, %s, 'closed-world', 'u1', 'u2', 'u3', 'u4');
                """,
                (snapshot_id, org_id, codebase_id, commit_sha, env_digest),
            )
    conn.close()
    return snapshot_id


# --------------------------------------------------------------------------- #
# SqlSnapshotPort — real dedup + real cross-org RLS isolation
# --------------------------------------------------------------------------- #


def test_sql_snapshot_port_dedup_hit_and_cross_org_isolation(live_pg_schema: str) -> None:
    """(1) A matching (org, codebase, commit) row is returned verbatim (dedup).
    (2) The SAME commit_sha under a DIFFERENT org is invisible — RLS denies the
    cross-org read, so it falls to the CREATE path and mints a genuinely new
    snapshot (never leaking org A's row to org B)."""
    database_url = live_pg_schema
    org_a, org_b = str(uuid4()), str(uuid4())
    codebase_a = str(uuid4())
    commit_sha = "a" * 40

    # org B deliberately gets NO `codebases`/`orgs` row of its own: neither the
    # RLS bind nor the adapter's SELECT is FK-constrained on read, and the
    # miss path (SnapshotService.create_snapshot) never inserts into either
    # table — so this is not needed to exercise the isolation this test pins.
    # (A real `codebases.id` PRIMARY KEY means org B could never legitimately
    # own a row with the SAME id as org A's codebase anyway.)
    _seed_org_and_codebase(database_url, org_id=org_a, codebase_id=codebase_a)
    seeded_id = _seed_snapshot(
        database_url,
        org_id=org_a,
        codebase_id=codebase_a,
        commit_sha=commit_sha,
        env_digest=_FAKE_ENV_DIGEST,
    )

    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)
    port = SqlSnapshotPort(
        connection_factory=_app_role_connection_factory(database_url),
        snapshot_service=service,
    )

    # (1) dedup hit under org A.
    from uuid import UUID

    hit = port.resolve_or_create(org_id=org_a, codebase_id=UUID(codebase_a), commit_sha=commit_sha)
    assert str(hit.snapshot_id) == seeded_id
    assert hit.env_digest == _FAKE_ENV_DIGEST
    assert service.queue.receive() is None  # dedup never enqueued a create job

    # (2) same codebase_id + same commit_sha, but org B — RLS-invisible, so a
    # FRESH snapshot is minted; org B never observes org A's row.
    miss = port.resolve_or_create(org_id=org_b, codebase_id=UUID(codebase_a), commit_sha=commit_sha)
    assert str(miss.snapshot_id) != seeded_id
    received = service.queue.receive()
    assert received is not None
    assert received.message.body["snapshot_id"] == str(miss.snapshot_id)


def test_sql_snapshot_port_natural_key_requires_exact_codebase_match(live_pg_schema: str) -> None:
    """A different ``codebase_id`` under the SAME org + commit_sha is also a
    miss (the natural key is the full triple, not just (org, commit))."""
    database_url = live_pg_schema
    org_a = str(uuid4())
    codebase_1, codebase_2 = str(uuid4()), str(uuid4())
    commit_sha = "b" * 40

    _seed_org(database_url, org_id=org_a)
    _seed_codebase(database_url, org_id=org_a, codebase_id=codebase_1)
    _seed_codebase(database_url, org_id=org_a, codebase_id=codebase_2)
    seeded_id = _seed_snapshot(
        database_url,
        org_id=org_a,
        codebase_id=codebase_1,
        commit_sha=commit_sha,
        env_digest=_FAKE_ENV_DIGEST,
    )

    from uuid import UUID

    service = SnapshotService(env_digest_provider=lambda: _FAKE_ENV_DIGEST)
    port = SqlSnapshotPort(
        connection_factory=_app_role_connection_factory(database_url),
        snapshot_service=service,
    )

    miss = port.resolve_or_create(org_id=org_a, codebase_id=UUID(codebase_2), commit_sha=commit_sha)
    assert str(miss.snapshot_id) != seeded_id


def test_sql_snapshot_port_env_rollover_mints_fresh_snapshot(live_pg_schema: str) -> None:
    """A row seeded under an OLD env_digest is never dedup-matched once the
    pinned Env has rolled over — against REAL Postgres, not just the hermetic
    fake (this closes the exact gap a WHERE clause missing ``env_digest``
    would silently reintroduce)."""
    database_url = live_pg_schema
    org_a = str(uuid4())
    codebase_id = str(uuid4())
    commit_sha = "f" * 40
    old_env_digest = "sha256:" + "0" * 64
    new_env_digest = "sha256:" + "1" * 64

    _seed_org(database_url, org_id=org_a)
    _seed_codebase(database_url, org_id=org_a, codebase_id=codebase_id)
    stale_id = _seed_snapshot(
        database_url,
        org_id=org_a,
        codebase_id=codebase_id,
        commit_sha=commit_sha,
        env_digest=old_env_digest,
    )

    from uuid import UUID

    service = SnapshotService(env_digest_provider=lambda: new_env_digest)
    port = SqlSnapshotPort(
        connection_factory=_app_role_connection_factory(database_url),
        snapshot_service=service,
    )

    resolution = port.resolve_or_create(
        org_id=org_a, codebase_id=UUID(codebase_id), commit_sha=commit_sha
    )

    assert str(resolution.snapshot_id) != stale_id
    assert resolution.env_digest == new_env_digest
    received = service.queue.receive()
    assert received is not None  # the create path genuinely ran


# --------------------------------------------------------------------------- #
# SqlSpecRegistryPort — real spec_versions resolution, global-scope only
# --------------------------------------------------------------------------- #


def test_sql_spec_registry_resolves_latest_global_and_excludes_customer_scope(
    live_pg_schema: str,
) -> None:
    database_url = live_pg_schema
    org_a = str(uuid4())
    import psycopg2

    _seed_org_and_codebase(database_url, org_id=org_a, codebase_id=str(uuid4()))
    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO spec_versions (org_id, "S_version", scope, spec_set, created_at)
                   VALUES (NULL, '1.0.0', 'global', '{}'::jsonb, now() - interval '1 hour');"""
            )
            cur.execute(
                """INSERT INTO spec_versions (org_id, "S_version", scope, spec_set, created_at)
                   VALUES (NULL, '2.7.0', 'global', '{}'::jsonb, now());"""
            )
            # A customer-scoped row with a version that would otherwise sort
            # latest by string value — must NEVER be resolved/registered by
            # this adapter (it is intentionally global-scope only).
            cur.execute(
                """INSERT INTO spec_versions (org_id, "S_version", scope, spec_set, created_at)
                   VALUES (%s, '9.9.9', 'customer', '{}'::jsonb, now() + interval '1 hour');""",
                (org_a,),
            )
    conn.close()

    port = SqlSpecRegistryPort(connection_factory=_app_role_connection_factory(database_url))

    assert port.resolve_latest() == "2.7.0"
    assert port.is_registered("1.0.0") is True
    assert port.is_registered("2.7.0") is True
    assert port.is_registered("9.9.9") is False  # customer-scoped — excluded
    assert port.is_registered("0.0.1") is False  # never registered at all


# --------------------------------------------------------------------------- #
# SqlJobStateStore — CAS state machine + the row-lock concurrency falsifier
# --------------------------------------------------------------------------- #


@pytest.fixture()
def live_jobs_table(live_pg_schema: str) -> Iterator[str]:
    """A test-local ``jobs`` table (see module docstring — SCHEMA GAP, no
    migration authored). Created/dropped directly by this fixture, never
    touching ``db/migrations/versions/``."""
    import psycopg2

    database_url = live_pg_schema
    with psycopg2.connect(database_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Defensive: `jobs` is NOT alembic-managed (live_pg_schema's
            # downgrade/upgrade cycle never touches it), so a prior run that
            # crashed before its own teardown could leave one behind.
            cur.execute("DROP TABLE IF EXISTS jobs;")
            cur.execute(PROPOSED_JOBS_TABLE_DDL)
    conn.close()
    try:
        yield database_url
    finally:
        with psycopg2.connect(database_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS jobs;")
        conn.close()


def test_sql_job_state_store_cas_state_machine_matches_in_memory_contract(
    live_jobs_table: str,
) -> None:
    from services.scan.api import InMemoryJobStateStore

    database_url = live_jobs_table
    store = SqlJobStateStore(connection_factory=psycopg2_connection_factory(database_url))
    in_memory = InMemoryJobStateStore()
    job_id = uuid4()

    sequence = [
        ("running", "s0"),
        ("running", "s0"),  # duplicate heartbeat
        ("done", "s1"),  # applied
        ("done", "s1"),  # duplicate terminal replay
        ("failed", "s2"),  # conflict — terminal already "done"
    ]

    for status, sha in sequence:
        sql_outcome = store.transition(job_id=job_id, status=status, body_sha256=sha)  # type: ignore[arg-type]
        mem_outcome = in_memory.transition(job_id=job_id, status=status, body_sha256=sha)  # type: ignore[arg-type]
        assert sql_outcome == mem_outcome, f"diverged at ({status!r}, {sha!r})"


def test_sql_job_state_store_concurrent_callbacks_row_lock_serializes(
    live_jobs_table: str,
) -> None:
    """FALSIFIER: two connections racing a transition for the SAME job_id must
    never both observe the pre-transition state — the ``SELECT ... FOR UPDATE``
    row lock must serialize them. Deterministic (not scheduler-luck-dependent):
    thread A is guaranteed to acquire the lock first (the main thread waits on
    an event set the instant A's lock-acquiring statement returns) and holds it
    for a fixed delay before committing; thread B's own lock-acquiring
    statement is only ISSUED after that event fires, so it genuinely blocks at
    the Postgres level until A commits.

    NEGATIVE CONTROL this proves against: a naive read-then-write
    implementation (SELECT without FOR UPDATE, decide in Python, then INSERT/
    UPDATE) would let both threads read "running" concurrently and both apply
    a transition — corrupting the state machine (two "applied" outcomes for
    what §4.5 defines as a single valid terminal transition). This test fails
    under that broken implementation and passes under the shipped
    ``SELECT ... FOR UPDATE`` one.
    """
    import psycopg2

    database_url = live_jobs_table
    job_id = uuid4()
    seed_store = SqlJobStateStore(connection_factory=psycopg2_connection_factory(database_url))
    assert seed_store.transition(job_id=job_id, status="running", body_sha256="s0") == "applied"

    lock_acquired = threading.Event()
    outcomes: dict[str, str] = {}
    errors: list[BaseException] = []

    def _delayed_factory(delay_seconds: float) -> Any:
        @contextmanager
        def _factory() -> Iterator[Any]:
            conn = psycopg2.connect(database_url)
            try:
                yield _DelayedConnection(conn, delay_seconds, lock_acquired)
            finally:
                conn.close()

        return _factory

    def _run(who: str, status: str, delay_seconds: float, wait_for_lock_event: bool) -> None:
        try:
            if wait_for_lock_event:
                lock_acquired.wait(timeout=5.0)
            store = SqlJobStateStore(connection_factory=_delayed_factory(delay_seconds))
            outcomes[who] = store.transition(job_id=job_id, status=status, body_sha256=f"sha-{who}")
        except BaseException as exc:
            errors.append(exc)

    thread_a = threading.Thread(target=_run, args=("a", "done", 0.4, False))
    thread_b = threading.Thread(target=_run, args=("b", "failed", 0.0, True))
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10.0)
    thread_b.join(timeout=10.0)

    assert not errors, f"unexpected error(s) in race threads: {errors}"
    assert set(outcomes) == {"a", "b"}
    # A always wins the race (guaranteed first lock acquisition); B's SELECT
    # FOR UPDATE was blocked until A committed, so B necessarily observes the
    # POST-A state ("done") when it finally proceeds — running->failed off a
    # "done" prior is a forbidden transition -> conflict, never "applied".
    assert outcomes["a"] == "applied"
    assert outcomes["b"] == "conflict"

    final = seed_store.transition(job_id=job_id, status="done", body_sha256="sha-a")
    assert final == "duplicate"  # the row genuinely holds "done" — B never overwrote it


@dataclass
class _DelayedCursor:
    _real: Any
    _delay_seconds: float
    _lock_acquired: threading.Event

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._real.execute(sql, params)
        if "FOR UPDATE" in sql:
            # The row lock is held server-side the instant this statement
            # returns — signal the other thread, THEN sleep while still
            # holding it (transaction not yet committed).
            self._lock_acquired.set()
            if self._delay_seconds:
                time.sleep(self._delay_seconds)

    def fetchone(self) -> tuple[object, ...] | None:
        return self._real.fetchone()  # type: ignore[no-any-return]

    def close(self) -> None:
        self._real.close()


@dataclass
class _DelayedConnection:
    """Wraps a REAL psycopg2 connection; used only to widen the row-lock hold
    window deterministically for the concurrency falsifier above. Delegates
    everything to the real connection except cursor(), which returns a
    delaying proxy around the real cursor."""

    _real: Any
    _delay_seconds: float
    _lock_acquired: threading.Event

    def cursor(self) -> _DelayedCursor:
        return _DelayedCursor(self._real.cursor(), self._delay_seconds, self._lock_acquired)

    def commit(self) -> None:
        self._real.commit()

    def rollback(self) -> None:
        self._real.rollback()


# --------------------------------------------------------------------------- #
# SecretsManagerHmacKeyIssuer — real moto Secrets Manager
# --------------------------------------------------------------------------- #


@pytest.fixture()
def moto_env() -> Iterator[None]:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", _REGION)
    with mock_aws():
        yield


def test_secrets_manager_hmac_issuer_round_trip_against_real_moto(moto_env: None) -> None:
    client = boto3.client("secretsmanager", region_name=_REGION)
    issuer = SecretsManagerHmacKeyIssuer(client=client)
    job_id, scan_id = uuid4(), uuid4()

    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    assert len(secret) == 32

    looked_up = issuer.lookup(job_id=job_id, key_id=key_id)
    assert looked_up == secret

    # Fail-closed: an unrelated job_id sees nothing, even with the right
    # key_id string (the resource name folds in job_id).
    assert issuer.lookup(job_id=uuid4(), key_id=key_id) is None


def test_secrets_manager_hmac_issuer_is_structural_hmac_key_issuer_live(moto_env: None) -> None:
    from services.scan.api import HmacKeyIssuer

    client = boto3.client("secretsmanager", region_name=_REGION)
    issuer = SecretsManagerHmacKeyIssuer(client=client)
    assert isinstance(issuer, HmacKeyIssuer)

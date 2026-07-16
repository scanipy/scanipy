# ruff: noqa: N803
#   ``S_version`` keeps its capital S throughout (normative provenance field
#   name, INV-2) on :meth:`SqlSpecRegistryPort.is_registered`, matching the
#   ``SpecRegistryPort`` Protocol it implements (``services/scan/api.py``).
#   Suppressed file-wide rather than per-parameter (same precedent as
#   ``services/scan/api.py`` / ``services/scan/worker.py``).
"""CMP-ORCH-01 — real SQL-backed adapters for the build-ahead ports (Track 1D).

``services/scan/api.py`` defines four build-ahead seams whose production
defaults fail closed (``fail_closed_snapshot_port`` / ``fail_closed_spec_registry``
/ ``fail_closed_hmac_key_issuer``) plus the explicitly non-durable
``InMemoryJobStateStore`` (its own docstring: "the Postgres compare-and-set
implementation is REQUIRED before the API ECS service runs more than one
task"). This module supplies the real adapters:

  * :class:`SqlSnapshotPort` — a ``SnapshotPort`` (CMP-SNAP-01 natural-key-dedup
    seam) over the real ``snapshots`` table (DOC-DB §4.7) via
    ``db/session.py::acquire_for_request``.
  * :class:`SqlSpecRegistryPort` — a ``SpecRegistryPort`` (INV-3 fence) over the
    real ``spec_versions`` table (DOC-DB §4.9).
  * :class:`SecretsManagerHmacKeyIssuer` — an ``HmacKeyIssuer`` (DOC-API §2.3)
    backed by AWS Secrets Manager, mirroring the ``S3ObjectStore`` lazy-boto3
    pattern (``services/substrate/object_store.py``).
  * :class:`SqlJobStateStore` — a durable Postgres compare-and-set
    ``JobStateStore`` (DOC-API §4.5 state machine; CLAR-DEPLOY-19 condition C-2)
    implementing the SAME state machine as ``InMemoryJobStateStore`` but
    surviving an API-service restart / horizontal scale-out.

SCHEMA GAP (reported, not invented — RULE-4): the ``jobs`` table
:class:`SqlJobStateStore` targets does **not** exist in
``db/migrations/versions/`` today. No migration is authored here (RULE-4 /
``.claude/rules/03-scope.md``: "do not invent a migration without a CLAR").
:data:`PROPOSED_JOBS_TABLE_DDL` documents the exact minimal shape the CAS logic
below assumes, so the eventual migration can copy it verbatim once a CLAR
ratifies it (see this PR's report for the exact ``new_clar_requests`` text).
Until that migration lands, :class:`SqlJobStateStore` is real, tested code with
no production table to point at — production wiring stays on
``InMemoryJobStateStore`` (or a future adapter once the table exists).

RLS / provenance note (RULE-6, ``.claude/rules/02-provenance.md``): this module
emits no findings — it is a pure port-adapter layer over ``scans``-adjacent
control tables (``snapshots``, ``spec_versions``, a not-yet-shipped ``jobs``
table). None of the four RULE-6 finding-level fields apply here; the INV-2
field it DOES thread (``env_digest`` read verbatim off the resolved/created
snapshot row, never re-derived) matches ``SnapshotResolution``'s existing
contract in ``services/scan/api.py``.

Every adapter is **framework-light** (mirrors ``db/session.py``'s hard
constraint): psycopg2 and boto3 are imported lazily, at call time on the
production path only, so a hermetic unit test that injects a fake connection
factory / fake boto3-shaped client needs neither installed.
"""

from __future__ import annotations

import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable
from uuid import UUID, uuid4

from db.session import acquire_for_request

from services.control_plane.constants import SCANNER_USER_ID
from services.scan.api import JobStatus, SnapshotResolution, TransitionOutcome
from services.snapshot.service import SnapshotRequest, SnapshotService

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager


@runtime_checkable
class _DbApiCursor(Protocol):
    """DB-API 2.0 cursor surface these adapters use: ``db.session.Cursor`` PLUS
    ``fetchone`` (needed to read query results back; ``acquire_for_request``'s
    own ``Cursor`` Protocol deliberately omits it since the RLS-binding seam
    never reads rows). A structural superset of ``db.session.Cursor``, so any
    connection satisfying THIS Protocol also satisfies that narrower one — the
    same object can be passed into ``acquire_for_request``.
    """

    def execute(self, sql: str, params: tuple[object, ...] = ..., /) -> object: ...

    def fetchone(self) -> tuple[object, ...] | None: ...

    def close(self) -> None: ...


@runtime_checkable
class Connection(Protocol):
    """DB-API 2.0 connection surface these adapters use (``db.session.Connection``
    PLUS a ``fetchone``-capable cursor). Real psycopg2 connections satisfy this
    structurally, as does any other DB-API driver and the in-test fake.
    """

    def cursor(self) -> _DbApiCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


if TYPE_CHECKING:
    # A per-call connection acquisition seam: production wires
    # :func:`psycopg2_connection_factory`; tests inject a fake DB-API2 double.
    # Structurally compatible with the ``connection_factory`` kwarg
    # ``services/scan/http/app.py::create_app`` already threads (same alias
    # shape), even though these adapters are self-contained and do not depend
    # on that HTTP-layer wiring (see module docstring "framework-light").
    ConnectionFactory = Callable[[], AbstractContextManager[Connection]]

# ---------------------------------------------------------------------------
# Shared: a per-call psycopg2 connection factory (lazy import)
# ---------------------------------------------------------------------------


def psycopg2_connection_factory(dsn: str) -> ConnectionFactory:
    """Build a :data:`ConnectionFactory` that opens+closes a psycopg2 connection.

    Each call opens a **fresh** non-autocommit connection (the ``acquire_for_request``
    contract requires non-autocommit — see ``db/session.py``) and closes it on
    context exit, regardless of outcome. This is the simplest correct pool-of-
    one adapter; a real connection pool (pgbouncer / psycopg2.pool) is a future
    substrate concern, not invented here (RULE-4) since none of Track 1D's
    hermetic tests need one and the "do not add new heavy deps" constraint
    (``db/session.py`` module docstring) argues against introducing a pooling
    library for this PR.

    ``psycopg2`` is imported **inside** the returned factory (never at this
    module's top level), mirroring ``S3ObjectStore``'s lazy-boto3 pattern
    (``services/substrate/object_store.py:247-251``) — hermetic tests that
    inject their own fake factory never need psycopg2 installed.
    """

    @contextmanager
    def _factory() -> Iterator[Connection]:
        import psycopg2

        conn = psycopg2.connect(dsn)
        try:
            yield conn
        finally:
            conn.close()

    return _factory


# ---------------------------------------------------------------------------
# SqlSnapshotPort — CMP-SNAP-01 natural-key-dedup adapter (SnapshotPort seam)
# ---------------------------------------------------------------------------


@dataclass
class SqlSnapshotPort:
    """A ``SnapshotPort`` over the real ``snapshots`` table (DOC-DB §4.7).

    "resolve-or-create" (``services/scan/api.py::SnapshotPort`` docstring):
    the shipped :class:`~services.snapshot.service.SnapshotService.create_snapshot`
    always mints a fresh id and never writes a ``snapshots`` row itself (its own
    docstring: "No relational row is written here — the shipped schema's
    ``precondition_status`` is NOT NULL, so the row is inserted only once the
    worker reports the verdict" via ``record_completion``, owned by the
    CMP-SNAP-05 worker in a different Track). This adapter is exactly the
    "natural-key-dedup adapter... wired over it" the ``SnapshotPort`` docstring
    calls for:

      1. **Resolve**: a real SQL ``SELECT`` for an existing row keyed on
         ``(org_id, codebase_id, commit_sha, env_digest)`` — the FULL natural
         key, matching the shipped
         ``snapshots_codebase_commit_env_key UNIQUE (codebase_id, commit_sha,
         env_digest)`` constraint (DOC-DB §4.7) exactly. ``env_digest`` is
         resolved from the SAME ``SnapshotService.env_digest_provider`` the
         create path would use, BEFORE the lookup — dedup is scoped to "a
         snapshot for this commit under the CURRENTLY pinned Env", never a
         stale one. Omitting the ``env_digest`` filter would be a real bug: an
         Env rollover (worker image digest change) would otherwise dedup a
         fresh scan submission onto an OLD snapshot built under a superseded
         toolchain, threading a stale ``env_digest`` onto brand-new jobs
         (violates the "re-run under a fixed Env" spirit of INV-2). If found,
         ``(id, env_digest)`` is returned verbatim (INV-2: never re-derived).
      2. **Create** (no matching row under the current Env): delegates to the
         injected ``SnapshotService.create_snapshot`` — mints
         ``(snapshot_id, env_digest)`` synchronously (the same
         ``EnvDigestProvider``, re-resolved and re-guarded there; no snapshot
         row exists yet) and enqueues the CMP-SNAP-05 worker job that will
         eventually call ``record_completion`` and INSERT the row this
         adapter's own SELECT will find on the next submission for the same
         ``(commit, Env)``.

    RLS binding: the SELECT runs inside ``acquire_for_request`` bound to the
    caller's ``org_id`` (the only parameter the ``SnapshotPort.resolve_or_create``
    Protocol carries). ``user_id``/``role`` are fixed to the scanner machine
    identity purely to satisfy ``acquire_for_request``'s signature — the RLS
    predicates on every standard table (``migrations/.../0002``) key on
    ``org_id`` alone, so the exact ``user_id``/``role`` value threaded here does
    not affect isolation; the real caller identity was already checked by
    ``CPGuard`` upstream of this port.
    """

    connection_factory: ConnectionFactory
    snapshot_service: SnapshotService

    def resolve_or_create(
        self, *, org_id: str, codebase_id: UUID, commit_sha: str
    ) -> SnapshotResolution:
        existing = self._select_existing(
            org_id=org_id, codebase_id=codebase_id, commit_sha=commit_sha
        )
        if existing is not None:
            return existing
        accepted = self.snapshot_service.create_snapshot(
            SnapshotRequest(org_id=UUID(org_id), codebase_id=codebase_id, commit_sha=commit_sha)
        )
        return SnapshotResolution(snapshot_id=accepted.snapshot_id, env_digest=accepted.env_digest)

    def _select_existing(
        self, *, org_id: str, codebase_id: UUID, commit_sha: str
    ) -> SnapshotResolution | None:
        # Resolve the CURRENT env_digest the same way the create path would
        # (same provider) — an unresolvable digest here means dedup cannot be
        # scoped correctly, so we skip straight to the create path, which
        # re-resolves + fail-closed-guards it properly (INV-2).
        current_env_digest = self.snapshot_service.env_digest_provider()
        if current_env_digest is None:
            return None

        with self.connection_factory() as conn:
            with acquire_for_request(conn, org_id=org_id, user_id=SCANNER_USER_ID, role="scanner"):
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, env_digest FROM snapshots "
                    "WHERE org_id = %s AND codebase_id = %s AND commit_sha = %s "
                    "AND env_digest = %s ORDER BY created_at DESC LIMIT 1;",
                    (org_id, str(codebase_id), commit_sha, current_env_digest),
                )
                row = cur.fetchone()
        if row is None:
            return None
        snapshot_id, env_digest = row
        return SnapshotResolution(snapshot_id=UUID(str(snapshot_id)), env_digest=str(env_digest))


# ---------------------------------------------------------------------------
# SqlSpecRegistryPort — INV-3 fence adapter (SpecRegistryPort seam)
# ---------------------------------------------------------------------------


@dataclass
class SqlSpecRegistryPort:
    """A ``SpecRegistryPort`` over the real ``spec_versions`` table (DOC-DB §4.9).

    DOC-CMP-ORCH-01 §6 step 3's pseudocode sketches ``SELECT MAX(version) FROM
    spec_versions``. A literal ``MAX()`` over the ``"S_version"`` **text**
    column is lexicographic, not semver-aware (e.g. ``"10.0.0" < "9.0.0"``
    string-wise) — a real bug if implemented verbatim. This adapter instead
    resolves "latest accepted" as **most recently created** (``ORDER BY
    created_at DESC LIMIT 1``), which is a correct, disclosed reading of the
    doc's intent ("latest accepted") rather than a silent reinterpretation: the
    ``spec_versions`` table is INSERT-only per row (CMP-TRI-02 writes a new row
    per acceptance; DOC-DB §4.9), so insertion order and acceptance order
    coincide, and ``created_at DESC`` is the only tie-break available in the
    schema-as-shipped that is not vulnerable to the string-ordering bug. This
    is implementation-fidelity discretion, not an unspecified decision needing
    a CLAR (the alternative reading is a plain bug, not a legitimate design
    choice PLAN/SDD left open).

    SCOPE (``scope = 'global'``): every query here is explicitly filtered to
    ``scope = 'global'`` rows. Customer-scoped rows (``scope = 'customer'``)
    exist in the shipped schema but have no write path yet (CLAR-DB-05: the
    CMP-TRI-03 customer-revalidation persistence design is ratified but its
    production migration is still to be written) — resolving against them here
    would be untestable dead code, so this adapter is intentionally scoped to
    the global spec set only, matching what CMP-TRI-02 actually writes today.
    No ``acquire_for_request`` org binding is needed for these reads: the
    ``spec_versions`` RLS policy (``migrations/.../0002``) makes
    ``scope = 'global'`` rows universally visible regardless of whether
    ``app.org_id`` is bound — an explicit ``WHERE scope = 'global'`` in the SQL
    below is the actual enforcement (RLS is defense-in-depth here, not the
    primary correctness mechanism, since a future non-RLS-bound caller must
    still never see the wrong scope).
    """

    connection_factory: ConnectionFactory

    def resolve_latest(self) -> str | None:
        with self.connection_factory() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT "S_version" FROM spec_versions
                   WHERE scope = 'global' ORDER BY created_at DESC LIMIT 1;"""
            )
            row = cur.fetchone()
            conn.commit()
        return None if row is None else cast(str, row[0])

    def is_registered(self, S_version: str) -> bool:
        with self.connection_factory() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT 1 FROM spec_versions
                   WHERE scope = 'global' AND "S_version" = %s LIMIT 1;""",
                (S_version,),
            )
            row = cur.fetchone()
            conn.commit()
        return row is not None


# ---------------------------------------------------------------------------
# SecretsManagerHmacKeyIssuer — DOC-API §2.3 adapter (HmacKeyIssuer seam)
# ---------------------------------------------------------------------------


@dataclass
class SecretsManagerHmacKeyIssuer:
    """An ``HmacKeyIssuer`` backed by AWS Secrets Manager.

    Mints a fresh 32-byte secret per ``issue()`` call and stores it at a
    deterministic-from-``(job_id, key_id)`` Secrets Manager resource name; both
    ``job_id`` and the freshly-minted ``key_id`` are folded into the name so an
    unknown/wrong ``(job_id, key_id)`` pair on ``lookup()`` naturally 404s —
    the AWS-side fail-closed equivalent of ``FakeHmacKeyIssuer``'s dict miss
    (``tests/orch01_fakes.py``).

    ``client`` is any boto3-Secrets-Manager-shaped object (production
    ``boto3.client("secretsmanager")``, moto-backed or hand-written fake in
    tests). boto3 is imported lazily on the ``None`` path only, mirroring
    ``S3ObjectStore`` (``services/substrate/object_store.py:247-251``) —
    hermetic unit runs need no boto3 install.
    """

    prefix: str = "scanipy/hmac-jobs"
    client: Any = None

    def __post_init__(self) -> None:
        if self.client is None:  # pragma: no cover — real-AWS path; tests always inject
            import boto3

            self.client = boto3.client("secretsmanager")

    def issue(self, *, job_id: UUID, scan_id: UUID) -> tuple[str, bytes]:
        key_id = f"k-{uuid4().hex}"
        secret_bytes = secrets.token_bytes(32)
        self.client.create_secret(
            Name=self._secret_name(job_id, key_id),
            SecretBinary=secret_bytes,
            Description=f"scanipy per-job HMAC secret for scan_id={scan_id}",
        )
        return key_id, secret_bytes

    def lookup(self, *, job_id: UUID, key_id: str) -> bytes | None:
        try:
            response = self.client.get_secret_value(SecretId=self._secret_name(job_id, key_id))
        except self.client.exceptions.ResourceNotFoundException:
            # Unknown key id → fail closed, matching FakeHmacKeyIssuer's dict
            # miss and the HmacKeyIssuer.lookup docstring contract.
            return None
        return cast(bytes, response["SecretBinary"])

    def _secret_name(self, job_id: UUID, key_id: str) -> str:
        return f"{self.prefix}/{job_id}/{key_id}"


# ---------------------------------------------------------------------------
# SqlJobStateStore — durable Postgres CAS adapter (JobStateStore seam, C-2)
# ---------------------------------------------------------------------------

# Proposed DDL for the `jobs` table this adapter targets (SCHEMA GAP — see
# module docstring; this is NOT wired into db/migrations/versions/, it is only
# documentation for the eventual migration once a CLAR ratifies the table).
# Minimal shape: only the three columns the CAS state machine below reads/
# writes. A fuller production `jobs` table (scan_id FK, detector_id,
# hmac_key_id, callback_path, 404-unknown-job read surface — referenced by
# WBS.md CLAR-DEPLOY-19's "Out of scope: ... 404 unknown-job (needs jobs
# table)" and CLAR-ORCH-07's "richer ScanState... needs the jobs table") is a
# separate, broader design question this adapter deliberately does not answer
# (RULE-4 — that richer shape was never asked for by Track 1D).
PROPOSED_JOBS_TABLE_DDL = """
CREATE TABLE jobs (
    job_id      uuid        NOT NULL PRIMARY KEY,
    status      text        NOT NULL,
    body_sha256 text        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT jobs_status_chk CHECK (status IN ('running', 'done', 'failed'))
);
"""


@dataclass
class SqlJobStateStore:
    """A durable Postgres compare-and-set ``JobStateStore`` (DOC-API §4.5, C-2).

    Implements the IDENTICAL state machine as ``InMemoryJobStateStore``
    (``services/scan/api.py``) — read that class's docstring for the four-case
    table — but the CAS decision is made under a ``SELECT ... FOR UPDATE`` row
    lock inside one transaction, so two concurrent worker callbacks for the
    SAME ``job_id`` (e.g. a retried HTTP request racing the original) cannot
    both observe "no prior state" and both insert / both apply a transition
    the state machine should have rejected as ``conflict``. This row lock is
    the actual "compare-and-set" — see ``tests/integration/
    test_orch01_sql_adapters.py``'s concurrency test for the falsifier that a
    naive read-then-write (no lock) would fail.

    SCHEMA GAP (module docstring): no ``jobs`` table ships in
    ``db/migrations/versions/`` yet. This class is real, tested code (against a
    test-local table matching :data:`PROPOSED_JOBS_TABLE_DDL`, never an
    Alembic migration authored by this PR) so it is ready to wire in the moment
    the table lands.

    No org binding / ``acquire_for_request`` here: worker callbacks carry no
    tenant header (DOC-API §2.5 — "worker callbacks carry NO
    X-Scanipy-Org-Id"; ``post_job_status``'s own docstring: "this handler does
    NOT run the CP-01 tenancy guard"), matching DOC-CMP-CP-03 §3.1's
    documented pattern for server-internal jobs: "Server-internal jobs
    (Attestor re-runs, scheduler, worker callback) use `SET LOCAL app.role =
    'system'`... has BYPASSRLS." The `jobs` table is not tenant data — job
    identity is already authenticated by the per-job HMAC secret
    (`post_job_status` verifies it before this store is ever called).
    """

    connection_factory: ConnectionFactory

    def transition(self, *, job_id: UUID, status: JobStatus, body_sha256: str) -> TransitionOutcome:
        with self.connection_factory() as conn:
            cur = conn.cursor()
            try:
                # Row lock: blocks a concurrent transition for the SAME job_id
                # until this transaction commits/rolls back — the actual
                # "compare" half of compare-and-set.
                cur.execute("SELECT status FROM jobs WHERE job_id = %s FOR UPDATE;", (str(job_id),))
                row = cur.fetchone()

                if row is None:
                    cur.execute(
                        "INSERT INTO jobs (job_id, status, body_sha256) VALUES (%s, %s, %s);",
                        (str(job_id), status, body_sha256),
                    )
                    conn.commit()
                    return "applied"

                (prior_status,) = row
                if prior_status == status:
                    # DOC-API §4.5: a same-status replay/retry is a no-op — the
                    # recorded state is NOT overwritten (release the lock via
                    # commit; no row mutated).
                    conn.commit()
                    return "duplicate"
                if prior_status == "running" and status in ("done", "failed"):
                    cur.execute(
                        "UPDATE jobs SET status = %s, body_sha256 = %s, updated_at = now() "
                        "WHERE job_id = %s;",
                        (status, body_sha256, str(job_id)),
                    )
                    conn.commit()
                    return "applied"
                # Terminal → different status: forbidden by the §4.5 state
                # machine — never overwrite; release the lock, report conflict.
                conn.commit()
                return "conflict"
            except BaseException:
                conn.rollback()
                raise


__all__ = [
    "PROPOSED_JOBS_TABLE_DDL",
    "SecretsManagerHmacKeyIssuer",
    "SqlJobStateStore",
    "SqlSnapshotPort",
    "SqlSpecRegistryPort",
    "psycopg2_connection_factory",
]

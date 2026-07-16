"""CMP-SNAP-01 — Snapshot service API (orchestration + persistence layer).

Implementation contract: ``docs/components/DOC-CMP-SNAP-01.md`` (§2 mandate, §4
inputs/outputs, §5 INV-2, §6 data flow, §7 fail-closed). Cross-cutting refs:
``DOC-INV §3/§4`` (INV-1/INV-2), ``.claude/rules/02-provenance.md`` (env_digest
threading), ``.claude/rules/00-global.md`` (RULE-6).

This module is the **entry point** of the Snapshotter subsystem. It is the
orchestration + persistence seam ONLY: the actual clone / CW-DETECT verdict /
CPG build / ΔG computation run in the CMP-SNAP-05 worker (not built here). Tests
simulate the worker the way CMP-FND-03 fixtured its KMS signer — by calling the
``record_completion`` seam with a verdict + the five artifact URIs.

Responsibilities discharged here, scoped to the four CMP-SNAP-01 ACs:

* **AC-SNAP-01a** — :meth:`SnapshotService.create_snapshot` mints the five
  deterministic S3 keys via :class:`SnapshotKeyBuilder` (reused from the
  CMP-DEPLOY-01 substrate) and persists the five artifact bodies to the injected
  :class:`ObjectStore`. Re-running the same request resolves byte-identical keys
  (the key scheme is a pure function of ``(org_id, codebase_id, commit_sha,
  env_digest, artifact_type)``).
* **AC-SNAP-01b** — :meth:`record_completion` persists a ``SnapshotRow`` whose
  ``precondition_status`` is one of ``closed-world | degraded | full-reparse``;
  a fourth value is rejected (application-layer mirror of the DDL CHECK).
* **AC-SNAP-01c / TST-INV-2-SNAP-01** — :meth:`create_snapshot` stamps
  ``env_digest`` from the pinned container image digest (INV-2). The effective
  digest is guarded against ``^sha256:[0-9a-f]{64}$``; a null or malformed digest
  raises :class:`InvariantViolation` (fail-closed, DOC §7 — "a missing digest is
  a fail-closed condition").

Everything is injected as a Protocol or a fake so the component is testable
offline without real AWS / PostgreSQL, mirroring the dependency-injection pattern
of ``services/credential_encryption.py`` and ``services/scan/provenance``.

DEFERRED (no AC coverage; CLAR-SNAP-02, WBS §17): the ``queued→ready`` state
machine, ``GET /status`` state surface, ``snapshot_digest`` / ``completed_at``
columns, the HMAC-bearer report-status callback, and the FastAPI / CMP-CP-01
HTTP wiring. None are storable against the shipped schema or covered by an AC.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from services.scan.provenance import InvariantViolation
from services.snapshot.models import PreconditionStatus, SnapshotRow
from services.substrate.object_store import (
    SNAPSHOT_ARTIFACT_TYPES,
    InMemoryObjectStore,
    ObjectStore,
    SnapshotKeyBuilder,
)
from services.substrate.queue import Queue, StandardQueue

# INV-2: the env_digest is the worker container image digest. Same format CHECK
# as the shipped ``snapshots.env_digest_chk`` DDL constraint.
_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# A 40-hex Git commit SHA. Same format CHECK as ``snapshots_commit_sha_chk``.
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# The three allowed precondition verdicts (AC-SNAP-01b; DOC §4.3).
_PRECONDITION_VALUES: frozenset[str] = frozenset(("closed-world", "degraded", "full-reparse"))


@dataclass(frozen=True)
class SnapshotRequest:
    """The ``POST /snapshots`` request body (DOC-CMP-SNAP-01 §3.1).

    ``parent_snapshot_id`` is the optional incremental hint; when present the ΔG
    artifact is meaningful (otherwise the snapshot is a full/first reparse and
    ``delta_g_uri`` is null, mirroring the only nullable URI column).
    """

    org_id: uuid.UUID
    codebase_id: uuid.UUID
    commit_sha: str
    parent_snapshot_id: uuid.UUID | None = None


@dataclass(frozen=True)
class SnapshotAccepted:
    """The accepted result of :meth:`SnapshotService.create_snapshot` (202).

    Carries the minted ``snapshot_id`` (which the worker-completion seam threads
    back into the persisted row), the five deterministic artifact keys, and the
    stamped ``env_digest`` (INV-2). No relational row exists yet — the row cannot
    be inserted until the worker reports the precondition verdict + URIs
    (CLAR-SNAP-02; the shipped schema has ``precondition_status`` NOT NULL).
    """

    snapshot_id: uuid.UUID
    artifact_keys: dict[str, str]
    env_digest: str


@runtime_checkable
class EnvDigestProvider(Protocol):
    """Resolves the worker container image digest (INV-2 source).

    Production reads the ECS task metadata / the ``SCANIPY_ENV_DIGEST`` env var
    injected by CMP-DEPLOY-02 (DOC-CMP-SNAP-05 §3.1). The provider returns
    ``None`` when no digest is resolvable; :meth:`SnapshotService.create_snapshot`
    treats that as a fail-closed condition (DOC §7).
    """

    def __call__(self) -> str | None: ...


def env_var_env_digest_provider() -> str | None:
    """Production env-digest provider: read ``SCANIPY_ENV_DIGEST`` lazily.

    Read at call time (never at import) so the lookup stays hermetic and the
    module imports cleanly with no environment. Returns ``None`` when the var is
    unset/empty, which :meth:`SnapshotService.create_snapshot` rejects fail-closed.
    """
    value = os.environ.get("SCANIPY_ENV_DIGEST")
    return value or None


@runtime_checkable
class SnapshotStore(Protocol):
    """Append/read port for persisted ``SnapshotRow`` rows (DOC-DB §4.7).

    Production binds a SQL-backed store under the SNAP-01 worker IAM role; tests
    wire :class:`InMemorySnapshotStore`. Keyed on ``snapshot_id`` — the value
    minted by :meth:`SnapshotService.create_snapshot` and threaded back by the
    worker-completion seam.
    """

    def put(self, row: SnapshotRow) -> None: ...

    def get(self, snapshot_id: uuid.UUID) -> SnapshotRow | None: ...


@dataclass
class InMemorySnapshotStore:
    """Deterministic offline stand-in for the ``snapshots`` table.

    No DB, no flush — so server defaults (``gen_random_uuid()``, ``now()``, the
    ``expires_at`` default) do NOT fire. The service therefore sets every
    test-read field (``id``, ``env_digest``, ``precondition_status``, the five
    URIs) explicitly before :meth:`put`.
    """

    _rows: dict[uuid.UUID, SnapshotRow] = field(default_factory=dict)

    def put(self, row: SnapshotRow) -> None:
        self._rows[row.id] = row

    def get(self, snapshot_id: uuid.UUID) -> SnapshotRow | None:
        return self._rows.get(snapshot_id)


@dataclass
class SnapshotService:
    """Framework-agnostic Snapshotter entry point (CMP-SNAP-01).

    DI-Protocol pattern: every collaborator is injected so the four ACs run with
    no DB and no AWS. Construct with all defaults for a fully in-memory,
    hermetic instance; production wires the S3-backed :class:`ObjectStore`
    (:class:`services.substrate.object_store.S3ObjectStore`), the SQS-backed
    :class:`Queue` (:class:`services.substrate.queue.SQSQueue`), the SQL-backed
    :class:`SnapshotStore`, and :func:`env_var_env_digest_provider`. The
    :class:`StandardQueue` default below is the hermetic in-memory test double.
    """

    object_store: ObjectStore = field(default_factory=InMemoryObjectStore)
    queue: Queue = field(default_factory=lambda: StandardQueue(name="snapshot-jobs"))
    snapshot_store: SnapshotStore = field(default_factory=InMemorySnapshotStore)
    env_digest_provider: EnvDigestProvider = field(
        default_factory=lambda: env_var_env_digest_provider
    )

    def create_snapshot(
        self,
        req: SnapshotRequest,
        *,
        image_digest: str | None = None,
    ) -> SnapshotAccepted:
        """Validate, resolve+guard ``env_digest``, mint keys, and enqueue a job.

        Steps (DOC-CMP-SNAP-01 §6 steps 1-7, scoped to the API seam):

        1. Validate ``commit_sha`` is 40-hex.
        2. Resolve the effective ``env_digest``: the explicit ``image_digest``
           param when supplied, else the injected provider. Guard it against the
           sha256 format — a null/malformed digest is fail-closed (INV-2, DOC §7).
        3. Mint the five deterministic artifact keys (CLAR-DEPLOY-02 scheme).
        4. Enqueue a ``SnapshotJob`` for the CMP-SNAP-05 worker (dedup on the
           minted ``snapshot_id``).
        5. Return the accepted result (202-shaped).

        No relational row is written here — the shipped schema's
        ``precondition_status`` is NOT NULL, so the row is inserted only once the
        worker reports the verdict via :meth:`record_completion` (CLAR-SNAP-02).
        """
        if not _COMMIT_SHA_RE.fullmatch(req.commit_sha):
            raise InvariantViolation(
                f"commit_sha must be 40-hex; got {req.commit_sha!r}",
                code="invalid_commit_sha",
            )

        env_digest = self._resolve_env_digest(image_digest)

        snapshot_id = uuid.uuid4()
        key_builder = SnapshotKeyBuilder(
            org_id=str(req.org_id),
            codebase_id=str(req.codebase_id),
            commit_sha=req.commit_sha,
            env_digest=env_digest,
        )
        artifact_keys = key_builder.all_artifact_keys()

        self.queue.send(
            body={
                "snapshot_id": str(snapshot_id),
                "org_id": str(req.org_id),
                "codebase_id": str(req.codebase_id),
                "commit_sha": req.commit_sha,
                "env_digest": env_digest,
                "parent_snapshot_id": (
                    "" if req.parent_snapshot_id is None else str(req.parent_snapshot_id)
                ),
            },
            dedup_key=str(snapshot_id),
        )

        return SnapshotAccepted(
            snapshot_id=snapshot_id,
            artifact_keys=artifact_keys,
            env_digest=env_digest,
        )

    def record_completion(
        self,
        accepted: SnapshotAccepted,
        req: SnapshotRequest,
        *,
        precondition_status: str,
        artifact_bodies: dict[str, bytes],
    ) -> SnapshotRow:
        """Persist the ``SnapshotRow`` once the worker reports its outputs.

        This is the simulated CMP-SNAP-05 worker-completion seam (tests call it
        directly the way CMP-FND-03 tests called its signer). It:

        1. Re-guards ``env_digest`` (INV-2 defence-in-depth).
        2. Validates ``precondition_status`` is one of the three verdicts
           (AC-SNAP-01b; application-layer mirror of the DDL CHECK).
        3. PUTs the supplied artifact bodies to the injected object store at the
           deterministic keys minted by :meth:`create_snapshot` — so "produces
           all five persisted artifacts at deterministic keys" is literally true.
           The four NOT-NULL artifacts (CPG tarball, reverse-symbol index,
           dynamic call graph, precondition-status record) are mandatory; the ΔG
           body is optional (a full/first reparse legitimately has no delta).
        4. Inserts the ``SnapshotRow`` under the minted ``snapshot_id`` with every
           field set explicitly (no DB flush fires server defaults in-memory).
           ``delta_g_uri`` (the only nullable URI) references the ΔG artifact iff
           a ΔG body was persisted; otherwise it is null — so the row never
           points at an object that was not stored, and never omits one that was.
        """
        env_digest = self._guard_env_digest(accepted.env_digest)

        if precondition_status not in _PRECONDITION_VALUES:
            raise InvariantViolation(
                "precondition_status must be one of "
                f"{sorted(_PRECONDITION_VALUES)}; got {precondition_status!r}",
                code="invalid_precondition_status",
            )

        keys = accepted.artifact_keys
        # The four NOT-NULL artifacts must always be supplied + persisted.
        for artifact_type in SNAPSHOT_ARTIFACT_TYPES:
            if artifact_type == "delta_graph":
                continue
            body = artifact_bodies.get(artifact_type)
            if body is None:
                raise InvariantViolation(
                    f"missing artifact body for {artifact_type!r}; the four "
                    "NOT-NULL artifacts must be supplied (AC-SNAP-01a)",
                    code="missing_artifact",
                )
            self.object_store.put(str(req.org_id), keys[artifact_type], body)

        # ΔG is the only nullable URI. Persist its body + reference it iff the
        # worker produced one (incremental); a full/first reparse omits it and
        # ``delta_g_uri`` stays null — the URI references stored objects only.
        delta_body = artifact_bodies.get("delta_graph")
        if delta_body is not None:
            self.object_store.put(str(req.org_id), keys["delta_graph"], delta_body)
            delta_g_uri: str | None = keys["delta_graph"]
        else:
            delta_g_uri = None

        row = SnapshotRow(
            id=accepted.snapshot_id,
            org_id=req.org_id,
            codebase_id=req.codebase_id,
            commit_sha=req.commit_sha,
            env_digest=env_digest,
            precondition_status=cast_precondition(precondition_status),
            cpg_tarball_uri=keys["cpg_tarball"],
            reverse_symbol_index_uri=keys["reverse_symbol_index"],
            dynamic_call_graph_uri=keys["dynamic_call_graph"],
            delta_g_uri=delta_g_uri,
            precondition_status_record_uri=keys["precondition_status"],
            parent_snapshot_id=req.parent_snapshot_id,
        )
        self.snapshot_store.put(row)
        return row

    def get(self, snapshot_id: uuid.UUID) -> SnapshotRow | None:
        """Read the persisted ``SnapshotRow`` (the AC-SNAP-01b read surface)."""
        return self.snapshot_store.get(snapshot_id)

    # --- internals ---------------------------------------------------------

    def _resolve_env_digest(self, image_digest: str | None) -> str:
        """Resolve the effective env_digest: explicit param else provider.

        The explicit ``image_digest`` wins when supplied (the 4 test stubs pin
        ``create(req, image_digest=X).env_digest == X``); otherwise the injected
        provider is consulted. Either way the result is format-guarded.
        """
        candidate = image_digest if image_digest is not None else self.env_digest_provider()
        return self._guard_env_digest(candidate)

    @staticmethod
    def _guard_env_digest(candidate: str | None) -> str:
        """Fail-closed INV-2 guard (DOC §7): null or malformed digest is refused."""
        if candidate is None or not _ENV_DIGEST_RE.fullmatch(candidate):
            raise InvariantViolation(
                "env_digest must be a pinned container image digest matching "
                f"'sha256:<64-hex>'; got {candidate!r} (INV-2, fail-closed)",
                code="invariant_inv2_violation",
            )
        return candidate


def cast_precondition(value: str) -> PreconditionStatus:
    """Narrow a validated verdict string to the ``PreconditionStatus`` literal.

    The caller has already checked ``value in _PRECONDITION_VALUES``; this is the
    type-level narrowing so the ORM assignment stays mypy-strict clean.
    """
    assert value in _PRECONDITION_VALUES  # narrowing guard; caller pre-validated
    return value  # type: ignore[return-value]


__all__ = [
    "EnvDigestProvider",
    "InMemorySnapshotStore",
    "SnapshotAccepted",
    "SnapshotRequest",
    "SnapshotService",
    "SnapshotStore",
    "env_var_env_digest_provider",
]

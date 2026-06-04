# ruff: noqa: N803
#   ``S_version`` keeps its capital S throughout (normative provenance field name,
#   INV-2) on the fake's submission helpers / ports, matching ``services/scan/
#   api.py``. Suppressed file-wide rather than per-parameter.
"""Hermetic offline fakes for CMP-ORCH-01 (scan API) specs.

No real AWS / SQS, no PostgreSQL, no FastAPI. The scan API's build-ahead seams
(the snapshot resolve-or-create port, the ``spec_versions`` registry port, and
the per-job HMAC key issuer — all env/dependency-gated per CLAR-PROC-01) are
supplied here as deterministic in-memory doubles, injected through the API's
typed DI seams. The prod defaults fail closed; these are never on the prod path.

Mirrors the established DI-fake convention (``tests/orch03_fakes.py``,
``tests/snap04_fakes.py``): one module that builds the synthetic inputs + the
injected ports so every spec test stays hermetic.

INDEPENDENCE: the HMAC key issuer here mints real per-job secrets and signs the
canonical request with the SAME secret the verifier looks up — so the positive
leg actually verifies and the negative legs (wrong key, skew) actually reject.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from services.control_plane.constants import Role
from services.control_plane.guard import JWTClaims
from services.scan.api import (
    JobStatusReport,
    ScanRequest,
    SnapshotResolution,
    canonical_request,
)

# A deterministic, valid-shaped env_digest (sha256:+64hex) the fake snapshot
# stamps and the API threads onto every job (INV-2).
FAKE_ENV_DIGEST = "sha256:" + "b" * 64

# Two distinct orgs for the cross-tenant isolation leg.
ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"


def claims_for(org_id: str, *, role: Role = "scanner", user_id: str = "scanner") -> JWTClaims:
    """Validated JWT claims for ``org_id`` (default the scanner machine identity)."""
    return JWTClaims(
        user_id=user_id,
        org_id=org_id,
        role=role,
        issued_at=0,
        expires_at=10_000_000_000,
    )


def headers_for(org_id: str, *, user_id: str = "scanner") -> dict[str, str]:
    """Tenancy headers matching ``claims_for`` (the CP-01 layer-1 check passes)."""
    return {"X-Scanipy-Org-Id": org_id, "X-Scanipy-User-Id": user_id}


def scan_request(detector_ids: tuple[str, ...], *, S_version: str | None = None) -> ScanRequest:
    """A valid-shaped scan submission over the given detector ids."""
    return ScanRequest(
        codebase_id=UUID(int=7),
        commit_sha="a" * 40,
        detector_ids=detector_ids,
        S_version=S_version,
    )


# ---------------------------------------------------------------------------
# Build-ahead ports (deterministic doubles)
# ---------------------------------------------------------------------------


@dataclass
class FakeSnapshotPort:
    """A deterministic snapshot resolve-or-create double (CMP-SNAP-01 seam).

    Mints a fixed-per-(codebase,commit) snapshot id and a constant env_digest, so
    "snapshot-if-absent" is honoured for the fan-out positive without a real
    SNAP-01 / S3 dependency."""

    env_digest: str = FAKE_ENV_DIGEST
    _by_key: dict[tuple[str, str], UUID] = field(default_factory=dict)

    def resolve_or_create(
        self, *, org_id: str, codebase_id: UUID, commit_sha: str
    ) -> SnapshotResolution:
        key = (str(codebase_id), commit_sha)
        snapshot_id = self._by_key.setdefault(key, uuid4())
        return SnapshotResolution(snapshot_id=snapshot_id, env_digest=self.env_digest)


@dataclass
class FakeSpecRegistry:
    """A deterministic ``spec_versions`` double (CMP-TRI-02 seam / INV-3 fence).

    ``accepted`` is the set of registered, accepted ``S_version`` rows; ``latest``
    is what ``resolve_latest`` returns when the request omits ``S_version``."""

    accepted: frozenset[str] = frozenset({"1.0.0", "2.7.0"})
    latest: str | None = "2.7.0"

    def resolve_latest(self) -> str | None:
        return self.latest

    def is_registered(self, S_version: str) -> bool:
        return S_version in self.accepted


@dataclass
class FakeHmacKeyIssuer:
    """A deterministic per-job HMAC key issuer (DOC-API §2.3 / CLAR-ORCH-06 seam).

    ``issue`` mints a fresh random secret keyed by ``(job_id, key_id)``; ``lookup``
    returns it on the callback path. This is a real HMAC keyring (not a stub) so
    the positive callback verifies and the wrong-key leg genuinely fails."""

    _keys: dict[tuple[UUID, str], bytes] = field(default_factory=dict)

    def issue(self, *, job_id: UUID, scan_id: UUID) -> tuple[str, bytes]:
        key_id = f"k-{job_id}"
        secret = secrets.token_bytes(32)
        self._keys[(job_id, key_id)] = secret
        return key_id, secret

    def lookup(self, *, job_id: UUID, key_id: str) -> bytes | None:
        return self._keys.get((job_id, key_id))


# ---------------------------------------------------------------------------
# Callback signing helper (mirrors what a real worker does before POSTing)
# ---------------------------------------------------------------------------


def sign_callback(
    *,
    job_id: UUID,
    worker_id: str,
    timestamp: int,
    body: JobStatusReport,
    key_id: str,
    secret: bytes,
) -> tuple[str, bytes]:
    """Produce ``(authorization_header, body_bytes)`` a worker would send.

    Serialises the body to bytes ONCE and signs the canonical request over those
    exact bytes with ``secret`` — so the verifier (which hashes the same bytes
    with the looked-up secret) accepts iff the secret matches. Returns both the
    ``Authorization: HMAC <key-id>:<digest>`` header and the wire body bytes."""
    body_bytes = json.dumps(
        {
            "job_id": str(body.job_id),
            "scan_id": str(body.scan_id),
            "status": body.status,
            "S_version": body.S_version,
            "env_digest": body.env_digest,
        },
        sort_keys=True,
    ).encode("utf-8")
    message = canonical_request(
        method="POST",
        path=f"/api/v1/jobs/{job_id}/status",
        worker_id=worker_id,
        body_bytes=body_bytes,
        timestamp=timestamp,
    )
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"HMAC {key_id}:{digest}", body_bytes


def done_report(job_id: UUID, scan_id: UUID) -> JobStatusReport:
    """A well-formed ``status=done`` callback body (INV-2 fields present)."""
    return JobStatusReport(
        job_id=job_id,
        scan_id=scan_id,
        status="done",
        S_version="2.7.0",
        env_digest=FAKE_ENV_DIGEST,
        result_uri="s3://bucket/result.sarif",
    )


__all__ = [
    "FAKE_ENV_DIGEST",
    "ORG_A",
    "ORG_B",
    "FakeHmacKeyIssuer",
    "FakeSnapshotPort",
    "FakeSpecRegistry",
    "claims_for",
    "done_report",
    "headers_for",
    "scan_request",
    "sign_callback",
]

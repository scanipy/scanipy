"""CMP-ORCH-01 — byte-level parse/serialise boundary for the HTTP surface.

CLAR-DEPLOY-19: the routes in ``services/scan/http/app.py`` deliberately carry
NO pydantic body models — framework body parsing is an independent read path,
which is exactly the C-1 hazard on the worker callback, and on ``POST /scans``
it would create a second validation authority drifting against the core's
``_validate_scan_request``. These functions are therefore the ONLY place wire
bytes become typed requests:

  * :func:`parse_job_status_report` is **THE C-1 parse function**: the callback
    route derives its handler-visible body as ``parse_job_status_report(
    body_bytes)`` over the same local variable the HMAC verified.
  * ANY malformation (non-JSON, wrong type, missing/unknown field, bad UUID)
    raises :class:`~services.scan.api.InvalidInputError` → ``400 invalid_input``
    per DOC-API §6.1 — fail-closed, never a partial parse.

Semantic validation (commit-sha shape, detector existence, S_version fencing,
INV-2 digests) stays in the framework-agnostic core — single validation
authority; this module checks structure only.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import UUID

from services.scan.api import (
    InvalidInputError,
    JobStatusReport,
    ScanRequest,
)

if TYPE_CHECKING:
    from services.scan.api import JobStatus, ScanCreated, ScanRecord

_JOB_STATUSES = ("running", "done", "failed")


def _load_json_object(body_bytes: bytes, *, what: str) -> dict[str, object]:
    """Decode ``body_bytes`` as a JSON object; anything else is a 400."""
    try:
        decoded = json.loads(body_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidInputError(f"{what} body is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise InvalidInputError(f"{what} body must be a JSON object")
    return decoded


def _reject_unknown_keys(body: dict[str, object], allowed: frozenset[str], *, what: str) -> None:
    """Fail closed on unrecognised fields (never silently drop client intent)."""
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise InvalidInputError(f"{what} body has unknown fields: {', '.join(unknown)}")


def _required_uuid(body: dict[str, object], key: str) -> UUID:
    value = body.get(key)
    if not isinstance(value, str):
        raise InvalidInputError(f"{key} must be a UUID string")
    try:
        return UUID(value)
    except ValueError as exc:
        raise InvalidInputError(f"{key} must be a UUID string") from exc


def _required_str(body: dict[str, object], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise InvalidInputError(f"{key} must be a non-empty string")
    return value


def _optional_str(body: dict[str, object], key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidInputError(f"{key} must be a string or null")
    return value


def _optional_count(body: dict[str, object], key: str) -> int:
    value = body.get(key, 0)
    # bool is an int subclass; a JSON `true` must not sneak in as a count.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidInputError(f"{key} must be a non-negative integer")
    return value


def parse_scan_request(body_bytes: bytes) -> ScanRequest:
    """Parse the ``POST /api/v1/scans`` wire body (DOC-API §4.1) — fail-closed.

    Structure-only: the handler core (``_validate_scan_request`` /
    ``_resolve_s_version`` / registry lookup) remains the single semantic
    validation authority.
    """
    body = _load_json_object(body_bytes, what="scan request")
    _reject_unknown_keys(
        body,
        frozenset({"codebase_id", "commit_sha", "detector_ids", "S_version", "policy_overrides"}),
        what="scan request",
    )

    detector_ids_raw = body.get("detector_ids")
    if not isinstance(detector_ids_raw, list) or not all(
        isinstance(d, str) and d for d in detector_ids_raw
    ):
        raise InvalidInputError("detector_ids must be a list of non-empty strings")

    policy_overrides_raw = body.get("policy_overrides", {})
    if not isinstance(policy_overrides_raw, dict) or not all(
        isinstance(k, str) for k in policy_overrides_raw
    ):
        raise InvalidInputError("policy_overrides must be an object")

    return ScanRequest(
        codebase_id=_required_uuid(body, "codebase_id"),
        commit_sha=_required_str(body, "commit_sha"),
        detector_ids=tuple(detector_ids_raw),
        S_version=_optional_str(body, "S_version"),
        policy_overrides=dict(policy_overrides_raw),
    )


def parse_job_status_report(body_bytes: bytes) -> JobStatusReport:
    """THE C-1 parse function: verified wire bytes → typed callback report.

    The callback route MUST call this on the exact ``body_bytes`` local that
    ``verify_worker_callback_hmac`` covers (``body == parse(body_bytes)``, the
    CLAR-DEPLOY-19 / ORCH-01 co-sign condition C-1). Shape per DOC-API §4.5.
    """
    body = _load_json_object(body_bytes, what="job status")
    _reject_unknown_keys(
        body,
        frozenset(
            {
                "job_id",
                "scan_id",
                "status",
                "S_version",
                "env_digest",
                "findings_count",
                "core_partition_count",
                "oracle_partition_count",
                "result_uri",
                "witness_uri",
                "error",
            }
        ),
        what="job status",
    )

    status_raw = body.get("status")
    if status_raw not in _JOB_STATUSES:
        raise InvalidInputError("status must be one of: running, done, failed")
    status = cast("JobStatus", status_raw)

    error_raw = body.get("error")
    error: dict[str, str] | None = None
    if error_raw is not None:
        if not isinstance(error_raw, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in error_raw.items()
        ):
            raise InvalidInputError("error must be an object of string values or null")
        error = dict(error_raw)

    return JobStatusReport(
        job_id=_required_uuid(body, "job_id"),
        scan_id=_required_uuid(body, "scan_id"),
        status=status,
        S_version=_required_str(body, "S_version"),
        env_digest=_required_str(body, "env_digest"),
        findings_count=_optional_count(body, "findings_count"),
        core_partition_count=_optional_count(body, "core_partition_count"),
        oracle_partition_count=_optional_count(body, "oracle_partition_count"),
        result_uri=_optional_str(body, "result_uri"),
        witness_uri=_optional_str(body, "witness_uri"),
        error=error,
    )


def scan_created_json(created: ScanCreated, *, replay: bool) -> dict[str, object]:
    """Serialise a :class:`ScanCreated` for the 201 / 200-replay response.

    ``replay`` is the route's 200-vs-201 inference (``created.job_ids == ()``
    iff idempotency replay — valid because ``detector_ids`` is non-empty, so a
    fresh scan always fans ≥ 1 job). The serializer re-checks that inference
    against the record so the coupled invariant can never drift silently: if a
    future core change (e.g. lazy fan-out) breaks it, this raises rather than
    mislabel a response status (the CLAR-DEPLOY-19 risk-note tripwire).

    ``created_at`` (DOC-API §4.1) is the persisted-row/DB-default follow-up
    (CLAR-ORCH-07 deviation 2); ``job_ids`` is the ratified fan-out addition.
    """
    if replay != (created.job_ids == ()):
        raise ValueError(
            "replay flag disagrees with the fan-out record "
            "(job_ids == () iff idempotency replay; see CLAR-DEPLOY-19 risk note)"
        )
    return {
        "scan_id": str(created.scan_id),
        "snapshot_id": str(created.snapshot_id),
        "status": created.status,
        "S_version": created.S_version,
        "env_digest": created.env_digest,
        "job_ids": [str(job_id) for job_id in created.job_ids],
    }


def scan_record_json(record: ScanRecord) -> dict[str, object]:
    """Serialise the thin RLS-bound :class:`ScanRecord` (CLAR-ORCH-07).

    The richer §3.1 ``ScanState`` (per-job summaries, findings_count,
    attestation_status) needs the persisted jobs table + CP-05 status — the
    DEPLOY-19-gated follow-up; this is the honest thin shape until then.
    Internal columns (org_id, idempotency key/hash) are never serialised.
    """
    return {
        "scan_id": str(record.scan_id),
        "codebase_id": str(record.codebase_id),
        "snapshot_id": str(record.snapshot_id),
        "commit_sha": record.commit_sha,
        "status": record.status,
        "S_version": record.S_version,
        "env_digest": record.env_digest,
        "detector_ids": list(record.detector_ids),
    }


__all__ = [
    "parse_job_status_report",
    "parse_scan_request",
    "scan_created_json",
    "scan_record_json",
]

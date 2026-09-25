"""Function-only PostgreSQL facade. Caller owns ONE transaction and tenant binding.

No native tool, source capture, final Finding, signing, entity or human write.
The optional transaction helper reuses existing driver-light tenancy plumbing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from db.session import acquire_for_request

from services.scan.sql_adapters import Connection

from ._schemas import MAX_FAILURE_PREFIX
from .codec import CanonicalEnvelope, EnvelopeError
from .models import (
    CaptureSeal,
    Claim,
    DetectionBatch,
    Fence,
    RequestHandle,
    RequestInput,
    RetainedBatch,
    WorkKind,
    envelope_pair,
)

if TYPE_CHECKING:
    from services.scan.sql_adapters import ConnectionFactory

STATEMENT_TIMEOUT_MS = 15000
LOCK_TIMEOUT_MS = 2000


class OccurrenceRepository:
    """Never commits independently; all mutators call narrowly granted functions."""

    def __init__(self, connection: Connection, org_id: UUID) -> None:
        if getattr(connection, "autocommit", False):
            raise ValueError("occurrence store requires caller transaction")
        self.connection = connection
        self.org_id = org_id
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT set_config('statement_timeout',%s,true),set_config('lock_timeout',%s,true)",
                (str(STATEMENT_TIMEOUT_MS), str(LOCK_TIMEOUT_MS)),
            )
        finally:
            cursor.close()

    def _call(self, function: str, parameters: tuple[object, ...]) -> dict[str, Any] | None:
        # Function names are constants or assembled only from a validated kind.
        cursor = self.connection.cursor()
        try:
            placeholders = ",".join("%s" for _ in parameters)
            cursor.execute(f"SELECT scanipy_execution.{function}({placeholders})", parameters)
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("store function returned no SQL row")
            if row[0] is not None and not isinstance(row[0], dict):
                raise RuntimeError("store function returned unsupported response")
            return cast(dict[str, Any] | None, row[0])
        finally:
            cursor.close()

    def _required(self, function: str, parameters: tuple[object, ...]) -> dict[str, Any]:
        result = self._call(function, parameters)
        if result is None:
            raise RuntimeError("store function unexpectedly returned null")
        return result

    def _fence(self, fence: Fence) -> tuple[object, ...]:
        if type(fence) is not Fence:
            raise EnvelopeError("fence must be an exact Fence")
        fence.__post_init__()
        return (
            str(self.org_id),
            str(fence.work_item_id),
            str(fence.attempt_id),
            fence.token,
            fence.revision,
        )

    def create_request(self, request: RequestInput) -> RequestHandle:
        if type(request) is not RequestInput:
            raise EnvelopeError("request must be an exact RequestInput")
        request.__post_init__()
        value = request.request.value
        if value["org_id"] != str(self.org_id):
            raise EnvelopeError("repository/request tenant mismatch")
        result = self._required(
            "create_request_v1",
            (
                str(self.org_id),
                value["codebase_id"],
                *envelope_pair(request.request, "request"),
                *envelope_pair(request.planned_policy, "planned-policy"),
            ),
        )
        return RequestHandle(
            UUID(result["request_id"]),
            UUID(result["work_item_id"]),
            result["revision"],
            result["replayed"],
        )

    def claim(
        self, kind: WorkKind, policy: CanonicalEnvelope, work_item_id: UUID | None = None
    ) -> Claim | None:
        if kind not in ("capture_detection", "identity"):
            raise ValueError("unknown work kind")
        result = self._call(
            f"claim_{kind}_v1",
            (
                str(self.org_id),
                None if work_item_id is None else str(work_item_id),
                *envelope_pair(policy, "attempt-policy"),
            ),
        )
        if result is None:
            return None
        return Claim(
            Fence(
                UUID(result["work_item_id"]),
                UUID(result["attempt_id"]),
                kind,
                result["fencing_token"],
                result["revision"],
            ),
            UUID(result["request_id"]),
            None if result["occurrence_id"] is None else UUID(result["occurrence_id"]),
            None if result["capture_id"] is None else UUID(result["capture_id"]),
            result["attempt_number"],
            datetime.fromisoformat(result["lease_expires_at"]),
            result["payload"],
        )

    def renew(self, fence: Fence) -> Fence:
        result = self._required(f"renew_{fence.kind}_v1", self._fence(fence))
        return Fence(
            fence.work_item_id, fence.attempt_id, fence.kind, fence.token, result["revision"]
        )

    def register_capture_and_seal(self, fence: Fence, capture: CaptureSeal) -> dict[str, Any]:
        if fence.kind != "capture_detection":
            raise ValueError("capture registration requires detector fence")
        if type(capture) is not CaptureSeal:
            raise EnvelopeError("capture must be an exact CaptureSeal")
        capture.__post_init__()
        return self._required(
            "register_capture_and_seal_v1",
            (
                *self._fence(fence),
                *envelope_pair(capture.seal, "seal"),
                *envelope_pair(capture.inventory, "source-inventory"),
                *envelope_pair(capture.accepted_content, "accepted-content"),
                capture.spec,
                list(capture.detectors),
                list(capture.rules),
                capture.authority_evidence,
            ),
        )

    def begin_detector_run(self, fence: Fence, invocation: CanonicalEnvelope) -> dict[str, Any]:
        if fence.kind != "capture_detection":
            raise ValueError("detector invocation requires detector fence")
        return self._required(
            "begin_detector_run_v1", (*self._fence(fence), *envelope_pair(invocation, "run-input"))
        )

    def retain_detection_batch(
        self, fence: Fence, run_id: UUID, batch: DetectionBatch
    ) -> RetainedBatch:
        if fence.kind != "capture_detection":
            raise ValueError("detection retention requires detector fence")
        if type(batch) is not DetectionBatch:
            raise EnvelopeError("batch must be an exact DetectionBatch")
        batch.__post_init__()
        result = self._required(
            "retain_detection_batch_v1",
            (
                *self._fence(fence),
                str(run_id),
                *envelope_pair(batch.envelope, "detection-batch"),
                batch.stdout,
                batch.stderr,
                [row.result for row in batch.observations],
                [row.witness for row in batch.observations],
            ),
        )
        return RetainedBatch(
            UUID(result["run_id"]),
            tuple(map(UUID, result["occurrence_ids"])),
            tuple(map(UUID, result["identity_work_ids"])),
            result["replayed"],
        )

    def fail_detector_run(
        self, fence: Fence, run_id: UUID, failure: CanonicalEnvelope, prefix: bytes
    ) -> dict[str, Any]:
        if fence.kind != "capture_detection":
            raise ValueError("failed detector run requires detector fence")
        if type(prefix) is not bytes or len(prefix) > MAX_FAILURE_PREFIX:
            raise EnvelopeError("failure prefix exceeds 64 KiB or is not bytes")
        envelope_pair(failure, "run-failure")
        value = failure.value
        actual = hashlib.sha256(prefix).hexdigest()
        count = value["observed_byte_count"]
        if value["prefix_sha256"] != actual or (count is not None and count < len(prefix)):
            raise EnvelopeError("failed-run prefix digest/count mismatch")
        if not value["truncated"] and (
            count != len(prefix) or value["observed_full_sha256"] not in (None, actual)
        ):
            raise EnvelopeError("untruncated failure requires exact observed bytes")
        return self._required(
            "fail_detector_run_v1",
            (*self._fence(fence), str(run_id), *envelope_pair(failure, "run-failure"), prefix),
        )

    def finish(self, fence: Fence, result: CanonicalEnvelope) -> dict[str, Any]:
        return self._required(
            f"finish_{fence.kind}_v1",
            (*self._fence(fence), *envelope_pair(result, "attempt-result")),
        )

    def expire(self, fence: Fence, result: CanonicalEnvelope) -> dict[str, Any]:
        return self._required(
            f"expire_{fence.kind}_v1",
            (*self._fence(fence), *envelope_pair(result, "attempt-result")),
        )

    def acquire_capture_lease(self, fence: Fence) -> dict[str, Any]:
        return self._required(f"acquire_{fence.kind}_capture_lease_v1", self._fence(fence))

    def renew_capture_lease(self, fence: Fence) -> Fence:
        result = self._required(f"renew_{fence.kind}_capture_lease_v1", self._fence(fence))
        return Fence(
            fence.work_item_id, fence.attempt_id, fence.kind, fence.token, result["revision"]
        )

    def release_capture_lease(self, fence: Fence, reason: CanonicalEnvelope) -> dict[str, Any]:
        return self._required(
            f"release_{fence.kind}_capture_lease_v1",
            (*self._fence(fence), *envelope_pair(reason, "lease-release")),
        )

    def cancel_request(
        self, request_id: UUID, revision: int, cancellation: CanonicalEnvelope
    ) -> dict[str, Any]:
        return self._required(
            "cancel_request_v1",
            (
                str(self.org_id),
                str(request_id),
                revision,
                *envelope_pair(cancellation, "cancellation"),
            ),
        )

    def claim_retirement(self, capture_id: UUID, revision: int) -> dict[str, Any]:
        return self._required("claim_retirement_v1", (str(self.org_id), str(capture_id), revision))

    def finish_retirement(
        self, capture_id: UUID, revision: int, evidence: CanonicalEnvelope
    ) -> dict[str, Any]:
        return self._required(
            "finish_retirement_v1",
            (str(self.org_id), str(capture_id), revision, *envelope_pair(evidence, "retirement")),
        )


@contextmanager
def occurrence_transaction(
    connection_factory: ConnectionFactory, org_id: UUID
) -> Iterator[OccurrenceRepository]:
    """Trusted dispatcher supplies org; the GUC is context, never authentication.

    The factory must yield a fresh connection and discard/close it on exit,
    including ambiguous commit failures. Success is acknowledged only AFTER
    this context exits. Retry immutable keys in a new transaction, never nest
    this helper inside an operation-owned transaction.
    """
    with connection_factory() as connection:
        with acquire_for_request(connection, org_id=str(org_id), user_id="scanner", role="scanner"):
            yield OccurrenceRepository(connection, org_id)

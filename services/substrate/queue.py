"""CMP-DEPLOY-01 — at-least-once queue with per-queue DLQ + idempotent consumer.

Implementation contract: ``docs/components/DOC-CMP-DEPLOY-01.md`` §6.1 step 4,
§5 (INV-1 supporting), §9 (AC-DEPLOY-01c). Substrate decision: ``CLAR-DEPLOY-06``
(``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md``) — Amazon SQS standard queues,
per-queue Dead Letter Queue, max-receive 3 before DLQ, at-least-once delivery,
worker-side idempotency keyed on snapshot/scan IDs.

This is the offline substrate primitive that proves the queue contract. It models
the three SQS behaviours the AC exercises:

  1. **At-least-once delivery** — a message can be received more than once; a
     receive is only removed from the queue on explicit ``ack`` (cf. SQS
     receive + delete). A receive that is neither acked nor failed is treated as
     a redelivery (the visibility-timeout expiry, modelled by re-enqueue).
  2. **Per-queue DLQ + max-receive 3** — a message that fails its handler three
     times is routed to the queue's DLQ and never redelivered to the main queue
     (CLAR-DEPLOY-06).
  3. **Idempotent worker contract** — :class:`IdempotentConsumer` dedupes by the
     message's ``dedup_key`` (the ``snapshot_id`` / ``scan_id``), so a redelivered
     message produces no duplicate side effect.

No boto3 / AWS is called; production binds the same surface to a boto3 SQS client.
The queue carries scan work, not findings, so the four provenance fields
(INV-1/2/5) are threaded by the worker that *emits* findings (CMP-ORCH-03), not
here — this module is the durable transport beneath that worker.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# CLAR-DEPLOY-06: a message is routed to the DLQ after this many receives without
# a successful ack. The third failed handler attempt is the one that DLQs it.
DEFAULT_MAX_RECEIVE_COUNT = 3


class QueueError(Exception):
    """Base class for queue-substrate errors."""


class UnknownReceiptError(QueueError):
    """``ack`` / ``fail`` referenced a receipt handle that is not in flight."""


@dataclass
class Message:
    """A queue message carrying a substrate payload + its idempotency key.

    ``dedup_key`` is the worker idempotency key (``snapshot_id`` / ``scan_id``,
    CLAR-DEPLOY-06). ``receive_count`` is incremented on each delivery and drives
    the max-receive DLQ routing.
    """

    body: dict[str, str]
    dedup_key: str
    receive_count: int = 0


@dataclass
class ReceivedMessage:
    """A message handed to a consumer, paired with its in-flight receipt handle.

    The receipt is required to ``ack`` (delete) or ``fail`` (return/visibility
    timeout) the message — mirroring an SQS ``ReceiptHandle``.
    """

    receipt_handle: int
    message: Message


@dataclass
class StandardQueue:
    """In-memory SQS-equivalent: at-least-once delivery + per-queue DLQ.

    Delivery contract (modelled offline):
      * :meth:`receive` pops the head, increments ``receive_count``, and hands
        back a :class:`ReceivedMessage` with a receipt handle. The message is now
        *in flight* — invisible to other receives until acked or failed.
      * :meth:`ack` deletes the in-flight message (successful processing).
      * :meth:`fail` returns the message for redelivery, unless it has now been
        received ``max_receive_count`` times, in which case it is routed to the
        DLQ and never redelivered (CLAR-DEPLOY-06, max-receive 3).
    """

    name: str
    max_receive_count: int = DEFAULT_MAX_RECEIVE_COUNT
    _ready: deque[Message] = field(default_factory=deque)
    _in_flight: dict[int, Message] = field(default_factory=dict)
    _dlq: list[Message] = field(default_factory=list)
    _next_receipt: int = 0

    def send(self, body: dict[str, str], dedup_key: str) -> None:
        """Enqueue a new message (SQS ``SendMessage``)."""
        self._ready.append(Message(body=dict(body), dedup_key=dedup_key))

    def receive(self) -> ReceivedMessage | None:
        """Deliver the head message, marking it in flight (SQS ``ReceiveMessage``).

        Returns ``None`` when the ready queue is empty. Each delivery increments
        the message's ``receive_count`` (at-least-once semantics).
        """
        if not self._ready:
            return None
        message = self._ready.popleft()
        message.receive_count += 1
        receipt = self._next_receipt
        self._next_receipt += 1
        self._in_flight[receipt] = message
        return ReceivedMessage(receipt_handle=receipt, message=message)

    def ack(self, receipt_handle: int) -> None:
        """Delete a successfully processed in-flight message (SQS ``DeleteMessage``)."""
        if receipt_handle not in self._in_flight:
            raise UnknownReceiptError(f"unknown / already-settled receipt {receipt_handle}")
        del self._in_flight[receipt_handle]

    def fail(self, receipt_handle: int) -> None:
        """Return a failed in-flight message for redelivery, or DLQ it.

        If the message has now been received ``max_receive_count`` times it is
        moved to the DLQ (CLAR-DEPLOY-06) and never redelivered; otherwise it
        re-enters the ready queue (SQS visibility-timeout expiry).
        """
        if receipt_handle not in self._in_flight:
            raise UnknownReceiptError(f"unknown / already-settled receipt {receipt_handle}")
        message = self._in_flight.pop(receipt_handle)
        if message.receive_count >= self.max_receive_count:
            self._dlq.append(message)
        else:
            self._ready.append(message)

    @property
    def dlq_messages(self) -> list[Message]:
        """Messages routed to the per-queue Dead Letter Queue."""
        return list(self._dlq)

    @property
    def ready_depth(self) -> int:
        """Number of messages currently available for delivery."""
        return len(self._ready)


@runtime_checkable
class Handler(Protocol):
    """Worker handler contract: returns normally on success, raises on failure.

    A raised exception is the failure signal that drives redelivery / DLQ routing.
    """

    def __call__(self, body: dict[str, str]) -> None: ...


@dataclass
class IdempotentConsumer:
    """Drives a :class:`StandardQueue` with an idempotent, at-least-once worker.

    Dedupe is keyed on the message ``dedup_key`` (``snapshot_id`` / ``scan_id``,
    CLAR-DEPLOY-06): once a ``dedup_key`` has been processed successfully, a later
    redelivery is acked *without* re-invoking the handler — so the worker's side
    effects are produced at-most-once even under at-least-once delivery.

    A handler that raises is counted as a failed receive: the message is
    ``fail``-ed back to the queue (or DLQ'd at max-receive), and its ``dedup_key``
    is *not* recorded as processed (a poison message never marks itself done).
    """

    queue: StandardQueue
    handler: Handler
    _processed_keys: set[str] = field(default_factory=set)
    handler_invocations: int = 0

    def poll_once(self) -> bool:
        """Receive and settle at most one message. Returns ``False`` if empty."""
        received = self.queue.receive()
        if received is None:
            return False
        message = received.message
        if message.dedup_key in self._processed_keys:
            # Redelivery of an already-processed message: ack without re-running
            # the side-effecting handler (idempotency, CLAR-DEPLOY-06).
            self.queue.ack(received.receipt_handle)
            return True
        try:
            self.handler(message.body)
        except Exception:
            # Failed handler -> return for redelivery / DLQ; do NOT mark done.
            self.queue.fail(received.receipt_handle)
            return True
        self.handler_invocations += 1
        self._processed_keys.add(message.dedup_key)
        self.queue.ack(received.receipt_handle)
        return True

    def drain(self, max_iterations: int = 1000) -> None:
        """Poll until the ready queue is empty (bounded to avoid an infinite loop)."""
        for _ in range(max_iterations):
            if not self.poll_once():
                return
        raise QueueError(f"drain exceeded {max_iterations} iterations — possible redelivery loop")

    @property
    def processed_keys(self) -> frozenset[str]:
        """The set of ``dedup_key`` values whose side effects have been committed."""
        return frozenset(self._processed_keys)


__all__ = [
    "DEFAULT_MAX_RECEIVE_COUNT",
    "Handler",
    "IdempotentConsumer",
    "Message",
    "QueueError",
    "ReceivedMessage",
    "StandardQueue",
    "UnknownReceiptError",
]

"""Unit tests for the CMP-DEPLOY-01 substrate primitives.

These exercise services/substrate/{object_store,queue}.py directly as units
(the DEPLOY-01 ACs in tests/integration/ drive them end-to-end; these give the
fast, offline unit coverage the CI unit-coverage gate measures). They assert the
CLAR-DEPLOY-02 key scheme + path-traversal guard and the CLAR-DEPLOY-06 queue
contract (at-least-once, DLQ-after-3, idempotent consumer).
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from services.substrate.object_store import (
    SNAPSHOT_ARTIFACT_SUFFIXES,
    SNAPSHOT_ARTIFACT_TYPES,
    CrossTenantAccessError,
    InMemoryObjectStore,
    ObjectStore,
    ObjectStoreError,
    PathTraversalError,
    S3ObjectStore,
    SnapshotKeyBuilder,
)
from services.substrate.queue import (
    DEFAULT_MAX_RECEIVE_COUNT,
    IdempotentConsumer,
    Queue,
    QueueError,
    SQSQueue,
    StandardQueue,
    UnknownReceiptError,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# SnapshotKeyBuilder — CLAR-DEPLOY-02 deterministic key scheme
# --------------------------------------------------------------------------- #

_KW = {
    "org_id": "org-abc",
    "codebase_id": "cb-1",
    "commit_sha": "a" * 40,
    "env_digest": "sha256:" + "b" * 64,
}


def test_prefix_matches_clar_deploy_02_scheme() -> None:
    b = SnapshotKeyBuilder(**_KW)
    assert b.prefix == (
        f"orgs/{_KW['org_id']}/codebases/{_KW['codebase_id']}"
        f"/snapshots/{_KW['commit_sha']}/{_KW['env_digest']}/"
    )


def test_artifact_key_for_every_type_carries_prefix_and_suffix() -> None:
    b = SnapshotKeyBuilder(**_KW)
    for art_type, suffix in SNAPSHOT_ARTIFACT_SUFFIXES.items():
        key = b.artifact_key(art_type)  # type: ignore[arg-type]
        assert key == f"{b.prefix}{suffix}"
        assert key.startswith(f"orgs/{_KW['org_id']}/")


def test_all_artifact_keys_returns_the_five_in_order() -> None:
    b = SnapshotKeyBuilder(**_KW)
    keys = b.all_artifact_keys()
    assert tuple(keys) == SNAPSHOT_ARTIFACT_TYPES
    assert len(keys) == 5
    assert len(set(keys.values())) == 5  # all distinct


def test_keys_are_deterministic_across_instances() -> None:
    assert (
        SnapshotKeyBuilder(**_KW).all_artifact_keys()
        == SnapshotKeyBuilder(**_KW).all_artifact_keys()
    )


def test_unknown_artifact_type_raises() -> None:
    b = SnapshotKeyBuilder(**_KW)
    with pytest.raises(ObjectStoreError):
        b.artifact_key("not_a_real_artifact")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad",
    ["../escape", "a/b", "a\\b", "%2e%2e", "%2fetc", "%5c", "x\x00y", ""],
)
@pytest.mark.parametrize("field", ["org_id", "codebase_id", "commit_sha", "env_digest"])
def test_path_traversal_in_any_component_is_rejected(field: str, bad: str) -> None:
    kw = {**_KW, field: bad}
    with pytest.raises(PathTraversalError):
        SnapshotKeyBuilder(**kw)


def test_case_folded_encoded_traversal_is_caught() -> None:
    with pytest.raises(PathTraversalError):
        SnapshotKeyBuilder(**{**_KW, "org_id": "X%2EY"})


# --------------------------------------------------------------------------- #
# InMemoryObjectStore — CLAR-DEPLOY-16 prefix isolation
# --------------------------------------------------------------------------- #


def test_store_is_structural_objectstore() -> None:
    assert isinstance(InMemoryObjectStore(), ObjectStore)


def test_put_get_round_trip_within_org_prefix() -> None:
    store = InMemoryObjectStore()
    key = SnapshotKeyBuilder(**_KW).artifact_key("cpg_tarball")
    store.put(_KW["org_id"], key, b"payload")
    assert store.get(_KW["org_id"], key) == b"payload"


def test_get_missing_object_raises() -> None:
    store = InMemoryObjectStore()
    key = SnapshotKeyBuilder(**_KW).artifact_key("delta_graph")
    with pytest.raises(ObjectStoreError):
        store.get(_KW["org_id"], key)


def test_cross_tenant_key_is_denied() -> None:
    store = InMemoryObjectStore()
    foreign = "orgs/org-other/codebases/cb/snapshots/x/y/cpg.tar.zst"
    with pytest.raises(CrossTenantAccessError):
        store.put(_KW["org_id"], foreign, b"x")
    with pytest.raises(CrossTenantAccessError):
        store.get(_KW["org_id"], foreign)


def test_traversal_in_access_key_is_denied() -> None:
    store = InMemoryObjectStore()
    with pytest.raises(PathTraversalError):
        store.put(_KW["org_id"], f"orgs/{_KW['org_id']}/../escape", b"x")


@pytest.mark.parametrize(
    "bad_key",
    [
        f"orgs/{_KW['org_id']}/%5c../escape",
        f"orgs/{_KW['org_id']}/a\\b/k",
        f"orgs/{_KW['org_id']}/%5C../escape",  # upper-case %5C (case-fold)
    ],
)
def test_backslash_encoded_traversal_in_guard_is_denied(bad_key: str) -> None:
    store = InMemoryObjectStore()
    with pytest.raises(PathTraversalError):
        store.put(_KW["org_id"], bad_key, b"x")


def test_store_validates_org_id_component() -> None:
    store = InMemoryObjectStore()
    with pytest.raises(PathTraversalError):
        store.put("bad/org", "orgs/bad/org/k", b"x")


# --------------------------------------------------------------------------- #
# S3ObjectStore — boto3 adapter behind the same CLAR-DEPLOY-16 guard
# (hermetic: a boto3-S3-shaped fake client is injected; no boto3/moto import.
#  Real-botocore conformance lives in tests/integration/
#  test_substrate_aws_conformance.py per CLAR-DEPLOY-21.)
# --------------------------------------------------------------------------- #


class _FakeS3Exceptions:
    class NoSuchKey(Exception):  # noqa: N818 — mirrors the boto3 exception name
        pass


class _FakeBoto3S3Client:
    """Minimal boto3-S3-shaped fake: put_object/get_object + .exceptions."""

    exceptions = _FakeS3Exceptions

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[str] = []

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.calls.append("put_object")
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        self.calls.append("get_object")
        if (Bucket, Key) not in self.objects:
            raise self.exceptions.NoSuchKey()
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


def test_s3_store_is_structural_objectstore() -> None:
    assert isinstance(S3ObjectStore("bkt", client=_FakeBoto3S3Client()), ObjectStore)


def test_s3_store_round_trip_with_injected_client() -> None:
    client = _FakeBoto3S3Client()
    store = S3ObjectStore("bkt", client=client)
    assert store.bucket == "bkt"
    key = SnapshotKeyBuilder(**_KW).artifact_key("cpg_tarball")
    store.put(_KW["org_id"], key, b"payload")
    assert client.objects == {("bkt", key): b"payload"}
    assert store.get(_KW["org_id"], key) == b"payload"


def test_s3_store_get_missing_object_raises_objectstoreerror() -> None:
    store = S3ObjectStore("bkt", client=_FakeBoto3S3Client())
    key = SnapshotKeyBuilder(**_KW).artifact_key("delta_graph")
    with pytest.raises(ObjectStoreError):
        store.get(_KW["org_id"], key)


def test_s3_store_guard_rejects_before_any_client_call() -> None:
    """The CLAR-DEPLOY-16 guard fires BEFORE the adapter touches the client."""
    client = _FakeBoto3S3Client()
    store = S3ObjectStore("bkt", client=client)
    with pytest.raises(PathTraversalError):
        store.put(_KW["org_id"], f"orgs/{_KW['org_id']}/../escape", b"x")
    with pytest.raises(PathTraversalError):
        store.get(_KW["org_id"], f"orgs/{_KW['org_id']}/%2e%2e/k")
    foreign = "orgs/org-other/codebases/cb/snapshots/x/y/cpg.tar.zst"
    with pytest.raises(CrossTenantAccessError):
        store.put(_KW["org_id"], foreign, b"x")
    with pytest.raises(CrossTenantAccessError):
        store.get(_KW["org_id"], foreign)
    assert client.calls == []  # no boto3-shaped call ever happened
    assert client.objects == {}


# --------------------------------------------------------------------------- #
# StandardQueue — CLAR-DEPLOY-06 at-least-once + DLQ-after-3
# --------------------------------------------------------------------------- #


def test_send_receive_ack_round_trip() -> None:
    q = StandardQueue(name="snap")
    q.send({"snapshot_id": "s1"}, dedup_key="s1")
    assert q.ready_depth == 1
    rcv = q.receive()
    assert rcv is not None
    assert rcv.message.receive_count == 1
    q.ack(rcv.receipt_handle)
    assert q.ready_depth == 0
    assert q.receive() is None


def test_ack_unknown_receipt_raises() -> None:
    q = StandardQueue(name="q")
    with pytest.raises(UnknownReceiptError):
        q.ack(999)


def test_fail_unknown_receipt_raises() -> None:
    q = StandardQueue(name="q")
    with pytest.raises(UnknownReceiptError):
        q.fail(999)


def test_fail_redelivers_until_max_receive_then_dlq() -> None:
    q = StandardQueue(name="snap")  # default max-receive 3
    q.send({"snapshot_id": "poison"}, dedup_key="poison")
    for expected_count in range(1, DEFAULT_MAX_RECEIVE_COUNT + 1):
        rcv = q.receive()
        assert rcv is not None
        assert rcv.message.receive_count == expected_count
        q.fail(rcv.receipt_handle)
    # Third fail (receive_count == 3) routes to the DLQ; not redelivered.
    assert q.ready_depth == 0
    assert q.receive() is None
    assert len(q.dlq_messages) == 1
    assert q.dlq_messages[0].dedup_key == "poison"


# --------------------------------------------------------------------------- #
# SQSQueue — boto3 adapter behind the same Queue Protocol
# (hermetic: a boto3-SQS-shaped fake client is injected; no boto3/moto import.
#  Real-botocore send/receive/delete conformance lives in tests/integration/
#  test_substrate_aws_conformance.py per CLAR-DEPLOY-21.)
# --------------------------------------------------------------------------- #


class _FakeSqsMessage:
    """One message sitting in a :class:`_FakeSqsClient` queue."""

    def __init__(self, message_id: str, body: str, dedup_key: str) -> None:
        self.message_id = message_id
        self.body = body
        self.dedup_key = dedup_key
        self.receive_count = 0


class _FakeSqsClient:
    """Minimal boto3-SQS-shaped fake: send/receive/delete/change_visibility.

    Models exactly the subset :class:`SQSQueue` calls — a FIFO ready list plus
    an in-flight map, keyed by a fake string ``ReceiptHandle`` (deliberately a
    string, never an int, so a test that leaked a raw boto3 handle through the
    port would fail type-wise rather than accidentally working).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._ready: list[_FakeSqsMessage] = []
        self._in_flight: dict[str, _FakeSqsMessage] = {}
        self._next_id = 0

    def send_message(
        self,
        *,
        QueueUrl: str,  # noqa: N803
        MessageBody: str,  # noqa: N803
        MessageAttributes: dict[str, Any],  # noqa: N803
    ) -> dict[str, str]:
        self.calls.append("send_message")
        self._next_id += 1
        message_id = f"msg-{self._next_id}"
        dedup_key = MessageAttributes["dedup_key"]["StringValue"]
        self._ready.append(_FakeSqsMessage(message_id, MessageBody, dedup_key))
        return {"MessageId": message_id}

    def receive_message(self, *, QueueUrl: str, **_kw: Any) -> dict[str, Any]:  # noqa: N803
        self.calls.append("receive_message")
        if not self._ready:
            return {}
        message = self._ready.pop(0)
        message.receive_count += 1
        receipt_handle = f"receipt-{message.message_id}-{message.receive_count}"
        self._in_flight[receipt_handle] = message
        return {
            "Messages": [
                {
                    "MessageId": message.message_id,
                    "ReceiptHandle": receipt_handle,
                    "Body": message.body,
                    "MessageAttributes": {
                        "dedup_key": {"DataType": "String", "StringValue": message.dedup_key}
                    },
                    "Attributes": {"ApproximateReceiveCount": str(message.receive_count)},
                }
            ]
        }

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str) -> None:  # noqa: N803
        self.calls.append("delete_message")
        self._in_flight.pop(ReceiptHandle, None)

    def change_message_visibility(
        self,
        *,
        QueueUrl: str,  # noqa: N803
        ReceiptHandle: str,  # noqa: N803
        VisibilityTimeout: int,  # noqa: N803
    ) -> None:
        self.calls.append("change_message_visibility")
        message = self._in_flight.pop(ReceiptHandle, None)
        if message is not None:
            self._ready.insert(0, message)  # immediately re-visible, FIFO head


def test_sqs_queue_is_structural_queue() -> None:
    assert isinstance(SQSQueue("https://sqs/q", client=_FakeSqsClient()), Queue)
    assert isinstance(StandardQueue(name="q"), Queue)


def test_sqs_queue_send_receive_ack_round_trip() -> None:
    client = _FakeSqsClient()
    q = SQSQueue("https://sqs/q", client=client)
    assert q.queue_url == "https://sqs/q"
    q.send({"snapshot_id": "s1"}, dedup_key="s1")
    rcv = q.receive()
    assert rcv is not None
    assert rcv.message.body == {"snapshot_id": "s1"}
    assert rcv.message.dedup_key == "s1"
    assert rcv.message.receive_count == 1
    q.ack(rcv.receipt_handle)
    assert client.calls[-1] == "delete_message"
    assert q.receive() is None  # deleted, not redelivered


def test_sqs_queue_ack_and_fail_reject_unknown_receipt_before_any_client_call() -> None:
    client = _FakeSqsClient()
    q = SQSQueue("https://sqs/q", client=client)
    with pytest.raises(UnknownReceiptError):
        q.ack(999)
    with pytest.raises(UnknownReceiptError):
        q.fail(999)
    assert client.calls == [], "guard must fire before any boto3-shaped call"


def test_sqs_queue_fail_resets_visibility_for_redelivery() -> None:
    client = _FakeSqsClient()
    q = SQSQueue("https://sqs/q", client=client)
    q.send({"snapshot_id": "poison"}, dedup_key="poison")
    for expected_count in range(1, DEFAULT_MAX_RECEIVE_COUNT + 1):
        rcv = q.receive()
        assert rcv is not None
        assert rcv.message.receive_count == expected_count
        q.fail(rcv.receipt_handle)
    assert client.calls.count("change_message_visibility") == DEFAULT_MAX_RECEIVE_COUNT
    # Real-SQS DLQ-after-3 routing is server-side RedrivePolicy state with no
    # client-side "move to DLQ" call (see SQSQueue.fail docstring) — asserted
    # against real botocore/moto mechanics in
    # test_substrate_aws_conformance.py, not reproducible on this fake, which
    # models no queue-attribute/RedrivePolicy state.


def test_sqs_queue_matches_standard_queue_contract() -> None:
    """SQSQueue and StandardQueue agree on the Queue Protocol round trip."""
    both: list[Queue] = [
        StandardQueue(name="parity"),
        SQSQueue("https://sqs/parity", client=_FakeSqsClient()),
    ]
    for q in both:
        q.send({"snapshot_id": "p1"}, dedup_key="p1")
        rcv = q.receive()
        assert rcv is not None
        assert rcv.message.body == {"snapshot_id": "p1"}
        assert rcv.message.dedup_key == "p1"
        q.ack(rcv.receipt_handle)
        assert q.receive() is None


# --------------------------------------------------------------------------- #
# IdempotentConsumer — dedupe by snapshot/scan id
# --------------------------------------------------------------------------- #


def test_consumer_processes_then_dedupes_redelivery() -> None:
    q = StandardQueue(name="snap")
    seen: list[str] = []
    consumer = IdempotentConsumer(queue=q, handler=lambda body: seen.append(body["snapshot_id"]))
    q.send({"snapshot_id": "s1"}, dedup_key="s1")
    # First delivery runs the handler.
    assert consumer.poll_once() is True
    assert consumer.handler_invocations == 1
    assert consumer.processed_keys == frozenset({"s1"})
    # A re-sent message with the same dedup_key is acked without re-running.
    q.send({"snapshot_id": "s1"}, dedup_key="s1")
    assert consumer.poll_once() is True
    assert consumer.handler_invocations == 1  # unchanged
    assert seen == ["s1"]


def test_consumer_poll_empty_returns_false() -> None:
    consumer = IdempotentConsumer(queue=StandardQueue(name="q"), handler=lambda body: None)
    assert consumer.poll_once() is False


def test_poison_message_is_failed_and_not_marked_done() -> None:
    q = StandardQueue(name="snap")

    def boom(body: dict[str, str]) -> None:
        raise ValueError("handler failure")

    consumer = IdempotentConsumer(queue=q, handler=boom)
    q.send({"snapshot_id": "bad"}, dedup_key="bad")
    # Poll three times: each fails the handler; the third DLQs the message.
    for _ in range(DEFAULT_MAX_RECEIVE_COUNT):
        assert consumer.poll_once() is True
    assert consumer.handler_invocations == 0
    assert consumer.processed_keys == frozenset()
    assert len(q.dlq_messages) == 1


def test_drain_empties_the_ready_queue() -> None:
    q = StandardQueue(name="snap")
    handled: list[str] = []
    consumer = IdempotentConsumer(queue=q, handler=lambda body: handled.append(body["snapshot_id"]))
    for i in range(5):
        q.send({"snapshot_id": f"s{i}"}, dedup_key=f"s{i}")
    consumer.drain()
    assert q.ready_depth == 0
    assert sorted(handled) == [f"s{i}" for i in range(5)]
    assert consumer.handler_invocations == 5


def test_drain_guard_raises_on_runaway() -> None:
    q = StandardQueue(name="snap")
    # A handler that always fails keeps re-enqueuing until DLQ; with a tiny
    # iteration cap and many poison messages, drain exceeds the cap and raises.
    consumer = IdempotentConsumer(
        queue=q, handler=lambda body: (_ for _ in ()).throw(RuntimeError("fail"))
    )
    for i in range(10):
        q.send({"snapshot_id": f"p{i}"}, dedup_key=f"p{i}")
    with pytest.raises(QueueError):
        consumer.drain(max_iterations=2)

"""Unit tests for the CMP-DEPLOY-01 substrate primitives.

These exercise services/substrate/{object_store,queue}.py directly as units
(the DEPLOY-01 ACs in tests/integration/ drive them end-to-end; these give the
fast, offline unit coverage the CI unit-coverage gate measures). They assert the
CLAR-DEPLOY-02 key scheme + path-traversal guard and the CLAR-DEPLOY-06 queue
contract (at-least-once, DLQ-after-3, idempotent consumer).
"""

from __future__ import annotations

import pytest

from services.substrate.object_store import (
    SNAPSHOT_ARTIFACT_SUFFIXES,
    SNAPSHOT_ARTIFACT_TYPES,
    CrossTenantAccessError,
    InMemoryObjectStore,
    ObjectStore,
    ObjectStoreError,
    PathTraversalError,
    SnapshotKeyBuilder,
)
from services.substrate.queue import (
    DEFAULT_MAX_RECEIVE_COUNT,
    IdempotentConsumer,
    QueueError,
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

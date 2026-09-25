"""Private, task-owned filesystem controls; never installed runtime authority."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PosixPath
from threading import Event, Thread, current_thread
from typing import Any
from uuid import UUID

import pytest

from tests.unit.test_process_evidence import graph_document, graph_node
from tests.unit.test_runtime_journal import History, refusal, root, uid, wire
from tools.worker import runtime_evidence as evidence
from tools.worker.process_evidence import EvidenceBlob

pytestmark = pytest.mark.unit

_FAULT_OPERATIONS = ("write", "link", "unlink", "fchmod", "fsync", "read", "close", "mkdir")
_FAULT_PHASES = (
    "begin-manifest",
    "begin-refusal",
    "member-manifest",
    "member-refusal",
    "finalize-manifest",
    "finalize-refusal",
    "recover-complete",
    "recover-pair",
    "reconcile-complete",
    "reconcile-pair",
    "writer-close",
)


def _blob(raw: bytes) -> EvidenceBlob:
    return EvidenceBlob(raw, hashlib.sha256(raw).digest())


def _installation(tmp_path: Path) -> evidence.RuntimeEvidenceInstallation:
    tmp_path.chmod(0o700)
    tree, work = tmp_path / "evidence", tmp_path / "work"
    for directory in (tree, work, tree / "attempts", tree / "refusals"):
        directory.mkdir(mode=0o700)
        directory.chmod(0o700)
    document = root()
    document.update(
        deployment_id=uid(2),
        store_id=uid(1),
        owner_uid=os.geteuid(),
        owner_gid=os.getegid(),
        evidence_root=str(tree),
        host_work_root=str(work),
    )
    raw = wire(document)
    (tree / "root.json").write_bytes(raw)
    (tree / "root.json").chmod(0o400)
    (tree / "writer.lock").write_bytes(b"")
    (tree / "writer.lock").chmod(0o600)
    return evidence.RuntimeEvidenceInstallation(
        UUID(uid(2)),
        UUID(uid(1)),
        "diagnostic",
        PosixPath(tree),
        PosixPath(work),
        os.geteuid(),
        os.getegid(),
        hashlib.sha256(raw).digest(),
    )


def _members(history: History) -> list[tuple[evidence.MemberSelector, bytes]]:
    result = []
    for kind, field in (
        ("prerequisite", "initial_prerequisite"),
        ("authority-inventory", "authority_inventory"),
        ("request", "request"),
        ("input", "input"),
        ("launch", "launch"),
        ("parent-barrier", "parent_barrier"),
    ):
        if history.m[field] is not None:
            result.append(
                (evidence.MemberSelector(kind, 0), history.data[history.m[field]["sha256"]])
            )
    for index, item in enumerate(history.m["metadata"]):
        result.append(
            (evidence.MemberSelector("metadata", index), history.data[item["blob"]["sha256"]])
        )
    inventory = json.loads(history.data[history.m["authority_inventory"]["sha256"]])
    for item in inventory["objects"]:
        result.append(
            (
                evidence.MemberSelector("authority", evidence._AUTH.index(item["role"])),
                history.data[item["bytes"]["sha256"]],
            )
        )
    return result


@pytest.mark.parametrize("mode", evidence._MODES)
def test_four_modes_publish_rebind_read_and_recover(tmp_path: Path, mode: str) -> None:
    installation = _installation(tmp_path)
    history = History(mode)
    key = evidence._ScopeKey("attempt", UUID(history.m["attempt_id"]))
    parent = UUID(uid(100))
    raw = wire(history.m)
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        scope = publisher.begin_manifest(key, parent, raw)
        assert not (
            installation.evidence_root / "attempts" / str(key.id) / "manifest.json"
        ).exists()
        members = _members(history)
        for index, (selector, content) in enumerate(members):
            ack = scope.publish_member(UUID(uid(200 + index)), selector, _blob(content))
            assert ack.publication.file.data == content
            assert ack.completion == "local-fsync-readback"
        ack = scope.finalize()
        assert ack.publication.file.data == raw
        assert ack.publication.record is not None
        assert ack.publication.record.validation == "local-structure-only"
        assert publisher._core.last_work.owner_calls <= 16
        scope.close()
    finally:
        publisher.close()
    reader = evidence.open_runtime_publication_reader(installation)
    try:
        visible = reader.read_publication(evidence._PublicationKey(key, parent))
        assert visible.file.data == raw
        assert visible.visibility == "verified-visible-file"
        assert not hasattr(visible, "completion")
    finally:
        reader.close()
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        rebound = publisher.begin_manifest(key, parent, raw)
        assert rebound.finalize().disposition == "exact-recovery"
        rebound.close()
        recovered = publisher.recover_publication(evidence._PublicationKey(key, parent))
        assert recovered.publication.file.data == raw
        assert recovered.disposition == "exact-recovery"
    finally:
        publisher.close()


@pytest.mark.parametrize("count", (0, 1, 16))
def test_refusal_members_and_exact_parent_recovery(tmp_path: Path, count: int) -> None:
    installation = _installation(tmp_path)
    contents = [f"opaque refusal evidence {index}".encode() for index in range(count)]
    row = refusal([History.reference(raw) for raw in contents])
    key = evidence._ScopeKey("refusal", UUID(row["refusal_id"]))
    parent = UUID(uid(100))
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        scope = publisher.begin_refusal(key, parent, wire(row))
        for index, raw in enumerate(contents):
            scope.publish_member(
                UUID(uid(200 + index)),
                evidence.MemberSelector("refusal-evidence", index),
                _blob(raw),
            )
        assert scope.finalize().publication.file.data == wire(row)
    finally:
        publisher.close()


def test_operational_installation_refuses_before_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installation = replace(_installation(tmp_path), artifact_domain="operational")
    monkeypatch.setattr(os, "open", lambda *_args, **_kwargs: pytest.fail("unexpected I/O"))
    for opener in (evidence._open_diagnostic_publisher, evidence.open_runtime_publication_reader):
        with pytest.raises(evidence.RuntimePublicationError, match=r"^unsupported$"):
            opener(installation)


def test_second_writer_refuses_without_changing_first(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    first = evidence._open_diagnostic_publisher(installation)
    try:
        with pytest.raises(evidence.RuntimePublicationError):
            evidence._open_diagnostic_publisher(installation)
        assert not list((installation.evidence_root / "attempts").iterdir())
    finally:
        first.close()


@pytest.mark.parametrize("primary", (None, "a" * 64))
def test_duplicate_refusal_hash_is_rejected_before_scope_effects(
    tmp_path: Path, primary: Any
) -> None:
    installation = _installation(tmp_path)
    reference = History.reference(b"same bytes")
    row = refusal([reference, reference.copy()])
    row["primary_error_id"] = primary
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        with pytest.raises(evidence.RuntimePublicationError):
            publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(row["refusal_id"])), UUID(uid(100)), wire(row)
            )
        assert list((installation.evidence_root / "refusals").iterdir()) == []
    finally:
        publisher.close()


def _maximum_history(mode: str) -> History:
    history = History(mode)
    for index, (item, field, size) in enumerate(
        zip(
            history.m["metadata"],
            (
                "installation_sha256",
                "controller_profile_sha256",
                "domain_profile_sha256",
                "inventory_sha256",
            ),
            (65536, 131072, 65536, 8388608),
            strict=True,
        )
    ):
        ref = history.add(bytes([65 + index]) * size)
        item["blob"] = ref
        item["observation"]["size"] = size
        history.m[field] = ref["sha256"]
    for field, size in (
        ("request", 65536),
        ("launch", 65536),
        ("input", 263244 if mode == "python-syntax" else 2621440),
        ("parent_barrier", 16384),
    ):
        if history.m[field] is not None:
            history.m[field] = history.add(field.encode()[:1] * size)
    inventory = json.loads(history.data[history.m["authority_inventory"]["sha256"]])
    prerequisite = json.loads(history.data[history.m["initial_prerequisite"]["sha256"]])
    count = len(inventory["objects"])
    for index, item in enumerate(inventory["objects"]):
        size = 1048576 // count + (1048576 % count if index == 0 else 0)
        item["bytes"] = history.add(bytes([97 + index]) * size)
        if item["role"] not in ("admission", "execution-authorization"):
            prerequisite[item["role"].replace("-", "_") + "_evidence_sha256"] = item["bytes"][
                "sha256"
            ]
    ref = history.add(wire(prerequisite))
    history.m["initial_prerequisite"] = ref
    inventory["prerequisite"] = ref
    history.m["authority_inventory"] = history.add(wire(inventory))
    return history


@pytest.mark.parametrize("mode", evidence._MODES)
def test_maximum_initial_modes_and_work_reservations(tmp_path: Path, mode: str) -> None:
    history = _maximum_history(mode)
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    try:
        key = evidence._ScopeKey("attempt", UUID(history.m["attempt_id"]))
        scope = publisher.begin_manifest(key, UUID(uid(100)), wire(history.m))
        for index, (selector, raw) in enumerate(_members(history)):
            scope.publish_member(UUID(uid(200 + index)), selector, _blob(raw))
            work = publisher._core.last_work
            assert work.owner_calls <= 16
            assert work.read <= 134217728 and work.write <= 67108864 and work.hash <= 268435456
            assert work.copies <= 192 * 1048576
            assert work.peak_buffers <= 96 * 1048576 and work.peak_slots <= 262144
            assert work.observations <= 512 and work.peak_fds <= 128 and work.os_calls <= 8192
        assert scope.finalize().publication.file.data == wire(history.m)
        completed, unresolved = publisher._core._completed(key)
        assert len(completed) == dict(zip(evidence._MODES, (12, 13, 16, 17), strict=True))[mode]
        assert unresolved == 0
        assert all(size < 4096 for size in completed.values())
    finally:
        publisher.close()


@pytest.mark.parametrize("match_index", (0, 15))
def test_refusal_decodes_all_sixteen_candidates(
    tmp_path: Path, match_index: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    installation = _installation(tmp_path)
    rows = [graph_document([graph_node(0)]) for _ in range(16)]
    for index, row in enumerate(rows):
        row["error_id"] = uid(1000 + index)
    contents = [wire(row) for row in rows]
    refusal_row = refusal([History.reference(raw) for raw in contents])
    refusal_row["primary_error_id"] = rows[match_index]["error_id"]
    key = evidence._ScopeKey("refusal", UUID(refusal_row["refusal_id"]))
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        scope = publisher.begin_refusal(key, UUID(uid(100)), wire(refusal_row))
        for index, raw in enumerate(contents):
            scope.publish_member(
                UUID(uid(200 + index)),
                evidence.MemberSelector("refusal-evidence", index),
                _blob(raw),
            )
        calls = []
        decode = evidence.decode_error_graph

        def spy(raw: bytes) -> Any:
            calls.append(raw)
            return decode(raw)

        with monkeypatch.context() as patch:
            patch.setattr(evidence, "decode_error_graph", spy)
            assert scope.finalize().publication.file.data == wire(refusal_row)
        assert calls == contents
        assert 16 < publisher._core.last_work.owner_calls <= 24
    finally:
        publisher.close()


@pytest.mark.parametrize("changed", ("deployment_id", "store_id", "attempt_id", "artifact_domain"))
def test_parent_root_binding_rejects_before_effects(tmp_path: Path, changed: str) -> None:
    installation = _installation(tmp_path)
    history = History()
    history.m[changed] = "operational" if changed == "artifact_domain" else uid(999)
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        with pytest.raises(evidence.RuntimePublicationError):
            publisher.begin_manifest(
                evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
            )
        assert not list((installation.evidence_root / "attempts").iterdir())
    finally:
        publisher.close()


@pytest.mark.parametrize(
    "kind,ordinal",
    (("unknown", 0), ("metadata", 4), ("input", 1), ("authority", -1), ("authority", True)),
)
def test_bad_selector_never_opens_files(
    tmp_path: Path, kind: Any, ordinal: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    installation = _installation(tmp_path)
    history = History()
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
        )
        with monkeypatch.context() as patch:
            patch.setattr(
                os, "open", lambda *_args, **_kwargs: pytest.fail("I/O before validation")
            )
            with pytest.raises(evidence.RuntimePublicationError):
                scope.publish_member(
                    UUID(uid(101)), evidence.MemberSelector(kind, ordinal), _blob(b"x")
                )
    finally:
        publisher.close()


@pytest.mark.parametrize("operation", ("finalize", "recover"))
def test_missing_children_never_publish_parent(tmp_path: Path, operation: str) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    key = evidence._ScopeKey("attempt", UUID(uid(3)))
    try:
        scope = publisher.begin_manifest(key, UUID(uid(100)), wire(History().m))
        with pytest.raises(evidence.RuntimePublicationError):
            if operation == "finalize":
                scope.finalize()
            else:
                publisher.recover_publication(evidence._PublicationKey(key, UUID(uid(100))))
        assert not (
            installation.evidence_root / "attempts" / str(key.id) / "manifest.json"
        ).exists()
    finally:
        publisher.close()


def test_new_publication_id_cannot_adopt_equal_destination(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    history = History()
    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
        )
        selector, raw = _members(history)[0]
        scope.publish_member(UUID(uid(101)), selector, _blob(raw))
        with pytest.raises(evidence.RuntimePublicationError):
            scope.publish_member(UUID(uid(102)), selector, _blob(raw))
        assert (
            scope.publish_member(UUID(uid(101)), selector, _blob(raw)).disposition
            == "exact-recovery"
        )
    finally:
        publisher.close()


@pytest.mark.parametrize("name", ("write", "fsync", "fchmod", "link", "unlink"))
@pytest.mark.parametrize("number", (1, 2))
def test_member_publication_fault_has_no_ack_and_invalidates_after_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    number: int,
) -> None:
    installation = _installation(tmp_path)
    history = History()
    publisher = evidence._open_diagnostic_publisher(installation)
    calls = 0
    original = getattr(os, name)

    def fail(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == number:
            raise OSError("private filename and bytes must not become wrapper text")
        return original(*args, **kwargs)

    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
        )
        selector, raw = _members(history)[0]
        with monkeypatch.context() as patch:
            patch.setattr(os, name, fail)
            if name in ("link", "unlink") and number == 2:
                scope.publish_member(UUID(uid(101)), selector, _blob(raw))
            else:
                with pytest.raises(evidence.RuntimePublicationError) as captured:
                    scope.publish_member(UUID(uid(101)), selector, _blob(raw))
                assert str(captured.value) in evidence._REASONS
                assert publisher._core.invalidated
        if publisher._core.invalidated:
            with pytest.raises(evidence.RuntimePublicationError):
                scope.publish_member(UUID(uid(101)), selector, _blob(raw))
    finally:
        publisher.close()


class _Poison:
    def __str__(self) -> str:
        pytest.fail("untrusted formatting")

    def __bool__(self) -> bool:
        pytest.fail("untrusted truth")

    def __iter__(self) -> Any:
        pytest.fail("untrusted iteration")


@pytest.mark.parametrize(
    "field,mutation",
    (
        ("deployment_id", "uuid-int"),
        ("evidence_root", "path-element"),
        ("evidence_root", "path-container"),
        ("evidence_root", "path-cache"),
        ("owner_uid", True),
        ("owner_gid", -1),
        ("root_record_sha256", bytearray(32)),
        ("artifact_domain", _Poison()),
        ("owner_uid", "missing"),
    ),
)
def test_poisoned_installation_never_formats_or_opens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    mutation: Any,
) -> None:
    installation = _installation(tmp_path)
    if mutation == "uuid-int" if type(mutation) is str else False:
        value = UUID(uid(2))
        object.__setattr__(value, "int", _Poison())
    elif type(mutation) is str and mutation.startswith("path-"):
        value = PosixPath(str(installation.evidence_root))
        storage = "_raw_paths" if hasattr(value, "_raw_paths") else "_parts"
        if mutation == "path-element":
            object.__setattr__(value, storage, ["/", _Poison()])
        elif mutation == "path-container":
            object.__setattr__(value, storage, _Poison())
        else:
            object.__setattr__(value, "_str", _Poison())
    else:
        value = mutation
    if mutation == "missing" if type(mutation) is str else False:
        object.__delattr__(installation, field)
    else:
        object.__setattr__(installation, field, value)
    if mutation == "path-cache":
        # Cached formatting is deliberately ignored; genuine raw components survive.
        opened = evidence._open_diagnostic_publisher(installation)
        opened.close()
        return
    with monkeypatch.context() as patch:
        patch.setattr(os, "open", lambda *_args, **_kwargs: pytest.fail("I/O before admission"))
        for opener in (
            evidence._open_diagnostic_publisher,
            evidence.open_runtime_publication_reader,
        ):
            with pytest.raises(evidence.RuntimePublicationError):
                opener(installation)


@pytest.mark.parametrize("target", ("root.json", "writer.lock", "attempts", "work"))
@pytest.mark.parametrize("change", ("symlink", "mode"))
def test_root_object_path_and_mode_refusal(tmp_path: Path, target: str, change: str) -> None:
    installation = _installation(tmp_path)
    path = installation.host_work_root if target == "work" else installation.evidence_root / target
    if change == "symlink":
        saved = path.with_name(path.name + "-saved")
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=saved.is_dir())
    else:
        path.chmod(0o770 if path.is_dir() else 0o660)
    with pytest.raises(evidence.RuntimePublicationError):
        evidence._open_diagnostic_publisher(installation)


@pytest.mark.parametrize("target", ("root.json", "writer.lock", "work"))
def test_held_root_object_drift_refuses(tmp_path: Path, target: str) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        path = (
            installation.host_work_root if target == "work" else installation.evidence_root / target
        )
        path.chmod(0o700 if target != "work" else 0o750)
        with pytest.raises(evidence.RuntimePublicationError):
            publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
            )
    finally:
        publisher.close()


def test_ancestor_sibling_activity_not_measured_root_drift(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        (tmp_path / "unrelated-sibling").mkdir(mode=0o700)
        scope = publisher.begin_refusal(
            evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
        )
        scope.finalize()
    finally:
        publisher.close()


@pytest.mark.parametrize("failure_class", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("release_first", (False, True))
def test_interruption_is_primary_when_cleanup_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_class: type[BaseException],
    release_first: bool,
) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    failure = failure_class("private cause")
    prior = OSError("prior implicit context")
    failure.__context__ = prior
    close = os.close
    read = os.read
    selected: list[int] = []
    uncertain: list[int] = []
    counts: dict[int, int] = {}

    def interrupt(fd: int, amount: int) -> bytes:
        if not selected:
            selected.append(fd)
            raise failure
        return read(fd, amount)

    def close_failure(fd: int) -> None:
        if selected and fd == selected[0]:
            counts[fd] = counts.get(fd, 0) + 1
            if release_first:
                close(fd)
            else:
                uncertain.append(fd)
            raise OSError("uncertain close")
        close(fd)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(os, "read", interrupt)
            patch.setattr(os, "close", close_failure)
            with pytest.raises(failure_class) as captured:
                publisher.begin_refusal(
                    evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
                )
        assert captured.value is failure
        assert list(counts.values()) == [1]
        assert isinstance(failure.__cause__, BaseExceptionGroup)
        assert prior in failure.__cause__.exceptions
    finally:
        # Only the test's deliberately unclosed descriptor is cleaned here.
        # Product code must not retry a close-failed numeric descriptor.
        for fd in uncertain:
            close(fd)
        publisher.close()


@pytest.mark.parametrize("stage", ("complete", "truncated", "unknown-id", "wrong-bytes"))
def test_exact_parent_rebind_requires_complete_original_plan(tmp_path: Path, stage: str) -> None:
    installation = _installation(tmp_path)
    key = evidence._ScopeKey("attempt", UUID(uid(3)))
    parent = UUID(uid(100))
    raw = wire(History().m)
    publisher = evidence._open_diagnostic_publisher(installation)
    publisher.begin_manifest(key, parent, raw)
    publisher.close()
    staged = (
        installation.evidence_root / "attempts" / str(key.id) / "staging" / (str(parent) + ".data")
    )
    if stage == "truncated":
        staged.chmod(0o600)
        staged.write_bytes(raw[:-1])
        staged.chmod(0o400)
        with pytest.raises(evidence.RuntimePublicationError):
            evidence._open_diagnostic_publisher(installation)
        return
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        if stage == "complete":
            assert publisher.begin_manifest(key, parent, raw) is not None
        else:
            with pytest.raises(evidence.RuntimePublicationError):
                publisher.begin_manifest(
                    key,
                    UUID(uid(101)) if stage == "unknown-id" else parent,
                    raw.replace(b"diagnostic", b"other-value") if stage == "wrong-bytes" else raw,
                )
    finally:
        publisher.close()


@pytest.mark.parametrize("position", ("before", "equal", "after"))
def test_prerequisite_time_relative_to_manifest(tmp_path: Path, position: str) -> None:
    history = History()
    prerequisite = json.loads(history.data[history.m["initial_prerequisite"]["sha256"]])
    if position == "before":
        history.m["created_at"] = "2026-09-25T09:59:59.999999Z"
    elif position == "equal":
        history.m["created_at"] = prerequisite["valid_until"]
    else:
        history.m["created_at"] = "2026-09-25T10:01:00.000001Z"
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
        )
        for index, (selector, raw) in enumerate(_members(history)[:2]):
            scope.publish_member(UUID(uid(200 + index)), selector, _blob(raw))
        with pytest.raises(evidence.RuntimePublicationError):
            selector, raw = _members(history)[-1]
            scope.publish_member(UUID(uid(300)), selector, _blob(raw))
    finally:
        publisher.close()


@pytest.mark.parametrize("point", ("link-before-unlink", "unlink-before-sync"))
def test_uncertain_publication_requires_fresh_read_sync_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    point: str,
) -> None:
    installation = _installation(tmp_path)
    history = History()
    key = evidence._ScopeKey("attempt", UUID(uid(3)))
    publisher = evidence._open_diagnostic_publisher(installation)
    scope = publisher.begin_manifest(key, UUID(uid(100)), wire(history.m))
    selector, raw = _members(history)[0]
    unlink, sync = os.unlink, os.fsync
    unlinked = False

    def fail_unlink(*args: Any, **kwargs: Any) -> None:
        nonlocal unlinked
        if point == "link-before-unlink":
            raise OSError("interrupted after link")
        unlink(*args, **kwargs)
        unlinked = True

    def fail_sync(fd: int) -> None:
        if unlinked:
            raise OSError("interrupted after unlink")
        sync(fd)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(os, "unlink", fail_unlink)
            patch.setattr(os, "fsync", fail_sync)
            with pytest.raises(evidence.RuntimePublicationError):
                scope.publish_member(UUID(uid(101)), selector, _blob(raw))
        assert publisher._core.invalidated
        with pytest.raises(evidence.RuntimePublicationError):
            publisher.recover_publication(evidence._PublicationKey(key, UUID(uid(101))))
    finally:
        publisher.close()
    final = (
        installation.evidence_root
        / "attempts"
        / str(key.id)
        / "blobs"
        / hashlib.sha256(raw).hexdigest()
    )
    assert final.read_bytes() == raw
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        # Opening alone neither deletes residue nor returns publication acknowledgment.
        assert final.stat().st_nlink == (2 if point == "link-before-unlink" else 1)
        ack = publisher.recover_publication(evidence._PublicationKey(key, UUID(uid(101))))
        assert ack.publication.file.data == raw
        assert ack.disposition == "exact-recovery"
        assert final.stat().st_nlink == 1
    finally:
        publisher.close()


def test_actual_io_and_hash_work_is_covered_by_reservations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installation = _installation(tmp_path)
    history = _maximum_history("verifier-historical")
    publisher = evidence._open_diagnostic_publisher(installation)
    scope = publisher.begin_manifest(
        evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
    )
    read, write, sha = os.read, os.write, hashlib.sha256
    measured = {"read": 0, "write": 0, "hash": 0}

    class CountedHash:
        def __init__(self, data: Any = b"") -> None:
            measured["hash"] += len(data)
            self.inner = sha(data)

        def update(self, data: Any) -> None:
            measured["hash"] += len(data)
            self.inner.update(data)

        def digest(self) -> bytes:
            return self.inner.digest()

        def hexdigest(self) -> str:
            return self.inner.hexdigest()

    def counted_read(fd: int, size: int) -> bytes:
        data = read(fd, size)
        measured["read"] += len(data)
        return data

    def counted_write(fd: int, data: Any) -> int:
        size = write(fd, data)
        measured["write"] += size
        return size

    try:
        selector, raw = next(
            pair for pair in _members(history) if pair[0] == evidence.MemberSelector("metadata", 3)
        )
        blob = _blob(raw)
        with monkeypatch.context() as patch:
            patch.setattr(os, "read", counted_read)
            patch.setattr(os, "write", counted_write)
            patch.setattr(hashlib, "sha256", CountedHash)
            scope.publish_member(UUID(uid(200)), selector, blob)
        work = publisher._core.last_work
        assert measured["read"] == work.read
        assert measured["write"] == work.write
        assert 0 < measured["hash"] <= work.hash
        assert work.copies >= 3 * work.read
        assert work.peak_buffers >= 2 * len(raw) + 12 * 1048576
    finally:
        publisher.close()


@pytest.mark.parametrize("phase", ("ordinary", "refusal", "root"))
def test_owner_calls_are_admitted_before_delegate(phase: str) -> None:
    work = evidence._Work(root=phase == "root", refusal_final=phase == "refusal")
    work.owner_calls = {"ordinary": 16, "refusal": 24, "root": 32768}[phase]
    with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
        evidence._decode("root", wire(root()), work)


def test_whole_operation_deadline_includes_completed_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    key = evidence._ScopeKey("refusal", UUID(uid(88)))
    scope = publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
    visible = publisher._core._visible
    clock = evidence.time.monotonic_ns
    now = [clock()]

    def delayed(*args: Any, **kwargs: Any) -> Any:
        result = visible(*args, **kwargs)
        now[0] += 2000000001
        return result

    try:
        with monkeypatch.context() as patch:
            patch.setattr(evidence.time, "monotonic_ns", lambda: now[0])
            patch.setattr(publisher._core, "_visible", delayed)
            with pytest.raises(evidence.RuntimePublicationError, match=r"^deadline$"):
                scope.finalize()
        assert publisher._core.invalidated
        assert (installation.evidence_root / "refusals" / str(key.id) / "refusal.json").exists()
    finally:
        publisher.close()


def _stored_refusal_scope(installation: evidence.RuntimeEvidenceInstallation, index: int) -> None:
    scope_id, publication_id = UUID(uid(10000 + index)), UUID(uid(20000 + index))
    row = refusal()
    row["refusal_id"] = str(scope_id)
    raw = wire(row)
    directory = installation.evidence_root / "refusals" / str(scope_id)
    directory.mkdir(mode=0o700)
    (directory / "staging").mkdir(mode=0o700)
    (directory / "blobs").mkdir(mode=0o700)
    intent = {
        "schema": "scanipy-runtime-publication-intent/1",
        "publication_id": str(publication_id),
        "store_id": str(installation.store_id),
        "scope_kind": "refusal",
        "scope_id": str(scope_id),
        "role": "refusal",
        "destination": "refusal.json",
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "expected_previous_event_digest": None,
    }
    for path, data in (
        (directory / "refusal.json", raw),
        (directory / "staging" / (str(publication_id) + ".json"), wire(intent)),
    ):
        path.write_bytes(data)
        path.chmod(0o400)


def test_cold_census_all_256_scopes_releases_child_descriptors(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    for index in range(256):
        _stored_refusal_scope(installation, index)
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        core = publisher._core
        work = core.last_work
        assert len(core.totals) == 256
        assert work.owner_calls == 513  # root + actual intent/parent for every scope
        assert len(core.files.owned) == 5
        assert work.fd_count == 5 and work.peak_fds <= 128
        assert work.os_calls <= 262144 and work.observations <= 131072
        assert len(core.census.data) == (4 + 256 * 5) * 256
        assert work.peak_slots <= 262144 and work.peak_buffers <= 96 * 1048576
    finally:
        publisher.close()


def test_257th_scope_rejects_without_new_store_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installation = _installation(tmp_path)
    for index in range(257):
        _stored_refusal_scope(installation, index)
    with monkeypatch.context() as patch:
        for name in ("write", "link", "unlink", "mkdir", "fchmod"):
            patch.setattr(os, name, lambda *_args, **_kwargs: pytest.fail("cold-pass mutation"))
        with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
            evidence._open_diagnostic_publisher(installation)


def test_fixed_reader_is_read_only_even_during_cold_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installation = _installation(tmp_path)
    _stored_refusal_scope(installation, 0)
    with monkeypatch.context() as patch:
        for name in ("write", "link", "unlink", "mkdir", "fchmod", "fsync"):
            patch.setattr(os, name, lambda *_args, **_kwargs: pytest.fail("reader mutation"))
        reader = evidence.open_runtime_publication_reader(installation)
        try:
            result = reader.read_publication(
                evidence._PublicationKey(
                    evidence._ScopeKey("refusal", UUID(uid(10000))), UUID(uid(20000))
                )
            )
            assert result.visibility == "verified-visible-file"
            assert result.record.validation == "local-structure-only"
        finally:
            reader.close()


@pytest.mark.parametrize("name", ("copies", "observations", "hash", "read", "write"))
def test_work_boundary_rejects_n_plus_one_without_refund(name: str) -> None:
    work = evidence._Work(totals=evidence._Totals())
    limit = {
        "copies": 192 * 1048576,
        "observations": 512,
        "hash": 268435456,
        "read": 134217728,
        "write": 67108864,
    }[name]
    work.charge(name, limit)
    with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
        work.charge(name, 1)
    assert getattr(work, name) == limit


def test_empty_duplicate_roles_have_one_physical_file_and_distinct_metadata_charge(
    tmp_path: Path,
) -> None:
    installation = _installation(tmp_path)
    history = History()
    history.m["request"] = history.add(b"")
    history.m["launch"] = history.m["request"].copy()
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), wire(history.m)
        )
        for kind in ("request", "launch"):
            ack = scope.publish_member(UUID(uid(101)), evidence.MemberSelector(kind, 0), _blob(b""))
            assert ack.publication.file.data == b""
        core = publisher._core
        with core.operation(scope._key) as (_, files):
            plan = core._load_plan(scope._key, core._scope_files(scope._key, files), files)
            assert ("request", 0) in plan.refs and ("launch", 0) in plan.refs
            assert len(core._intent_names(scope._key)) == 2
    finally:
        publisher.close()


@pytest.mark.parametrize("change", ("unknown-name", "unreferenced-blob", "foreign-hardlink"))
def test_cold_pass_does_not_adopt_unexplained_names(tmp_path: Path, change: str) -> None:
    installation = _installation(tmp_path)
    _stored_refusal_scope(installation, 0)
    directory = installation.evidence_root / "refusals" / uid(10000)
    if change == "unknown-name":
        (directory / "surprise").write_bytes(b"not accepted")
    elif change == "unreferenced-blob":
        path = directory / "blobs" / hashlib.sha256(b"not accepted").hexdigest()
        path.write_bytes(b"not accepted")
        path.chmod(0o400)
    else:
        os.link(directory / "refusal.json", tmp_path / "foreign-hardlink")
    with pytest.raises(evidence.RuntimePublicationError):
        evidence._open_diagnostic_publisher(installation)


@pytest.mark.parametrize("count", (0, 2))
def test_refusal_primary_requires_exactly_one_associated_graph(tmp_path: Path, count: int) -> None:
    installation = _installation(tmp_path)
    first = graph_document([graph_node(0)])
    second = graph_document([graph_node(0, suppress_context=True)])
    raw = [wire(first), wire(second)] if count else [b"not JSON", b"x" * 8193]
    row = refusal([History.reference(data) for data in raw])
    row["primary_error_id"] = first["error_id"]
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        key = evidence._ScopeKey("refusal", UUID(row["refusal_id"]))
        scope = publisher.begin_refusal(key, UUID(uid(100)), wire(row))
        for index, data in enumerate(raw):
            scope.publish_member(
                UUID(uid(200 + index)),
                evidence.MemberSelector("refusal-evidence", index),
                _blob(data),
            )
        with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
            scope.finalize()
        assert not (installation.evidence_root / "refusals" / str(key.id) / "refusal.json").exists()
    finally:
        publisher.close()


@pytest.mark.parametrize(
    "components", (("/tmp/example",), ("/tmp", "example"), ("/", "tmp", "example"))
)
def test_supported_path_layout_fragments_are_cloned(components: tuple[str, ...]) -> None:
    path = PosixPath(*components)
    clone = evidence._path(path)
    assert clone == PosixPath("/tmp/example")
    assert clone is not path


def test_installed_binding_is_detached_from_caller_slots(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    object.__setattr__(installation.deployment_id, "int", _Poison())
    object.__setattr__(installation.evidence_root, "_str", _Poison())
    object.__setattr__(installation, "owner_uid", _Poison())
    try:
        scope = publisher.begin_refusal(
            evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
        )
        assert scope.finalize().completion == "local-fsync-readback"
    finally:
        publisher.close()


def test_returned_identity_has_no_alias_to_held_scope(tmp_path: Path) -> None:
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    try:
        scope = publisher.begin_refusal(
            evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
        )
        ack = scope.finalize()
        object.__setattr__(ack.publication.key.scope.id, "int", _Poison())
        object.__setattr__(ack.publication.key.publication_id, "int", _Poison())
        assert scope.finalize().disposition == "exact-recovery"
    finally:
        publisher.close()


def test_ordinary_hash_aliases_do_not_discount_logical_metadata(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    history = History()
    history.m["request"] = history.add(b"x" * 65536)
    history.m["launch"] = history.m["request"].copy()
    raw = wire(history.m)
    parsed = evidence.decode_journal_record("manifest", raw)
    plan = evidence._Plan(
        evidence._ScopeKey("attempt", UUID(uid(3))), UUID(uid(100)), parsed, installation
    )
    metadata, retained = plan.quota({})
    other_metadata = sum(
        reference.size
        for (kind, _), reference in plan.refs.items()
        if reference.metadata and kind not in ("request", "launch")
    )
    assert metadata == len(raw) + 2 * 65536 + other_metadata + 12 * 4096 + 196608
    unique = {reference.checksum: reference.size for reference in plan.refs.values()}
    assert retained == len(raw) + sum(unique.values()) + 1048576 + 12 * 4096 + 2097152


@pytest.mark.parametrize("target", ("initial_prerequisite", "authority_inventory"))
def test_declared_authority_dependency_cycles_reject_in_plan_accountant(
    tmp_path: Path, target: str
) -> None:
    installation = _installation(tmp_path)
    history = History()
    plan = evidence._Plan(
        evidence._ScopeKey("attempt", UUID(uid(3))),
        UUID(uid(100)),
        evidence.decode_journal_record("manifest", wire(history.m)),
        installation,
    )
    # Internal graph falsifier: no claim these mutually self-hashed records
    # could pass actual raw-file binding. The declared cycle fence is separate.
    plan.prerequisite = json.loads(history.data[history.m["initial_prerequisite"]["sha256"]])
    plan.inventory = json.loads(history.data[history.m["authority_inventory"]["sha256"]])
    plan.inventory["objects"][0]["bytes"] = history.m[target].copy()
    plan.prerequisite["authentication_evidence_sha256"] = history.m[target]["sha256"]
    with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
        plan._links()


def test_future_129_credit_arithmetic_is_not_an_initial_scope_positive(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    parsed = evidence.decode_journal_record("refusal", wire(refusal()))
    plan = evidence._Plan(
        evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), parsed, installation
    )
    # This is an accountant falsifier only. Public plans never permit 129 IDs.
    plan.maximum = 129
    with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
        plan.quota({})


def test_close_rebind_does_not_reset_cumulative_work_or_retained_intents(tmp_path: Path) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    key = evidence._ScopeKey("refusal", UUID(uid(88)))
    try:
        scope = publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
        ack = scope.finalize()
        before = publisher._core.totals[key].read
        completed = publisher._core._completed(key)
        scope.close()
        rebound = publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
        assert publisher._core.totals[key].read > before
        assert publisher._core._completed(key) == completed
        assert rebound.finalize().publication.intent.data == ack.publication.intent.data
    finally:
        publisher.close()


def test_joint_refusal_quota_rejects_sixteen_maximum_blob_claims_before_effects(
    tmp_path: Path,
) -> None:
    installation = _installation(tmp_path)
    refs = [
        {"sha256": f"{index + 1:064x}", "size": 8388608, "key": f"blobs/{index + 1:064x}"}
        for index in range(16)
    ]
    publisher = evidence._open_diagnostic_publisher(installation)
    try:
        with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
            publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal(refs))
            )
        assert list((installation.evidence_root / "refusals").iterdir()) == []
    finally:
        publisher.close()


def test_fd_bound_admits_before_open(monkeypatch: pytest.MonkeyPatch) -> None:
    work = evidence._Work()
    work.fd_count = 128
    descriptors = evidence._Descriptors(work)
    monkeypatch.setattr(os, "open", lambda *_args, **_kwargs: pytest.fail("FD over-admission"))
    with pytest.raises(evidence.RuntimePublicationError, match=r"^limit$"):
        descriptors.open("/not-opened", os.O_RDONLY)
    assert descriptors.owned == set()


def test_name_iterator_cleanup_preserves_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original = os.scandir
    failure = KeyboardInterrupt("original")

    class FailingIterator:
        def __init__(self, fd: int) -> None:
            self.inner = original(fd)

        def __iter__(self) -> Any:
            return self

        def __next__(self) -> Any:
            raise failure

        def close(self) -> None:
            self.inner.close()
            raise OSError("private iterator cleanup failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(os, "scandir", FailingIterator)
            with pytest.raises(KeyboardInterrupt) as captured:
                evidence._names(directory, evidence._Work(), 10)
        assert captured.value is failure
        assert isinstance(failure.__cause__, BaseExceptionGroup)
    finally:
        os.close(directory)


@pytest.mark.parametrize("name", ("read", "fstat", "stat", "open", "close"))
def test_storage_failure_never_leaks_arbitrary_wrapper_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    original = getattr(os, name)
    fired = False

    def fail_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal fired
        if not fired:
            fired = True
            if name == "close":
                original(*args, **kwargs)  # uncertain numeric FD is already released
            raise PermissionError("PRIVATE-MESSAGE/path?raw=secret")
        return original(*args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(os, name, fail_once)
            with pytest.raises(evidence.RuntimePublicationError) as captured:
                publisher.begin_refusal(
                    evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
                )
        assert fired
        assert "PRIVATE" not in str(captured.value)
        assert captured.value.__cause__ is not None
    finally:
        publisher.close()


def test_begin_scope_lifetime_is_atomic_with_method_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    completed_io, release_first = Event(), Event()
    original = publisher._core.operation
    outcomes: dict[str, Any] = {}

    @contextmanager
    def scheduled(key: Any, **kwargs: Any) -> Any:
        with original(key, **kwargs) as operation:
            yield operation
        if current_thread().name == "first-scope":
            completed_io.set()
            assert release_first.wait(5), "test scheduling timeout"

    monkeypatch.setattr(publisher._core, "operation", scheduled)

    def begin(label: str, index: int) -> None:
        row = refusal()
        row["refusal_id"] = uid(index)
        try:
            outcomes[label] = publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(uid(index))),
                UUID(uid(index + 1000)),
                wire(row),
            )
        except BaseException as error:
            outcomes[label] = error

    first = Thread(target=begin, args=("first", 501), name="first-scope")
    second = Thread(target=begin, args=("second", 502), name="second-scope")
    try:
        first.start()
        assert completed_io.wait(5)
        second.start()
        second.join(5)
        assert not second.is_alive()
    finally:
        release_first.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
        publisher.close()
    assert not first.is_alive()
    assert type(outcomes["first"]) is evidence._PlannedScope
    assert type(outcomes["second"]) is evidence.RuntimePublicationError
    assert outcomes["second"].reason == "conflict"


class _PauseBeforeAcquire:
    """Expose the real pre-acquire scheduling boundary without changing ownership."""

    def __init__(self, lock: Any) -> None:
        self.lock = lock
        self.reached, self.resume = Event(), Event()

    def acquire(self, *, blocking: bool) -> bool:
        if current_thread().name == "delayed-method":
            self.reached.set()
            assert self.resume.wait(5), "test scheduling timeout"
        return bool(self.lock.acquire(blocking=blocking))

    def release(self) -> None:
        self.lock.release()


def test_publisher_closed_while_method_waits_is_rechecked_before_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    gate = _PauseBeforeAcquire(publisher._core.lock)
    monkeypatch.setattr(publisher._core, "lock", gate)
    result: list[BaseException] = []

    def begin() -> None:
        try:
            publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(uid(88))), UUID(uid(100)), wire(refusal())
            )
        except BaseException as error:
            result.append(error)

    worker = Thread(target=begin, name="delayed-method")
    try:
        worker.start()
        assert gate.reached.wait(5)
        publisher.close()
        with monkeypatch.context() as patch:
            patch.setattr(evidence, "_walk", lambda *_a, **_k: pytest.fail("I/O after close"))
            gate.resume.set()
            worker.join(5)
            assert not worker.is_alive()
    finally:
        gate.resume.set()
        worker.join(5)
        publisher.close()
    assert len(result) == 1 and type(result[0]) is evidence.RuntimePublicationError
    assert result[0].reason == "conflict"


def test_scope_close_cannot_change_lifetime_during_owned_operation(tmp_path: Path) -> None:
    publisher = evidence._open_diagnostic_publisher(_installation(tmp_path))
    try:
        key = evidence._ScopeKey("refusal", UUID(uid(88)))
        scope = publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
        with publisher._core.operation(key):
            with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
                scope.close()
            assert publisher._core.active is scope and not scope._closed
        scope.close()
        assert publisher._core.active is None and scope._closed
    finally:
        publisher.close()


@pytest.mark.parametrize("method", ("member", "finalize"))
def test_closed_scope_is_rechecked_after_method_acquires_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    installation = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installation)
    raw = b"inert member"
    row = refusal([History.reference(raw)] if method == "member" else [])
    key = evidence._ScopeKey("refusal", UUID(row["refusal_id"]))
    scope = publisher.begin_refusal(key, UUID(uid(100)), wire(row))
    gate = _PauseBeforeAcquire(publisher._core.lock)
    monkeypatch.setattr(publisher._core, "lock", gate)
    result: list[Any] = []

    def perform() -> None:
        try:
            result.append(
                scope.publish_member(
                    UUID(uid(101)), evidence.MemberSelector("refusal-evidence", 0), _blob(raw)
                )
                if method == "member"
                else scope.finalize()
            )
        except BaseException as error:
            result.append(error)

    worker = Thread(target=perform, name="delayed-method")
    try:
        worker.start()
        assert gate.reached.wait(5)
        scope.close()
        gate.resume.set()
        worker.join(5)
        assert not worker.is_alive()
        assert len(result) == 1 and type(result[0]) is evidence.RuntimePublicationError
        assert result[0].reason == "conflict"
        assert len(publisher._core._intent_names(key)) == 1
        assert not (installation.evidence_root / "refusals" / str(key.id) / "refusal.json").exists()
    finally:
        gate.resume.set()
        worker.join(5)
        publisher.close()


@dataclass(frozen=True)
class _FaultPoint:
    operation: str
    ordinal: int
    target: str


class _FilesystemTrace:
    """Faults only an observed task-owned call; cleanup uses known test FDs.

    This does not model power loss or pretend that a close exception tells
    production whether the descriptor was released. The harness knows which
    of its two explicit before/after stubs ran, and cleans only its own leak.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = str(directory)
        self.originals = {name: getattr(os, name) for name in (*_FAULT_OPERATIONS, "open")}
        self.readlink = os.readlink
        self.points: list[_FaultPoint] = []
        self.counts: dict[str, int] = {}
        self.active = False
        self.target: tuple[int, _FaultPoint] | None = None
        self.cleanup_target: tuple[int, _FaultPoint] | None = None
        self.when = "before"
        self.cleanup_when = "before"
        self.failure: BaseException | None = None
        self.cleanup_failure = OSError("task-private cleanup failure")
        self.prior_cause = OSError("task-private cause preceding interruption")
        self.injected = 0
        self.cleanup_injected = 0
        self.all_calls = 0
        self.next_generation = 0
        self.live: dict[int, int] = {}
        self.uncertain: dict[int, int] = {}
        self.close_attempts: dict[int, int] = {}

    def _fd_name(self, fd: int) -> str:
        return self.readlink(f"/proc/self/fd/{fd}").replace(self.directory, "<case>")

    def _point(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _FaultPoint:
        if name in ("read", "write", "fchmod", "fsync", "close"):
            target = self._fd_name(args[0])
        elif name == "link":
            target = (
                f"{self._fd_name(kwargs['src_dir_fd'])}/{args[0]} -> "
                f"{self._fd_name(kwargs['dst_dir_fd'])}/{args[1]}"
            )
        else:
            target = f"{self._fd_name(kwargs['dir_fd'])}/{args[0]}"
        self.counts[name] = self.counts.get(name, 0) + 1
        return _FaultPoint(name, self.counts[name], target)

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        self.all_calls += 1
        selected = False
        cleanup_selected = False
        if self.active and name != "open":
            point = self._point(name, args, kwargs)
            self.points.append(point)
            if self.target is not None and len(self.points) - 1 == self.target[0]:
                assert point == self.target[1], (point, self.target)
                selected = True
            if self.cleanup_target is not None and len(self.points) - 1 == self.cleanup_target[0]:
                assert point == self.cleanup_target[1], (point, self.cleanup_target)
                assert name == "close" and self.injected == 1
                cleanup_selected = True
        fault = self.cleanup_failure if cleanup_selected else self.failure if selected else None
        timing = self.cleanup_when if cleanup_selected else self.when
        generation = None
        if name == "close":
            fd = args[0]
            generation = self.live.pop(fd, None)
            assert generation is not None, ("unowned/retried close", fd)
            self.close_attempts[generation] = self.close_attempts.get(generation, 0) + 1
            assert self.close_attempts[generation] == 1
        if fault is not None and timing == "before":
            if generation is not None:
                self.uncertain[args[0]] = generation
            if cleanup_selected:
                self.cleanup_injected += 1
            else:
                self.injected += 1
            raise fault
        result = self.originals[name](*args, **kwargs)
        if name == "open":
            self.next_generation += 1
            assert result not in self.live and result not in self.uncertain
            self.live[result] = self.next_generation
        if fault is not None and timing == "after":
            if cleanup_selected:
                self.cleanup_injected += 1
            else:
                self.injected += 1
            raise fault
        return result

    def install(self, patch: pytest.MonkeyPatch) -> None:
        for name in self.originals:

            def invoke(*args: Any, _name: str = name, **kwargs: Any) -> Any:
                return self._call(_name, *args, **kwargs)

            patch.setattr(os, name, invoke)

    def clean_test_owned_uncertain_fds(self) -> None:
        # Production must not retry numeric FDs. These remain open only because
        # this harness deliberately raised BEFORE the real close operation.
        for fd in tuple(self.uncertain):
            self.originals["close"](fd)
            del self.uncertain[fd]


class _FaultScenario:
    def __init__(self, installation: evidence.RuntimeEvidenceInstallation, phase: str) -> None:
        self.installation = installation
        self.phase = phase
        self.publishers: list[evidence._DiagnosticPublisher] = []
        self.publisher: evidence._DiagnosticPublisher | None = None
        self.scope: evidence._PlannedScope | None = None
        self.parent = UUID(uid(100))
        self.member_id = UUID(uid(200))
        self.history = History()
        if phase.endswith("manifest"):
            self.key = evidence._ScopeKey("attempt", UUID(self.history.m["attempt_id"]))
            self.parent_raw = wire(self.history.m)
            self.members = _members(self.history)
        else:
            # Exercise more than the first read/write chunk while remaining a
            # small inert fixture, far below the existing 8 MiB member ceiling.
            raw = b"inert systematic fault member\n" * 2400
            row = refusal([History.reference(raw)])
            self.key = evidence._ScopeKey("refusal", UUID(row["refusal_id"]))
            self.parent_raw = wire(row)
            self.members = [(evidence.MemberSelector("refusal-evidence", 0), raw)]

    def _open(self) -> evidence._DiagnosticPublisher:
        publisher = evidence._open_diagnostic_publisher(self.installation)
        self.publishers.append(publisher)
        self.publisher = publisher
        return publisher

    def _begin(self) -> evidence._PlannedScope:
        assert self.publisher is not None
        begin = (
            self.publisher.begin_manifest
            if self.key.kind == "attempt"
            else self.publisher.begin_refusal
        )
        self.scope = begin(self.key, self.parent, self.parent_raw)
        return self.scope

    def prepare(self) -> None:
        self._open()
        if self.phase.startswith("begin-") or self.phase == "writer-close":
            return
        scope = self._begin()
        if self.phase.startswith("member-"):
            return
        if self.phase.endswith("pair"):
            # Real link succeeded, but the target invocation stopped before
            # unlink. Fresh cold reconciliation may observe, not repair it.
            with pytest.MonkeyPatch.context() as patch:

                def interrupt_unlink(*_args: Any, **_kwargs: Any) -> None:
                    raise OSError("task-private prepared link/unlink interruption")

                patch.setattr(os, "unlink", interrupt_unlink)
                with pytest.raises(evidence.RuntimePublicationError):
                    selector, raw = self.members[0]
                    scope.publish_member(self.member_id, selector, _blob(raw))
        else:
            for index, (selector, raw) in enumerate(self.members):
                scope.publish_member(UUID(uid(200 + index)), selector, _blob(raw))
            if not self.phase.startswith("finalize-"):
                scope.finalize()
        if self.phase.startswith(("recover-", "reconcile-")):
            assert self.publisher is not None
            self.publisher.close()
            if self.phase.startswith("recover-"):
                self._open()

    def run(self) -> Any:
        if self.phase.startswith("reconcile-"):
            return self._open()
        assert self.publisher is not None
        if self.phase.startswith("begin-"):
            return self._begin()
        if self.phase == "writer-close":
            return self.publisher.close()
        if self.phase.startswith("recover-"):
            identity = self.member_id if self.phase.endswith("pair") else self.parent
            return self.publisher.recover_publication(evidence._PublicationKey(self.key, identity))
        assert self.scope is not None
        if self.phase.startswith("member-"):
            selector, raw = self.members[0]
            return self.scope.publish_member(self.member_id, selector, _blob(raw))
        return self.scope.finalize()

    def close(self) -> None:
        for publisher in reversed(self.publishers):
            publisher.close()


def _error_contains(error: BaseException, selected: BaseException) -> bool:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is selected:
            return True
        if id(current) in seen:
            continue
        seen.add(id(current))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)
    return False


def _stored_bytes(directory: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _fault_invocation(
    path: Path,
    phase: str,
    *,
    target: tuple[int, _FaultPoint] | None = None,
    when: str = "before",
    failure_class: type[BaseException] = OSError,
    cleanup_target: tuple[int, _FaultPoint] | None = None,
    cleanup_when: str = "before",
) -> _FilesystemTrace:
    path.mkdir(mode=0o700)
    installation = _installation(path)
    trace = _FilesystemTrace(path)
    trace.target, trace.when = target, when
    trace.cleanup_target, trace.cleanup_when = cleanup_target, cleanup_when
    trace.failure = failure_class("task-private failure payload must stay in the cause chain")
    if cleanup_target is not None:
        trace.failure.__cause__ = trace.prior_cause
    scenario = _FaultScenario(installation, phase)
    failure: BaseException | None = None
    result: Any = None
    with pytest.MonkeyPatch.context() as patch:
        trace.install(patch)
        try:
            scenario.prepare()
            previous = _stored_bytes(installation.evidence_root)
            trace.active = True
            try:
                result = scenario.run()
            except BaseException as error:
                failure = error
            finally:
                trace.active = False
            if target is None:
                assert failure is None, failure
            else:
                assert trace.injected == 1, (phase, target, trace.points)
                assert result is None, "a failing syscall must not return a handle/ack"
                assert failure is not None
                assert _error_contains(failure, trace.failure)
                if cleanup_target is not None:
                    assert trace.cleanup_injected == 1
                    assert _error_contains(failure, trace.cleanup_failure)
                    assert _error_contains(failure, trace.prior_cause)
                if failure_class in (KeyboardInterrupt, SystemExit):
                    assert failure is trace.failure
                else:
                    assert type(failure) is evidence.RuntimePublicationError
                    assert str(failure) in evidence._REASONS
                publisher = scenario.publisher
                if publisher is not None and not phase.startswith("reconcile-"):
                    core = publisher._core
                    work = core.last_work
                    if phase == "writer-close":
                        assert core.closed
                    elif work is not None and (
                        work.effects_started
                        or failure_class is OSError
                        or target[1].operation == "close"
                        or cleanup_target is not None
                    ):
                        assert core.invalidated
                        before = trace.all_calls
                        with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
                            publisher.recover_publication(
                                evidence._PublicationKey(scenario.key, scenario.parent)
                            )
                        assert trace.all_calls == before, "poisoned writer performed more I/O"
                remaining = _stored_bytes(installation.evidence_root)
                for name, raw in previous.items():
                    if name in remaining:
                        assert remaining[name] == raw, ("overwritten prior bytes", name)
                    else:
                        assert name.endswith(".data")
                        assert raw in remaining.values(), ("lost prior bytes", name)
        finally:
            trace.active = False
            try:
                scenario.close()
                assert not trace.live, ("leaked acknowledged descriptor", trace.live)
            finally:
                trace.clean_test_owned_uncertain_fds()
    return trace


@pytest.mark.parametrize("phase", _FAULT_PHASES)
@pytest.mark.parametrize("when", ("before", "after"))
def test_every_observed_filesystem_fault_position(
    tmp_path: Path, request: pytest.FixtureRequest, phase: str, when: str
) -> None:
    baseline = _fault_invocation(tmp_path / "baseline", phase)
    assert baseline.points
    request.node.user_properties.append(
        (
            "observed_positions",
            json.dumps([vars(point) for point in baseline.points], sort_keys=True),
        )
    )
    for index, point in enumerate(baseline.points):
        _fault_invocation(tmp_path / f"fault-{index:04d}", phase, target=(index, point), when=when)
    request.node.user_properties.append(("injected_positions", len(baseline.points)))


@pytest.mark.parametrize("phase", _FAULT_PHASES)
@pytest.mark.parametrize("failure_class", (KeyboardInterrupt, SystemExit))
def test_each_observed_operation_preserves_original_interruption(
    tmp_path: Path, request: pytest.FixtureRequest, phase: str, failure_class: type[BaseException]
) -> None:
    baseline = _fault_invocation(tmp_path / "baseline", phase)
    final: dict[str, tuple[int, _FaultPoint]] = {}
    for index, point in enumerate(baseline.points):
        final[point.operation] = index, point
    for index, point in final.values():
        _fault_invocation(
            tmp_path / f"interrupt-{index:04d}",
            phase,
            target=(index, point),
            when="after",
            failure_class=failure_class,
        )
    request.node.user_properties.append(("interruption_operation_kinds", sorted(final)))


@pytest.mark.parametrize("phase", _FAULT_PHASES)
@pytest.mark.parametrize("failure_class", (KeyboardInterrupt, SystemExit))
@pytest.mark.parametrize("cleanup_when", ("before", "after"))
def test_every_observed_cleanup_close_preserves_primary_and_prior_cause(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    phase: str,
    failure_class: type[BaseException],
    cleanup_when: str,
) -> None:
    success = _fault_invocation(tmp_path / "baseline", phase)
    reads = [
        (index, point) for index, point in enumerate(success.points) if point.operation == "read"
    ]
    primary = reads[-1] if reads else (0, success.points[0])
    interrupted = _fault_invocation(
        tmp_path / "interrupted",
        phase,
        target=primary,
        when="after",
        failure_class=failure_class,
    )
    cleanup = [
        (index, point)
        for index, point in enumerate(interrupted.points)
        if index > primary[0] and point.operation == "close"
    ]
    assert cleanup, (phase, primary, interrupted.points)
    for index, point in cleanup:
        _fault_invocation(
            tmp_path / f"dual-{index:04d}",
            phase,
            target=primary,
            when="after",
            failure_class=failure_class,
            cleanup_target=(index, point),
            cleanup_when=cleanup_when,
        )
    request.node.user_properties.append(
        (
            "cleanup_close_positions",
            json.dumps([vars(point) for _, point in cleanup], sort_keys=True),
        )
    )
    request.node.user_properties.append(("dual_failure_positions", len(cleanup)))


@pytest.mark.parametrize("change", ("leaf-bytes", "directory-membership"))
def test_detected_census_drift_poisoning_prevents_different_scope(
    tmp_path: Path, change: str
) -> None:
    installed = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installed)
    data = b"actual diagnostic member"
    reference = History.reference(data)
    first_row = refusal([reference])
    first_key = evidence._ScopeKey("refusal", UUID(first_row["refusal_id"]))
    try:
        scope = publisher.begin_refusal(first_key, UUID(uid(100)), wire(first_row))
        scope.publish_member(
            UUID(uid(101)), evidence.MemberSelector("refusal-evidence", 0), _blob(data)
        )
        blobs = installed.evidence_root / "refusals" / str(first_key.id) / "blobs"
        if change == "leaf-bytes":
            leaf = blobs / reference["sha256"]
            leaf.chmod(0o600)
            leaf.write_bytes(b"X" + data[1:])
            leaf.chmod(0o400)
        else:
            (blobs / "unexpected-name").write_bytes(b"diagnostic drift")
        with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
            scope.finalize()
        scope.close()
        second_row = refusal()
        second_row["refusal_id"] = uid(89)
        with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
            publisher.begin_refusal(
                evidence._ScopeKey("refusal", UUID(uid(89))),
                UUID(uid(102)),
                wire(second_row),
            )
    finally:
        publisher.close()


@pytest.mark.parametrize("release_first", (False, True))
def test_uncertain_read_only_close_poisoning_prevents_more_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release_first: bool
) -> None:
    installed = _installation(tmp_path)
    publisher = evidence._open_diagnostic_publisher(installed)
    original_close = os.close
    unclosed: list[int] = []
    fired = False

    def fail_one_close(fd: int) -> None:
        nonlocal fired
        if not fired:
            fired = True
            if release_first:
                original_close(fd)
            else:
                unclosed.append(fd)
            raise OSError("controlled uncertain close")
        original_close(fd)

    try:
        key = evidence._ScopeKey("refusal", UUID(uid(88)))
        with monkeypatch.context() as patch:
            patch.setattr(os, "close", fail_one_close)
            with pytest.raises(evidence.RuntimePublicationError):
                publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
        assert fired
        assert not list((installed.evidence_root / "refusals").iterdir())
        with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
            publisher.begin_refusal(key, UUID(uid(100)), wire(refusal()))
    finally:
        publisher.close()
        # Fixture-owned BEFORE-close leaks only; no production uncertain retry.
        for fd in unclosed:
            original_close(fd)


def test_cold_member_priority_does_not_follow_publication_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = _installation(tmp_path)
    history = History()
    publisher = evidence._open_diagnostic_publisher(installed)
    try:
        scope = publisher.begin_manifest(
            evidence._ScopeKey("attempt", UUID(history.m["attempt_id"])),
            UUID(uid(100)),
            wire(history.m),
        )
        for index, (selector, raw) in enumerate(_members(history)):
            ordinal = {"prerequisite": 900, "authority-inventory": 899}.get(
                selector.kind, 300 + index
            )
            scope.publish_member(UUID(uid(ordinal)), selector, _blob(raw))
        scope.finalize()
    finally:
        publisher.close()

    original_read = evidence._read
    body_reads: list[str] = []

    def observed_read(parent: int, name: str, *args: Any, **kwargs: Any) -> Any:
        if len(name) == 64:
            body_reads.append(name)
        return original_read(parent, name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(evidence, "_read", observed_read)
        reopened = evidence._open_diagnostic_publisher(installed)
        reopened.close()
    assert body_reads[:2] == [
        history.m["initial_prerequisite"]["sha256"],
        history.m["authority_inventory"]["sha256"],
    ]


@pytest.mark.parametrize("boundary", ("owned-operation", "cold-constructor"))
@pytest.mark.parametrize("release_first", (False, True))
@pytest.mark.parametrize("primary_class", (None, KeyboardInterrupt, SystemExit))
def test_iterator_close_uncertainty_at_real_owner_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    release_first: bool,
    primary_class: type[BaseException] | None,
) -> None:
    installation = _installation(tmp_path)
    trace = _FilesystemTrace(tmp_path)
    real_scandir = os.scandir
    primary = None if primary_class is None else primary_class("private original interruption")
    prior_cause = OSError("private preceding cause")
    if primary is not None:
        primary.__cause__ = prior_cause
    cleanup_failure = OSError("private iterator close failure")
    iterators: list[Any] = []
    publisher: evidence._DiagnosticPublisher | None = None
    result: Any = None

    class FailingIterator:
        def __init__(self, fd: int) -> None:
            self.inner = real_scandir(fd)
            self.real_close = self.inner.close
            self.close_attempts = 0
            self.real_close_calls = 0
            self.released = False
            iterators.append(self)

        def __iter__(self) -> Any:
            return self

        def __next__(self) -> Any:
            if primary is not None:
                raise primary
            return next(self.inner)

        def release_test_owned_iterator(self) -> None:
            self.real_close_calls += 1
            self.real_close()
            self.released = True

        def close(self) -> None:
            self.close_attempts += 1
            assert self.close_attempts == 1, "production retried uncertain iterator close"
            if release_first:
                self.release_test_owned_iterator()
            raise cleanup_failure

    with monkeypatch.context() as patch:
        trace.install(patch)
        try:
            if boundary == "owned-operation":
                publisher = evidence._open_diagnostic_publisher(installation)
            patch.setattr(os, "scandir", FailingIterator)
            with pytest.raises(BaseException) as captured:
                if publisher is None:
                    result = evidence._open_diagnostic_publisher(installation)
                else:
                    key = evidence._ScopeKey("refusal", UUID(uid(88)))
                    # Public steady methods do not currently enumerate names.
                    # Exercise the actual helper under its real owner context,
                    # without claiming an invented public publication route.
                    with publisher._core.operation(key) as (work, _files):
                        result = evidence._names(publisher._core.root, work, 4)
            assert result is None, "failed cleanup returned a handle or value"
            assert len(iterators) == 1 and iterators[0].close_attempts == 1
            assert _error_contains(captured.value, cleanup_failure)
            if primary is None:
                assert type(captured.value) is evidence.RuntimePublicationError
                assert str(captured.value) in evidence._REASONS
            else:
                assert captured.value is primary
                assert _error_contains(captured.value, prior_cause)
            if publisher is not None:
                assert publisher._core.invalidated
                assert publisher._core.last_work is not None
                assert publisher._core.last_work.cleanup_uncertain
                before = trace.all_calls
                with pytest.raises(evidence.RuntimePublicationError, match=r"^conflict$"):
                    publisher.begin_refusal(
                        evidence._ScopeKey("refusal", UUID(uid(89))),
                        UUID(uid(100)),
                        wire({**refusal(), "refusal_id": uid(89)}),
                    )
                assert trace.all_calls == before, "poisoned writer performed more I/O"
            else:
                assert not trace.live, "failed cold constructor leaked an owned descriptor"
        finally:
            if publisher is not None:
                publisher.close()
            assert not trace.live, "owned descriptors were not released exactly once"
            for iterator in iterators:
                if not iterator.released:
                    # Only this fixture knows its BEFORE-close stub did not
                    # call the saved real method; no product repair is implied.
                    iterator.release_test_owned_iterator()
                assert iterator.real_close_calls == 1
                assert iterator.close_attempts == 1

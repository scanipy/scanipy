"""Raw authored object data only: these tests never invoke native Git."""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from integrations.scm import git_objects as git
from services.scan.source_capture import CaptureLimits

pytestmark = pytest.mark.unit


def build_one(files: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    """Builder A: direct byte concatenation, independent of production encoding."""
    objects: dict[str, bytes] = {}

    def add(kind: bytes, content: bytes) -> str:
        raw = kind + b" " + str(len(content)).encode() + b"\x00" + content
        oid = hashlib.sha1(raw, usedforsecurity=False).hexdigest()
        objects[oid] = raw
        return oid

    entries = []
    for name, payload in sorted(files.items()):
        blob = add(b"blob", payload)
        entries.append(b"100644 " + name.encode() + b"\x00" + bytes.fromhex(blob))
    tree = add(b"tree", b"".join(entries))
    commit = add(b"commit", b"tree " + tree.encode() + b"\n\nmessage\n")
    return commit, objects


def build_two(files: dict[str, bytes]) -> tuple[str, dict[str, bytes]]:
    """Builder B: independently framed bytearray/hex digest; no shared builder."""
    from binascii import unhexlify
    from io import BytesIO

    storage: dict[str, bytes] = {}

    def record(category: str, content: bytes) -> str:
        envelope = BytesIO()
        envelope.write(f"{category} {len(content)}".encode("ascii"))
        envelope.write(bytes([0]))
        envelope.write(content)
        result = envelope.getvalue()
        digest = hashlib.new("sha1", usedforsecurity=False)
        for cursor in range(0, len(result), 7):
            digest.update(result[cursor : cursor + 7])
        identity = digest.hexdigest()
        storage[identity] = result
        return identity

    listing = bytearray()
    for path in sorted(files, key=lambda name: name.encode("utf-8") + bytes([0])):
        blob_id = record("blob", files[path])
        listing.extend("100644 ".encode("ascii"))
        listing.extend(path.encode("utf-8"))
        listing.append(0)
        listing.extend(unhexlify(blob_id))
    tree_id = record("tree", bytes(listing))
    commit_id = record("commit", f"tree {tree_id}\n\nmessage\n".encode("ascii"))
    return commit_id, storage


def write_objects(root: Path, objects: dict[str, bytes]) -> Path:
    root.mkdir(mode=0o700)
    for oid, raw in objects.items():
        path = root / (oid + ".object")
        path.write_bytes(raw)
        path.chmod(0o600)
    return root


def load(root: Path, commit: str, limits: git.GitCaptureLimits | None = None) -> git.GitTree:
    with git.open_directory(root) as descriptor:
        return git.load_object_directory(descriptor, commit, limits or git.GitCaptureLimits())


def raw(kind: str, content: bytes) -> tuple[str, bytes]:
    preimage = kind.encode() + b" " + str(len(content)).encode() + b"\0" + content
    return hashlib.sha1(preimage, usedforsecurity=False).hexdigest(), preimage


def commit_with_tree(
    tree: bytes, other: dict[str, bytes] | None = None
) -> tuple[str, dict[str, bytes]]:
    tree_oid, tree_raw = raw("tree", tree)
    commit_oid, commit_raw = raw("commit", b"tree " + tree_oid.encode() + b"\n\nmessage\n")
    return commit_oid, {**(other or {}), tree_oid: tree_raw, commit_oid: commit_raw}


@pytest.mark.parametrize("builder", [build_one, build_two], ids=["concat", "independent-stream"])
def test_independent_builders_exact_positive(tmp_path: Path, builder: object) -> None:
    files = {"a.bin": b"\0\xff\n", "empty": b"", "é.py": b"print('data')\n"}
    # Both independently built fixture encodings must agree, not merely share a hasher.
    expected_commit, expected_objects = build_one(files)
    actual_commit, actual_objects = build_two(files)
    assert (actual_commit, actual_objects) == (expected_commit, expected_objects)
    selected = build_one if builder is build_one else build_two
    commit, objects = selected(files)
    tree = load(write_objects(tmp_path / "objects", objects), commit)
    assert tree.commit_oid == expected_commit
    assert [(item.path, item.size) for item in tree.files] == [
        (name, len(files[name])) for name in sorted(files)
    ]
    assert all(item.payload is None for item in tree.objects if item.kind == "blob")
    assert all(len(item.preimage_sha256) == len(item.payload_sha256) == 32 for item in tree.objects)


def test_reused_subtrees_modes_empty_dirs_and_literal_lfs(tmp_path: Path) -> None:
    pointer = (
        b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"a" * 64 + b"\nsize 123\n"
    )
    blob_oid, blob = raw("blob", pointer)
    child_oid, child = raw("tree", b"100755 run\0" + bytes.fromhex(blob_oid))
    empty_oid, empty = raw("tree", b"")
    root = b"".join(
        (
            b"40000 a\0" + bytes.fromhex(child_oid),
            b"40000 b\0" + bytes.fromhex(child_oid),
            b"40000 empty\0" + bytes.fromhex(empty_oid),
        )
    )
    commit, objects = commit_with_tree(root, {blob_oid: blob, child_oid: child, empty_oid: empty})
    tree = load(write_objects(tmp_path / "objects", objects), commit)
    assert [item.path for item in tree.files] == ["a/run", "b/run"]
    assert all(item.mode == "100755" and item.size == len(pointer) for item in tree.files)
    assert [item.path for item in tree.directories] == ["a", "b", "empty"]
    with pytest.raises(git.GitObjectError, match="limit"):
        load(
            tmp_path / "objects",
            commit,
            git.GitCaptureLimits(CaptureLimits(max_total_bytes=len(pointer))),
        )


@pytest.mark.parametrize(
    "bad",
    [
        b"blob 01\0a",
        b"blob +1\0a",
        b"blob -1\0a",
        b"blob 1\0aa",
        b"blob 2\0a",
        b"tag 1\0a",
        b"blob 1a",
        b"blob  1\0a",
    ],
)
def test_bad_framing(tmp_path: Path, bad: bytes) -> None:
    oid = hashlib.sha1(bad, usedforsecurity=False).hexdigest()
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", {oid: bad}), oid)


@pytest.mark.parametrize(
    "name", [b".", b"..", b".git", b"a/b", b"a\\b", b"", b"a\x01", b"\xff", b"x\xc2\x85"]
)
def test_unsafe_tree_names(tmp_path: Path, name: bytes) -> None:
    oid, blob = raw("blob", b"x")
    commit, objects = commit_with_tree(b"100644 " + name + b"\0" + bytes.fromhex(oid), {oid: blob})
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", objects), commit)


@pytest.mark.parametrize("mode", [b"120000", b"160000", b"040000", b"100664", b"100600", b"0"])
def test_unsupported_modes_reject_whole_capture(tmp_path: Path, mode: bytes) -> None:
    oid, blob = raw("blob", b"x")
    commit, objects = commit_with_tree(mode + b" a\0" + bytes.fromhex(oid), {oid: blob})
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", objects), commit)


@pytest.mark.parametrize("names", [[b"b", b"a"], [b"a", b"a"]])
def test_duplicate_or_unsorted_tree(tmp_path: Path, names: list[bytes]) -> None:
    oid, blob = raw("blob", b"x")
    commit, objects = commit_with_tree(
        b"".join(b"100644 " + name + b"\0" + bytes.fromhex(oid) for name in names), {oid: blob}
    )
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", objects), commit)


def test_git_directory_sort_semantics(tmp_path: Path) -> None:
    blob_oid, blob = raw("blob", b"x")
    empty_oid, empty = raw("tree", b"")
    root = b"100644 foo.bar\0" + bytes.fromhex(blob_oid) + b"40000 foo\0" + bytes.fromhex(empty_oid)
    commit, objects = commit_with_tree(root, {blob_oid: blob, empty_oid: empty})
    assert load(write_objects(tmp_path / "objects", objects), commit).directories[0].path == "foo"


@pytest.mark.parametrize(
    "header",
    [
        b"parent " + b"a" * 40,
        b"tree " + b"0" * 40,
        b"tree " + b"a" * 40 + b"\ntree " + b"a" * 40,
        b"tree " + b"a" * 40 + b"\nparent bad",
        b"tree " + b"a" * 40 + b"\nbad",
    ],
)
def test_commit_header_rejects(tmp_path: Path, header: bytes) -> None:
    oid, content = raw("commit", header + b"\n\nmessage")
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", {oid: content}), oid)


def test_commit_continuations_and_parent_not_traversed(tmp_path: Path) -> None:
    tree_oid, tree = raw("tree", b"")
    payload = (
        b"tree "
        + tree_oid.encode()
        + b"\nparent "
        + b"a" * 40
        + b"\ngpgsig unverified\n tree "
        + b"b" * 40
        + b"\n\nraw\xffmessage"
    )
    commit, content = raw("commit", payload)
    result = load(write_objects(tmp_path / "objects", {tree_oid: tree, commit: content}), commit)
    assert result.files == result.directories == ()


@pytest.mark.parametrize("case", ["missing", "extra", "wrong-oid", "wrong-type", "truncated-tree"])
def test_inventory_closure_and_types(tmp_path: Path, case: str) -> None:
    commit, objects = build_one({"a": b"x"})
    blob_oid = next(oid for oid, value in objects.items() if value.startswith(b"blob "))
    if case == "missing":
        del objects[blob_oid]
    elif case == "extra":
        extra, content = raw("blob", b"unused")
        objects[extra] = content
    elif case == "wrong-oid":
        objects["f" * 40] = objects.pop(blob_oid)
    elif case == "wrong-type":
        commit, objects = commit_with_tree(
            b"40000 a\0" + bytes.fromhex(blob_oid), {blob_oid: objects[blob_oid]}
        )
    else:
        commit, objects = commit_with_tree(b"100644 a\0\x01")
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", objects), commit)


@pytest.mark.parametrize(
    "change",
    ["symlink-root", "symlink-file", "hardlink", "fifo", "directory", "public", "extra-name"],
)
def test_filesystem_refusal(tmp_path: Path, change: str) -> None:
    commit, objects = build_one({"a": b"x"})
    root = write_objects(tmp_path / "objects", objects)
    victim = root / (commit + ".object")
    if change == "symlink-root":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif change == "symlink-file":
        victim.unlink()
        victim.symlink_to(tmp_path / "missing")
    elif change == "hardlink":
        os.link(victim, tmp_path / "link")
    elif change == "fifo":
        victim.unlink()
        os.mkfifo(victim, 0o600)
    elif change == "directory":
        victim.unlink()
        victim.mkdir(mode=0o700)
    elif change == "public":
        victim.chmod(0o644)
    else:
        (root / "README").write_bytes(b"extra")
    with pytest.raises((git.GitObjectError, OSError)):
        load(root, commit)


@pytest.mark.parametrize(
    "limits",
    [
        git.GitCaptureLimits(CaptureLimits(max_files=1)),
        git.GitCaptureLimits(CaptureLimits(max_entries=1)),
        git.GitCaptureLimits(CaptureLimits(max_path_bytes=1)),
        git.GitCaptureLimits(CaptureLimits(max_file_bytes=1)),
        git.GitCaptureLimits(CaptureLimits(max_total_bytes=2)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_objects=2)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_commit_bytes=1)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_commit_header_bytes=1)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_tree_bytes=1)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_total_tree_bytes=1)),
        git.GitCaptureLimits(objects=git.GitObjectLimits(max_total_preimage_bytes=1)),
    ],
    ids=[
        "files",
        "entries",
        "path",
        "blob",
        "expanded",
        "objects",
        "commit",
        "header",
        "tree",
        "trees",
        "preimages",
    ],
)
def test_all_caps(tmp_path: Path, limits: git.GitCaptureLimits) -> None:
    commit, objects = build_one({"aa": b"xx", "bb": b"yy"})
    with pytest.raises(git.GitObjectError):
        load(write_objects(tmp_path / "objects", objects), commit, limits)


def test_private_limits_snapshot_does_not_call_instance_method() -> None:
    capture = CaptureLimits()
    object.__setattr__(capture, "__post_init__", lambda: pytest.fail("caller callback"))
    frozen = git.freeze_limits(git.GitCaptureLimits(capture))
    assert frozen.capture == CaptureLimits()
    object.__setattr__(capture, "max_files", False)
    with pytest.raises(git.GitObjectError):
        git.freeze_limits(git.GitCaptureLimits(capture))


def test_blob_stream_copy_and_changed_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"x" * (git.CHUNK * 3 + 7)
    commit, objects = build_one({"a": content})
    root = write_objects(tmp_path / "objects", objects)
    tree = load(root, commit)
    blob = next(obj for obj in tree.objects if obj.kind == "blob")
    original = os.write
    writes: list[int] = []

    def short_write(fd: int, data: bytes) -> int:
        writes.append(len(data))
        return original(fd, data[:17])

    monkeypatch.setattr(git.os, "write", short_write)
    with git.open_directory(root) as source:
        target = os.open(tmp_path / "copy", git.CREATE_FLAGS, 0o600)
        try:
            git.copy_verified_blob(source, blob, target, git.GitCaptureLimits())
        finally:
            os.close(target)
        assert (tmp_path / "copy").read_bytes() == content
        assert max(writes) <= git.CHUNK
        path = root / (blob.oid + ".object")
        path.write_bytes(objects[blob.oid][:-1] + b"z")
        with pytest.raises(git.GitObjectError, match="changed-input"):
            git.recheck_object_directory(source, tree, git.GitCaptureLimits())


def test_metadata_replay_and_cross_hash_rejection(tmp_path: Path) -> None:
    commit, objects = build_one({"a": b"x"})
    tree = load(write_objects(tmp_path / "objects", objects), commit)
    replay = tuple(
        git.metadata_object(item.oid, objects[item.oid], git.GitCaptureLimits())
        if item.kind != "blob"
        else replace(item, stamp=None)
        for item in tree.objects
    )
    assert git.expand_objects(commit, replay, git.GitCaptureLimits()).files == tree.files
    damaged = tuple(
        replace(item, payload_sha256=b"x" * 32) if item.kind == "tree" else item for item in replay
    )
    with pytest.raises(git.GitObjectError):
        git.expand_objects(commit, damaged, git.GitCaptureLimits())


def test_aggregate_tree_cap_admitted_before_payload_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deliberately malformed payload is irrelevant: the declared aggregate
    # budget must reject BEFORE an allocation/read of its full payload.
    identity, content = raw("tree", b"x" * 4096)
    root = write_objects(tmp_path / "objects", {identity: content})
    original = os.read
    reads: list[int] = []

    def observed(fd: int, size: int) -> bytes:
        reads.append(size)
        return original(fd, size)

    monkeypatch.setattr(git.os, "read", observed)
    with git.open_directory(root) as parent:
        descriptor = os.open(identity + ".object", git.FILE_FLAGS, dir_fd=parent)
        try:
            with pytest.raises(git.GitObjectError, match="limit"):
                git._read_object(descriptor, identity, git.GitCaptureLimits(), tree_remaining=1)
        finally:
            os.close(descriptor)
    assert reads == [64]


@pytest.mark.parametrize("value", ["HEAD", "a" * 39, "A" * 40, "0" * 40, True, None])
def test_exact_nonzero_commit_identity(value: object) -> None:
    with pytest.raises(git.GitObjectError):
        git.check_oid(value)  # type: ignore[arg-type]


def test_expanded_depth_bound(tmp_path: Path) -> None:
    empty_oid, empty = raw("tree", b"")
    child_oid, child = raw("tree", b"40000 nested\0" + bytes.fromhex(empty_oid))
    commit, objects = commit_with_tree(
        b"40000 root\0" + bytes.fromhex(child_oid), {empty_oid: empty, child_oid: child}
    )
    with pytest.raises(git.GitObjectError, match="limit"):
        load(
            write_objects(tmp_path / "objects", objects),
            commit,
            git.GitCaptureLimits(CaptureLimits(max_depth=1)),
        )


@pytest.mark.parametrize("already_closed", [False, True])
def test_parent_close_failure_retains_child_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, already_closed: bool
) -> None:
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    real_open, real_close = os.open, os.close
    opened: list[int] = []
    attempted: list[int] = []
    failure = OSError("private close failure")

    def observed_open(*args: object, **kwargs: object) -> int:
        descriptor = real_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def failed_close(descriptor: int) -> None:
        attempted.append(descriptor)
        if len(attempted) == 1:
            if already_closed:
                real_close(descriptor)
            raise failure
        real_close(descriptor)

    monkeypatch.setattr(git.os, "open", observed_open)
    monkeypatch.setattr(git.os, "close", failed_close)
    with pytest.raises(OSError) as caught:
        with git.open_directory(root):
            pytest.fail("close failure must prevent successful entry")
    assert caught.value is failure
    assert attempted == opened  # Child was closed; uncertain first number was NOT retried.
    with pytest.raises(OSError):
        os.fstat(opened[1])
    if not already_closed:
        real_close(opened[0])  # Test owns the deliberately unclosed simulated failure.


def test_final_close_failure_preserves_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    real_close = os.close
    primary = RuntimeError("original body failure")
    prior = OSError("original explicit cause")
    cleanup = OSError("original cleanup failure")
    selected: int | None = None

    def failed_close(descriptor: int) -> None:
        real_close(descriptor)
        if descriptor == selected:
            raise cleanup

    monkeypatch.setattr(git.os, "close", failed_close)
    with pytest.raises(RuntimeError) as caught:
        with git.open_directory(root) as descriptor:
            selected = descriptor
            raise primary from prior
    assert caught.value is primary
    assert isinstance(primary.__cause__, BaseExceptionGroup)
    assert primary.__cause__.exceptions == (prior, cleanup)


def test_metadata_size_checked_before_preimage_concatenation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = git.GitObject("a" * 40, "tree", 2, b"a" * 32, b"b" * 32, b"xx")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("oversized metadata reached header/concatenation")

    monkeypatch.setattr(git, "object_header", forbidden)
    with pytest.raises(git.GitObjectError, match="limit"):
        git.expand_objects(
            "b" * 40, (item,), git.GitCaptureLimits(objects=git.GitObjectLimits(max_tree_bytes=1))
        )


def test_raw_name_size_checked_before_unicode_decode() -> None:
    with pytest.raises(git.GitObjectError, match="limit"):
        git._tree_entries(
            b"100644 " + b"\xff" * 100 + b"\0" + b"a" * 20, CaptureLimits(max_path_bytes=2)
        )


class _PoisonPathMember:
    def __str__(self) -> str:
        pytest.fail("caller path formatting invoked")

    def __iter__(self) -> object:
        pytest.fail("caller path iterator invoked")

    def __bool__(self) -> bool:
        pytest.fail("caller path truthiness invoked")


@pytest.mark.parametrize(
    "kind", ["iterable", "member", "oversized-list", "oversized-member", "drive", "root"]
)
def test_path_primitive_snapshot_refuses_poison_before_callbacks(kind: str) -> None:
    path = Path("/tmp/legitimate")
    storage = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    if kind == "iterable":
        object.__setattr__(path, storage, _PoisonPathMember())
    elif kind == "member":
        object.__setattr__(path, storage, ["/", _PoisonPathMember()])
    elif kind == "oversized-list":
        object.__setattr__(path, storage, ["x"] * 100_000)
    elif kind == "oversized-member":
        object.__setattr__(path, storage, ["/", "x" * 4097])
    elif storage == "_parts":
        object.__setattr__(path, "_drv" if kind == "drive" else "_root", _PoisonPathMember())
    else:
        object.__setattr__(path, storage, [_PoisonPathMember()])
    with pytest.raises(git.GitObjectError):
        git.check_absolute(path)


def test_path_snapshot_ignores_poisoned_caches_and_clones_components(tmp_path: Path) -> None:
    path = tmp_path / "objects"
    path.mkdir(mode=0o700)
    expected = Path(str(path))
    for name in ("_str", "_pparts"):
        try:
            object.__setattr__(path, name, _PoisonPathMember())
        except AttributeError:
            pass
    clone = git.check_absolute(path)
    assert clone is not path and str(clone) == str(expected)
    with git.open_directory(path) as descriptor:
        assert os.fstat(descriptor).st_ino == expected.stat().st_ino
    storage = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    object.__getattribute__(path, storage)[-1] = "mutated-after-copy"
    assert str(clone) == str(expected)

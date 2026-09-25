"""Controlled filesystem falsifiers for the source-custody backend, not SCM proof."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import uuid4

import pytest

from services.scan import source_capture as custody

pytestmark = pytest.mark.unit


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "checkout"
    store = tmp_path / "captures"
    source.mkdir(mode=0o700)
    store.mkdir(mode=0o700)
    return source, store


@pytest.fixture
def binding() -> custody.CaptureBinding:
    # Synthetic commit-format fixture, not a credential or verified SCM binding.
    commit = "1234567890abcdef" * 2 + "12345678"  # pragma: allowlist secret
    return custody.CaptureBinding(uuid4(), uuid4(), uuid4(), commit)


def _independent_tree(files: dict[str, bytes]) -> bytes:
    digest = hashlib.sha256()
    for path, content in sorted(files.items()):
        name = path.encode("utf-8")
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(len(content).to_bytes(8, "big") + content)
    return digest.digest()


def _write_sources(source: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o600)
        parent = path.parent
        while parent != source:
            parent.chmod(0o700)
            parent = parent.parent


def test_binary_unicode_inventory_framing_and_fresh_verification(roots, binding):
    source, root = roots
    files = {"z.py": b"\x00\xff\n", "a/\U0001f642.txt": b"one", "a/\u00e9.txt": b"two"}
    _write_sources(source, files)
    (source / "empty").mkdir(mode=0o700)
    original_modes = {name: (source / name).stat().st_mode for name in files}
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    assert receipt.tree_digest == _independent_tree(files)
    expected_inventory = {
        "schema": "scanipy-execution/source-inventory/1",
        "files": [
            {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(files.items())
        ],
    }
    expected_bytes = json.dumps(
        expected_inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert receipt.inventory_bytes == expected_bytes
    assert (
        receipt.inventory_digest
        == hashlib.sha256(b"scanipy-execution/source-inventory/1\n" + expected_bytes).digest()
    )
    copied = custody.LocalSourceCaptureStore(root).verify(receipt)
    assert copied == root / str(receipt.object_id) / "source"
    assert receipt.binding == binding
    assert receipt.file_count == len(files)
    assert receipt.content_bytes == sum(map(len, files.values()))
    for name, content in files.items():
        assert (copied / name).read_bytes() == content
        assert stat.S_IMODE((copied / name).stat().st_mode) == 0o444
        assert (source / name).stat().st_mode == original_modes[name]
    assert (copied / "empty").is_dir()
    assert stat.S_IMODE((copied / "empty").stat().st_mode) == 0o555
    manifest = (copied.parent / "manifest.json").read_bytes()
    assert (
        receipt.manifest_digest
        == hashlib.sha256(b"scanipy-source-custody/manifest/1\n" + manifest).digest()
    )
    assert (copied.parent / "SEALED").read_bytes() == receipt.manifest_digest.hex().encode() + b"\n"


def test_empty_tree_is_real_empty_capture_not_missing_input(roots, binding):
    source, root = roots
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    assert receipt.tree_digest == hashlib.sha256(b"").digest()
    assert receipt.file_count == receipt.content_bytes == 0
    store.verify(receipt)
    with pytest.raises(OSError):
        store.capture(source / "missing", binding)


def test_identical_bytes_have_distinct_per_request_objects(roots, binding):
    source, root = roots
    _write_sources(source, {"a.py": b"same"})
    store = custody.LocalSourceCaptureStore(root)
    one = store.capture(source, binding)
    two = store.capture(source, replace(binding, request_id=uuid4()))
    three = store.capture(source, binding)
    assert len({one.object_id, two.object_id, three.object_id}) == 3
    assert one.tree_digest == two.tree_digest == three.tree_digest
    assert one.inventory_bytes == two.inventory_bytes
    assert one.manifest_digest != two.manifest_digest
    with pytest.raises(FrozenInstanceError):
        one.file_count = 99


def test_existing_object_never_overwritten(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"a.py": b"original"})
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    monkeypatch.setattr(custody, "uuid4", lambda: receipt.object_id)
    (source / "a.py").write_bytes(b"different")
    with pytest.raises(FileExistsError):
        store.capture(source, binding)
    assert (store.verify(receipt) / "a.py").read_bytes() == b"original"


@pytest.mark.parametrize(
    "name", [".git", "a\\b", "line\nbreak", "bad\x7f", "bad\x85", "nested/.git"]
)
def test_unsafe_names_are_rejected_without_exclusion(roots, binding, name):
    source, root = roots
    _write_sources(source, {name: b"content"})
    store = custody.LocalSourceCaptureStore(root)
    with pytest.raises(custody.SourceCaptureError):
        store.capture(source, binding)
    assert list(root.iterdir()) == []


def test_non_unicode_filename_rejected(roots, binding):
    source, root = roots
    (source / ("bad" + chr(0xDCFF))).write_bytes(b"content")
    with pytest.raises(custody.SourceCaptureError, match="Unicode"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)


@pytest.mark.parametrize("kind", ["file-symlink", "dir-symlink", "hardlink", "fifo"])
def test_links_and_special_files_rejected(roots, binding, tmp_path, kind):
    source, root = roots
    external = tmp_path / "external"
    external.mkdir(mode=0o700)
    (external / "secret").write_bytes(b"do not copy")
    (external / "secret").chmod(0o600)
    target = source / "entry"
    if kind == "file-symlink":
        target.symlink_to(external / "secret")
    elif kind == "dir-symlink":
        target.symlink_to(external, target_is_directory=True)
    elif kind == "hardlink":
        os.link(external / "secret", target)
    else:
        os.mkfifo(target)
    message = "exactly one link" if kind == "hardlink" else "symlink or special"
    with pytest.raises(custody.SourceCaptureError, match=message):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    assert list(root.iterdir()) == []
    assert (external / "secret").read_bytes() == b"do not copy"


def test_root_or_ancestor_symlink_rejected(roots, binding, tmp_path):
    source, root = roots
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    (source / "sub").mkdir(mode=0o700)
    store = custody.LocalSourceCaptureStore(root)
    with pytest.raises(OSError):
        store.capture(alias, binding)
    with pytest.raises(OSError):
        store.capture(alias / "sub", binding)
    alias_store = tmp_path / "store-link"
    alias_store.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        custody.LocalSourceCaptureStore(alias_store)


@pytest.mark.parametrize(
    "target,mode", [("source", 0o777), ("root", 0o755), ("file", 0o666), ("dir", 0o777)]
)
def test_unsafe_permissions_rejected_without_chmod(roots, binding, target, mode):
    source, root = roots
    _write_sources(source, {"file": b"safe"})
    (source / "dir").mkdir(mode=0o700)
    selected = {"source": source, "root": root, "file": source / "file", "dir": source / "dir"}[
        target
    ]
    selected.chmod(mode)
    with pytest.raises(custody.SourceCaptureError):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    assert stat.S_IMODE(selected.stat().st_mode) == mode


def test_wrong_owner_rejected(roots, monkeypatch):
    _, root = roots
    monkeypatch.setattr(custody.os, "geteuid", lambda: root.stat().st_uid + 1)
    with pytest.raises(custody.SourceCaptureError, match="owned"):
        custody.LocalSourceCaptureStore(root)


def test_overlapping_or_relative_roots_rejected(roots, binding):
    source, root = roots
    store = custody.LocalSourceCaptureStore(root)
    for invalid in (
        root,
        root / "child",
        root.parent,
        Path("relative"),
        source / ".." / "checkout",
    ):
        with pytest.raises(custody.SourceCaptureError):
            store.capture(invalid, binding)


@pytest.mark.parametrize(
    "field,limit,files",
    [
        ("max_files", 1, {"a": b"1", "b": b"2"}),
        ("max_entries", 1, {"a/b": b"1"}),
        ("max_depth", 1, {"a/b": b"1"}),
        ("max_path_bytes", 1, {"ab": b"1"}),
        ("max_file_bytes", 1, {"a": b"12"}),
        ("max_total_bytes", 1, {"a": b"1", "b": b"2"}),
        ("max_metadata_bytes", 1, {"a": b"1"}),
    ],
)
def test_all_declared_bounds_fail_without_complete_receipt(roots, binding, field, limit, files):
    source, root = roots
    _write_sources(source, files)
    limits = replace(custody.CaptureLimits(), **{field: limit})
    with pytest.raises(custody.SourceCaptureError, match=r"limit|bound"):
        custody.LocalSourceCaptureStore(root, limits=limits).capture(source, binding)
    assert not list(root.glob("*/SEALED"))


@pytest.mark.parametrize("value", [True, 0, -1, 10_001, 1.5, "1"])
def test_invalid_limit_types_and_ranges_rejected(value):
    with pytest.raises(custody.SourceCaptureError):
        custody.CaptureLimits(max_files=value)


@pytest.mark.parametrize("commit", ["", "0" * 40, "a" * 39, "A" * 40, "x" * 40, "main", None])
def test_unresolved_or_fabricated_commit_rejected(binding, commit):
    with pytest.raises(custody.SourceCaptureError):
        replace(binding, resolved_commit=commit)


def test_scope_requires_uuids(binding):
    with pytest.raises(custody.SourceCaptureError):
        replace(binding, org_id="org")


@pytest.mark.parametrize("phase", ["copy", "manifest", "seal"])
def test_storage_failure_retains_explicit_unsealed_orphan(roots, binding, monkeypatch, phase):
    source, root = roots
    _write_sources(source, {"a.py": b"actual bytes"})
    original_write = custody._write_all

    def fail_selected(fd, payload):
        text = bytes(payload)
        selected = {
            "copy": text == b"actual bytes",
            "manifest": b'"custody_profile"' in text,
            "seal": len(text) == 65 and text.endswith(b"\n"),
        }[phase]
        if selected:
            raise OSError("controlled storage failure")
        return original_write(fd, payload)

    monkeypatch.setattr(custody, "_write_all", fail_selected)
    with pytest.raises(OSError, match="controlled"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    objects = list(root.iterdir())
    assert len(objects) == 1
    assert stat.S_IMODE(objects[0].stat().st_mode) == 0o700
    # A failed seal write may leave an empty file, never a valid seal marker.
    marker = objects[0] / "SEALED"
    assert not marker.exists() or marker.read_bytes() == b""
    assert (source / "a.py").read_bytes() == b"actual bytes"


def test_observable_mutation_during_copy_fails(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"a.py": b"original"})
    original_write = custody._write_all
    changed = False

    def mutate_after_read(fd, payload):
        nonlocal changed
        original_write(fd, payload)
        if not changed:
            changed = True
            (source / "a.py").write_bytes(b"modified")

    monkeypatch.setattr(custody, "_write_all", mutate_after_read)
    with pytest.raises(custody.SourceCaptureError, match="changed"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    assert not list(root.glob("*/SEALED"))


def test_stored_readback_rejects_corrupt_write_before_publication(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"a.py": b"original"})
    original_write = custody._write_all

    def corrupt_write(fd, payload):
        original_write(fd, b"corrupt!" if bytes(payload) == b"original" else payload)

    monkeypatch.setattr(custody, "_write_all", corrupt_write)
    with pytest.raises(custody.SourceCaptureError, match="readback differs"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    assert not list(root.glob("*/manifest.json"))
    assert not list(root.glob("*/SEALED"))


def test_short_os_writes_are_completed_and_read_back(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"a.py": b"all bytes must survive"})
    actual_write = os.write

    def short_write(fd, payload):
        return actual_write(fd, payload[:3])

    monkeypatch.setattr(custody.os, "write", short_write)
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    assert (store.verify(receipt) / "a.py").read_bytes() == b"all bytes must survive"


@pytest.mark.parametrize("phase", ["manifest", "seal"])
def test_metadata_readback_rejects_corruption_without_receipt(roots, binding, monkeypatch, phase):
    source, root = roots
    _write_sources(source, {"a.py": b"source"})
    actual_write = custody._write_all

    def corrupt_metadata(fd, payload):
        content = bytes(payload)
        selected = b'"custody_profile"' in content if phase == "manifest" else len(content) == 65
        actual_write(fd, bytes([content[0] ^ 1]) + content[1:] if selected else content)

    monkeypatch.setattr(custody, "_write_all", corrupt_metadata)
    with pytest.raises(custody.SourceCaptureError, match=f"stored {phase} readback"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    assert stat.S_IMODE(next(root.iterdir()).stat().st_mode) == 0o700


@pytest.mark.parametrize(
    "kind",
    [
        "change",
        "remove",
        "add",
        "manifest",
        "seal",
        "writable-file",
        "writable-dir",
        "extra-object",
        "symlink",
    ],
)
def test_verification_rejects_retained_tampering(roots, binding, kind):
    source, root = roots
    _write_sources(source, {"folder/a.py": b"trusted"})
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    obj = root / str(receipt.object_id)
    copied = obj / "source"
    path = copied / "folder/a.py"
    if kind == "change":
        path.chmod(0o600)
        path.write_bytes(b"changed")
        path.chmod(0o444)
    elif kind == "remove":
        path.parent.chmod(0o700)
        path.unlink()
        path.parent.chmod(0o555)
    elif kind == "add":
        copied.chmod(0o700)
        (copied / "extra").write_bytes(b"not inventoried")
        (copied / "extra").chmod(0o444)
        copied.chmod(0o555)
    elif kind in ("manifest", "seal"):
        selected = obj / ("manifest.json" if kind == "manifest" else "SEALED")
        selected.chmod(0o600)
        selected.write_bytes(b"modified")
        selected.chmod(0o444)
    elif kind == "writable-file":
        path.chmod(0o644)
    elif kind == "writable-dir":
        path.parent.chmod(0o755)
    elif kind == "extra-object":
        obj.chmod(0o700)
        (obj / "extra").write_bytes(b"untracked")
        obj.chmod(0o555)
    else:
        path.parent.chmod(0o700)
        path.unlink()
        path.symlink_to(source / "folder/a.py")
        path.parent.chmod(0o555)
    with pytest.raises((custody.SourceCaptureError, OSError)):
        store.verify(receipt)


def test_receipt_digest_binding_not_self_declared_manifest(roots, binding):
    source, root = roots
    _write_sources(source, {"a.py": b"actual"})
    store = custody.LocalSourceCaptureStore(root)
    receipt = store.capture(source, binding)
    with pytest.raises(custody.SourceCaptureError, match="digests"):
        store.verify(replace(receipt, tree_digest=b"x" * 32))
    with pytest.raises(custody.SourceCaptureError, match="digest"):
        store.verify(replace(receipt, manifest_digest=b""))
    with pytest.raises(custody.SourceCaptureError, match="digests"):
        store.verify(replace(receipt, binding=replace(binding, request_id=uuid4())))


def test_durable_publication_order_and_final_flush(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"nested/a.py": b"durable"})
    calls = []
    actual_fsync = os.fsync

    def observed_fsync(fd):
        calls.append(str(Path(f"/proc/self/fd/{fd}").readlink()))
        actual_fsync(fd)

    monkeypatch.setattr(custody.os, "fsync", observed_fsync)
    receipt = custody.LocalSourceCaptureStore(root).capture(source, binding)
    obj = root / str(receipt.object_id)
    assert calls.index(str(obj / "source/nested/a.py")) < calls.index(str(obj / "source/nested"))
    assert calls.index(str(obj / "source")) < calls.index(str(obj / "manifest.json"))
    assert calls.index(str(obj / "manifest.json")) < calls.index(str(obj / "SEALED"))
    assert calls[-2:] == [str(obj), str(root)]


def test_final_flush_failure_is_not_acknowledged_capture(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(source, {"a.py": b"retained but not acknowledged"})
    actual_fsync = os.fsync

    def fail_final(fd):
        if Path(f"/proc/self/fd/{fd}").readlink() == root:
            raise OSError("controlled final durability failure")
        actual_fsync(fd)

    monkeypatch.setattr(custody.os, "fsync", fail_final)
    with pytest.raises(OSError, match="durability failure"):
        custody.LocalSourceCaptureStore(root).capture(source, binding)
    # A marker can exist before a failed final flush. Discovery must never
    # interpret it as a committed DB seal; this backend returns no receipt.
    assert len(list(root.glob("*/SEALED"))) == 1


def test_source_and_verification_never_execute_programs(roots, binding, monkeypatch):
    source, root = roots
    _write_sources(
        source,
        {"setup.py": b"raise RuntimeError('must never run')", "Makefile": b"all:\n\tfalse\n"},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("source custody must not execute a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    store = custody.LocalSourceCaptureStore(root)
    store.verify(store.capture(source, binding))

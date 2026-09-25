"""Real inert-file controls for metadata/ancestor recheck role separation."""

from __future__ import annotations

import os
import time

import pytest

from tests.unit import test_runtime_profiles as fixtures
from tools.worker import runtime_profiles as profiles

pytestmark = pytest.mark.unit

_FIELDS = ("device", "inode", "mode", "nlink", "size", "uid", "gid", "mtime", "ctime")
_METADATA = ("installation", "outer", "domain", "inventory")


@pytest.mark.parametrize("purpose", ["python-syntax", "accepted-verifier"])
@pytest.mark.parametrize("short_reads", [False, True])
def test_unmeasured_sibling_keeps_actual_metadata_load_valid(
    tmp_path, monkeypatch, purpose, short_reads
):
    anchor = fixtures.prepare(tmp_path, purpose).persist()
    actual_measure = fixtures.artifacts.require_installed_runtime_artifacts
    actual_recheck = profiles._Files.recheck
    selected = tuple(tmp_path / "metadata" / name for name in _METADATA)
    before = {path: profiles._stamp(path.stat()) for path in selected}
    if short_reads:
        actual_read = os.read
        monkeypatch.setattr(os, "read", lambda fd, size: actual_read(fd, min(size, 7)))

    def measured_then_sibling(*args, **kwargs):
        result = actual_measure(*args, **kwargs)
        (tmp_path / "unmeasured-sibling").mkdir(mode=0o700)
        assert {path: profiles._stamp(path.stat()) for path in selected} == before
        return result

    def observed_recheck(files):
        held = files.held[tmp_path]
        current = profiles._stamp(os.fstat(held.descriptor))
        changes = {index for index in range(9) if current[index] != held.stamp[index]}
        assert changes and changes <= {3, 4, 7, 8}
        # Full observations remain stored even when comparison is role-specific.
        assert len(held.stamp) == 9 and held.stamp != current
        return actual_recheck(files)

    monkeypatch.setattr(
        fixtures.artifacts, "require_installed_runtime_artifacts", measured_then_sibling
    )
    monkeypatch.setattr(profiles._Files, "recheck", observed_recheck)
    loaded = profiles.load_installed_runtime(anchor)
    assert loaded.anchor == anchor
    assert len(loaded.metadata_observations) == 4
    for observation in loaded.metadata_observations:
        original = before[observation.path]
        assert (
            observation.nlink,
            observation.size,
            observation.mtime_ns,
            observation.ctime_ns,
        ) == (original[3], original[4], original[7], original[8])


@pytest.fixture
def held_files(tmp_path):
    anchor = fixtures.prepare(tmp_path).persist()
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    try:
        for name in _METADATA:
            files.open(tmp_path / "metadata" / name)
        yield files
    finally:
        files.close(None)


def _changed_stat(original: os.stat_result, field: int) -> os.stat_result:
    """Inject one bounded kernel-observation fault, not a real chown/mount."""
    values = list(original)
    nanos = {
        "st_atime_ns": original.st_atime_ns,
        "st_mtime_ns": original.st_mtime_ns,
        "st_ctime_ns": original.st_ctime_ns,
    }
    if field in (7, 8):
        nanos["st_mtime_ns" if field == 7 else "st_ctime_ns"] += 1
    else:
        values[{0: 2, 1: 1, 2: 0, 3: 3, 4: 6, 5: 4, 6: 5}[field]] += 1
    changed = os.stat_result(values, nanos)
    before, after = profiles._stamp(original), profiles._stamp(changed)
    assert {index for index in range(9) if before[index] != after[index]} == {field}
    return changed


def _inject_observation(monkeypatch, held, operation, field):
    original = getattr(os, operation)
    hits = []

    def observed(*args, **kwargs):
        info = original(*args, **kwargs)
        target = (
            args == (held.descriptor,)
            if operation == "fstat"
            else args == (held.name,)
            and kwargs == {"dir_fd": held.parent, "follow_symlinks": False}
        )
        if target:
            hits.append(operation)
            return _changed_stat(info, field)
        return info

    monkeypatch.setattr(os, operation, observed)
    return hits


@pytest.mark.parametrize("operation", ["fstat", "stat"])
@pytest.mark.parametrize("field", range(9), ids=_FIELDS)
@pytest.mark.parametrize("target", ["metadata", *(f"metadata/{name}" for name in _METADATA)])
def test_metadata_and_direct_parent_keep_all_nine_fields(
    held_files, tmp_path, monkeypatch, target, field, operation
):
    held = held_files.held[tmp_path / target]
    original_stamp = held.stamp
    hits = _inject_observation(monkeypatch, held, operation, field)
    with pytest.raises(profiles.RuntimeProfileError, match=r"^metadata-invalid$"):
        held_files.recheck_one(held)
    assert hits == [operation]
    assert held.stamp == original_stamp


@pytest.mark.parametrize("operation", ["fstat", "stat"])
@pytest.mark.parametrize("field", range(9), ids=_FIELDS)
def test_only_four_ancestor_namespace_fields_are_projected(
    held_files, tmp_path, monkeypatch, field, operation
):
    held = held_files.held[tmp_path]
    original_stamp = held.stamp
    hits = _inject_observation(monkeypatch, held, operation, field)
    if field in (3, 4, 7, 8):
        held_files.recheck_one(held)
    else:
        with pytest.raises(profiles.RuntimeProfileError, match=r"^metadata-invalid$"):
            held_files.recheck_one(held)
    assert hits == [operation]
    assert held.stamp == original_stamp


@pytest.mark.parametrize("nested_parent", [False, True])
def test_real_direct_parent_namespace_change_still_fails(tmp_path, nested_parent):
    anchor = fixtures.prepare(tmp_path).persist()
    metadata = tmp_path / "metadata"
    if nested_parent:
        (metadata / "nested").mkdir(mode=0o700)
        fixtures.write(metadata / "nested" / "file", b"inert metadata")
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    try:
        files.open(metadata / "installation")
        if nested_parent:
            files.open(metadata / "nested" / "file")
        held = files.held[metadata]
        (metadata / "changed-namespace").mkdir(mode=0o700)
        assert profiles._stamp(os.fstat(held.descriptor)) != held.stamp
        with pytest.raises(profiles.RuntimeProfileError, match=r"^metadata-invalid$"):
            files.recheck_one(held)
    finally:
        files.close(None)


def test_real_safe_but_changed_ancestor_mode_still_fails(held_files, tmp_path):
    held = held_files.held[tmp_path]
    assert held.stamp[2] & 0o7777 == 0o700
    tmp_path.chmod(0o755)  # Still safe for traversal, but not the original mode.
    with pytest.raises(profiles.RuntimeProfileError, match=r"^metadata-invalid$"):
        held_files.recheck_one(held)


def test_direct_parent_tracking_remains_bounded(held_files, tmp_path):
    # All four selected metadata files share one protected direct parent here.
    assert held_files.metadata_parents == {tmp_path / "metadata"}
    assert len(held_files.held) == len(held_files.owned)
    assert all(len(held.stamp) == 9 for held in held_files.held.values())

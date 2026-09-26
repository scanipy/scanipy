"""Small ordinary-UID filesystem histories, not native/runtime qualification.

Only fresh pytest-owned roots are populated. No processes, mounts, keys, host
configuration, Docker or database are used; no power-loss durability is claimed.
"""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from tests.unit.test_runtime_evidence import _history_tree
from tests.unit.test_runtime_journal import History, admitted, collect, register
from tools.worker import runtime_evidence as evidence

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", evidence._MODES)
@pytest.mark.parametrize("phase", ("reserved", "admitted"))
def test_small_filesystem_history_preserves_actual_owner_report(
    tmp_path: Path, mode: str, phase: str
) -> None:
    history = History(mode)
    if phase == "admitted":
        admitted(history)
    expected = history.replay()
    installation, directory, _ = _history_tree(tmp_path, history)
    before = {
        path.relative_to(tmp_path): (path.stat().st_mode, path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    actual = evidence.read_diagnostic_attempt_history(installation, UUID(history.m["attempt_id"]))
    after = {
        path.relative_to(tmp_path): (path.stat().st_mode, path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert actual.report == expected and before == after
    assert directory.stat().st_uid == os.geteuid()
    assert actual.visibility == "verified-visible-prefix"
    assert actual.report.validation == "local-structure-only"
    assert actual.report.opaque_owner_values == expected.opaque_owner_values
    with pytest.raises(FrozenInstanceError):
        actual.visibility = "durable"  # type: ignore[misc,assignment]


def test_small_registered_history_does_not_follow_retained_spool_path(tmp_path: Path) -> None:
    history = History()
    call = history.intent("daemon-version")
    registration = register(history, call)
    collect(history, call, registration, "stdout", b"diagnostic output")
    collect(history, call, registration, "stderr", b"")
    installation, _, _ = _history_tree(tmp_path, history)
    (installation.host_work_root / "not-a-validated-spool").write_bytes(b"outside read scope")
    actual = evidence.read_diagnostic_attempt_history(installation, UUID(history.m["attempt_id"]))
    assert actual.report == history.replay()
    assert actual.report.calls[0].result is None
    assert not (installation.host_work_root / "call-spools").exists()


def test_small_reader_does_not_require_an_empty_other_attempt_or_refusal(tmp_path: Path) -> None:
    history = History()
    installation, _, _ = _history_tree(tmp_path, history)
    other = installation.evidence_root / "attempts" / "unrelated-diagnostic-residue"
    other.mkdir(mode=0o700)
    (other / "not-a-history").write_bytes(b"not traversed")
    (installation.evidence_root / "refusals" / "unrelated").write_bytes(b"not traversed")
    assert (
        evidence.read_diagnostic_attempt_history(installation, UUID(history.m["attempt_id"])).report
        == history.replay()
    )


@pytest.mark.parametrize("kind", ("symlink", "hardlink", "writable", "fifo"))
def test_small_real_inode_custody_rejects_nonpublished_leaf(tmp_path: Path, kind: str) -> None:
    history = History()
    installation, directory, _ = _history_tree(tmp_path, history)
    leaf = directory / "manifest.json"
    if kind == "symlink":
        target = tmp_path / "detached"
        leaf.rename(target)
        leaf.symlink_to(target)
    elif kind == "hardlink":
        os.link(leaf, tmp_path / "second-name")
    elif kind == "writable":
        leaf.chmod(0o600)
    else:
        leaf.unlink()
        os.mkfifo(leaf, 0o400)
    with pytest.raises(evidence.RuntimePublicationError):
        evidence.read_diagnostic_attempt_history(installation, UUID(history.m["attempt_id"]))

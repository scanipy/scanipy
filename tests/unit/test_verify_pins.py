"""Focused unit coverage for the AC-DEPLOY-02c publish gate (verify_pins).

`workers/build/verify_pins.py` is the INV-2 producer defence (DOC-CMP-DEPLOY-02
§3.3 / §5): it refuses to build the worker image if any pinned base-image or
tool digest in `workers/pins.json` is unspecified, so `env_digest` (the ECR
image digest) is never derived from an unpinned input.

These tests are fully hermetic — no docker, no ECR, no network. They drive the
gate from self-built manifest fixtures and a `tmp_path` file. AC-DEPLOY-02a/02b
(pinned tools present at digest inside a built image; digest changes on tool
mutation) require a real build substrate and are deferred (see the skipped
specs in `tests/unit/test_deploy_specs.py`).

Source-of-truth: DOC-CMP-DEPLOY-02.md §3.3 + §9 (verbatim AC-DEPLOY-02c).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from workers.build.verify_pins import SNAPSHOT_LOCKFILE, check_lockfile, check_pins, main

_DIGEST = "0" * 64


def _complete_pins() -> dict[str, Any]:
    """A fully-pinned manifest that the gate must accept."""
    return {
        "schema_version": 1,
        "base_images": {
            "debian": {"tag": "12-slim", "sha256": _DIGEST},
            "python": {"tag": "3.11-slim-bookworm", "sha256": _DIGEST},
        },
        "tools": {
            "joern": {"version": "v4.0.0", "sha256": _DIGEST},
            "codeql": {"version": "v2.20.0", "sha256": _DIGEST},
            "git": {"version": "1:2.39.5", "sha256": _DIGEST},
        },
        "python_packages_lockfile_sha256": _DIGEST,
    }


@pytest.mark.unit
def test_complete_manifest_passes() -> None:
    """A fully-pinned manifest yields no missing fields (gate accepts)."""
    assert check_pins(_complete_pins()) == []


@pytest.mark.unit
def test_empty_base_image_sha256_rejected() -> None:
    """An empty base-image sha256 is reported as missing."""
    pins = _complete_pins()
    pins["base_images"]["debian"]["sha256"] = ""
    assert check_pins(pins) == ["base_images.debian.sha256"]


@pytest.mark.unit
def test_empty_tool_sha256_rejected() -> None:
    """An empty tool sha256 is reported as missing."""
    pins = _complete_pins()
    pins["tools"]["joern"]["sha256"] = ""
    assert check_pins(pins) == ["tools.joern.sha256"]


@pytest.mark.unit
def test_empty_tool_version_rejected() -> None:
    """An empty tool version is reported as missing (versions are pins too)."""
    pins = _complete_pins()
    pins["tools"]["codeql"]["version"] = ""
    assert check_pins(pins) == ["tools.codeql.version"]


@pytest.mark.unit
def test_missing_sha256_key_rejected() -> None:
    """An absent sha256 key is treated identically to an empty one."""
    pins = _complete_pins()
    del pins["tools"]["git"]["sha256"]
    assert check_pins(pins) == ["tools.git.sha256"]


@pytest.mark.unit
def test_none_digest_rejected() -> None:
    """A null (None) digest is treated as unspecified."""
    pins = _complete_pins()
    pins["base_images"]["python"]["sha256"] = None
    assert check_pins(pins) == ["base_images.python.sha256"]


@pytest.mark.unit
def test_empty_lockfile_sha256_rejected() -> None:
    """An empty python lockfile sha256 is reported as missing."""
    pins = _complete_pins()
    pins["python_packages_lockfile_sha256"] = ""
    assert check_pins(pins) == ["python_packages_lockfile_sha256"]


@pytest.mark.unit
def test_multiple_missing_all_reported() -> None:
    """All missing fields are reported, not just the first."""
    pins = _complete_pins()
    pins["base_images"]["debian"]["sha256"] = ""
    pins["tools"]["joern"]["sha256"] = ""
    pins["python_packages_lockfile_sha256"] = ""
    missing = check_pins(pins)
    assert set(missing) == {
        "base_images.debian.sha256",
        "tools.joern.sha256",
        "python_packages_lockfile_sha256",
    }


@pytest.mark.unit
def test_empty_base_images_section_rejected() -> None:
    """An empty/absent base_images section is itself a missing pin."""
    pins = _complete_pins()
    pins["base_images"] = {}
    assert check_pins(pins) == ["base_images"]


@pytest.mark.unit
def test_empty_tools_section_rejected() -> None:
    """An empty/absent tools section is itself a missing pin."""
    pins = _complete_pins()
    pins["tools"] = {}
    assert check_pins(pins) == ["tools"]


@pytest.mark.unit
def test_main_passes_on_complete_file(tmp_path: Path) -> None:
    """main() returns 0 only for complete pins bound to actual lock bytes."""
    pins = _pins_with_lock(tmp_path)
    pins_file = tmp_path / "pins.json"
    pins_file.write_text(json.dumps(pins), encoding="utf-8")
    assert main([str(pins_file), "--repo-root", str(tmp_path)]) == 0


@pytest.mark.unit
def test_main_refuses_on_incomplete_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() returns non-zero and names the missing field for an incomplete manifest."""
    pins = _complete_pins()
    pins["tools"]["joern"]["sha256"] = ""
    pins_file = tmp_path / "pins.json"
    pins_file.write_text(json.dumps(pins), encoding="utf-8")

    assert main([str(pins_file)]) == 1
    captured = capsys.readouterr()
    assert "AC-DEPLOY-02c" in captured.err
    assert "tools.joern.sha256" in captured.err


@pytest.mark.unit
def test_committed_pins_file_passes_gate() -> None:
    """The committed pins must be complete AND match actual lock bytes."""
    repo_root = Path(__file__).resolve().parents[2]
    pins_path = repo_root / "workers" / "pins.json"
    committed = json.loads(pins_path.read_text(encoding="utf-8"))
    assert check_pins(committed) == []
    assert main([str(pins_path)]) == 0


def _pins_with_lock(root: Path) -> dict[str, Any]:
    lock = root / SNAPSHOT_LOCKFILE
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"example==1.0 --hash=sha256:controlled\n")
    pins = _complete_pins()
    pins["python_packages_lockfile"] = SNAPSHOT_LOCKFILE
    pins["python_packages_lockfile_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    return pins


@pytest.mark.unit
def test_changed_lock_bytes_fail_even_with_all_pins_populated(tmp_path: Path) -> None:
    pins = _pins_with_lock(tmp_path)
    lock = tmp_path / SNAPSHOT_LOCKFILE
    lock.write_bytes(lock.read_bytes() + b"# one additional byte matters\n")
    assert check_pins(pins) == []  # The old gate accepted this mismatch.
    errors = check_lockfile(pins, tmp_path)
    assert len(errors) == 1
    assert "expected" in errors[0] and "actual" in errors[0]
    manifest = tmp_path / "pins.json"
    manifest.write_text(json.dumps(pins))
    assert main([str(manifest), "--repo-root", str(tmp_path)]) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "digest", [None, "", "a" * 63, "A" * 64, "z" * 64, "sha256:" + "a" * 64, 1]
)
def test_malformed_lock_digest_rejected(tmp_path: Path, digest: Any) -> None:
    pins = _pins_with_lock(tmp_path)
    pins["python_packages_lockfile_sha256"] = digest
    assert "64 lowercase" in check_lockfile(pins, tmp_path)[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        7,
        "/tmp/requirements.txt",
        "../requirements.txt",
        "workers/../requirements.txt",
        "workers/snapshot/./requirements.txt",
        "workers\\snapshot\\requirements.txt",
        "other.txt",
    ],
)
def test_lock_path_must_bind_exact_dockerfile_copy(tmp_path: Path, path: Any) -> None:
    pins = _pins_with_lock(tmp_path)
    # A different same-content file must not stand in for the Dockerfile input.
    (tmp_path / "other.txt").write_bytes((tmp_path / SNAPSHOT_LOCKFILE).read_bytes())
    pins["python_packages_lockfile"] = path
    assert "must be exactly" in check_lockfile(pins, tmp_path)[0]


@pytest.mark.unit
def test_missing_lock_and_non_directory_root_rejected(tmp_path: Path) -> None:
    pins = _pins_with_lock(tmp_path)
    (tmp_path / SNAPSHOT_LOCKFILE).unlink()
    assert "cannot read lock" in check_lockfile(pins, tmp_path)[0]
    assert "not a directory" in check_lockfile(pins, tmp_path / "absent")[0]


@pytest.mark.unit
def test_directory_cannot_be_lock(tmp_path: Path) -> None:
    pins = _pins_with_lock(tmp_path)
    lock = tmp_path / SNAPSHOT_LOCKFILE
    lock.unlink()
    lock.mkdir()
    assert "regular file" in check_lockfile(pins, tmp_path)[0]


@pytest.mark.unit
@pytest.mark.parametrize("directory_link", [False, True])
def test_symlink_lock_or_parent_rejected(tmp_path: Path, directory_link: bool) -> None:
    pins = _pins_with_lock(tmp_path)
    path = tmp_path / ("workers/snapshot" if directory_link else SNAPSHOT_LOCKFILE)
    target = tmp_path / "retained-original"
    path.rename(target)
    path.symlink_to(target, target_is_directory=directory_link)
    assert "symlink" in check_lockfile(pins, tmp_path)[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "[",
        "[]",
        "null",
        "1",
        '"not an object"',
        '{"tools": {}, "tools": {}}',
        '{"tools": {"joern": {"sha256": "a", "sha256": "b"}}}',
    ],
)
def test_malformed_pins_refuse_cleanly(tmp_path: Path, content: str, capsys) -> None:
    manifest = tmp_path / "pins.json"
    manifest.write_text(content)
    assert main([str(manifest)]) == 1
    assert "cannot load pins" in capsys.readouterr().err


@pytest.mark.unit
def test_missing_manifest_refuses_cleanly(tmp_path: Path) -> None:
    assert main([str(tmp_path / "absent.json")]) == 1


@pytest.mark.unit
def test_default_manifest_and_root_do_not_depend_on_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main([]) == 0


@pytest.mark.unit
def test_http_stack_pinned_versions() -> None:
    """The installed HTTP stack matches the CLAR-DEPLOY-19 exact pins.

    CLAR-DEPLOY-19 (RESOLVED 2026-07-14) pins the security-relevant HTTP
    parsing layer exactly (pyproject `http` extra; httpx2 in `dev`). fastapi's
    starlette bound is uncapped, so only this tripwire catches a resolver
    drifting the stack a CVE-relevant patch away from what was reviewed.
    """
    from importlib import metadata

    pins = {
        "fastapi": "0.138.2",
        "starlette": "1.3.1",
        "pydantic": "2.13.4",
        "uvicorn": "0.51.0",
        # dev-extra pin: the warning-clean TestClient backend (filterwarnings=error).
        "httpx2": "2.6.0",
    }
    installed = {name: metadata.version(name) for name in pins}
    assert installed == pins

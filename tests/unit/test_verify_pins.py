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

import json
from pathlib import Path
from typing import Any

import pytest

from workers.build.verify_pins import check_pins, main

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
    """main() returns 0 for a complete manifest file."""
    pins_file = tmp_path / "pins.json"
    pins_file.write_text(json.dumps(_complete_pins()), encoding="utf-8")
    assert main([str(pins_file)]) == 0


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
    """The committed workers/pins.json must pass the gate (every pin non-empty)."""
    repo_root = Path(__file__).resolve().parents[2]
    pins_path = repo_root / "workers" / "pins.json"
    committed = json.loads(pins_path.read_text(encoding="utf-8"))
    assert check_pins(committed) == []
    assert main([str(pins_path)]) == 0


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

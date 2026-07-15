"""TST-AC-DEPLOY-04c — SLSA-3 provenance predicate content coverage.

`workers/build/slsa_predicate.py::build_predicate` is the single source of
predicate shape shared by `deploy.yml:build-images` (which attaches it via
`cosign attest --type slsaprovenance`) and this test — so the workflow and the
test can never silently drift apart on what the attestation actually contains.

AC-DEPLOY-04c (verbatim, `DOC-CMP-DEPLOY-04.md §9`): *"Image provenance (build
commit, build inputs, tool digests) is signed and published with the
artifact."* This module covers the *content* half hermetically (no docker, no
cosign, no ECR): given a self-built `pins.json` + `Dockerfile` +
`requirements.txt` fixture tree, assert the predicate links the image digest,
build commit, every build-input content hash, and every pinned tool digest.

Source-of-truth: DOC-CMP-DEPLOY-04.md §3.6 (verbatim predicate contents).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from workers.build.slsa_predicate import (
    BUILD_TYPE,
    PREDICATE_TYPE,
    build_predicate,
    file_sha256,
    main,
)

_IMAGE_DIGEST = "sha256:" + "a" * 64
_BUILD_COMMIT = "b" * 40


def _write_fixture_tree(root: Path) -> tuple[Path, Path, Path]:
    """A minimal pins.json + Dockerfile + requirements.txt fixture tree."""
    pins_path = root / "workers" / "pins.json"
    pins_path.parent.mkdir(parents=True, exist_ok=True)
    pins_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tools": {
                    "joern": {"version": "v4.0.554", "sha256": "c" * 64},
                    "codeql": {"version": "v2.20.0", "sha256": "d" * 64},
                },
            }
        ),
        encoding="utf-8",
    )
    dockerfile_path = root / "workers" / "snapshot" / "Dockerfile"
    dockerfile_path.parent.mkdir(parents=True, exist_ok=True)
    dockerfile_path.write_text("FROM debian:12-slim\n", encoding="utf-8")
    requirements_path = root / "workers" / "snapshot" / "requirements.txt"
    requirements_path.write_text("fastapi==0.115.0\n", encoding="utf-8")
    return pins_path, dockerfile_path, requirements_path


def _build(root: Path, **overrides: object) -> dict[str, object]:
    pins_path, dockerfile_path, requirements_path = _write_fixture_tree(root)
    kwargs: dict[str, object] = {
        "image_digest": _IMAGE_DIGEST,
        "build_commit": _BUILD_COMMIT,
        "source_ref": "refs/tags/v0.1.2",
        "repository": "scanipy/scanipy-v3.2",
        "builder_id": "https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@refs/tags/v0.1.2",
        "pins_path": pins_path,
        "dockerfile_path": dockerfile_path,
        "requirements_path": requirements_path,
        "build_started_on": "2026-07-15T00:00:00Z",
        "build_finished_on": "2026-07-15T00:05:00Z",
        "repo_root": root,
    }
    kwargs.update(overrides)
    return build_predicate(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# file_sha256 — the content-hash primitive every material entry relies on
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_bytes(b"hello world")
    assert file_sha256(p) == hashlib.sha256(b"hello world").hexdigest()


# ---------------------------------------------------------------------------
# build_predicate — top-level shape
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_predicate_type_and_build_type_are_slsa_v02() -> None:
    assert PREDICATE_TYPE == "https://slsa.dev/provenance/v0.2"
    assert BUILD_TYPE.startswith("https://")


@pytest.mark.unit
def test_predicate_links_builder_and_image_digest(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    assert predicate["builder"] == {
        "id": "https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@refs/tags/v0.1.2"
    }
    assert predicate["buildType"] == BUILD_TYPE
    parameters = predicate["invocation"]["parameters"]  # type: ignore[index]
    assert parameters["image_digest"] == _IMAGE_DIGEST


@pytest.mark.unit
def test_predicate_links_build_commit_via_config_source(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    config_source = predicate["invocation"]["configSource"]  # type: ignore[index]
    assert config_source["digest"] == {"sha1": _BUILD_COMMIT}
    assert config_source["uri"] == "git+https://github.com/scanipy/scanipy-v3.2@refs/tags/v0.1.2"
    assert config_source["entryPoint"] == ".github/workflows/deploy.yml"


@pytest.mark.unit
def test_predicate_metadata_carries_build_timestamps(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    metadata = predicate["metadata"]  # type: ignore[index]
    assert metadata["buildStartedOn"] == "2026-07-15T00:00:00Z"
    assert metadata["buildFinishedOn"] == "2026-07-15T00:05:00Z"
    assert metadata["reproducible"] is False


# ---------------------------------------------------------------------------
# build_predicate — materials (build inputs)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_predicate_materials_include_source_commit(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    materials = predicate["materials"]  # type: ignore[index]
    source_materials = [m for m in materials if m["digest"] == {"sha1": _BUILD_COMMIT}]  # type: ignore[index]
    assert len(source_materials) == 1


@pytest.mark.unit
def test_predicate_materials_include_pins_dockerfile_requirements_content_hashes(
    tmp_path: Path,
) -> None:
    pins_path, dockerfile_path, requirements_path = _write_fixture_tree(tmp_path)
    predicate = _build(tmp_path)
    materials = predicate["materials"]  # type: ignore[index]
    digests = {m["digest"].get("sha256") for m in materials if "sha256" in m["digest"]}  # type: ignore[index]

    assert file_sha256(pins_path) in digests
    assert file_sha256(dockerfile_path) in digests
    assert file_sha256(requirements_path) in digests


@pytest.mark.unit
def test_predicate_materials_include_every_pinned_tool_digest(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    materials = predicate["materials"]  # type: ignore[index]
    tool_uris = {m["uri"] for m in materials if str(m["uri"]).startswith("scanipy:tool/")}  # type: ignore[index]
    assert tool_uris == {
        "scanipy:tool/joern@v4.0.554",
        "scanipy:tool/codeql@v2.20.0",
    }
    tool_digests = {
        m["uri"]: m["digest"]["sha256"]  # type: ignore[index]
        for m in materials
        if str(m["uri"]).startswith("scanipy:tool/")  # type: ignore[index]
    }
    assert tool_digests["scanipy:tool/joern@v4.0.554"] == "c" * 64
    assert tool_digests["scanipy:tool/codeql@v2.20.0"] == "d" * 64


@pytest.mark.unit
def test_predicate_material_paths_are_repo_relative(tmp_path: Path) -> None:
    predicate = _build(tmp_path)
    materials = predicate["materials"]  # type: ignore[index]
    uris = {str(m["uri"]) for m in materials}  # type: ignore[index]
    assert "scanipy:workers/pins.json" in uris
    assert "scanipy:workers/snapshot/Dockerfile" in uris
    assert "scanipy:workers/snapshot/requirements.txt" in uris


# ---------------------------------------------------------------------------
# build_predicate — refuses to attest unpinned inputs (INV-2 upstream defence)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_predicate_refuses_pins_with_no_tools_section(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text("FROM debian:12-slim\n", encoding="utf-8")
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("fastapi==0.115.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no tools section"):
        build_predicate(
            image_digest=_IMAGE_DIGEST,
            build_commit=_BUILD_COMMIT,
            source_ref="refs/tags/v0.1.2",
            repository="scanipy/scanipy-v3.2",
            builder_id="https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@x",
            pins_path=pins_path,
            dockerfile_path=dockerfile_path,
            requirements_path=requirements_path,
            build_started_on="2026-07-15T00:00:00Z",
            build_finished_on="2026-07-15T00:05:00Z",
        )


@pytest.mark.unit
def test_build_predicate_refuses_a_tool_missing_sha256(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(
        json.dumps({"tools": {"joern": {"version": "v4.0.554", "sha256": ""}}}),
        encoding="utf-8",
    )
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text("FROM debian:12-slim\n", encoding="utf-8")
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text("fastapi==0.115.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="lacks version/sha256"):
        build_predicate(
            image_digest=_IMAGE_DIGEST,
            build_commit=_BUILD_COMMIT,
            source_ref="refs/tags/v0.1.2",
            repository="scanipy/scanipy-v3.2",
            builder_id="https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@x",
            pins_path=pins_path,
            dockerfile_path=dockerfile_path,
            requirements_path=requirements_path,
            build_started_on="2026-07-15T00:00:00Z",
            build_finished_on="2026-07-15T00:05:00Z",
        )


# ---------------------------------------------------------------------------
# CLI (main) — writes the predicate JSON file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_writes_predicate_and_returns_zero(tmp_path: Path) -> None:
    pins_path, dockerfile_path, requirements_path = _write_fixture_tree(tmp_path)
    out_path = tmp_path / "predicate.json"
    rc = main(
        [
            "--image-digest",
            _IMAGE_DIGEST,
            "--build-commit",
            _BUILD_COMMIT,
            "--source-ref",
            "refs/tags/v0.1.2",
            "--repository",
            "scanipy/scanipy-v3.2",
            "--builder-id",
            "https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@x",
            "--pins",
            str(pins_path),
            "--dockerfile",
            str(dockerfile_path),
            "--requirements",
            str(requirements_path),
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["invocation"]["parameters"]["image_digest"] == _IMAGE_DIGEST


@pytest.mark.unit
def test_cli_returns_one_on_missing_pins_file(tmp_path: Path) -> None:
    out_path = tmp_path / "predicate.json"
    rc = main(
        [
            "--image-digest",
            _IMAGE_DIGEST,
            "--build-commit",
            _BUILD_COMMIT,
            "--source-ref",
            "refs/tags/v0.1.2",
            "--repository",
            "scanipy/scanipy-v3.2",
            "--builder-id",
            "https://github.com/scanipy/scanipy-v3.2/.github/workflows/deploy.yml@x",
            "--pins",
            str(tmp_path / "nope.json"),
            "--dockerfile",
            str(tmp_path / "Dockerfile"),
            "--requirements",
            str(tmp_path / "requirements.txt"),
            "--out",
            str(out_path),
        ]
    )
    assert rc == 1
    assert not out_path.exists()

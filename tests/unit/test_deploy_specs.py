"""DEPLOY-family unit test specs — TST-AC-DEPLOY-02a..c.

Spec-first TDD stubs for CMP-DEPLOY-02 (worker container baseline). Production
and infra code do not exist yet, so each spec is registered-but-dormant: marked
xfail so the CI job exists and is collectable, and bodies `pytest.skip(...)`
until CMP-DEPLOY-02 is DONE.

The image digest IS the authoritative `env_digest` (AC-SNAP-05b / INV-2). These
specs verify the pinned-tool bundling contract and the publish-time digest gate.

Source-of-truth: WBS.md §2.4 / §4.2; DOC-CMP-DEPLOY-02.md §9 (verbatim ACs);
DOC-DEPLOY-DECISIONS.md (CLAR-DEPLOY-05, CLAR-DEPLOY-13).

When CMP-DEPLOY-02 is DONE, replace xfail markers + skips with real assertions.

PARTIAL STATUS (CMP-DEPLOY-02): AC-DEPLOY-02c (the hermetic publish gate,
`workers/build/verify_pins.py`) is implemented and green below. AC-DEPLOY-02a
and AC-DEPLOY-02b require a real ECR docker build (joern/codeql/git present at
pinned digests inside a built image; mutating a tool changes the image digest);
those two remain xfail+skip until a build substrate exists. Deep two-arm
coverage of the gate lives in `tests/unit/test_verify_pins.py`.
"""

import json
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-DEPLOY-02 (worker container baseline) not yet implemented",
    strict=False,
)
def test_deploy_02a_pinned_tools_present_at_pinned_digests() -> None:
    """Pinned analysis tools are present in the image at their pinned digests.

    Test id: TST-AC-DEPLOY-02a
    Maps to AC: AC-DEPLOY-02a — `joern`, `codeql`, `git` are present at pinned
        digests inside the image.
    Kind tag: [UNIT]
    Inputs: built `scanipy-snapshot` worker image; `workers/pins.json` pin set.
    Outputs: per-tool sha256 of `/opt/joern/bin/joern`, `/opt/codeql/codeql`,
        `/usr/bin/git` inside the image.
    Pass criteria: each tool binary's measured sha256 equals the corresponding
        `sha256` in `workers/pins.json`; all three tools are present.
    Frequency: every CI run.
    Hard gate?: yes — INV-2 producer (env_digest derives from pinned tools).
    """
    # TODO: build image; `docker run --rm <image> sha256sum /opt/joern/bin/joern
    #       /opt/codeql/codeql /usr/bin/git`; compare each against workers/pins.json
    #       when CMP-DEPLOY-02 is DONE.
    pytest.skip("CMP-DEPLOY-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-DEPLOY-02 (worker container baseline) not yet implemented",
    strict=False,
)
def test_deploy_02b_tool_mutation_changes_image_digest() -> None:
    """Mutating a bundled tool changes the image digest = authoritative env_digest.

    Test id: TST-AC-DEPLOY-02b
    Maps to AC: AC-DEPLOY-02b — Mutating any bundled tool changes the image
        digest, and that digest is the authoritative `env_digest` exposed to the
        snapshot worker.
    Kind tag: [UNIT]
    Inputs: image built at commit A (digest D1); `pins.json` with `joern` sha256
        mutated to a different value (digest D2).
    Outputs: two ECR image digests D1, D2.
    Pass criteria: `D1 != D2`; the digest is the value `CMP-SNAP-05` reads as
        `env_digest`. Cross-test with TST-AC-SNAP-05b.
    Frequency: every CI run.
    Hard gate?: yes — INV-2; a digest that does not change on tool change is a
        platform-wide invariant violation.
    """
    # TODO: build at commit A -> D1; bump joern sha256 in pins.json; rebuild -> D2;
    #       assert D1 != D2; cross-check env_digest exposure when CMP-DEPLOY-02 DONE.
    pytest.skip("CMP-DEPLOY-02 not implemented yet")


@pytest.mark.unit
def test_deploy_02c_build_refuses_unspecified_pinned_digest() -> None:
    """The image-build process refuses to publish if any pinned digest is unspecified.

    Test id: TST-AC-DEPLOY-02c
    Maps to AC: AC-DEPLOY-02c — The image-build process refuses to publish if
        any pinned digest is unspecified.
    Kind tag: [UNIT]
    Inputs: a `pins.json` with exactly one empty `sha256` field, fed to
        `workers/build/verify_pins.py`.
    Outputs: process exit code from `verify_pins.py`.
    Pass criteria: non-zero exit; the diagnostic names the missing pin field.
        (Integration counterpart: full GHA build fails before any `docker push`.)
    Frequency: every CI run.
    Hard gate?: yes — upstream defence for INV-2 (no env_digest from unpinned input).
    """
    from workers.build.verify_pins import check_pins, main

    digest = "0" * 64

    def _complete_pins() -> dict[str, object]:
        return {
            "schema_version": 1,
            "base_images": {
                "debian": {"tag": "12-slim", "sha256": digest},
                "python": {"tag": "3.11-slim-bookworm", "sha256": digest},
            },
            "tools": {
                "joern": {"version": "v4.0.0", "sha256": digest},
                "codeql": {"version": "v2.20.0", "sha256": digest},
                "git": {"version": "1:2.39.5", "sha256": digest},
            },
            "python_packages_lockfile_sha256": digest,
        }

    # A complete manifest passes the gate (no missing fields).
    assert check_pins(_complete_pins()) == []

    # Exactly one empty sha256 ⇒ the gate refuses and names the missing field.
    malformed = _complete_pins()
    malformed["base_images"]["python"]["sha256"] = ""  # type: ignore[index]
    missing = check_pins(malformed)
    assert missing == ["base_images.python.sha256"]

    # The CLI wrapper exits non-zero on the malformed manifest (build refused).
    bad_file = Path(__file__).resolve().parent / "_tmp_bad_pins.json"
    bad_file.write_text(json.dumps(malformed), encoding="utf-8")
    try:
        assert main([str(bad_file)]) == 1
    finally:
        bad_file.unlink()

    # The committed workers/pins.json must itself pass the gate (non-empty pins).
    repo_root = Path(__file__).resolve().parents[2]
    committed = json.loads((repo_root / "workers" / "pins.json").read_text(encoding="utf-8"))
    assert check_pins(committed) == []
    assert main([str(repo_root / "workers" / "pins.json")]) == 0


@pytest.mark.unit
def test_deploy_02b_registered_env_digest_history_is_authoritative() -> None:
    """The registered `env_digest` history is the authoritative production surface.

    Test id: TST-AC-DEPLOY-02b (hermetic half — CLAR-DEPLOY-22)
    Maps to AC: AC-DEPLOY-02b's second clause — "that digest is the authoritative
        `env_digest` exposed to the snapshot worker." The build-time half (image
        digest changes when a tool changes) stays xfail above pending a real ECR
        build; this half is always-on because the registration surface is a
        committed, hermetically-checkable file: `workers/env_digest_history.json`.
    Kind tag: [UNIT]
    Inputs: the committed `workers/env_digest_history.json`.
    Outputs: `check_registry` violation list; per-image active-entry count;
        presence/status of the four known-void v0.1.0/v0.1.1 digests.
    Pass criteria: zero schema/invariant violations; exactly one `active` entry
        per worker image; every active digest is well-formed
        (`^sha256:[0-9a-f]{64}$`) and not the all-zero placeholder; every
        non-active row carries a non-empty `note`; the four v0.1.0/v0.1.1
        digests are present with `status == "void"` (CLAR-DEPLOY-22 disposition
        — prose-only nomination / tainted direct-push provenance, never
        machine-registered as production `env_digest`).
    Frequency: every CI run.
    Hard gate?: yes — INV-2 producer; a malformed or under-specified registry
        cannot back CP-06's production-`env_digest` enforcement.
    """
    from workers.build.env_digest_registry import (
        PLACEHOLDER_DIGEST,
        VALID_IMAGES,
        check_registry,
    )

    repo_root = Path(__file__).resolve().parents[2]
    registry_path = repo_root / "workers" / "env_digest_history.json"
    doc = json.loads(registry_path.read_text(encoding="utf-8"))

    assert check_registry(doc) == []

    entries = doc["entries"]
    active_by_image: dict[str, int] = {}
    for entry in entries:
        assert entry["env_digest"] != PLACEHOLDER_DIGEST
        if entry["status"] == "active":
            active_by_image[entry["image"]] = active_by_image.get(entry["image"], 0) + 1
        else:
            assert entry["note"].strip(), f"non-active entry missing note: {entry}"
    for image in VALID_IMAGES:
        # Zero active is the legal pre-bootstrap state (CLAR-CP-06-02
        # record-and-warn); more than one is a hard schema violation already
        # caught by check_registry above. This asserts we are at most 1.
        assert active_by_image.get(image, 0) <= 1

    known_void = {
        (
            "scanipy-snapshot",
            "sha256:f3d51cf67de7b3a5f7acd72dd385ce1c6b1e44ecd3677ba0bb6fb58cd270d09f",
        ),
        (
            "scanipy-detector",
            "sha256:a2a25f8e40dc7ca68ea833a5991191fb290ffe04b62f1d044eeee221d11cde47",
        ),
        (
            "scanipy-snapshot",
            "sha256:65d2edd6a6eb5775ac0f0b107b1de0ba5a9e877b82ffacb30a7a01ebb4d1bd1e",
        ),
        (
            "scanipy-detector",
            "sha256:234d467a50af210065ab11c3191c92de8f13f5d76f894f73a8bce5d495d2b78d",
        ),
    }
    present = {(e["image"], e["env_digest"]): e["status"] for e in entries}
    for key in known_void:
        assert key in present, f"missing known CLAR-DEPLOY-22 void digest: {key}"
        assert present[key] == "void", f"{key} must be status=void (CLAR-DEPLOY-22 disposition)"

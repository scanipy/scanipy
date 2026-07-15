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


# CLAR-DEPLOY-21 (binding): AC-DEPLOY-02a and AC-DEPLOY-02b are DOCKER-BUILD-
# gated, not AWS-emulation-addressable — they assert tool digests inside a
# BUILT image and digest change on tool mutation. A fake registry's digests are
# meaningless, so these two tests MUST NOT be greened against moto ECR (that
# would be a fake-green). They keep their xfail+skip until a `docker buildx`
# CI harness exists (separate, non-AWS-emulation follow-up).
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


# CLAR-DEPLOY-21: docker-build-gated like 02a above — MUST NOT be greened
# against moto ECR (fake digests = fake-green).
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

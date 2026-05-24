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
"""

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
@pytest.mark.xfail(
    reason="CMP-DEPLOY-02 (worker container baseline) not yet implemented",
    strict=False,
)
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
    # TODO: import workers.build.verify_pins; run against a malformed pins.json with
    #       one empty sha256; assert returncode != 0 when CMP-DEPLOY-02 is DONE.
    pytest.skip("CMP-DEPLOY-02 not implemented yet")

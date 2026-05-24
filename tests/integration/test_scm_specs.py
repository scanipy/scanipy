"""SCM-family conformance / integration test specs — Phase 1 stubs.

Covers the [CONFORMANCE] and [INTEGRATION] acceptance criteria of the SCM
Integration subsystem (WBS §4.2):

  TST-AC-SCM-01c  reusable conformance-suite harness skeleton    [CONFORMANCE]
  TST-AC-SCM-02a  GitHub connector passes the conformance suite  [CONFORMANCE]
  TST-AC-SCM-03a  GL/BB/ADO each pass the conformance suite       [CONFORMANCE]
  TST-AC-SCM-03c  canary repo → identical commit resolution       [INTEGRATION]

Mirrors tests/unit/test_dsl_proofs.py: each spec is a registered stub marked
`xfail(strict=False)` while the implementation is absent. Closed marker set
(--strict-markers): [CONFORMANCE] and [INTEGRATION] both map to the `integration`
marker; the kind tag is recorded in the docstring only.

The conformance harness (SCM-01c) is written as a single parametrizable spec that
every concrete connector plugs into: SCM-02a (GitHub) and SCM-03a (GL/BB/ADO) are
invocations of that one harness against their connector instance.
"""

import asyncio
import hashlib
import hmac

import pytest

# ---------------------------------------------------------------------------
# Conformance harness contract (DOC-CMP-SCM-01 §3.3):
#   run_conformance_suite(connector, *, fixture_repo, canary_commit_sha)
#     -> ConformanceReport(provider, passed, failures, is_conformant)
# The suite drives the fixed operation sequence below (DOC §3.3) and asserts
# provider-neutral behaviour. The same harness is reused by every connector.
# ---------------------------------------------------------------------------

_CONFORMANCE_OPERATIONS = (
    "list_repos",
    "clone",
    "register_webhook",
    "verify_webhook_positive",
    "verify_webhook_negative",
    "get_default_branch",
    "resolve_commit",
)

_FIXTURE_SHA = "a" * 40  # a canary 40-hex SHA for the provider-neutral harness


def _make_stub_connector_cls():
    """Build a minimal, fully-conformant in-memory SCMConnector subclass.

    No network I/O: every method returns the documented shape. `sign_webhook`
    is the conformance harness's test hook (DOC §3.3) — an HMAC-SHA256 over the
    body so the positive/negative verify_webhook cases are distinguishable.
    """
    from datetime import UTC, datetime
    from pathlib import Path
    from typing import ClassVar

    from integrations.scm.base import (
        CloneMetadata,
        RepoRef,
        SCMConnector,
        WebhookSubscription,
    )

    class _StubConnector(SCMConnector):
        provider_id: ClassVar[str] = "stub"

        async def list_repos(self, *, org_or_workspace, page_size=100):
            yield RepoRef(
                provider="stub",
                owner=org_or_workspace,
                name="repo",
                clone_url="https://stub.example/r.git",
                default_branch="main",
            )

        async def clone(self, repo_ref, *, commit_sha, dest_dir: Path, shallow=True):
            return CloneMetadata(
                provider="stub",
                repo_ref=repo_ref,
                commit_sha=commit_sha,
                parent_shas=(),
                cloned_at=datetime.now(UTC),
                bytes_on_disk=0,
                shallow=shallow,
            )

        async def register_webhook(self, repo_ref, *, target_url, events, secret):
            return WebhookSubscription(
                provider="stub",
                repo_ref=repo_ref,
                webhook_id="wh_1",
                target_url=target_url,
                events=events,
                secret_ref="ref-to-encrypted-blob",  # pragma: allowlist secret
                created_at=datetime.now(UTC),
            )

        def verify_webhook(self, *, raw_body, headers, secret):
            expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(headers.get("X-Stub-Signature", ""), expected)

        async def get_default_branch(self, repo_ref):
            return "main"

        async def resolve_commit(self, repo_ref, *, ref):
            return _FIXTURE_SHA

        # Conformance test hook (DOC §3.3): sign a body under the connector scheme.
        def sign_webhook(self, *, raw_body, secret):
            sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            return {"X-Stub-Signature": sig}

    return _StubConnector


def _fixture_repo():
    from integrations.scm.base import RepoRef

    return RepoRef(
        provider="stub",
        owner="acme",
        name="repo",
        clone_url="https://stub.example/r.git",
        default_branch="main",
    )


# ---------------------------------------------------------------------------
# TST-AC-SCM-01c — reusable conformance-suite harness skeleton  [CONFORMANCE]
# CMP-SCM-01 · hard gate: yes. This is the parametrizable harness future
# connectors plug into; SCM-02a / SCM-03a invoke it.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_scm_01c_conformance_suite_exists_and_is_invokable() -> None:
    """run_conformance_suite exists and returns a ConformanceReport for a connector.

    Test id: TST-AC-SCM-01c-1
    Maps to AC: AC-SCM-01c
    Kind tag: [CONFORMANCE]
    Inputs: integrations.scm.conformance.run_conformance_suite; a stub SCMConnector,
      a fixture RepoRef, and a canary commit SHA.
    Outputs: a ConformanceReport with .provider, .passed, .failures, .is_conformant.
    Pass criteria: the harness is importable and callable against any SCMConnector
      subclass and yields a ConformanceReport (DOC-CMP-SCM-01 §3.3); the harness is
      declarative and provider-neutral (no GitHub-specific assertions).
    Frequency: every CI run
    Hard gate?: yes
    """
    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.conformance import ConformanceReport, run_conformance_suite

    connector = _make_stub_connector_cls()(
        SCMCredentials(provider="github", mode=SCMAuthMode.PAT, payload={"token": "t"})
    )
    report = asyncio.run(
        run_conformance_suite(
            connector,
            fixture_repo=_fixture_repo(),
            canary_commit_sha=_FIXTURE_SHA,
        )
    )
    assert isinstance(report, ConformanceReport)
    assert report.provider == "stub"
    assert report.is_conformant  # the fully-conformant stub yields no failures
    assert frozenset(report.passed) == frozenset(_CONFORMANCE_OPERATIONS)


def _broken_connector_cls(operation: str):
    """Subclass the conformant stub and break exactly `operation`."""
    base = _make_stub_connector_cls()

    class _Broken(base):  # type: ignore[valid-type, misc]
        if operation == "list_repos":

            async def list_repos(self, *, org_or_workspace, page_size=100):
                raise RuntimeError("list_repos boom")
                yield  # pragma: no cover — unreachable; keeps this an async generator

        elif operation == "clone":

            async def clone(self, repo_ref, *, commit_sha, dest_dir, shallow=True):
                raise RuntimeError("clone boom")

        elif operation == "register_webhook":

            async def register_webhook(self, repo_ref, *, target_url, events, secret):
                raise RuntimeError("register_webhook boom")

        elif operation == "verify_webhook_positive":

            def verify_webhook(self, *, raw_body, headers, secret):
                # Reject the genuine body too → the positive case fails.
                return False

        elif operation == "verify_webhook_negative":

            def verify_webhook(self, *, raw_body, headers, secret):
                # Accept everything → the tampered-body negative case fails.
                return True

        elif operation == "get_default_branch":

            async def get_default_branch(self, repo_ref):
                return ""  # empty → wrong shape

        elif operation == "resolve_commit":

            async def resolve_commit(self, repo_ref, *, ref):
                return "not-a-sha"

    return _Broken


@pytest.mark.integration
@pytest.mark.parametrize("operation", _CONFORMANCE_OPERATIONS)
def test_scm_01c_conformance_suite_covers_operation(operation: str) -> None:
    """The conformance suite drives each operation in the fixed sequence.

    Test id: TST-AC-SCM-01c-2..8 (one per operation in the fixed sequence)
    Maps to AC: AC-SCM-01c
    Kind tag: [CONFORMANCE]
    Inputs: the operation name from the DOC-CMP-SCM-01 §3.3 fixed sequence
      (list, clone, register_webhook, verify_webhook +/-, get_default_branch,
      resolve_commit); a connector that fails exactly this operation.
    Outputs: ConformanceReport.failures references the failing operation; a fully
      conformant connector yields .is_conformant == True.
    Pass criteria: a connector failing `operation` produces a ConformanceFailure naming
      that method; a conformant connector yields an empty failures tuple. Confirms the
      suite actually exercises every operation rather than passing vacuously.
    Frequency: every CI run
    Hard gate?: yes
    """
    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.conformance import run_conformance_suite

    creds = SCMCredentials(provider="github", mode=SCMAuthMode.PAT, payload={"token": "t"})
    connector = _broken_connector_cls(operation)(creds)
    report = asyncio.run(
        run_conformance_suite(
            connector,
            fixture_repo=_fixture_repo(),
            canary_commit_sha=_FIXTURE_SHA,
        )
    )

    failed_ops = {f.method for f in report.failures}
    assert operation in failed_ops  # the broken operation is flagged by name
    assert operation not in report.passed
    assert not report.is_conformant
    # Only the targeted operation fails; the suite exercises each independently.
    assert failed_ops == {operation}


# ---------------------------------------------------------------------------
# TST-AC-SCM-02a — GitHub connector passes the conformance suite  [CONFORMANCE]
# CMP-SCM-02 · hard gate: yes. Invocation of the SCM-01c harness on GitHubConnector.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(reason="CMP-SCM-02 (GitHub connector) not yet implemented", strict=False)
def test_scm_02a_github_passes_conformance_suite() -> None:
    """GitHubConnector passes the CMP-SCM-01 conformance suite with no failures.

    Test id: TST-AC-SCM-02a-1
    Maps to AC: AC-SCM-02a
    Kind tag: [CONFORMANCE]
    Inputs: a GitHubConnector(credentials) wired to a recorded/mocked GitHub API
      surface; the SCM-01c run_conformance_suite harness; a GitHub fixture RepoRef and
      canary commit SHA.
    Outputs: ConformanceReport for provider == "github".
    Pass criteria: report.is_conformant is True AND report.passed covers all six ABC
      methods (DOC-CMP-SCM-02 §6 — the conformance suite is the harness driving this).
    Frequency: every CI run
    Hard gate?: yes
    """
    # TODO: report = await run_conformance_suite(GitHubConnector(creds), ...)
    # assert report.is_conformant and report.provider == "github"
    pytest.skip("CMP-SCM-02 not implemented yet")


# ---------------------------------------------------------------------------
# TST-AC-SCM-03a — GL/BB/ADO each pass the conformance suite  [CONFORMANCE]
# CMP-SCM-03 · hard gate: yes. One invocation per connector class.
# ---------------------------------------------------------------------------

_SCM03_CONNECTORS = ("gitlab", "bitbucket", "azure-devops")


@pytest.mark.integration
@pytest.mark.xfail(reason="CMP-SCM-03 (GL/BB/ADO connectors) not yet implemented", strict=False)
@pytest.mark.parametrize("provider", _SCM03_CONNECTORS)
def test_scm_03a_connector_passes_conformance_suite(provider: str) -> None:
    """Each of GitLab/Bitbucket/Azure DevOps passes the conformance suite.

    Test id: TST-AC-SCM-03a-1..3 (one per connector)
    Maps to AC: AC-SCM-03a
    Kind tag: [CONFORMANCE]
    Inputs: the provider-specific connector (GitLabConnector / BitbucketConnector /
      AzureDevOpsConnector) wired to a recorded/mocked provider API surface; the SCM-01c
      harness; a provider fixture RepoRef and canary commit SHA.
    Outputs: ConformanceReport for the matching provider id.
    Pass criteria: report.is_conformant is True and report.provider == provider, for all
      three connectors (DOC-CMP-SCM-03 §2 — "passes the same conformance suite").
    Frequency: every CI run
    Hard gate?: yes
    """
    # TODO: connector = {gitlab: GitLabConnector, ...}[provider](creds)
    # report = await run_conformance_suite(connector, ...)
    # assert report.is_conformant and report.provider == provider
    pytest.skip("CMP-SCM-03 not implemented yet")


# ---------------------------------------------------------------------------
# TST-AC-SCM-03c — canary repo → identical commit resolution  [INTEGRATION]
# CMP-SCM-03 · hard gate: yes. Depends on CMP-CORP-CANARY-01 deliverable (the
# four-SCM mirror). Pass criterion IS specified (identical 40-hex SHA), so this
# is a dependency xfail, NOT a PASS-CRITERION-UNSPECIFIED skip.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-SCM-03 + CMP-CORP-CANARY-01 (four-SCM mirror) not yet available",
    strict=False,
)
def test_scm_03c_identical_commit_resolution_across_four_scms() -> None:
    """A canary repo mirrored to all four SCMs resolves a ref to the same 40-hex SHA.

    Test id: TST-AC-SCM-03c-1
    Maps to AC: AC-SCM-03c
    Kind tag: [INTEGRATION]
    Inputs: the CMP-CORP-CANARY-01 canary repo mirrored to GitHub, GitLab, Bitbucket,
      and Azure DevOps; one SCMConnector per provider; a shared canary ref.
    Outputs: four resolve_commit(repo, ref=<canary-ref>) results, one per connector.
    Pass criteria: all four results are byte-identical 40-hex commit SHAs
      (DOC-CMP-SCM-03 §4.2 / §8 — cross-SCM determinism precondition). Each result
      matches /^[0-9a-f]{40}$/ and len({sha_gh, sha_gl, sha_bb, sha_ado}) == 1.
    Frequency: nightly
    Hard gate?: yes
    """
    # TODO: shas = {p: await connectors[p].resolve_commit(repo, ref=ref) for p in PROVIDERS}
    # assert len(set(shas.values())) == 1
    # assert all(re.fullmatch(r"[0-9a-f]{40}", s) for s in shas.values())
    pytest.skip("CMP-SCM-03 / CMP-CORP-CANARY-01 not implemented yet")

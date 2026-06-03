"""SCM-family unit / negative / regression-unit test specs — Phase 1 stubs.

Covers the [UNIT], [NEGATIVE], and unit-flavoured [REGRESSION] acceptance
criteria of the SCM Integration subsystem (WBS §4.2):

  TST-AC-SCM-01a  ABC defines all six methods with typed signatures   [UNIT]
  TST-AC-SCM-01b  SCMCredentials round-trips four auth modes           [UNIT]
  TST-AC-SCM-02b  v2 retry/rate-limit/tiered-star byte-for-byte        [REGRESSION]
  TST-AC-SCM-02c  integrations/github shim re-export                   [REGRESSION]
  TST-AC-SCM-03b  per-provider webhook forgery rejection               [NEGATIVE]
  TST-AC-SCM-05a  exponential backoff + provider rate-limit honouring  [UNIT]

Mirrors tests/unit/test_dsl_proofs.py: each spec is a registered stub marked
`xfail(strict=False)` so the CI job exists and is exercisable while the
implementation is absent. Replace the `pytest.skip(...)` body with real
assertions when the owning CMP reaches DONE. Closed marker set
(--strict-markers): kind tags live in docstrings, never as markers.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from integrations.scm.base import RepoRef, SCMConnector

_GitRunner = Callable[[Sequence[str], Path], Awaitable[tuple[int, str, str]]]

# ---------------------------------------------------------------------------
# Mock CMP-CP-02 encrypt/decrypt envelope (T-CMP-SCM-01-04).
# The real key service lands with CMP-CP-02 (DOC-CMP-SCM-01 §6); until then a
# deterministic in-test mock exercises the round-trip property of AC-SCM-01b.
# It must round-trip SCMCredentials back to a structurally-equal instance,
# leaving the storage-set metadata fields (encrypted_at, key_version) as the
# caller left them.
# ---------------------------------------------------------------------------


class _MockCP02:
    """Deterministic mock of the CMP-CP-02 envelope encrypt/decrypt service."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def encrypt(self, cred: object) -> bytes:
        import pickle

        return pickle.dumps(cred)

    def decrypt(self, blob: bytes) -> object:
        import pickle

        return pickle.loads(blob)


# ---------------------------------------------------------------------------
# TST-AC-SCM-01a — ABC defines all six methods with typed signatures  [UNIT]
# CMP-SCM-01 · hard gate: yes. DOC-CMP-SCM-01 §3.2: "six methods. No more,
# no fewer." → six per-method sub-tests + one structural "exactly six" test.
# ---------------------------------------------------------------------------

_ABC_METHODS = (
    "list_repos",
    "clone",
    "register_webhook",
    "verify_webhook",
    "get_default_branch",
    "resolve_commit",
)


@pytest.mark.unit
@pytest.mark.parametrize("method_name", _ABC_METHODS)
def test_scm_01a_abc_declares_method(method_name: str) -> None:
    """Each of the six ABC methods is declared @abstractmethod with a docstring.

    Test id: TST-AC-SCM-01a-1..6 (one per parametrised method)
    Maps to AC: AC-SCM-01a
    Kind tag: [UNIT]
    Inputs: integrations.scm.base.SCMConnector class object; method_name fixture.
    Outputs: each name resolves to an abstract method carrying a contract docstring.
    Pass criteria: method_name in SCMConnector.__abstractmethods__ AND the attribute
      has a non-empty __doc__ documenting its contract (DOC-CMP-SCM-01 §3.2).
    Frequency: every CI run
    Hard gate?: yes
    """
    from integrations.scm.base import SCMConnector

    assert method_name in SCMConnector.__abstractmethods__
    assert getattr(SCMConnector, method_name).__doc__


@pytest.mark.unit
def test_scm_01a_abc_declares_exactly_six_methods() -> None:
    """The ABC declares exactly six abstract methods — no more, no fewer.

    Test id: TST-AC-SCM-01a-7
    Maps to AC: AC-SCM-01a
    Kind tag: [UNIT]
    Inputs: integrations.scm.base.SCMConnector.__abstractmethods__.
    Outputs: the abstract-method set equals the documented six.
    Pass criteria: frozenset(SCMConnector.__abstractmethods__) == frozenset(_ABC_METHODS)
      (DOC-CMP-SCM-01 §3.2 "six methods. No more, no fewer").
    Frequency: every CI run
    Hard gate?: yes
    """
    from integrations.scm.base import SCMConnector

    assert frozenset(SCMConnector.__abstractmethods__) == frozenset(_ABC_METHODS)


# ---------------------------------------------------------------------------
# TST-AC-SCM-01b — SCMCredentials round-trips four auth modes  [UNIT]
# CMP-SCM-01 · hard gate: yes. CMP-CP-02 mocked until available (DOC §6).
# Four modes (DOC-CMP-SCM-01 §4.1) → four round-trip sub-tests.
# ---------------------------------------------------------------------------

_AUTH_MODES = ("pat", "app_installation", "oauth", "ssh_key")


_MODE_PAYLOADS: dict[str, dict[str, str]] = {
    # Mode-specific required keys — DOC-CMP-SCM-01 §4.1. All values are strings.
    "pat": {"token": "ghp_exampletoken000"},
    "app_installation": {
        "app_id": "123456",
        "installation_id": "987654",
        # Opaque placeholder, not a real PEM (avoids the detect-private-key hook).
        "private_key_pem": "FAKE-APP-PRIVATE-KEY-PEM-PLACEHOLDER",  # pragma: allowlist secret
    },
    "oauth": {
        "access_token": "at_example",
        "refresh_token": "rt_example",
        "expires_at": "2026-06-01T00:00:00Z",
    },
    "ssh_key": {
        # Opaque placeholder, not a real PEM (avoids the detect-private-key hook).
        "private_key_pem": "FAKE-SSH-PRIVATE-KEY-PEM-PLACEHOLDER",  # pragma: allowlist secret
        "known_hosts": "github.com ssh-ed25519 AAAAC3...",
    },
}


@pytest.mark.unit
@pytest.mark.parametrize("mode", _AUTH_MODES)
def test_scm_01b_credentials_roundtrip(mode: str) -> None:
    """An SCMCredentials instance survives encrypt→persist→decrypt unchanged.

    Test id: TST-AC-SCM-01b-1..4 (one per auth mode)
    Maps to AC: AC-SCM-01b
    Kind tag: [UNIT]
    Inputs: SCMCredentials(provider, mode, payload) with the mode-specific payload
      keys from DOC-CMP-SCM-01 §4.1; a deterministic mock CMP-CP-02 encrypt/decrypt
      envelope (T-CMP-SCM-01-04) until the real key service lands.
    Outputs: a deserialised SCMCredentials structurally equal to the original.
    Pass criteria: decrypt(encrypt(cred)) == cred under dataclass structural equality,
      for all four modes; payload values are strings only (no binary).
    Frequency: every CI run
    Hard gate?: yes
    """
    from integrations.scm.base import SCMAuthMode, SCMCredentials

    payload = _MODE_PAYLOADS[mode]
    assert all(isinstance(v, str) for v in payload.values())  # payload is strings only

    cred = SCMCredentials(provider="github", mode=SCMAuthMode(mode), payload=payload)

    cp02 = _MockCP02()
    restored = cp02.decrypt(cp02.encrypt(cred))

    assert restored == cred  # frozen-dataclass structural equality across the round-trip
    assert isinstance(restored, SCMCredentials)
    assert restored.encrypted_at is None  # storage-set metadata untouched by the round-trip
    assert restored.key_version is None


# ---------------------------------------------------------------------------
# TST-AC-SCM-02b — v2 retry/rate-limit/tiered-star byte-for-byte  [REGRESSION]
# CMP-SCM-02 · hard gate: yes. BLOCKED on CLAR-SCM-01: the v2 baseline source
# (vendored copy / git-history snapshot / golden-fixture archive) is unpinned,
# so the byte-for-byte pass criterion cannot be authored. Skip with a
# PASS-CRITERION-UNSPECIFIED marker rather than guessing a baseline.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-SCM-02 byte-for-byte baseline blocked on CLAR-SCM-01", strict=False)
def test_scm_02b_retry_behaviour_matches_v2_baseline() -> None:
    """GitHub connector retry/backoff curve matches the v2 baseline byte-for-byte.

    Test id: TST-AC-SCM-02b-1
    Maps to AC: AC-SCM-02b
    Kind tag: [REGRESSION]
    Inputs: captured v2 retry/backoff trace (sleep sequence per simulated 429 /
      secondary-limit response) — baseline location UNPINNED.
    Outputs: replayed v3.2 GitHubConnector trace identical to the v2 baseline.
    Pass criteria: PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned —
      needs CLAR-SCM-01 (DOC-CMP-SCM-02 §10). Cannot author byte-for-byte oracle
      until the baseline (vendored / git-history / golden-fixture) is named.
    Frequency: every CI run
    Hard gate?: yes
    """
    # TODO: blocked — CLAR-SCM-01 must name the v2 baseline before this is authored.
    pytest.skip("PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned — needs CLAR-SCM-01")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-SCM-02 byte-for-byte baseline blocked on CLAR-SCM-01", strict=False)
def test_scm_02b_rate_limit_honouring_matches_v2_baseline() -> None:
    """GitHub connector rate-limit honouring matches the v2 baseline byte-for-byte.

    Test id: TST-AC-SCM-02b-2
    Maps to AC: AC-SCM-02b
    Kind tag: [REGRESSION]
    Inputs: captured v2 primary + secondary rate-limit handling behaviour —
      baseline location UNPINNED.
    Outputs: replayed v3.2 behaviour identical to the v2 baseline.
    Pass criteria: PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned —
      needs CLAR-SCM-01 (DOC-CMP-SCM-02 §10).
    Frequency: every CI run
    Hard gate?: yes
    """
    # TODO: blocked — CLAR-SCM-01 must name the v2 baseline before this is authored.
    pytest.skip("PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned — needs CLAR-SCM-01")


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-SCM-02 byte-for-byte baseline blocked on CLAR-SCM-01", strict=False)
def test_scm_02b_tiered_star_listing_matches_v2_baseline() -> None:
    """GitHub tiered-star repo discovery matches the v2 baseline byte-for-byte.

    Test id: TST-AC-SCM-02b-3
    Maps to AC: AC-SCM-02b
    Kind tag: [REGRESSION]
    Inputs: captured v2 list_repos_tiered_star result shaping / star-tier ordering
      (DOC-CMP-SCM-02 §3.3) — baseline location UNPINNED.
    Outputs: replayed v3.2 tiered-star output identical to the v2 baseline.
    Pass criteria: PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned —
      needs CLAR-SCM-01 (DOC-CMP-SCM-02 §10).
    Frequency: every CI run
    Hard gate?: yes
    """
    # TODO: blocked — CLAR-SCM-01 must name the v2 baseline before this is authored.
    pytest.skip("PASS-CRITERION-UNSPECIFIED: v2 baseline location not pinned — needs CLAR-SCM-01")


# ---------------------------------------------------------------------------
# TST-AC-SCM-02c — integrations/github shim re-export  [REGRESSION]
# CMP-SCM-02 · hard gate: yes. NOT blocked by CLAR-SCM-01 — the shim's
# caller-visible contract is fully specified in DOC-CMP-SCM-02 §3.5.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scm_02c_shim_exports_search_repositories() -> None:
    """integrations.github.search_repositories imports as a caller-transparent shim.

    Test id: TST-AC-SCM-02c-1
    Maps to AC: AC-SCM-02c
    Kind tag: [REGRESSION]
    Inputs: `from integrations.github import search_repositories` (the v2 public symbol).
    Outputs: a callable resolved at the legacy import path.
    Pass criteria: the import succeeds and search_repositories is callable; the symbol
      lives at integrations/github/__init__.py (DOC-CMP-SCM-02 §3.5).
    Frequency: every CI run
    Hard gate?: yes
    """
    import integrations.github as github_shim
    from integrations.github import search_repositories

    assert callable(search_repositories)
    # The symbol resolves at the legacy import path (integrations/github/__init__.py).
    assert search_repositories.__module__ == "integrations.github"
    assert github_shim.search_repositories is search_repositories


@pytest.mark.unit
def test_scm_02c_shim_signature_unchanged() -> None:
    """The shim preserves the v2 public signature with no caller-visible change.

    Test id: TST-AC-SCM-02c-2
    Maps to AC: AC-SCM-02c
    Kind tag: [REGRESSION]
    Inputs: inspect.signature(integrations.github.search_repositories).
    Outputs: the call signature a v2 caller relies on (e.g. `scanipy --query …`).
    Pass criteria: signature matches the v2 public contract; a v2 invocation observes
      no behavioural difference (DOC-CMP-SCM-02 §3.5 — delegates to
      GitHubConnector.list_repos_tiered_star, signature unchanged).
    Frequency: every CI run
    Hard gate?: yes

    Note: the *exact* v2 parameter list is part of the CLAR-SCM-01 baseline
    capture (see TST-AC-SCM-02b, BLOCKED). DOC §3.5 specifies only the existence
    and shape contract, so this test asserts the shape — a leading positional
    `query` parameter and delegation to the tiered-star helper — not a captured
    byte-for-byte signature. The byte-for-byte signature check lands with
    TST-AC-SCM-02b once CLAR-SCM-01 names the baseline.
    """
    import inspect

    from integrations.github import search_repositories

    sig = inspect.signature(search_repositories)
    params = list(sig.parameters.values())
    # The v2 public contract takes the search query as its leading argument.
    assert params, "search_repositories must accept at least the query argument"
    assert params[0].name == "query"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    # Delegates to the tiered-star helper (DOC §3.5): the helper exists and is an
    # async generator (async def + yield, matching the ABC's list_repos shape).
    from integrations.scm.github import GitHubConnector

    assert inspect.isasyncgenfunction(GitHubConnector.list_repos_tiered_star)


# ---------------------------------------------------------------------------
# TST-AC-SCM-03b — per-provider webhook forgery rejection  [NEGATIVE]
# CMP-SCM-03 · hard gate: yes. Three providers (GL/BB/ADO); GitHub is SCM-02.
# DOC-CMP-SCM-03 §3.3 / §7: a tampered byte → verify_webhook returns False.
# ---------------------------------------------------------------------------

_SCM03_PROVIDERS = ("gitlab", "bitbucket", "azure-devops")


# --- SCM-03 test scaffolding --------------------------------------------------
# A no-op async transport: CMP-SCM-03's verify_webhook is a pure, offline
# cryptographic predicate and performs no I/O, so the constructor's required
# `transport` seam is satisfied with a stub that is never called.


class _NullTransport:
    """Async HTTP transport stub for tests that never touch the network."""

    async def request(self, method, url, *, headers=None, params=None, json=None):
        raise AssertionError("transport must not be called by verify_webhook")


def _scm03_connector(provider: str):
    """Instantiate the CMP-SCM-03 connector for `provider` with a PAT envelope."""
    from integrations.scm.ado import AzureDevOpsConnector
    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.bitbucket import BitbucketConnector
    from integrations.scm.gitlab import GitLabConnector

    creds = SCMCredentials(provider=provider, mode=SCMAuthMode.PAT, payload={"token": "t"})
    transport = _NullTransport()
    if provider == "gitlab":
        return GitLabConnector(creds, transport=transport)
    if provider == "bitbucket":
        return BitbucketConnector(creds, transport=transport)
    if provider == "azure-devops":
        return AzureDevOpsConnector(creds, organization="acme", transport=transport)
    raise AssertionError(f"unhandled SCM-03 provider: {provider}")


@pytest.mark.unit
@pytest.mark.parametrize("provider", _SCM03_PROVIDERS)
def test_scm_03b_forged_webhook_rejected(provider: str) -> None:
    """A forged/tampered webhook makes verify_webhook return False (positive sanity first).

    Test id: TST-AC-SCM-03b-1..3 (one per provider)
    Maps to AC: AC-SCM-03b
    Kind tag: [NEGATIVE]
    Inputs: a genuine payload + valid provider signature (via the connector's
      `sign_webhook` test hook), then a forgery. Per-provider scheme from
      DOC-CMP-SCM-03 §3.3:
        - GitLab: `X-Gitlab-Token` plain shared-secret equality. The token is
          *body-independent*, so the honest forgery is a wrong/absent token —
          tampering a body byte alone is undetectable by GitLab's native scheme
          and asserting otherwise would misrepresent the provider guarantee.
        - Azure DevOps: `Authorization: Basic base64(":<secret>")` — the secret
          rides as the HTTP Basic password, no body HMAC (CLAR-SCM-02 RESOLVED
          2026-06-03). *Body-independent*, like GitLab: the honest forgery is a
          wrong/absent Basic credential, not a tampered body byte.
        - Bitbucket: `X-Hub-Signature` = sha256=HMAC-SHA256(secret, body). The
          forgery tampers one body byte while keeping the original signature.
    Outputs: verify_webhook(...) -> bool.
    Pass criteria: the genuine delivery returns True; the forgery returns False;
      no exception is raised (DOC-CMP-SCM-03 §7 — predicate, not fault path).
    Frequency: every CI run
    Hard gate?: yes
    """
    connector = _scm03_connector(provider)
    secret = "shared-webhook-secret"  # pragma: allowlist secret
    body = b'{"event":"push","ref":"refs/heads/main"}'

    # Positive sanity: a genuine signature/token verifies True.
    genuine_headers = connector.sign_webhook(raw_body=body, secret=secret)
    assert connector.verify_webhook(raw_body=body, headers=genuine_headers, secret=secret) is True

    if provider == "gitlab":
        # GitLab's token is body-independent — forge the token, not the body.
        forged_headers = {"X-Gitlab-Token": "wrong-token"}
        assert (
            connector.verify_webhook(raw_body=body, headers=forged_headers, secret=secret) is False
        )
        # A genuine token but missing header also fails.
        assert connector.verify_webhook(raw_body=body, headers={}, secret=secret) is False
    elif provider == "azure-devops":
        # ADO's Basic-auth credential is body-independent (no body HMAC). The
        # genuine header must verify even against a *tampered* body — proving the
        # predicate checks the credential, not the body. Forge the credential.
        # Anti-vacuity: sign_webhook actually emits a Basic header.
        auth = genuine_headers.get("Authorization", "")
        assert auth.startswith("Basic ")
        tampered_body = b'{"event":"push","ref":"refs/heads/MAIN"}'
        assert (
            connector.verify_webhook(raw_body=tampered_body, headers=genuine_headers, secret=secret)
            is True
        )
        # Negative controls: a Basic header echoing the WRONG password → False.
        import base64 as _b64

        wrong = "Basic " + _b64.b64encode(b":wrong-secret").decode("ascii")
        assert (
            connector.verify_webhook(raw_body=body, headers={"Authorization": wrong}, secret=secret)
            is False
        )
        # Absent Authorization header → False (no exception).
        assert connector.verify_webhook(raw_body=body, headers={}, secret=secret) is False
    else:
        # Bitbucket HMAC scheme: tamper one body byte, keep the signature over
        # the original.
        tampered_body = b'{"event":"push","ref":"refs/heads/MAIN"}'
        assert (
            connector.verify_webhook(raw_body=tampered_body, headers=genuine_headers, secret=secret)
            is False
        )
        # A missing/malformed signature header also fails (no exception).
        assert connector.verify_webhook(raw_body=body, headers={}, secret=secret) is False
        assert (
            connector.verify_webhook(
                raw_body=body, headers={"X-Hub-Signature": "garbage"}, secret=secret
            )
            is False
        )


# ---------------------------------------------------------------------------
# TST-AC-SCM-03a — per-provider SCMConnector conformance suite  [CONFORMANCE]
# CMP-SCM-03 · hard gate: yes. Authored (gap #242 closed): each connector is
# driven through the shared SCM-01c run_conformance_suite harness over a
# queue-mocked async transport + a fake git runner (no network / subprocess I/O).
# Mirrors the integration-marked driver in tests/integration/test_scm_specs.py so
# each test module is independently collectable (the unit run measures coverage).
#
# The mock transport pops one response per request regardless of method/URL, so
# only the count, order, and JSON shape of the queued responses matter. Every
# response is a non-rate-limited 200 so `with_retry` never pops an extra entry.
# The suite issues exactly five transport calls per provider — list_repos (GET),
# find-hooks/subscriptions (GET), register (POST), get_default_branch (GET),
# resolve_commit (GET) — and drives `clone` purely through the git runner.
# ---------------------------------------------------------------------------

_SCM03A_OPERATIONS = (
    "list_repos",
    "clone",
    "register_webhook",
    "verify_webhook_positive",
    "verify_webhook_negative",
    "get_default_branch",
    "resolve_commit",
)
_SCM03A_SHA = "a" * 40  # the 40-hex SHA every connector's resolve_commit must return


class _ConfResp:
    """An HTTPResponse-shaped stub (status_code, headers, text, json())."""

    def __init__(self, body: Any, *, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = ""
        self._body = body

    def json(self) -> Any:
        return self._body


class _ConfTransport:
    """Queue-based async transport: pops one queued response per request."""

    def __init__(self, responses: Sequence[_ConfResp]) -> None:
        self._queue = list(responses)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,
    ) -> _ConfResp:
        return self._queue.pop(0)


def _conf_git_runner() -> _GitRunner:
    """Fake GitRunner: rev-parse → the canary SHA; rev-list → SHA+parent; else ok."""

    async def runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
        cmd = argv[0]
        if cmd == "rev-parse":
            return (0, f"{_SCM03A_SHA}\n", "")
        if cmd == "rev-list":
            return (0, f"{_SCM03A_SHA} {'b' * 40}\n", "")
        return (0, "", "")

    return runner


def _conf_responses(provider: str) -> list[_ConfResp]:
    """The five queued responses (in suite order) for `provider`."""
    if provider == "gitlab":
        return [
            _ConfResp([]),  # list_repos
            _ConfResp([]),  # _find_existing_hook
            _ConfResp({"id": 1}),  # register_webhook POST
            _ConfResp({"default_branch": "main"}),  # get_default_branch
            _ConfResp({"id": _SCM03A_SHA}),  # resolve_commit (.id)
        ]
    if provider == "bitbucket":
        return [
            _ConfResp({"values": [], "next": None}),  # list_repos
            _ConfResp({"values": []}),  # _find_existing_hook
            _ConfResp({"uuid": "{abc}"}),  # register_webhook POST
            _ConfResp({"mainbranch": {"name": "main"}}),  # get_default_branch
            _ConfResp({"hash": _SCM03A_SHA}),  # resolve_commit (.hash)
        ]
    if provider == "azure-devops":
        return [
            _ConfResp({"value": []}),  # list_repos
            _ConfResp({"value": []}),  # _find_existing_subscription
            _ConfResp({"id": "sub-1"}),  # register_webhook POST
            _ConfResp({"defaultBranch": "refs/heads/main"}),  # get_default_branch
            _ConfResp({"value": [{"commitId": _SCM03A_SHA}]}),  # resolve_commit
        ]
    raise AssertionError(f"unhandled SCM-03a provider: {provider}")


def _conf_connector(provider: str, transport: _ConfTransport) -> SCMConnector:
    """Build the concrete connector for `provider` over `transport` + fake git."""
    from integrations.scm.ado import AzureDevOpsConnector
    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.bitbucket import BitbucketConnector
    from integrations.scm.gitlab import GitLabConnector

    creds = SCMCredentials(provider=provider, mode=SCMAuthMode.PAT, payload={"token": "t"})
    git_runner = _conf_git_runner()
    if provider == "gitlab":
        return GitLabConnector(creds, transport=transport, git_runner=git_runner)
    if provider == "bitbucket":
        return BitbucketConnector(creds, transport=transport, git_runner=git_runner)
    if provider == "azure-devops":
        return AzureDevOpsConnector(
            creds, organization="acme", transport=transport, git_runner=git_runner
        )
    raise AssertionError(f"unhandled SCM-03a provider: {provider}")


def _conf_repo(provider: str) -> RepoRef:
    """A provider-matching fixture RepoRef the suite drives the connector with."""
    owner = "acme/proj" if provider == "azure-devops" else "acme"
    return RepoRef(
        provider=provider,
        owner=owner,
        name="widgets",
        clone_url="https://scm.example/acme/widgets.git",
        default_branch="main",
    )


@pytest.mark.unit
@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_scm_03a_connector_conformance(provider: str) -> None:
    """Each connector passes the shared SCMConnector conformance suite.

    Test id: TST-AC-SCM-03a-1..3 (one per provider)
    Maps to AC: AC-SCM-03a
    Kind tag: [CONFORMANCE]
    Inputs: a GitLab / Bitbucket / Azure-DevOps connector + the shared
      run_conformance_suite harness driven by a queue-mocked transport + fake git.
    Outputs: is_conformant verdict per provider.
    Pass criteria: report.is_conformant is True and report.provider == provider,
      with all six ABC methods exercised (DOC-CMP-SCM-03 §2 — "passes the same
      conformance suite"). Gap #242 closed.
    Frequency: every CI run
    Hard gate?: yes
    """
    import asyncio

    from integrations.scm.conformance import run_conformance_suite

    transport = _ConfTransport(_conf_responses(provider))
    connector = _conf_connector(provider, transport)
    report = asyncio.run(
        run_conformance_suite(
            connector,
            fixture_repo=_conf_repo(provider),
            canary_commit_sha=_SCM03A_SHA,
        )
    )
    assert report.provider == provider
    assert report.is_conformant, report.failures
    assert frozenset(report.passed) == frozenset(_SCM03A_OPERATIONS)


# ---------------------------------------------------------------------------
# TST-AC-SCM-05a — backoff + provider rate-limit honouring  [UNIT]
# CMP-SCM-05 · hard gate: yes. DOC-CMP-SCM-05 §9 enumerates 10 sub-cases →
# ten parametrised sub-tests.
# ---------------------------------------------------------------------------

_SCM05_CASES = (
    "curve_exponential_full_jitter_max_attempts",
    "retry_after_seconds_overrides_curve",
    "retry_after_http_date_overrides_curve",
    "github_primary_ratelimit_remaining_zero_reset",
    "github_secondary_ratelimit_body_marker",
    "gitlab_429_retry_after",
    "bitbucket_429_abuse_vs_primary",
    "azure_devops_429_max_retry_after_and_delay",
    "total_deadline_exhaustion_raises_ratelimit",
    "non_retryable_exceptions_propagate",
)


# --- SCM-05a test scaffolding -------------------------------------------------
# A deterministic, sleep-free harness: a fake response with a case-insensitive
# header map, and a recorder that runs `with_retry` under asyncio while
# capturing the realised sleep sequence (the decorator's `_sleep` test seam).


class _FakeResponse:
    """Minimal httpx.Response-shaped stub for the classify_* hooks."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


def _run_retry(*, policy, classify, responses, jitter_seed: int = 0):
    """Drive with_retry over a scripted response/exception sequence.

    `responses` is a list whose items are either _FakeResponse instances (the
    decorated call returns them) or Exception instances (the decorated call
    raises them). The final scripted item is repeated if attempts outlast it.
    Returns (outcome, sleeps) where outcome is the return value or the raised
    exception, and sleeps is the captured sleep sequence (seam, no real wait).
    """
    import asyncio
    import random

    from integrations.scm._http import with_retry

    sleeps: list[float] = []

    async def _record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    script = list(responses)
    state = {"i": 0}

    async def _call():
        idx = min(state["i"], len(script) - 1)
        state["i"] += 1
        item = script[idx]
        if isinstance(item, Exception):
            raise item
        return item

    decorated = with_retry(
        policy=policy,
        classify=classify,
        _sleep=_record_sleep,
        _rng=random.Random(jitter_seed),
    )(_call)

    try:
        outcome: object = asyncio.run(decorated())
    except Exception as exc:  # the test inspects the terminal error object
        outcome = exc
    return outcome, sleeps


@pytest.mark.unit
@pytest.mark.parametrize("case", _SCM05_CASES)
def test_scm_05a_retry_behaviour(case: str) -> None:
    """with_retry honours the backoff curve and per-provider rate-limit semantics.

    Test id: TST-AC-SCM-05a-1..10 (one per DOC-CMP-SCM-05 §9 sub-case)
    Maps to AC: AC-SCM-05a
    Kind tag: [UNIT]
    Inputs: simulated provider responses (429 / secondary / Retry-After seconds &
      HTTP-date / X-RateLimit-* / 5xx / auth) fed to the with_retry decorator with the
      matching classify_* hook (DOC-CMP-SCM-05 §3.2-§3.4). Deterministic jitter source.
    Outputs: the realised sleep sequence and terminal outcome (return / raise) of the
      decorated call.
    Pass criteria: per case —
      curve: base[i]=min(initial*factor**i, max), full-jitter bounded, max_attempts honoured;
      retry_after_*: provider-honoured wait overrides the curve;
      github_primary: X-RateLimit-Remaining:0 + X-RateLimit-Reset honoured;
      github_secondary: body marker triggers secondary backoff;
      gitlab/bitbucket/ado: provider Retry-After / X-RateLimit-Delay (max wins) honoured;
      total_deadline_exhaustion: raises SCMRateLimitError;
      non_retryable: SCMAuthError / SCMNotFoundError propagate without retry.
    Frequency: every CI run
    Hard gate?: yes
    """
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    from integrations.scm._http import (
        JitterMode,
        RetryPolicy,
        classify_azure_devops,
        classify_bitbucket,
        classify_github,
        classify_gitlab,
    )
    from integrations.scm.base import (
        SCMAuthError,
        SCMNotFoundError,
        SCMRateLimitError,
        SCMTransientError,
    )

    if case == "curve_exponential_full_jitter_max_attempts":
        # All attempts rate-limited (no Retry-After) → curve drives the sleeps;
        # full jitter keeps each sleep in [0, base[i]] with base growing
        # exponentially and clamped at max_backoff_s. max_attempts honoured
        # (one fewer sleep than attempts), terminal error is SCMRateLimitError.
        policy = RetryPolicy(
            initial_backoff_s=1.0,
            max_backoff_s=10.0,
            backoff_factor=2.0,
            jitter=JitterMode.FULL,
            max_attempts=5,
            honor_retry_after=True,
        )
        limited = _FakeResponse(status_code=429)  # gitlab-style, no Retry-After
        outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
        assert isinstance(outcome, SCMRateLimitError)
        assert len(sleeps) == policy.max_attempts - 1  # 4 sleeps for 5 attempts
        bases = [min(1.0 * 2.0**i, 10.0) for i in range(len(sleeps))]
        assert bases == [1.0, 2.0, 4.0, 8.0]  # exponential, clamped at 10
        for slept, base in zip(sleeps, bases, strict=True):
            assert 0.0 <= slept <= base  # full jitter is bounded by the curve

    elif case == "retry_after_seconds_overrides_curve":
        # Retry-After: 7 (delta-seconds) overrides the jittered curve exactly.
        policy = RetryPolicy(max_attempts=3, jitter=JitterMode.FULL, honor_retry_after=True)
        limited = _FakeResponse(status_code=429, headers={"Retry-After": "7"})
        outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
        assert isinstance(outcome, SCMRateLimitError)
        assert sleeps == [7.0, 7.0]  # provider wait wins over the curve, every retry

    elif case == "retry_after_http_date_overrides_curve":
        # Retry-After as an HTTP-date ~30s in the future overrides the curve.
        future = datetime.now(UTC) + timedelta(seconds=30)
        limited = _FakeResponse(
            status_code=429, headers={"Retry-After": format_datetime(future, usegmt=True)}
        )
        policy = RetryPolicy(max_attempts=2, honor_retry_after=True)
        outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
        assert isinstance(outcome, SCMRateLimitError)
        assert len(sleeps) == 1
        assert 20.0 <= sleeps[0] <= 31.0  # ~30s honoured (slack for parse/now drift)

    elif case == "github_primary_ratelimit_remaining_zero_reset":
        # 403 + X-RateLimit-Remaining:0 + X-RateLimit-Reset (epoch) → primary
        # limit; reset honoured as the wait. Recovers on the second response.
        reset = datetime.now(UTC).timestamp() + 12.0
        limited = _FakeResponse(
            status_code=403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
        )
        ok = _FakeResponse(status_code=200)
        policy = RetryPolicy(max_attempts=4, honor_retry_after=True)
        outcome, sleeps = _run_retry(
            policy=policy, classify=classify_github, responses=[limited, ok]
        )
        assert isinstance(outcome, _FakeResponse) and outcome.status_code == 200
        assert len(sleeps) == 1
        assert 6.0 <= sleeps[0] <= 13.0  # X-RateLimit-Reset (~12s) honoured

    elif case == "github_secondary_ratelimit_body_marker":
        # 403 with a secondary/abuse body marker → secondary class, Retry-After
        # honoured, on_attempt reason carries the secondary tag.
        limited = _FakeResponse(
            status_code=403,
            headers={"Retry-After": "5"},
            text="You have exceeded a secondary rate limit. Please wait.",
        )
        ok = _FakeResponse(status_code=200)
        verdict = classify_github(limited)
        assert verdict.is_rate_limited and verdict.is_secondary
        reasons: list[str] = []
        policy = RetryPolicy(max_attempts=3, honor_retry_after=True, honor_secondary=True)
        from integrations.scm._http import with_retry

        sleeps: list[float] = []

        async def _seam(s: float) -> None:
            sleeps.append(s)

        script = [limited, ok]
        idx = {"i": 0}

        async def _call() -> _FakeResponse:
            i = min(idx["i"], len(script) - 1)
            idx["i"] += 1
            return script[i]

        import asyncio

        decorated = with_retry(
            policy=policy,
            classify=classify_github,
            on_attempt=lambda _i, _s, reason: reasons.append(reason),
            _sleep=_seam,
        )(_call)
        result = asyncio.run(decorated())
        assert result.status_code == 200
        assert sleeps == [5.0]  # secondary Retry-After honoured
        assert reasons == ["rate-limited-secondary"]

    elif case == "gitlab_429_retry_after":
        # GitLab 429 + Retry-After:3; no secondary class exists for GitLab.
        limited = _FakeResponse(status_code=429, headers={"Retry-After": "3"})
        v = classify_gitlab(limited)
        assert v.is_rate_limited and v.retry_after_s == 3.0 and v.is_secondary is False
        ok = _FakeResponse(status_code=200)
        policy = RetryPolicy(max_attempts=3, honor_retry_after=True)
        outcome, sleeps = _run_retry(
            policy=policy, classify=classify_gitlab, responses=[limited, ok]
        )
        assert isinstance(outcome, _FakeResponse) and outcome.status_code == 200
        assert sleeps == [3.0]

    elif case == "bitbucket_429_abuse_vs_primary":
        # Bitbucket differentiates abuse (secondary) from primary by header.
        primary = _FakeResponse(status_code=429, headers={"Retry-After": "2"})
        abuse = _FakeResponse(
            status_code=429,
            headers={"Retry-After": "2", "X-Bitbucket-Type": "abuse"},
        )
        v_primary = classify_bitbucket(primary)
        v_abuse = classify_bitbucket(abuse)
        assert v_primary.is_rate_limited and v_primary.is_secondary is False
        assert v_abuse.is_rate_limited and v_abuse.is_secondary is True
        ok = _FakeResponse(status_code=200)
        policy = RetryPolicy(max_attempts=3, honor_retry_after=True)
        outcome, sleeps = _run_retry(
            policy=policy, classify=classify_bitbucket, responses=[abuse, ok]
        )
        assert isinstance(outcome, _FakeResponse) and outcome.status_code == 200
        assert sleeps == [2.0]

    elif case == "azure_devops_429_max_retry_after_and_delay":
        # ADO 429 with both Retry-After and X-RateLimit-Delay → max wins.
        limited = _FakeResponse(
            status_code=429,
            headers={"Retry-After": "4", "X-RateLimit-Delay": "9"},
        )
        v = classify_azure_devops(limited)
        assert v.is_rate_limited and v.retry_after_s == 9.0  # max(4, 9)
        ok = _FakeResponse(status_code=200)
        policy = RetryPolicy(max_attempts=3, honor_retry_after=True)
        outcome, sleeps = _run_retry(
            policy=policy, classify=classify_azure_devops, responses=[limited, ok]
        )
        assert isinstance(outcome, _FakeResponse) and outcome.status_code == 200
        assert sleeps == [9.0]

    elif case == "total_deadline_exhaustion_raises_ratelimit":
        # A short total_deadline_s is breached mid-curve → SCMRateLimitError,
        # raised before max_attempts is reached.
        policy = RetryPolicy(
            initial_backoff_s=5.0,
            max_backoff_s=60.0,
            backoff_factor=2.0,
            jitter=JitterMode.NONE,
            max_attempts=6,
            honor_retry_after=True,
            total_deadline_s=8.0,  # first sleep is 5s; second would breach 8s
        )
        limited = _FakeResponse(status_code=429)  # no Retry-After → curve drives
        outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
        assert isinstance(outcome, SCMRateLimitError)
        assert sleeps == [5.0]  # one sleep landed; the next would exceed the deadline

    elif case == "non_retryable_exceptions_propagate":
        # SCMAuthError and SCMNotFoundError propagate with zero retries; a
        # transient error, by contrast, is retried and re-raised after the budget.
        policy = RetryPolicy(max_attempts=4, jitter=JitterMode.NONE)
        for exc_type in (SCMAuthError, SCMNotFoundError):
            outcome, sleeps = _run_retry(
                policy=policy, classify=classify_github, responses=[exc_type("nope")]
            )
            assert isinstance(outcome, exc_type)
            assert sleeps == []  # never slept; never retried
        # Transient is retryable and re-raised (NOT mapped to SCMRateLimitError).
        outcome, sleeps = _run_retry(
            policy=policy,
            classify=classify_github,
            responses=[SCMTransientError("5xx")],
        )
        assert isinstance(outcome, SCMTransientError)
        assert len(sleeps) == policy.max_attempts - 1

    else:  # pragma: no cover — guards against an unhandled case name
        raise AssertionError(f"unhandled SCM-05a case: {case}")


# ---------------------------------------------------------------------------
# TST-AC-SCM-05a supplementary unit coverage — RetryPolicy value type, the
# per-provider default policies, classify_* non-rate-limited paths, the
# honor_retry_after=False branch, and the on_attempt observability hook. These
# close the branch-coverage of integrations/scm/_http.py beyond the ten §9
# enumerated cases (still AC-SCM-05a; not new scope).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scm_05a_retrypolicy_defaults_and_immutability() -> None:
    """RetryPolicy carries the DOC §3.1 defaults and is a frozen value type."""
    import dataclasses

    from integrations.scm._http import JitterMode, RetryPolicy

    p = RetryPolicy()
    assert p.initial_backoff_s == 1.0
    assert p.max_backoff_s == 60.0
    assert p.backoff_factor == 2.0
    assert p.jitter is JitterMode.FULL
    assert p.max_attempts == 6
    assert p.honor_429 and p.honor_secondary and p.honor_retry_after
    assert p.total_deadline_s is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.max_attempts = 9  # type: ignore[misc]


@pytest.mark.unit
def test_scm_05a_provider_default_policies() -> None:
    """Per-provider defaults (DOC §3.2): GitLab/ADO drop the secondary class."""
    from integrations.scm._http import (
        AZURE_DEVOPS_DEFAULT,
        BITBUCKET_DEFAULT,
        GITHUB_DEFAULT,
        GITLAB_DEFAULT,
    )

    assert GITHUB_DEFAULT.honor_secondary is True
    assert BITBUCKET_DEFAULT.honor_secondary is True
    assert GITLAB_DEFAULT.honor_secondary is False
    assert AZURE_DEVOPS_DEFAULT.honor_secondary is False
    for pol in (GITHUB_DEFAULT, GITLAB_DEFAULT, BITBUCKET_DEFAULT, AZURE_DEVOPS_DEFAULT):
        assert pol.max_attempts == 6
        assert pol.honor_429 is True
        assert pol.total_deadline_s is None


@pytest.mark.unit
def test_scm_05a_honor_secondary_false_passes_through() -> None:
    """honor_secondary=False: a secondary-classed response is returned, not retried (DOC §3.1)."""
    from integrations.scm._http import RetryPolicy, classify_github

    policy = RetryPolicy(max_attempts=4, honor_secondary=False)
    secondary = _FakeResponse(
        status_code=403,
        headers={"Retry-After": "5"},
        text="You have exceeded a secondary rate limit. Please wait.",
    )
    assert classify_github(secondary).is_secondary is True
    outcome, sleeps = _run_retry(policy=policy, classify=classify_github, responses=[secondary])
    assert outcome is secondary  # passed through, not retried
    assert sleeps == []


@pytest.mark.unit
def test_scm_05a_honor_429_false_passes_through() -> None:
    """honor_429=False: a primary 429 is returned, not retried (DOC §3.1)."""
    from integrations.scm._http import RetryPolicy, classify_gitlab

    policy = RetryPolicy(max_attempts=4, honor_429=False)
    limited = _FakeResponse(status_code=429, headers={"Retry-After": "3"})
    v = classify_gitlab(limited)
    assert v.is_rate_limited is True and v.is_secondary is False
    outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
    assert outcome is limited  # passed through, not retried
    assert sleeps == []


@pytest.mark.unit
def test_scm_05a_classify_not_rate_limited_on_2xx() -> None:
    """Every classify_* returns is_rate_limited=False on a clean 200."""
    from integrations.scm._http import (
        classify_azure_devops,
        classify_bitbucket,
        classify_github,
        classify_gitlab,
    )

    ok = _FakeResponse(status_code=200, headers={"X-RateLimit-Remaining": "4999"})
    for fn in (classify_github, classify_gitlab, classify_bitbucket, classify_azure_devops):
        v = fn(ok)
        assert v.is_rate_limited is False
        assert v.retry_after_s is None
        assert v.is_secondary is False


@pytest.mark.unit
def test_scm_05a_classify_github_403_without_remaining_zero_is_not_limited() -> None:
    """A bare 403 (no Remaining:0, no secondary marker) is not a rate limit."""
    from integrations.scm._http import classify_github

    resp = _FakeResponse(status_code=403, text="forbidden")
    assert classify_github(resp).is_rate_limited is False


@pytest.mark.unit
def test_scm_05a_honor_retry_after_false_falls_back_to_curve() -> None:
    """With honor_retry_after=False the curve is used even when Retry-After set."""
    from integrations.scm._http import JitterMode, RetryPolicy, classify_gitlab
    from integrations.scm.base import SCMRateLimitError

    policy = RetryPolicy(
        initial_backoff_s=1.0,
        backoff_factor=2.0,
        jitter=JitterMode.NONE,
        max_attempts=3,
        honor_retry_after=False,
    )
    limited = _FakeResponse(status_code=429, headers={"Retry-After": "99"})
    outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
    assert isinstance(outcome, SCMRateLimitError)
    assert sleeps == [1.0, 2.0]  # curve, NOT the 99s Retry-After


@pytest.mark.unit
def test_scm_05a_equal_jitter_bounds() -> None:
    """JitterMode.EQUAL yields sleeps in [base/2, base]."""
    from integrations.scm._http import JitterMode, RetryPolicy, classify_gitlab

    policy = RetryPolicy(
        initial_backoff_s=4.0,
        backoff_factor=1.0,  # base stays 4.0 each attempt
        jitter=JitterMode.EQUAL,
        max_attempts=4,
    )
    limited = _FakeResponse(status_code=429)
    _, sleeps = _run_retry(
        policy=policy,
        classify=classify_gitlab,
        responses=[limited],
        jitter_seed=42,  # fixed seed, consistent with the rest of the suite
    )
    for slept in sleeps:
        assert 2.0 <= slept <= 4.0  # base/2 .. base


@pytest.mark.unit
def test_scm_05a_retry_after_unparseable_falls_back_to_curve() -> None:
    """A malformed Retry-After is ignored; the curve drives the backoff."""
    from integrations.scm._http import JitterMode, RetryPolicy, classify_gitlab
    from integrations.scm.base import SCMRateLimitError

    policy = RetryPolicy(
        initial_backoff_s=1.0, backoff_factor=2.0, jitter=JitterMode.NONE, max_attempts=2
    )
    limited = _FakeResponse(status_code=429, headers={"Retry-After": "not-a-date"})
    outcome, sleeps = _run_retry(policy=policy, classify=classify_gitlab, responses=[limited])
    assert isinstance(outcome, SCMRateLimitError)
    assert sleeps == [1.0]  # unparseable header → curve


@pytest.mark.unit
def test_scm_05a_header_lookup_is_case_insensitive_on_plain_dict() -> None:
    """A lowercase-keyed plain dict still resolves Retry-After (case-fold scan)."""
    from integrations.scm._http import classify_gitlab

    resp = _FakeResponse(status_code=429, headers={"retry-after": "6"})
    v = classify_gitlab(resp)
    assert v.is_rate_limited and v.retry_after_s == 6.0


@pytest.mark.unit
def test_scm_05a_retry_after_naive_http_date_assumed_utc() -> None:
    """An HTTP-date without an explicit zone is treated as UTC, not rejected."""
    from datetime import UTC, datetime, timedelta

    from integrations.scm._http import classify_gitlab

    future = datetime.now(UTC) + timedelta(seconds=20)
    naive_date = future.strftime("%a, %d %b %Y %H:%M:%S")  # no GMT/zone suffix
    resp = _FakeResponse(status_code=429, headers={"Retry-After": naive_date})
    v = classify_gitlab(resp)
    assert v.is_rate_limited
    assert v.retry_after_s is not None and 10.0 <= v.retry_after_s <= 21.0


@pytest.mark.unit
def test_scm_05a_github_malformed_reset_yields_no_wait() -> None:
    """A non-numeric X-RateLimit-Reset is ignored (retry_after_s is None)."""
    from integrations.scm._http import classify_github

    resp = _FakeResponse(
        status_code=403,
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "soon"},
    )
    v = classify_github(resp)
    assert v.is_rate_limited and v.is_secondary is False
    assert v.retry_after_s is None


@pytest.mark.unit
def test_scm_05a_empty_retry_after_is_none() -> None:
    """An empty/whitespace Retry-After parses to None (no provider wait)."""
    from integrations.scm._http import classify_gitlab

    resp = _FakeResponse(status_code=429, headers={"Retry-After": "   "})
    v = classify_gitlab(resp)
    assert v.is_rate_limited and v.retry_after_s is None


@pytest.mark.unit
def test_scm_05a_success_first_try_no_sleep() -> None:
    """A clean first response returns immediately with no retries or sleeps."""
    from integrations.scm._http import RetryPolicy, classify_github

    ok = _FakeResponse(status_code=200)
    outcome, sleeps = _run_retry(
        policy=RetryPolicy(max_attempts=5), classify=classify_github, responses=[ok]
    )
    assert isinstance(outcome, _FakeResponse) and outcome.status_code == 200
    assert sleeps == []


# ---------------------------------------------------------------------------
# TST-AC-SCM-01c (unit) — drive the conformance harness end-to-end against an
# in-memory stub connector. It is pure (no real network/disk), so it belongs in
# the unit run; this also gives integrations/scm/conformance.py its unit
# coverage (the integration-marked copy does not count toward the unit-tests
# coverage gate, which measures `--cov=.` over the unit run only).
# ---------------------------------------------------------------------------


def _stub_connector_cls(*, break_op: str | None = None):
    import hashlib
    import hmac
    from datetime import UTC, datetime
    from typing import ClassVar

    from integrations.scm.base import (
        CloneMetadata,
        RepoRef,
        SCMConnector,
        WebhookSubscription,
    )

    class _Stub(SCMConnector):
        provider_id: ClassVar[str] = "stub"

        async def list_repos(self, *, org_or_workspace, page_size=100):
            if break_op == "list_repos":
                raise RuntimeError("induced list_repos failure")
            yield RepoRef(
                provider="stub",
                owner=org_or_workspace,
                name="r",
                clone_url="https://stub.example/r.git",
                default_branch="main",
            )

        async def clone(self, repo_ref, *, commit_sha, dest_dir, shallow=True):
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
            return "a" * 40

        def sign_webhook(self, *, raw_body, secret):
            sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
            return {"X-Stub-Signature": sig}

    return _Stub


def _conformance_fixture_repo():
    from integrations.scm.base import RepoRef

    return RepoRef(
        provider="stub",
        owner="acme",
        name="r",
        clone_url="https://stub.example/r.git",
        default_branch="main",
    )


@pytest.mark.unit
def test_scm_01c_conformance_suite_conformant_unit() -> None:
    """A fully-conformant stub yields an empty-failures, is_conformant report."""
    import asyncio

    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.conformance import ConformanceReport, run_conformance_suite

    conn = _stub_connector_cls()(
        SCMCredentials(provider="github", mode=SCMAuthMode.PAT, payload={"token": "t"})
    )
    report = asyncio.run(
        run_conformance_suite(
            conn, fixture_repo=_conformance_fixture_repo(), canary_commit_sha="a" * 40
        )
    )
    assert isinstance(report, ConformanceReport)
    assert report.is_conformant
    assert report.failures == ()
    assert "list_repos" in report.passed
    assert "verify_webhook_negative" in report.passed


@pytest.mark.unit
def test_scm_01c_conformance_suite_records_failure_unit() -> None:
    """A connector that breaks one op is non-conformant and the failure names it."""
    import asyncio

    from integrations.scm.base import SCMAuthMode, SCMCredentials
    from integrations.scm.conformance import run_conformance_suite

    conn = _stub_connector_cls(break_op="list_repos")(
        SCMCredentials(provider="github", mode=SCMAuthMode.PAT, payload={"token": "t"})
    )
    report = asyncio.run(
        run_conformance_suite(
            conn, fixture_repo=_conformance_fixture_repo(), canary_commit_sha="a" * 40
        )
    )
    assert not report.is_conformant
    assert any(f.method == "list_repos" for f in report.failures)

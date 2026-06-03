"""Unit coverage for CMP-SCM-03 GitLab/Bitbucket/Azure DevOps connectors.

These tests exercise the concrete `SCMConnector` subclasses through a stub async
HTTP transport (the `AsyncHTTPTransport` Protocol each module declares) and a
stub `GitRunner`, with no real network or subprocess I/O. They drive the real
code paths — auth-header construction, the six ABC methods, pagination, the
terminal-status → `SCMError` mapping, the retry path through `with_retry` +
`classify_*`, and the per-provider `verify_webhook` schemes (valid + tampered).

`CMP-SCM-03` emits no findings and threads no provenance fields, so these tests
assert no INV-1/INV-2 provenance (RULE-6 non-touch); they are pure connector
unit tests. Async is driven via `asyncio.run(...)` (no pytest-asyncio).
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from integrations.scm._http import JitterMode, RetryPolicy
from integrations.scm.ado import AzureDevOpsConnector
from integrations.scm.base import (
    RepoRef,
    SCMAuthError,
    SCMAuthMode,
    SCMConnector,
    SCMCredentials,
    SCMNotFoundError,
    SCMRateLimitError,
    SCMTransientError,
    WebhookSubscription,
)
from integrations.scm.bitbucket import BitbucketConnector
from integrations.scm.gitlab import GitLabConnector

pytestmark = pytest.mark.unit

_SHA = "a" * 40
_PARENT = "b" * 40
_WH_SECRET = "sek"  # pragma: allowlist secret
_HOOK_SECRET = "s"  # pragma: allowlist secret

# A sleep-free, single-shot retry policy: zero backoff so any retried response
# (429/5xx) does not actually sleep, and a low attempt cap so exhaustion paths
# terminate immediately. `with_retry` is applied inside `_request`, which exposes
# no `_sleep` seam — the only lever is the construction-time policy.
_FAST = RetryPolicy(
    initial_backoff_s=0.0,
    max_backoff_s=0.0,
    backoff_factor=1.0,
    jitter=JitterMode.NONE,
    max_attempts=1,
)
_FAST2 = RetryPolicy(
    initial_backoff_s=0.0,
    max_backoff_s=0.0,
    backoff_factor=1.0,
    jitter=JitterMode.NONE,
    max_attempts=2,
)


# ---------------------------------------------------------------------------
# Stubs satisfying the per-module AsyncHTTPTransport + HTTPResponse protocols.
# ---------------------------------------------------------------------------


class _Resp:
    """An HTTPResponse-shaped stub (status_code, headers, text, json())."""

    def __init__(
        self,
        status_code: int = 200,
        *,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.text = text
        self._body = body

    def json(self) -> Any:
        return self._body


class _Transport:
    """Queue-based async transport: pops one queued response per request.

    Each `_request` consumes exactly one entry, so multi-page listings and
    "rate-limited then success" sequences are expressed explicitly. The
    last-request args are recorded for assertion.
    """

    def __init__(self, responses: Sequence[_Resp]) -> None:
        self._queue = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,
    ) -> _Resp:
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "params": params, "json": json}
        )
        return self._queue.pop(0)


def _git_runner(extra: dict[str, tuple[int, str, str]] | None = None):
    """Build a fake GitRunner dispatching on argv[0]; success by default."""
    extra = extra or {}

    async def runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
        cmd = argv[0]
        if cmd in extra:
            return extra[cmd]
        if cmd == "rev-parse":
            return (0, f"{_SHA}\n", "")
        if cmd == "rev-list":
            return (0, f"{_SHA} {_PARENT}\n", "")
        return (0, "", "")

    return runner


# ---------------------------------------------------------------------------
# Connector construction helpers.
# ---------------------------------------------------------------------------


_DEFAULT: Any = object()  # sentinel: "use default token" vs an explicit {}.


def _gitlab(
    transport: _Transport,
    *,
    payload: Any = _DEFAULT,
    policy: RetryPolicy | None = None,
    git_runner=None,
) -> GitLabConnector:
    pl = {"token": "tok"} if payload is _DEFAULT else dict(payload or {})
    creds = SCMCredentials(provider="gitlab", mode=SCMAuthMode.PAT, payload=pl)
    return GitLabConnector(
        creds, transport=transport, retry_policy=policy or _FAST, git_runner=git_runner
    )


def _bitbucket(
    transport: _Transport,
    *,
    payload: Any = _DEFAULT,
    policy: RetryPolicy | None = None,
    git_runner=None,
) -> BitbucketConnector:
    pl = {"access_token": "tok"} if payload is _DEFAULT else dict(payload or {})
    creds = SCMCredentials(provider="bitbucket", mode=SCMAuthMode.PAT, payload=pl)
    return BitbucketConnector(
        creds, transport=transport, retry_policy=policy or _FAST, git_runner=git_runner
    )


def _ado(
    transport: _Transport,
    *,
    payload: Any = _DEFAULT,
    policy: RetryPolicy | None = None,
    git_runner=None,
) -> AzureDevOpsConnector:
    pl = {"token": "tok"} if payload is _DEFAULT else dict(payload or {})
    creds = SCMCredentials(provider="azure-devops", mode=SCMAuthMode.PAT, payload=pl)
    return AzureDevOpsConnector(
        creds,
        organization="acme",
        transport=transport,
        retry_policy=policy or _FAST,
        git_runner=git_runner,
    )


_GITLAB_REPO = RepoRef(
    provider="gitlab",
    owner="grp",
    name="widgets",
    clone_url="https://gitlab.com/grp/widgets.git",
    default_branch="main",
)
_BB_REPO = RepoRef(
    provider="bitbucket",
    owner="ws",
    name="widgets",
    clone_url="https://bitbucket.org/ws/widgets.git",
    default_branch="main",
)
_ADO_REPO = RepoRef(
    provider="azure-devops",
    owner="acme/proj",
    name="widgets",
    clone_url="https://dev.azure.com/acme/proj/_git/widgets",
    default_branch="main",
)


# ---------------------------------------------------------------------------
# Auth header construction (PAT vs OAuth vs none) — provider-specific schemes.
# ---------------------------------------------------------------------------


def test_gitlab_auth_headers_pat_and_oauth_and_none() -> None:
    pat = _gitlab(_Transport([]), payload={"token": "T"})._auth_headers()
    assert pat["PRIVATE-TOKEN"] == "T"
    assert "Authorization" not in pat

    oauth = _gitlab(_Transport([]), payload={"access_token": "AT"})._auth_headers()
    assert oauth["Authorization"] == "Bearer AT"

    none = _gitlab(_Transport([]), payload={})._auth_headers()
    assert "PRIVATE-TOKEN" not in none and "Authorization" not in none


def test_bitbucket_auth_headers_token_and_none() -> None:
    tok = _bitbucket(_Transport([]), payload={"access_token": "AT"})._auth_headers()
    assert tok["Authorization"] == "Bearer AT"
    legacy = _bitbucket(_Transport([]), payload={"token": "T"})._auth_headers()
    assert legacy["Authorization"] == "Bearer T"
    none = _bitbucket(_Transport([]), payload={})._auth_headers()
    assert "Authorization" not in none


def test_ado_auth_headers_basic_pat_and_bearer_and_none() -> None:
    basic = _ado(_Transport([]), payload={"token": "T"})._auth_headers()
    assert basic["Authorization"].startswith("Basic ")
    bearer = _ado(_Transport([]), payload={"access_token": "AT"})._auth_headers()
    assert bearer["Authorization"] == "Bearer AT"
    none = _ado(_Transport([]), payload={})._auth_headers()
    assert "Authorization" not in none


# ---------------------------------------------------------------------------
# Terminal-status → SCMError mapping (parametrized, uniform across providers).
# ---------------------------------------------------------------------------

_BUILDERS = {
    "gitlab": (_gitlab, _GITLAB_REPO),
    "bitbucket": (_bitbucket, _BB_REPO),
    "azure-devops": (_ado, _ADO_REPO),
}


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (404, SCMNotFoundError),
        (401, SCMAuthError),
        (403, SCMAuthError),
        (400, SCMTransientError),
    ],
)
def test_terminal_status_mapping(provider: str, status: int, exc: type[Exception]) -> None:
    build, repo = _BUILDERS[provider]
    conn = build(_Transport([_Resp(status, body={}, text="boom")]))
    with pytest.raises(exc):
        asyncio.run(conn.get_default_branch(repo))


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_transport_5xx_raises_transient_after_exhaustion(provider: str) -> None:
    build, repo = _BUILDERS[provider]
    # A 5xx is mapped to SCMTransientError inside the retried call; with
    # max_attempts=1 the budget is immediately exhausted and it propagates.
    conn = build(_Transport([_Resp(500, body={})]))
    with pytest.raises(SCMTransientError):
        asyncio.run(conn.get_default_branch(repo))


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_rate_limited_exhaustion_raises_ratelimit(provider: str) -> None:
    build, repo = _BUILDERS[provider]
    # A 429 is classified as rate-limited; max_attempts=1 → SCMRateLimitError.
    conn = build(_Transport([_Resp(429, body={}, headers={"Retry-After": "0"})]))
    with pytest.raises(SCMRateLimitError):
        asyncio.run(conn.get_default_branch(repo))


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_rate_limited_then_success(provider: str) -> None:
    build, repo = _BUILDERS[provider]
    ok_body = {
        "gitlab": {"default_branch": "main"},
        "bitbucket": {"mainbranch": {"name": "main"}},
        "azure-devops": {"defaultBranch": "refs/heads/main"},
    }[provider]
    # Zero-backoff 2-attempt policy: 429 then 200 → resolves without real sleep.
    conn = build(
        _Transport([_Resp(429, body={}, headers={"Retry-After": "0"}), _Resp(200, body=ok_body)]),
        policy=_FAST2,
    )
    assert asyncio.run(conn.get_default_branch(repo)) == "main"


# ---------------------------------------------------------------------------
# list_repos: pagination + RepoRef shaping.
# ---------------------------------------------------------------------------


def test_gitlab_list_repos_paginates_via_next_page_header() -> None:
    page1 = _Resp(
        200,
        headers={"X-Next-Page": "2"},
        body=[
            {
                "path": "alpha",
                "http_url_to_repo": "https://gitlab.com/grp/alpha.git",
                "default_branch": "main",
                "namespace": {"full_path": "grp"},
            }
        ],
    )
    page2 = _Resp(
        200,
        headers={"X-Next-Page": ""},
        body=[{"path": "beta", "http_url_to_repo": "https://gitlab.com/grp/beta.git"}],
    )
    conn = _gitlab(_Transport([page1, page2]))

    async def go() -> list[RepoRef]:
        return [r async for r in conn.list_repos(org_or_workspace="grp", page_size=50)]

    repos = asyncio.run(go())
    assert [r.name for r in repos] == ["alpha", "beta"]
    assert repos[0].owner == "grp"
    assert repos[0].default_branch == "main"
    # beta has no namespace/default_branch → owner empty, branch None.
    assert repos[1].owner == ""
    assert repos[1].default_branch is None


def test_bitbucket_list_repos_paginates_via_next_url() -> None:
    page1 = _Resp(
        200,
        body={
            "values": [
                {
                    "slug": "alpha",
                    "workspace": {"slug": "ws"},
                    "mainbranch": {"name": "main"},
                    "links": {"clone": [{"name": "https", "href": "https://bb/ws/alpha.git"}]},
                }
            ],
            "next": "https://api.bitbucket.org/2.0/repositories/ws?page=2",
        },
    )
    page2 = _Resp(200, body={"values": [{"slug": "beta"}]})
    conn = _bitbucket(_Transport([page1, page2]))

    async def go() -> list[RepoRef]:
        return [r async for r in conn.list_repos(org_or_workspace="ws")]

    repos = asyncio.run(go())
    assert [r.name for r in repos] == ["alpha", "beta"]
    assert repos[0].owner == "ws"
    assert repos[0].clone_url == "https://bb/ws/alpha.git"
    # beta with no links/workspace → empty clone_url and owner.
    assert repos[1].clone_url == ""
    assert repos[1].owner == ""


def test_ado_list_repos_single_page_value_array() -> None:
    resp = _Resp(
        200,
        body={
            "value": [
                {
                    "name": "alpha",
                    "remoteUrl": "https://dev.azure.com/acme/proj/_git/alpha",
                    "defaultBranch": "refs/heads/main",
                }
            ]
        },
    )
    conn = _ado(_Transport([resp]))

    async def go() -> list[RepoRef]:
        return [r async for r in conn.list_repos(org_or_workspace="proj")]

    repos = asyncio.run(go())
    assert len(repos) == 1
    assert repos[0].name == "alpha"
    assert repos[0].owner == "acme/proj"
    assert repos[0].default_branch == "main"


# ---------------------------------------------------------------------------
# clone(): git-runner orchestration + CloneMetadata + auth URL injection.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_clone_returns_metadata(provider: str, tmp_path: Path) -> None:
    build, repo = _BUILDERS[provider]
    conn = build(_Transport([]), git_runner=_git_runner())
    dest = tmp_path / "tree"
    (tmp_path).mkdir(exist_ok=True)
    meta = asyncio.run(conn.clone(repo, commit_sha=_SHA, dest_dir=dest, shallow=True))
    assert meta.commit_sha == _SHA
    assert meta.parent_shas == (_PARENT,)
    assert meta.shallow is True
    assert meta.provider == provider
    assert dest.exists()


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_clone_scrubs_token_bearing_remote_after_checkout(provider: str, tmp_path: Path) -> None:
    """The token-bearing origin remote is removed after checkout (credential-at-rest).

    `remote add origin <authed_url>` writes the token into dest/.git/config; clone()
    must `remote remove origin` after the working tree is materialized so the
    credential does not survive on disk.
    """
    build, repo = _BUILDERS[provider]
    recorded: list[tuple[str, ...]] = []

    async def recording_runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
        recorded.append(tuple(argv))
        if argv[0] == "rev-parse":
            return (0, f"{_SHA}\n", "")
        if argv[0] == "rev-list":
            return (0, f"{_SHA} {_PARENT}\n", "")
        return (0, "", "")

    conn = build(_Transport([]), git_runner=recording_runner)
    asyncio.run(conn.clone(repo, commit_sha=_SHA, dest_dir=tmp_path / "t", shallow=True))
    assert ("remote", "remove", "origin") in recorded
    checkout_idx = next(i for i, a in enumerate(recorded) if a[0] == "checkout")
    scrub_idx = recorded.index(("remote", "remove", "origin"))
    assert scrub_idx > checkout_idx


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_clone_non_shallow_and_no_parents(provider: str, tmp_path: Path) -> None:
    build, repo = _BUILDERS[provider]
    # rev-list fails / empty → parent_shas == ().
    conn = build(_Transport([]), git_runner=_git_runner({"rev-list": (1, "", "no")}))
    dest = tmp_path / "tree"
    meta = asyncio.run(conn.clone(repo, commit_sha=_SHA, dest_dir=dest, shallow=False))
    assert meta.parent_shas == ()
    assert meta.shallow is False


@pytest.mark.parametrize("provider", ["gitlab", "bitbucket", "azure-devops"])
def test_clone_git_failure_raises_transient(provider: str, tmp_path: Path) -> None:
    build, repo = _BUILDERS[provider]
    conn = build(_Transport([]), git_runner=_git_runner({"fetch": (128, "", "fatal: nope")}))
    dest = tmp_path / "tree"
    with pytest.raises(SCMTransientError):
        asyncio.run(conn.clone(repo, commit_sha=_SHA, dest_dir=dest))


def test_authed_clone_url_provider_prefixes_and_passthrough() -> None:
    gl = _gitlab(_Transport([]), payload={"token": "T"})
    assert (
        gl._authed_clone_url("https://gitlab.com/g/r.git") == "https://oauth2:T@gitlab.com/g/r.git"
    )
    # SSH and no-token are passthrough.
    assert gl._authed_clone_url("git@gitlab.com:g/r.git") == "git@gitlab.com:g/r.git"
    assert (
        _gitlab(_Transport([]), payload={})._authed_clone_url("https://x/y.git")
        == "https://x/y.git"
    )

    bb = _bitbucket(_Transport([]), payload={"access_token": "T"})
    assert (
        bb._authed_clone_url("https://bitbucket.org/w/r.git")
        == "https://x-token-auth:T@bitbucket.org/w/r.git"
    )
    assert bb._authed_clone_url("ssh://git@bb/r.git") == "ssh://git@bb/r.git"

    ado = _ado(_Transport([]), payload={"token": "T"})
    assert (
        ado._authed_clone_url("https://dev.azure.com/o/p/_git/r")
        == "https://pat:T@dev.azure.com/o/p/_git/r"
    )
    assert _ado(_Transport([]), payload={})._authed_clone_url("https://x/y") == "https://x/y"


# ---------------------------------------------------------------------------
# register_webhook: create-new path + idempotent reuse path.
# ---------------------------------------------------------------------------


def test_gitlab_register_webhook_creates_new() -> None:
    # 1st GET (find existing) returns [], then POST returns the new hook.
    conn = _gitlab(_Transport([_Resp(200, body=[]), _Resp(200, body={"id": 77})]))
    sub = asyncio.run(
        conn.register_webhook(
            _GITLAB_REPO,
            target_url="https://scanipy/hook",
            events=("push", "pull_request"),
            secret=_HOOK_SECRET,
        )
    )
    assert isinstance(sub, WebhookSubscription)
    assert sub.webhook_id == "77"
    assert sub.provider == "gitlab"


def test_gitlab_register_webhook_idempotent_reuse() -> None:
    existing = _Resp(200, body=[{"id": 9, "url": "https://scanipy/hook"}])
    conn = _gitlab(_Transport([existing]))
    sub = asyncio.run(
        conn.register_webhook(
            _GITLAB_REPO, target_url="https://scanipy/hook", events=("push",), secret=_HOOK_SECRET
        )
    )
    assert sub.webhook_id == "9"


def test_bitbucket_register_webhook_creates_and_maps_events() -> None:
    transport = _Transport([_Resp(200, body={"values": []}), _Resp(200, body={"uuid": "{abc}"})])
    conn = _bitbucket(transport)
    sub = asyncio.run(
        conn.register_webhook(
            _BB_REPO,
            target_url="https://scanipy/hook",
            events=("push", "pull_request"),
            secret=_HOOK_SECRET,
        )
    )
    assert sub.webhook_id == "{abc}"
    posted = transport.calls[-1]["json"]
    assert posted["events"] == ["repo:push", "pullrequest:created"]


def test_bitbucket_register_webhook_idempotent_reuse() -> None:
    existing = _Resp(200, body={"values": [{"uuid": "{x}", "url": "https://scanipy/hook"}]})
    conn = _bitbucket(_Transport([existing]))
    sub = asyncio.run(
        conn.register_webhook(
            _BB_REPO, target_url="https://scanipy/hook", events=("push",), secret=_HOOK_SECRET
        )
    )
    assert sub.webhook_id == "{x}"


def test_ado_register_webhook_creates_new() -> None:
    conn = _ado(_Transport([_Resp(200, body={"value": []}), _Resp(200, body={"id": "sub-1"})]))
    sub = asyncio.run(
        conn.register_webhook(
            _ADO_REPO, target_url="https://scanipy/hook", events=("push",), secret=_HOOK_SECRET
        )
    )
    assert sub.webhook_id == "sub-1"
    assert sub.provider == "azure-devops"


def test_ado_register_webhook_idempotent_reuse() -> None:
    existing = _Resp(
        200,
        body={"value": [{"id": "sub-9", "consumerInputs": {"url": "https://scanipy/hook"}}]},
    )
    conn = _ado(_Transport([existing]))
    sub = asyncio.run(
        conn.register_webhook(
            _ADO_REPO, target_url="https://scanipy/hook", events=("push",), secret=_HOOK_SECRET
        )
    )
    assert sub.webhook_id == "sub-9"


# ---------------------------------------------------------------------------
# get_default_branch + resolve_commit (success + missing → SCMNotFoundError).
# ---------------------------------------------------------------------------


def test_gitlab_default_branch_and_missing() -> None:
    conn = _gitlab(_Transport([_Resp(200, body={"default_branch": "trunk"})]))
    assert asyncio.run(conn.get_default_branch(_GITLAB_REPO)) == "trunk"
    miss = _gitlab(_Transport([_Resp(200, body={})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.get_default_branch(_GITLAB_REPO))


def test_bitbucket_default_branch_and_missing() -> None:
    conn = _bitbucket(_Transport([_Resp(200, body={"mainbranch": {"name": "develop"}})]))
    assert asyncio.run(conn.get_default_branch(_BB_REPO)) == "develop"
    miss = _bitbucket(_Transport([_Resp(200, body={"mainbranch": {}})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.get_default_branch(_BB_REPO))


def test_ado_default_branch_and_missing() -> None:
    conn = _ado(_Transport([_Resp(200, body={"defaultBranch": "refs/heads/dev"})]))
    assert asyncio.run(conn.get_default_branch(_ADO_REPO)) == "dev"
    miss = _ado(_Transport([_Resp(200, body={})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.get_default_branch(_ADO_REPO))


def test_gitlab_resolve_commit_and_missing() -> None:
    conn = _gitlab(_Transport([_Resp(200, body={"id": _SHA})]))
    assert asyncio.run(conn.resolve_commit(_GITLAB_REPO, ref="main")) == _SHA
    miss = _gitlab(_Transport([_Resp(200, body={})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.resolve_commit(_GITLAB_REPO, ref="nope"))


def test_bitbucket_resolve_commit_and_missing() -> None:
    conn = _bitbucket(_Transport([_Resp(200, body={"hash": _SHA})]))
    assert asyncio.run(conn.resolve_commit(_BB_REPO, ref="main")) == _SHA
    miss = _bitbucket(_Transport([_Resp(200, body={})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.resolve_commit(_BB_REPO, ref="nope"))


def test_ado_resolve_commit_and_missing() -> None:
    conn = _ado(_Transport([_Resp(200, body={"value": [{"commitId": _SHA}]})]))
    assert asyncio.run(conn.resolve_commit(_ADO_REPO, ref="main")) == _SHA
    miss = _ado(_Transport([_Resp(200, body={"value": []})]))
    with pytest.raises(SCMNotFoundError):
        asyncio.run(miss.resolve_commit(_ADO_REPO, ref="nope"))


def test_ado_split_owner_without_slash_falls_back() -> None:
    repo = RepoRef(
        provider="azure-devops",
        owner="solo",
        name="r",
        clone_url="https://dev.azure.com/acme/solo/_git/r",
    )
    conn = _ado(_Transport([_Resp(200, body={"defaultBranch": "refs/heads/main"})]))
    # owner has no '/', so _split_owner returns (owner, owner); request succeeds.
    assert asyncio.run(conn.get_default_branch(repo)) == "main"


# ---------------------------------------------------------------------------
# verify_webhook: per-provider scheme, valid + tampered (via sign_webhook hook).
# ---------------------------------------------------------------------------


def test_gitlab_verify_webhook_constant_time_token() -> None:
    conn = _gitlab(_Transport([]))
    body = b'{"e":"push"}'
    good = conn.sign_webhook(raw_body=body, secret=_WH_SECRET)
    assert conn.verify_webhook(raw_body=body, headers=good, secret=_WH_SECRET) is True
    # wrong token, absent header, and case-insensitive header lookup.
    assert (
        conn.verify_webhook(raw_body=body, headers={"X-Gitlab-Token": "x"}, secret=_WH_SECRET)
        is False
    )
    assert conn.verify_webhook(raw_body=body, headers={}, secret=_WH_SECRET) is False
    lower = {"x-gitlab-token": "sek"}
    assert conn.verify_webhook(raw_body=body, headers=lower, secret=_WH_SECRET) is True


def test_bitbucket_verify_webhook_hmac_sha256() -> None:
    conn = _bitbucket(_Transport([]))
    body = b'{"e":"push"}'
    good = conn.sign_webhook(raw_body=body, secret=_WH_SECRET)
    assert conn.verify_webhook(raw_body=body, headers=good, secret=_WH_SECRET) is True
    # tampered body with original signature → False.
    assert conn.verify_webhook(raw_body=b'{"e":"PUSH"}', headers=good, secret=_WH_SECRET) is False
    # missing + malformed (no sha256= prefix) headers → False.
    assert conn.verify_webhook(raw_body=body, headers={}, secret=_WH_SECRET) is False
    assert (
        conn.verify_webhook(raw_body=body, headers={"X-Hub-Signature": "md5=z"}, secret=_WH_SECRET)
        is False
    )


def test_ado_verify_webhook_basic_auth_secret_equality() -> None:
    # Native ADO service-hooks carry no body HMAC: the secret rides as the HTTP
    # Basic password (CLAR-SCM-02 RESOLVED 2026-06-03). The predicate is
    # body-independent — it checks the credential, not the body.
    import base64

    conn = _ado(_Transport([]))
    body = b'{"e":"push"}'
    good = conn.sign_webhook(raw_body=body, secret=_WH_SECRET)
    # Anti-vacuity: sign_webhook emits a Basic header that genuinely verifies.
    assert good.get("Authorization", "").startswith("Basic ")
    assert conn.verify_webhook(raw_body=body, headers=good, secret=_WH_SECRET) is True
    # Body-independence: a tampered body still verifies True (credential checked,
    # not the body) — this is the de-vacuumed positive, replacing the old
    # body-tamper assert that the HMAC scheme implied.
    assert conn.verify_webhook(raw_body=b'{"e":"PUSH"}', headers=good, secret=_WH_SECRET) is True
    # Negative control: a Basic header echoing the WRONG password → False.
    wrong = "Basic " + base64.b64encode(b":not-the-secret").decode("ascii")
    assert (
        conn.verify_webhook(raw_body=body, headers={"Authorization": wrong}, secret=_WH_SECRET)
        is False
    )
    # Negative control: absent Authorization header → False (no exception).
    assert conn.verify_webhook(raw_body=body, headers={}, secret=_WH_SECRET) is False


# ---------------------------------------------------------------------------
# Misc edge branches: GitLab _project_id empty owner; provider_id classvars.
# ---------------------------------------------------------------------------


def test_gitlab_project_id_empty_owner() -> None:
    from integrations.scm.gitlab import _project_id

    repo = RepoRef(provider="gitlab", owner="", name="solo", clone_url="https://x/solo.git")
    assert _project_id(repo) == "solo"
    nested = RepoRef(provider="gitlab", owner="grp/sub", name="r", clone_url="https://x/r.git")
    assert _project_id(nested) == "grp%2Fsub%2Fr"


@pytest.mark.parametrize(
    ("conn", "pid"),
    [
        (GitLabConnector, "gitlab"),
        (BitbucketConnector, "bitbucket"),
        (AzureDevOpsConnector, "azure-devops"),
    ],
)
def test_provider_ids(conn: type[SCMConnector], pid: str) -> None:
    assert conn.provider_id == pid

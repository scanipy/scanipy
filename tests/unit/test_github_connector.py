"""Unit coverage for CMP-SCM-02 GitHubConnector (lifts the unit-coverage gate).

These tests drive the GitHub connector entirely through injected stubs — a
stub async HTTP transport implementing the `AsyncHTTPTransport` Protocol and a
recording stub git runner — so no real network or subprocess I/O occurs. They
exercise the real connector code paths (auth headers, the six `SCMConnector`
methods, webhook verify/sign, `_request` retry/error mapping, and the
Research-mode helpers) to raise `integrations/scm/github.py` coverage.

CMP-SCM-02 is upstream of the provenance chain and threads no provenance
fields (RULE-6 non-touch); these tests assert no provenance behaviour.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from integrations.github import search_repositories
from integrations.scm._http import JitterMode, RetryPolicy
from integrations.scm.base import (
    CloneMetadata,
    RepoRef,
    SCMAuthError,
    SCMAuthMode,
    SCMConnector,
    SCMCredentials,
    SCMNotFoundError,
    SCMTransientError,
    WebhookSubscription,
)
from integrations.scm.github import (
    CodeSearchHit,
    GitHubConnector,
    HTTPResponse,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

# A retry policy that never sleeps and never retries: the first transient or
# rate-limit verdict raises immediately, so error-mapping tests don't burn the
# default ~30s GitHub backoff curve.
_NO_RETRY = RetryPolicy(
    initial_backoff_s=0.0,
    max_backoff_s=0.0,
    max_attempts=1,
    jitter=JitterMode.NONE,
)


@dataclass
class StubResponse:
    """An `HTTPResponse`-shaped response (status_code, headers, text, json())."""

    status_code: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    text: str = ""
    _json: Any = None

    def json(self) -> Any:
        return self._json


@dataclass
class StubTransport:
    """An `AsyncHTTPTransport`: serves queued responses and records requests."""

    responses: list[StubResponse] = field(default_factory=list)
    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,
    ) -> HTTPResponse:
        self.calls.append((method, url, {"headers": headers, "params": params, "json": json}))
        if not self.responses:
            raise AssertionError(f"no stub response queued for {method} {url}")
        return self.responses.pop(0)


@dataclass
class StubGitRunner:
    """A recording `GitRunner` stub: maps argv[0] to a canned (code, out, err)."""

    results: dict[str, tuple[int, str, str]] = field(default_factory=dict)
    invocations: list[tuple[tuple[str, ...], Path]] = field(default_factory=list)

    async def __call__(self, argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
        self.invocations.append((tuple(argv), cwd))
        return self.results.get(argv[0], (0, "", ""))


def _pat_creds(token: str | None = "ghp_token") -> SCMCredentials:
    payload: dict[str, str] = {"token": token} if token is not None else {}
    return SCMCredentials(provider="github", mode=SCMAuthMode.PAT, payload=payload)


def _connector(
    transport: StubTransport,
    *,
    token: str | None = "ghp_token",
    git_runner: StubGitRunner | None = None,
) -> GitHubConnector:
    return GitHubConnector(
        _pat_creds(token),
        transport=transport,
        retry_policy=_NO_RETRY,
        git_runner=git_runner,
    )


def _drain(aiter: AsyncIterator[Any]) -> list[Any]:
    async def _collect() -> list[Any]:
        return [item async for item in aiter]

    return asyncio.run(_collect())


_REPO_JSON = {
    "name": "repo1",
    "owner": {"login": "acme"},
    "clone_url": "https://github.com/acme/repo1.git",
    "default_branch": "main",
}


# ---------------------------------------------------------------------------
# Construction + auth headers
# ---------------------------------------------------------------------------


def test_provider_id_and_is_scm_connector() -> None:
    conn = _connector(StubTransport())
    assert GitHubConnector.provider_id == "github"
    assert isinstance(conn, SCMConnector)


def test_auth_headers_with_pat_token() -> None:
    conn = _connector(StubTransport(), token="ghp_secret")
    headers = conn._auth_headers()
    assert headers["Authorization"] == "Bearer ghp_secret"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_auth_headers_with_oauth_access_token() -> None:
    creds = SCMCredentials(
        provider="github",
        mode=SCMAuthMode.OAUTH,
        payload={"access_token": "oauth_tok"},
    )
    conn = GitHubConnector(creds, transport=StubTransport(), retry_policy=_NO_RETRY)
    assert conn._auth_headers()["Authorization"] == "Bearer oauth_tok"


def test_auth_headers_without_token_omits_authorization() -> None:
    conn = _connector(StubTransport(), token=None)
    assert "Authorization" not in conn._auth_headers()


def test_ghe_base_url_is_stripped_and_used() -> None:
    transport = StubTransport(responses=[StubResponse(_json=_REPO_JSON)])
    conn = GitHubConnector(
        _pat_creds(),
        transport=transport,
        api_base_url="https://ghe.example.com/api/v3/",
        retry_policy=_NO_RETRY,
    )
    asyncio.run(conn.get_default_branch(RepoRef("github", "acme", "repo1", "")))
    _method, url, _ = transport.calls[0]
    assert url == "https://ghe.example.com/api/v3/repos/acme/repo1"


def test_default_retry_policy_and_git_runner_assigned() -> None:
    conn = GitHubConnector(_pat_creds(), transport=StubTransport())
    assert conn._retry_policy is not None
    assert conn._git_runner is not None  # default runner installed


# ---------------------------------------------------------------------------
# _request error mapping
# ---------------------------------------------------------------------------


def test_request_5xx_maps_to_transient() -> None:
    transport = StubTransport(responses=[StubResponse(status_code=503, text="boom")])
    conn = _connector(transport)
    with pytest.raises(SCMTransientError):
        asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", "")))


def test_request_404_maps_to_not_found() -> None:
    transport = StubTransport(responses=[StubResponse(status_code=404, text="missing")])
    conn = _connector(transport)
    with pytest.raises(SCMNotFoundError):
        asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", "")))


@pytest.mark.parametrize("status", [401, 403])
def test_request_auth_statuses_map_to_auth_error(status: int) -> None:
    transport = StubTransport(responses=[StubResponse(status_code=status, text="nope")])
    conn = _connector(transport)
    with pytest.raises(SCMAuthError):
        asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", "")))


def test_request_other_4xx_maps_to_transient() -> None:
    transport = StubTransport(responses=[StubResponse(status_code=422, text="unprocessable")])
    conn = _connector(transport)
    with pytest.raises(SCMTransientError):
        asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", "")))


def test_request_2xx_passes_through() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"default_branch": "trunk"})])
    conn = _connector(transport)
    assert asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", ""))) == "trunk"


# ---------------------------------------------------------------------------
# list_repos (method 1) + pagination via Link header
# ---------------------------------------------------------------------------


def test_list_repos_single_page() -> None:
    transport = StubTransport(responses=[StubResponse(_json=[_REPO_JSON])])
    conn = _connector(transport)
    repos = _drain(conn.list_repos(org_or_workspace="acme"))
    assert len(repos) == 1
    assert repos[0].owner == "acme"
    assert repos[0].name == "repo1"
    assert repos[0].provider == "github"
    assert repos[0].default_branch == "main"


def test_list_repos_paginates_via_link_header() -> None:
    page2_url = "https://api.github.com/orgs/acme/repos?page=2"
    page1 = StubResponse(
        headers={"Link": f'<{page2_url}>; rel="next", <...>; rel="last"'},
        _json=[_REPO_JSON],
    )
    page2 = StubResponse(_json=[{**_REPO_JSON, "name": "repo2"}])
    transport = StubTransport(responses=[page1, page2])
    conn = _connector(transport)
    repos = _drain(conn.list_repos(org_or_workspace="acme", page_size=1))
    assert [r.name for r in repos] == ["repo1", "repo2"]
    # second request hit the absolute next-link URL with no extra params
    assert transport.calls[1][1] == page2_url
    assert transport.calls[1][2]["params"] is None


def test_list_repos_skips_non_mapping_body() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"unexpected": "object"})])
    conn = _connector(transport)
    assert _drain(conn.list_repos(org_or_workspace="acme")) == []


def test_repo_ref_from_json_handles_missing_owner_and_branch() -> None:
    transport = StubTransport(responses=[StubResponse(_json=[{"name": "bare"}])])
    conn = _connector(transport)
    repos = _drain(conn.list_repos(org_or_workspace="acme"))
    assert repos[0].owner == ""
    assert repos[0].name == "bare"
    assert repos[0].default_branch is None


# ---------------------------------------------------------------------------
# clone (method 2)
# ---------------------------------------------------------------------------


def test_clone_runs_git_sequence_and_returns_metadata(tmp_path: Path) -> None:
    dest = tmp_path / "wt"
    runner = StubGitRunner(
        results={
            "rev-parse": (0, "a" * 40 + "\n", ""),
            "rev-list": (0, ("a" * 40) + " " + ("b" * 40) + "\n", ""),
        }
    )
    conn = _connector(StubTransport(), git_runner=runner)
    repo = RepoRef("github", "acme", "repo1", "https://github.com/acme/repo1.git")
    # seed a file so _tree_bytes walks something non-zero
    dest.mkdir(parents=True)
    (dest / "f.txt").write_text("hello")

    meta = asyncio.run(conn.clone(repo, commit_sha="c" * 40, dest_dir=dest, shallow=True))
    assert isinstance(meta, CloneMetadata)
    assert meta.commit_sha == "a" * 40
    assert meta.parent_shas == ("b" * 40,)
    assert meta.shallow is True
    assert meta.bytes_on_disk == len("hello")
    subcommands = [argv[0] for argv, _ in runner.invocations]
    assert subcommands[:4] == ["init", "remote", "fetch", "checkout"]
    # shallow → --depth=1 in the fetch argv
    fetch_argv = next(argv for argv, _ in runner.invocations if argv[0] == "fetch")
    assert "--depth=1" in fetch_argv


def test_clone_non_shallow_omits_depth(tmp_path: Path) -> None:
    dest = tmp_path / "wt2"
    runner = StubGitRunner(results={"rev-parse": (0, "d" * 40, ""), "rev-list": (0, "", "")})
    conn = _connector(StubTransport(), git_runner=runner)
    repo = RepoRef("github", "acme", "repo1", "https://github.com/acme/repo1.git")
    meta = asyncio.run(conn.clone(repo, commit_sha="c" * 40, dest_dir=dest, shallow=False))
    fetch_argv = next(argv for argv, _ in runner.invocations if argv[0] == "fetch")
    assert "--depth=1" not in fetch_argv
    # empty rev-list → no parents
    assert meta.parent_shas == ()


def test_clone_raises_on_git_failure(tmp_path: Path) -> None:
    runner = StubGitRunner(results={"init": (1, "", "fatal: nope")})
    conn = _connector(StubTransport(), git_runner=runner)
    repo = RepoRef("github", "acme", "repo1", "https://github.com/acme/repo1.git")
    with pytest.raises(SCMTransientError):
        asyncio.run(conn.clone(repo, commit_sha="c" * 40, dest_dir=tmp_path / "wt3"))


def test_authed_clone_url_injects_token() -> None:
    conn = _connector(StubTransport(), token="ghs_x")
    url = conn._authed_clone_url("https://github.com/acme/repo1.git")
    assert (
        url == "https://x-access-token:ghs_x@github.com/acme/repo1.git"  # pragma: allowlist secret
    )


def test_authed_clone_url_passthrough_for_ssh_and_no_token() -> None:
    conn = _connector(StubTransport(), token="ghs_x")
    ssh = "git@github.com:acme/repo1.git"
    assert conn._authed_clone_url(ssh) == ssh
    no_tok = _connector(StubTransport(), token=None)
    https = "https://github.com/acme/repo1.git"
    assert no_tok._authed_clone_url(https) == https


# ---------------------------------------------------------------------------
# register_webhook (method 3)
# ---------------------------------------------------------------------------


def test_register_webhook_creates_new_hook() -> None:
    transport = StubTransport(
        responses=[
            StubResponse(_json=[]),  # _find_existing_hook: no hooks
            StubResponse(_json={"id": 42}),  # POST create
        ]
    )
    conn = _connector(transport)
    repo = RepoRef("github", "acme", "repo1", "")
    sub = asyncio.run(
        conn.register_webhook(
            repo,
            target_url="https://hook.example/cb",
            events=("push", "pull_request"),
            secret="s3cr3t",  # pragma: allowlist secret
        )
    )
    assert isinstance(sub, WebhookSubscription)
    assert sub.webhook_id == "42"
    assert sub.target_url == "https://hook.example/cb"
    assert sub.events == ("push", "pull_request")
    # the POST body carried the secret + config
    post_call = transport.calls[1]
    assert post_call[0] == "POST"
    assert post_call[2]["json"]["config"]["secret"] == "s3cr3t"  # pragma: allowlist secret


def test_register_webhook_is_idempotent_on_existing_target() -> None:
    existing = [{"id": 7, "config": {"url": "https://hook.example/cb"}}]
    transport = StubTransport(responses=[StubResponse(_json=existing)])
    conn = _connector(transport)
    repo = RepoRef("github", "acme", "repo1", "")
    sub = asyncio.run(
        conn.register_webhook(
            repo, target_url="https://hook.example/cb", events=("push",), secret="x"
        )
    )
    assert sub.webhook_id == "7"
    # only the GET happened; no POST create
    assert len(transport.calls) == 1


def test_find_existing_hook_ignores_non_list_and_other_targets() -> None:
    hooks = [
        {"id": 1, "config": {"url": "https://other/cb"}},
        {"not": "a-config-mapping"},
    ]
    transport = StubTransport(responses=[StubResponse(_json=hooks), StubResponse(_json={"id": 99})])
    conn = _connector(transport)
    repo = RepoRef("github", "acme", "repo1", "")
    sub = asyncio.run(
        conn.register_webhook(
            repo, target_url="https://hook.example/cb", events=("push",), secret="x"
        )
    )
    # none matched → a new hook was created
    assert sub.webhook_id == "99"


# ---------------------------------------------------------------------------
# verify_webhook + sign_webhook (method 4)
# ---------------------------------------------------------------------------


def test_verify_webhook_accepts_valid_signature() -> None:
    conn = _connector(StubTransport())
    body = b'{"action":"opened"}'
    secret = "hook-secret"  # pragma: allowlist secret
    headers = conn.sign_webhook(raw_body=body, secret=secret)
    assert conn.verify_webhook(raw_body=body, headers=headers, secret=secret) is True


def test_verify_webhook_rejects_tampered_body() -> None:
    conn = _connector(StubTransport())
    secret = "hook-secret"  # pragma: allowlist secret
    headers = conn.sign_webhook(raw_body=b"original", secret=secret)
    assert conn.verify_webhook(raw_body=b"TAMPERED", headers=headers, secret=secret) is False


def test_verify_webhook_rejects_missing_and_malformed_header() -> None:
    conn = _connector(StubTransport())
    body = b"x"
    secret = "s"
    assert conn.verify_webhook(raw_body=body, headers={}, secret=secret) is False
    assert (
        conn.verify_webhook(
            raw_body=body, headers={"X-Hub-Signature-256": "md5=abc"}, secret=secret
        )
        is False
    )


def test_verify_webhook_header_lookup_is_case_insensitive() -> None:
    conn = _connector(StubTransport())
    body = b"payload"
    secret = "s"
    signed = conn.sign_webhook(raw_body=body, secret=secret)
    sig = signed["X-Hub-Signature-256"]
    assert (
        conn.verify_webhook(raw_body=body, headers={"x-hub-signature-256": sig}, secret=secret)
        is True
    )


# ---------------------------------------------------------------------------
# get_default_branch (method 5) + resolve_commit (method 6)
# ---------------------------------------------------------------------------


def test_get_default_branch_success() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"default_branch": "main"})])
    conn = _connector(transport)
    assert asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", ""))) == "main"


def test_get_default_branch_missing_field_raises_not_found() -> None:
    transport = StubTransport(responses=[StubResponse(_json={})])
    conn = _connector(transport)
    with pytest.raises(SCMNotFoundError):
        asyncio.run(conn.get_default_branch(RepoRef("github", "a", "b", "")))


def test_resolve_commit_success() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"sha": "e" * 40})])
    conn = _connector(transport)
    sha = asyncio.run(conn.resolve_commit(RepoRef("github", "a", "b", ""), ref="main"))
    assert sha == "e" * 40
    assert transport.calls[0][1].endswith("/repos/a/b/commits/main")


def test_resolve_commit_unknown_ref_raises_not_found() -> None:
    transport = StubTransport(responses=[StubResponse(_json={})])
    conn = _connector(transport)
    with pytest.raises(SCMNotFoundError):
        asyncio.run(conn.resolve_commit(RepoRef("github", "a", "b", ""), ref="nope"))


# ---------------------------------------------------------------------------
# Research-mode helpers (search_code, list_repos_tiered_star, CodeSearchHit)
# ---------------------------------------------------------------------------


def test_search_code_yields_hits_and_paginates() -> None:
    item = {
        "path": "src/app.py",
        "html_url": "https://github.com/acme/repo1/blob/main/src/app.py",
        "sha": "abc123",
        "score": 1.5,
        "repository": _REPO_JSON,
    }
    next_url = "https://api.github.com/search/code?page=2"
    page1 = StubResponse(headers={"Link": f'<{next_url}>; rel="next"'}, _json={"items": [item]})
    page2 = StubResponse(_json={"items": [{**item, "path": "src/two.py"}]})
    transport = StubTransport(responses=[page1, page2])
    conn = _connector(transport)
    hits = _drain(conn.search_code("foo", page_size=1))
    assert all(isinstance(h, CodeSearchHit) for h in hits)
    assert [h.path for h in hits] == ["src/app.py", "src/two.py"]
    assert hits[0].repo.name == "repo1"
    assert hits[0].score == 1.5


def test_search_code_handles_missing_repository_and_score() -> None:
    item = {"path": "p", "html_url": "u", "sha": "s"}  # no repository, no score
    transport = StubTransport(responses=[StubResponse(_json={"items": [item, "junk"]})])
    conn = _connector(transport)
    hits = _drain(conn.search_code("q"))
    assert len(hits) == 1
    assert hits[0].repo.name == ""
    assert hits[0].score == 0.0


def test_list_repos_tiered_star_dedupes_across_tiers() -> None:
    # Tier 1 yields repo1; tier 2 re-yields repo1 (deduped) + repo2.
    tier1 = StubResponse(_json={"items": [_REPO_JSON]})
    tier2 = StubResponse(_json={"items": [_REPO_JSON, {**_REPO_JSON, "name": "repo2"}]})
    # remaining two tiers (10, 0) return empty item lists
    empty = StubResponse(_json={"items": []})
    transport = StubTransport(responses=[tier1, tier2, empty, empty])
    conn = _connector(transport)
    repos = _drain(conn.list_repos_tiered_star(query="lang:python"))
    assert [r.name for r in repos] == ["repo1", "repo2"]
    # first tier uses an inclusive lower bound; later tiers use a banded range
    assert transport.calls[0][2]["params"]["q"] == "lang:python stars:>=1000"
    assert transport.calls[1][2]["params"]["q"] == "lang:python stars:100..999"


def test_list_repos_tiered_star_handles_non_list_items() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"items": None})] * 4)
    conn = _connector(transport)
    assert _drain(conn.list_repos_tiered_star(query="q", star_tiers=(0,))) == []


# ---------------------------------------------------------------------------
# integrations.github shim (search_repositories) — AC-SCM-02c
# ---------------------------------------------------------------------------


def test_search_repositories_shim_drives_connector() -> None:
    transport = StubTransport(responses=[StubResponse(_json={"items": [_REPO_JSON]})])
    conn = _connector(transport)
    repos = search_repositories("lang:python", connector=conn, star_tiers=(0,))
    assert isinstance(repos, list)
    assert repos[0].name == "repo1"


def test_v2_argv_shim_is_not_implemented() -> None:
    from integrations.github import _v2_argv_shim

    with pytest.raises(NotImplementedError):
        _v2_argv_shim(["--query", "x"])

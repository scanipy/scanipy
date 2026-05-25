"""CMP-SCM-02 — GitHub connector.

Concrete `SCMConnector` subclass for GitHub.com and GitHub Enterprise
(`SDD.md §3 CMP-SCM-02`; DOC-CMP-SCM-02). Implements the six abstract methods
of `CMP-SCM-01` over the GitHub REST + webhook surfaces and additionally
exposes GitHub-only Research-mode helpers (`search_code`,
`list_repos_tiered_star`) that are *not* part of the provider-neutral ABC
(DOC §3.3; restricted to `CMP-RES-01`).

Design (matches the rest of the SCM subsystem, which is stdlib-only + injected
seams — see `integrations/scm/_http.py`):

  * **Injected async HTTP transport.** The connector performs no real I/O of its
    own; it calls an injected `AsyncHTTPTransport` whose responses satisfy the
    `_http.HTTPResponseLike` shape (`status_code`, case-insensitive `headers`,
    `text`) plus a `json()` accessor. This keeps the connector free of any
    third-party HTTP dependency and fully unit-testable.
  * **Injected git runner.** `clone()` shells out through an injected
    `GitRunner` callable; the default runner uses `asyncio.create_subprocess_exec`
    over the pinned `git` binary. Tests inject a recording stub.
  * **Shared retry/backoff.** Every REST call is wrapped with `CMP-SCM-05`'s
    `with_retry` + `classify_github`, so the GitHub default backoff curve and
    primary/secondary rate-limit honouring apply uniformly (DOC §3.4).

`CMP-SCM-02` emits no findings and threads **no** provenance fields — it is
upstream of the provenance chain (DOC §5, §8; RULE-6 non-touch). It never sets
`origin`, `S_version`, `env_digest`, or `cpg_order_hash`.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from integrations.scm._http import (
    GITHUB_DEFAULT,
    RetryPolicy,
    classify_github,
    with_retry,
)
from integrations.scm.base import (
    CloneMetadata,
    RepoRef,
    SCMAuthError,
    SCMConnector,
    SCMCredentials,
    SCMNotFoundError,
    SCMTransientError,
    WebhookSubscription,
)

__all__ = [
    "AsyncHTTPTransport",
    "CodeSearchHit",
    "GitHubConnector",
    "GitRunner",
    "HTTPResponse",
]


# ---------------------------------------------------------------------------
# Injected transport + git-runner seams (DOC §3.1; client-agnostic per
# DOC-CMP-SCM-05 §3.5). No third-party dependency is imported here.
# ---------------------------------------------------------------------------


@runtime_checkable
class HTTPResponse(Protocol):
    """Response surface read by the connector.

    A superset of `_http.HTTPResponseLike` (which reads `status_code`,
    `headers`, `text`): the connector additionally decodes a JSON body via
    `json()`. Any client whose response exposes these satisfies the contract.
    """

    status_code: int
    headers: Mapping[str, str]
    text: str

    def json(self) -> Any: ...  # noqa: ANN401 — provider JSON is an opaque shape


@runtime_checkable
class AsyncHTTPTransport(Protocol):
    """Minimal async HTTP transport the connector calls (DOC §3.1).

    Implementations perform the actual network I/O; the connector stays pure.
    `headers`/`params`/`json` are optional per request.
    """

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,  # noqa: ANN401 — request body is an opaque shape
    ) -> HTTPResponse: ...


# A git runner takes the argv (after the `git` program name) and a cwd, runs it,
# and returns (returncode, stdout, stderr). The default runner shells out to the
# pinned `git` binary; tests inject a recording stub. Async to match clone().
GitRunner = Callable[[Sequence[str], Path], Awaitable[tuple[int, str, str]]]


@dataclass(frozen=True, slots=True)
class CodeSearchHit:
    """A single GitHub code-search result row (Research mode; DOC §3.3).

    Out-of-band of the SAST scan path. Shape mirrors the fields a v2 caller
    consumed; `repo` is the owning repository, `path` the file path within it.
    """

    repo: RepoRef
    path: str
    html_url: str
    sha: str
    score: float


async def _default_git_runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    """Default git runner: exec the pinned `git` binary via asyncio subprocess.

    Off the determinism partition; performs the only real I/O in this module.
    """
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        "git",
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return (
        proc.returncode if proc.returncode is not None else -1,
        out.decode("utf-8", "replace"),
        err.decode("utf-8", "replace"),
    )


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class GitHubConnector(SCMConnector):
    """GitHub.com / GitHub Enterprise connector. AC-SCM-02a..c."""

    provider_id: ClassVar[str] = "github"

    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        transport: AsyncHTTPTransport,
        api_base_url: str = "https://api.github.com",  # override for GHE
        retry_policy: RetryPolicy | None = None,  # default = §3.4 GitHub curve
        git_runner: GitRunner | None = None,
    ) -> None:
        super().__init__(credentials)
        self._transport = transport
        self._api_base_url = api_base_url.rstrip("/")
        self._retry_policy = retry_policy if retry_policy is not None else GITHUB_DEFAULT
        self._git_runner: GitRunner = git_runner if git_runner is not None else _default_git_runner

    # ---- internal REST plumbing -------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build the Authorization + Accept headers from the credential envelope.

        PAT and app-installation modes both present a bearer token on the wire
        (the installation token is minted just-in-time by the caller and placed
        in the payload under `token`; never persisted — DOC §4.3). OAuth carries
        an `access_token`.
        """
        payload = self._credentials.payload
        token = payload.get("token") or payload.get("access_token")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,  # noqa: ANN401 — request body is an opaque shape
    ) -> HTTPResponse:
        """Perform one retried REST call and map terminal statuses to errors.

        The `with_retry` decorator (CMP-SCM-05) retries rate-limited responses
        (via `classify_github`) and `SCMTransientError`; 5xx is raised as
        transient *inside* the call so the budget applies. Non-retryable
        terminal statuses (401/403-bad-creds/404) are mapped after the retried
        call returns a non-rate-limited response (DOC §7).
        """
        url = path if path.startswith("http") else f"{self._api_base_url}{path}"
        headers = self._auth_headers()

        @with_retry(policy=self._retry_policy, classify=classify_github)
        async def _call() -> HTTPResponse:
            resp = await self._transport.request(
                method, url, headers=headers, params=params, json=json
            )
            if resp.status_code >= 500:
                # Retryable transient (DOC §7). Rate-limited 403/429 is handled
                # by classify_github on the returned response, NOT here.
                raise SCMTransientError(f"GitHub {resp.status_code} on {method} {path}")
            return resp

        resp = await _call()
        self._raise_for_terminal_status(resp, method, path)
        return resp

    @staticmethod
    def _raise_for_terminal_status(resp: HTTPResponse, method: str, path: str) -> None:
        """Map a non-rate-limited terminal status to the SCM error hierarchy.

        Rate-limited 403/429 never reaches here — `with_retry` consumed it. A
        403 that survives is a genuine auth/permission failure (DOC §7 table).
        """
        status = resp.status_code
        if status == 404:
            raise SCMNotFoundError(f"GitHub 404 on {method} {path}")
        if status in (401, 403):
            raise SCMAuthError(f"GitHub {status} on {method} {path}: {resp.text[:200]}")
        if status >= 400:
            # Any other 4xx is non-retryable and unexpected; surface verbatim.
            raise SCMTransientError(f"GitHub {status} on {method} {path}: {resp.text[:200]}")

    @staticmethod
    def _next_link(resp: HTTPResponse) -> str | None:
        """Extract the `rel="next"` URL from a GitHub `Link` header, if present.

        Cursor pagination per DOC §3.2. Returns the absolute next-page URL or
        None when there is no further page.
        """
        link = resp.headers.get("Link") or resp.headers.get("link")
        if not link:
            return None
        for part in link.split(","):
            segments = part.split(";")
            if len(segments) < 2:
                continue
            url_seg = segments[0].strip()
            if not (url_seg.startswith("<") and url_seg.endswith(">")):
                continue
            rels = {s.strip() for s in segments[1:]}
            if 'rel="next"' in rels:
                return url_seg[1:-1]
        return None

    def _repo_ref_from_json(self, obj: Mapping[str, Any]) -> RepoRef:
        """Build a provider='github' RepoRef from a GitHub repository object."""
        owner = obj.get("owner", {})
        owner_login = owner.get("login") if isinstance(owner, Mapping) else None
        return RepoRef(
            provider="github",
            owner=str(owner_login) if owner_login is not None else "",
            name=str(obj.get("name", "")),
            clone_url=str(obj.get("clone_url", "")),
            default_branch=(
                str(obj["default_branch"]) if obj.get("default_branch") is not None else None
            ),
        )

    # ---- ABC method 1 : list_repos ----------------------------------------

    async def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every repository under `org_or_workspace` (DOC §3.2).

        GET /orgs/{org}/repos?per_page={page_size}; cursor-paginates via the
        `Link` header until `rel="next"` is absent.
        """
        path: str | None = f"/orgs/{org_or_workspace}/repos"
        params: Mapping[str, str] | None = {"per_page": str(page_size)}
        while path is not None:
            resp = await self._request("GET", path, params=params)
            body = resp.json()
            if isinstance(body, list):
                for obj in body:
                    if isinstance(obj, Mapping):
                        yield self._repo_ref_from_json(obj)
            path = self._next_link(resp)
            params = None  # the next-link URL already carries its query string

    # ---- ABC method 2 : clone ---------------------------------------------

    async def clone(
        self,
        repo_ref: RepoRef,
        *,
        commit_sha: str,
        dest_dir: Path,
        shallow: bool = True,
    ) -> CloneMetadata:
        """Materialise the working tree at `commit_sha` into `dest_dir` (DOC §3.2).

        Uses HTTPS clone with the installation token / PAT injected into the
        clone URL's userinfo, then `git fetch` + `git checkout` the exact SHA.
        `shallow=True` ⇒ `--depth=1`. Returns CloneMetadata feeding CMP-SNAP-01.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        authed_url = self._authed_clone_url(repo_ref.clone_url)

        init_args = ["init", "--quiet"]
        await self._run_git(init_args, dest_dir)
        await self._run_git(["remote", "add", "origin", authed_url], dest_dir)

        fetch_args = ["fetch", "--quiet"]
        if shallow:
            fetch_args.append("--depth=1")
        fetch_args += ["origin", commit_sha]
        await self._run_git(fetch_args, dest_dir)
        await self._run_git(["checkout", "--quiet", commit_sha], dest_dir)

        resolved = await self._git_rev_parse(dest_dir, "HEAD")
        parents = await self._git_parents(dest_dir, resolved)
        return CloneMetadata(
            provider="github",
            repo_ref=repo_ref,
            commit_sha=resolved,
            parent_shas=parents,
            cloned_at=datetime.now(UTC),
            bytes_on_disk=self._tree_bytes(dest_dir),
            shallow=shallow,
        )

    def _authed_clone_url(self, clone_url: str) -> str:
        """Inject the bearer token into an HTTPS clone URL's userinfo.

        The token is used in-memory only and never written to disk (DOC §4.3).
        SSH clone URLs are returned unchanged (key auth handled by the runner).
        """
        payload = self._credentials.payload
        token = payload.get("token") or payload.get("access_token")
        if not token or not clone_url.startswith("https://"):
            return clone_url
        rest = clone_url[len("https://") :]
        return f"https://x-access-token:{token}@{rest}"

    async def _run_git(self, argv: Sequence[str], cwd: Path) -> str:
        """Run a git subcommand via the injected runner; raise on non-zero."""
        code, out, err = await self._git_runner(argv, cwd)
        if code != 0:
            raise SCMTransientError(f"git {argv[0]} failed (exit {code}): {err.strip()[:300]}")
        return out

    async def _git_rev_parse(self, cwd: Path, ref: str) -> str:
        out = await self._run_git(["rev-parse", ref], cwd)
        return out.strip()

    async def _git_parents(self, cwd: Path, sha: str) -> tuple[str, ...]:
        """Return parent SHAs of `sha` (empty for a root/shallow-grafted commit)."""
        code, out, _err = await self._git_runner(["rev-list", "--parents", "-n", "1", sha], cwd)
        if code != 0 or not out.strip():
            return ()
        parts = out.strip().split()
        return tuple(parts[1:])  # first token is the commit itself

    @staticmethod
    def _tree_bytes(dest_dir: Path) -> int:
        total = 0
        for p in dest_dir.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    # ---- ABC method 3 : register_webhook ----------------------------------

    async def register_webhook(
        self,
        repo_ref: RepoRef,
        *,
        target_url: str,
        events: tuple[str, ...],
        secret: str,
    ) -> WebhookSubscription:
        """Create the repo webhook (DOC §3.2).

        POST /repos/{owner}/{repo}/hooks with config.secret = `secret`,  # pragma: allowlist secret
        content_type = 'json'. Idempotent on (owner, repo, target_url): an
        existing hook with the same target is reused rather than duplicated.
        """
        owner, name = repo_ref.owner, repo_ref.name
        existing = await self._find_existing_hook(owner, name, target_url)
        if existing is not None:
            hook_id = existing
        else:
            resp = await self._request(
                "POST",
                f"/repos/{owner}/{name}/hooks",
                json={
                    "name": "web",
                    "active": True,
                    "events": list(events),
                    "config": {
                        "url": target_url,
                        "content_type": "json",
                        "secret": secret,
                    },
                },
            )
            body = resp.json()
            hook_id = str(body.get("id")) if isinstance(body, Mapping) else ""
        return WebhookSubscription(
            provider="github",
            repo_ref=repo_ref,
            webhook_id=hook_id,
            target_url=target_url,
            events=events,
            # Opaque ref to the encrypted secret blob owned by CMP-CP-02 — not a secret.
            secret_ref="github-webhook-secret",  # noqa: S106  # pragma: allowlist secret
            created_at=datetime.now(UTC),
        )

    async def _find_existing_hook(self, owner: str, name: str, target_url: str) -> str | None:
        """Return the id of an existing hook with this target_url, else None."""
        resp = await self._request("GET", f"/repos/{owner}/{name}/hooks")
        body = resp.json()
        if not isinstance(body, list):
            return None
        for hook in body:
            if not isinstance(hook, Mapping):
                continue
            config = hook.get("config", {})
            if isinstance(config, Mapping) and config.get("url") == target_url:
                hook_id = hook.get("id")
                return str(hook_id) if hook_id is not None else None
        return None

    # ---- ABC method 4 : verify_webhook ------------------------------------

    def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        secret: str,
    ) -> bool:
        """Verify the GitHub `X-Hub-Signature-256` HMAC-SHA256 signature (DOC §3.2).

        Scheme: header value = "sha256=" + HMAC-SHA256(secret, raw_body), hex.
        Constant-time comparison via `hmac.compare_digest`. Returns False on any
        mismatch / missing / malformed header; never raises (DOC §7 predicate).
        """
        provided = self._lookup_header(headers, "X-Hub-Signature-256")
        if not provided or not provided.startswith("sha256="):
            return False
        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        expected = "sha256=" + digest
        return hmac.compare_digest(provided, expected)

    def sign_webhook(self, *, raw_body: bytes, secret: str) -> dict[str, str]:
        """Test hook: produce the header a genuine GitHub delivery would carry.

        Used by the conformance harness (`_signature_headers`) to drive the
        positive `verify_webhook` case provider-neutrally. Not a production path.
        """
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return {"X-Hub-Signature-256": sig}

    @staticmethod
    def _lookup_header(headers: Mapping[str, str], name: str) -> str | None:
        """Case-insensitive header lookup over a plain mapping."""
        direct = headers.get(name)
        if direct is not None:
            return direct
        lowered = name.lower()
        for key, value in headers.items():
            if key.lower() == lowered:
                return value
        return None

    # ---- ABC method 5 : get_default_branch --------------------------------

    async def get_default_branch(self, repo_ref: RepoRef) -> str:
        """GET /repos/{owner}/{repo} -> .default_branch (DOC §3.2)."""
        resp = await self._request("GET", f"/repos/{repo_ref.owner}/{repo_ref.name}")
        body = resp.json()
        branch = body.get("default_branch") if isinstance(body, Mapping) else None
        if not branch:
            raise SCMNotFoundError(f"no default_branch for {repo_ref.owner}/{repo_ref.name}")
        return str(branch)

    # ---- ABC method 6 : resolve_commit ------------------------------------

    async def resolve_commit(self, repo_ref: RepoRef, *, ref: str) -> str:
        """GET /repos/{owner}/{repo}/commits/{ref} -> .sha (DOC §3.2)."""
        resp = await self._request("GET", f"/repos/{repo_ref.owner}/{repo_ref.name}/commits/{ref}")
        body = resp.json()
        sha = body.get("sha") if isinstance(body, Mapping) else None
        if not sha:
            raise SCMNotFoundError(
                f"could not resolve ref {ref!r} in {repo_ref.owner}/{repo_ref.name}"
            )
        return str(sha)

    # ---- GitHub-only extensions (Research mode; CMP-RES-01; DOC §3.3) ------

    async def search_code(
        self,
        query: str,
        *,
        page_size: int = 50,
    ) -> AsyncIterator[CodeSearchHit]:
        """GitHub-only code search (Research mode; CMP-RES-01; DOC §3.3).

        MUST NOT be invoked from production scan paths. Not on `SCMConnector`;
        a static type-checker rejects a `GitHubConnector` substituted into an
        `SCMConnector` slot that calls this (DOC §3.3, T-CMP-SCM-02-02).
        """
        path: str | None = "/search/code"
        params: Mapping[str, str] | None = {"q": query, "per_page": str(page_size)}
        while path is not None:
            resp = await self._request("GET", path, params=params)
            body = resp.json()
            items = body.get("items") if isinstance(body, Mapping) else None
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, Mapping):
                        yield self._code_hit_from_json(item)
            path = self._next_link(resp)
            params = None

    def _code_hit_from_json(self, item: Mapping[str, Any]) -> CodeSearchHit:
        repo_obj = item.get("repository", {})
        repo = (
            self._repo_ref_from_json(repo_obj)
            if isinstance(repo_obj, Mapping)
            else RepoRef(provider="github", owner="", name="", clone_url="")
        )
        return CodeSearchHit(
            repo=repo,
            path=str(item.get("path", "")),
            html_url=str(item.get("html_url", "")),
            sha=str(item.get("sha", "")),
            score=float(item.get("score", 0.0) or 0.0),
        )

    async def list_repos_tiered_star(
        self,
        *,
        query: str,
        star_tiers: tuple[int, ...] = (1000, 100, 10, 0),
    ) -> AsyncIterator[RepoRef]:
        """Tiered-star repository discovery helper (Research mode; DOC §3.3).

        Preserved from v2 `integrations/github/github.py` per AC-SCM-02b: walks
        the star tiers high→low, issuing one `GET /search/repositories` query per
        tier band (`stars:>=hi` intersected with `stars:<prev`), de-duplicating
        repos already yielded so each repo surfaces in its highest matching tier.
        GitHub-only. (Byte-for-byte regression vs. v2 is BLOCKED on CLAR-SCM-01;
        this implementation reproduces the documented tiering behaviour.)
        """
        seen: set[tuple[str, str]] = set()
        upper: int | None = None  # exclusive upper bound from the previous tier
        for tier in star_tiers:
            qualifier = f"stars:>={tier}" if upper is None else f"stars:{tier}..{upper - 1}"
            tier_query = f"{query} {qualifier}".strip()
            path: str | None = "/search/repositories"
            params: Mapping[str, str] | None = {"q": tier_query, "sort": "stars", "order": "desc"}
            while path is not None:
                resp = await self._request("GET", path, params=params)
                body = resp.json()
                items = body.get("items") if isinstance(body, Mapping) else None
                if isinstance(items, list):
                    for obj in items:
                        if not isinstance(obj, Mapping):
                            continue
                        ref = self._repo_ref_from_json(obj)
                        key = (ref.owner, ref.name)
                        if key in seen:
                            continue
                        seen.add(key)
                        yield ref
                path = self._next_link(resp)
                params = None
            upper = tier

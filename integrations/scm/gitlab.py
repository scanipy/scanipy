"""CMP-SCM-03 — GitLab connector.

Concrete `SCMConnector` subclass for GitLab.com and self-hosted GitLab
(`SDD.md §3 CMP-SCM-03`; DOC-CMP-SCM-03). Implements the six abstract methods
of `CMP-SCM-01` over the GitLab REST v4 + webhook surfaces. Unlike GitHub
(`CMP-SCM-02`), GitLab exposes no Research-mode helpers (DOC §3.5).

Design (matches the rest of the SCM subsystem — stdlib-only + injected seams,
see `integrations/scm/_http.py`):

  * **Injected async HTTP transport.** The connector performs no real I/O of
    its own; it calls an injected `AsyncHTTPTransport` whose responses satisfy
    the `_http.HTTPResponseLike` shape (`status_code`, case-insensitive
    `headers`, `text`) plus a `json()` accessor. No third-party HTTP dependency.
  * **Injected git runner.** `clone()` shells out through an injected
    `GitRunner`; the default runner uses `asyncio.create_subprocess_exec` over
    the pinned `git` binary. Tests inject a recording stub.
  * **Shared retry/backoff.** Every REST call is wrapped with `CMP-SCM-05`'s
    `with_retry` + `classify_gitlab`, so the GitLab default backoff curve and
    `429`/`Retry-After` honouring apply uniformly (DOC §3.4).

`CMP-SCM-03` emits no findings and threads **no** provenance fields — it is
upstream of the provenance chain (DOC §5, §8; RULE-6 non-touch). It never sets
`origin`, `S_version`, `env_digest`, or `cpg_order_hash`.
"""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable
from urllib.parse import quote

from integrations.scm._http import (
    GITLAB_DEFAULT,
    RetryPolicy,
    classify_gitlab,
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
    "GitLabConnector",
    "GitRunner",
    "HTTPResponse",
]


# ---------------------------------------------------------------------------
# Injected transport + git-runner seams (DOC §3.1; client-agnostic per
# DOC-CMP-SCM-05 §3.5). Defined locally — structurally identical to the
# protocols CMP-SCM-02 declares in github.py; kept per-module so SCM-03 has no
# cross-connector import dependency (PR-merge ordering hazard avoidance).
# ---------------------------------------------------------------------------


@runtime_checkable
class HTTPResponse(Protocol):
    """Response surface read by the connector (superset of HTTPResponseLike)."""

    status_code: int
    headers: Mapping[str, str]
    text: str

    def json(self) -> Any: ...  # noqa: ANN401 — provider JSON is an opaque shape


@runtime_checkable
class AsyncHTTPTransport(Protocol):
    """Minimal async HTTP transport the connector calls (DOC §3.1)."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,  # noqa: ANN401 — request body is an opaque shape
    ) -> HTTPResponse: ...


# (returncode, stdout, stderr) for a git argv (after the `git` program name).
GitRunner = Callable[[Sequence[str], Path], Awaitable[tuple[int, str, str]]]


async def _default_git_runner(argv: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    """Default git runner: exec the pinned `git` binary via asyncio subprocess."""
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


def _project_id(repo_ref: RepoRef) -> str:
    """URL-encoded `group/name` project identifier for GitLab REST paths.

    GitLab accepts the URL-encoded `namespace/path` in place of a numeric id
    (e.g. `acme%2Fwidgets`). `owner` carries the group/namespace.
    """
    full_path = f"{repo_ref.owner}/{repo_ref.name}" if repo_ref.owner else repo_ref.name
    return quote(full_path, safe="")


class GitLabConnector(SCMConnector):
    """GitLab.com / self-hosted GitLab. AC-SCM-03a..c."""

    provider_id: ClassVar[str] = "gitlab"

    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        transport: AsyncHTTPTransport,
        api_base_url: str = "https://gitlab.com/api/v4",
        retry_policy: RetryPolicy | None = None,
        git_runner: GitRunner | None = None,
    ) -> None:
        super().__init__(credentials)
        self._transport = transport
        self._api_base_url = api_base_url.rstrip("/")
        self._retry_policy = retry_policy if retry_policy is not None else GITLAB_DEFAULT
        self._git_runner: GitRunner = git_runner if git_runner is not None else _default_git_runner

    # ---- internal REST plumbing -------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers from the credential envelope.

        GitLab PATs go in `PRIVATE-TOKEN`; OAuth bearer tokens in
        `Authorization: Bearer` (DOC §4.1).
        """
        payload = self._credentials.payload
        headers: dict[str, str] = {"Accept": "application/json"}
        token = payload.get("token")
        access_token = payload.get("access_token")
        if token:
            headers["PRIVATE-TOKEN"] = token
        elif access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Any | None = None,  # noqa: ANN401 — request body is an opaque shape
    ) -> HTTPResponse:
        """Perform one retried REST call and map terminal statuses to errors."""
        url = path if path.startswith("http") else f"{self._api_base_url}{path}"
        headers = self._auth_headers()

        @with_retry(policy=self._retry_policy, classify=classify_gitlab)
        async def _call() -> HTTPResponse:
            resp = await self._transport.request(
                method, url, headers=headers, params=params, json=json
            )
            if resp.status_code >= 500:
                raise SCMTransientError(f"GitLab {resp.status_code} on {method} {path}")
            return resp

        resp = await _call()
        self._raise_for_terminal_status(resp, method, path)
        return resp

    @staticmethod
    def _raise_for_terminal_status(resp: HTTPResponse, method: str, path: str) -> None:
        """Map a non-rate-limited terminal status to the SCM error hierarchy (DOC §7)."""
        status = resp.status_code
        if status == 404:
            raise SCMNotFoundError(f"GitLab 404 on {method} {path}")
        if status in (401, 403):
            raise SCMAuthError(f"GitLab {status} on {method} {path}: {resp.text[:200]}")
        if status >= 400:
            raise SCMTransientError(f"GitLab {status} on {method} {path}: {resp.text[:200]}")

    def _repo_ref_from_json(self, obj: Mapping[str, Any]) -> RepoRef:
        """Build a provider='gitlab' RepoRef from a GitLab project object."""
        namespace = obj.get("namespace", {})
        ns_path = namespace.get("full_path") if isinstance(namespace, Mapping) else None
        return RepoRef(
            provider="gitlab",
            owner=str(ns_path) if ns_path is not None else "",
            name=str(obj.get("path", obj.get("name", ""))),
            clone_url=str(obj.get("http_url_to_repo", "")),
            default_branch=(
                str(obj["default_branch"]) if obj.get("default_branch") is not None else None
            ),
        )

    @staticmethod
    def _next_page(resp: HTTPResponse) -> str | None:
        """GitLab keyset/offset pagination: the `X-Next-Page` header, if non-empty."""
        nxt = resp.headers.get("X-Next-Page") or resp.headers.get("x-next-page")
        return nxt if nxt else None

    # ---- ABC method 1 : list_repos ----------------------------------------

    async def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every project under the named group (DOC §3.2).

        GET /groups/{group}/projects?per_page={page_size}; offset-paginates via
        the `X-Next-Page` header until it is absent/empty.
        """
        group = quote(org_or_workspace, safe="")
        path = f"/groups/{group}/projects"
        page = "1"
        while page:
            resp = await self._request(
                "GET", path, params={"per_page": str(page_size), "page": page}
            )
            body = resp.json()
            if isinstance(body, list):
                for obj in body:
                    if isinstance(obj, Mapping):
                        yield self._repo_ref_from_json(obj)
            nxt = self._next_page(resp)
            page = nxt if nxt is not None else ""

    # ---- ABC method 2 : clone ---------------------------------------------

    async def clone(
        self,
        repo_ref: RepoRef,
        *,
        commit_sha: str,
        dest_dir: Path,
        shallow: bool = True,
    ) -> CloneMetadata:
        """Materialise the working tree at `commit_sha` into `dest_dir` (DOC §3.2)."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        authed_url = self._authed_clone_url(repo_ref.clone_url)

        await self._run_git(["init", "--quiet"], dest_dir)
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
            provider="gitlab",
            repo_ref=repo_ref,
            commit_sha=resolved,
            parent_shas=parents,
            cloned_at=datetime.now(UTC),
            bytes_on_disk=self._tree_bytes(dest_dir),
            shallow=shallow,
        )

    def _authed_clone_url(self, clone_url: str) -> str:
        """Inject a token into an HTTPS clone URL's userinfo (in-memory only; DOC §4.3).

        GitLab uses `oauth2:<token>@host` for both PAT and OAuth tokens. SSH
        clone URLs are returned unchanged (key auth handled by the runner).
        """
        payload = self._credentials.payload
        token = payload.get("token") or payload.get("access_token")
        if not token or not clone_url.startswith("https://"):
            return clone_url
        rest = clone_url[len("https://") :]
        return f"https://oauth2:{token}@{rest}"

    async def _run_git(self, argv: Sequence[str], cwd: Path) -> str:
        code, out, err = await self._git_runner(argv, cwd)
        if code != 0:
            raise SCMTransientError(f"git {argv[0]} failed (exit {code}): {err.strip()[:300]}")
        return out

    async def _git_rev_parse(self, cwd: Path, ref: str) -> str:
        out = await self._run_git(["rev-parse", ref], cwd)
        return out.strip()

    async def _git_parents(self, cwd: Path, sha: str) -> tuple[str, ...]:
        code, out, _err = await self._git_runner(["rev-list", "--parents", "-n", "1", sha], cwd)
        if code != 0 or not out.strip():
            return ()
        return tuple(out.strip().split()[1:])

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
        """Create the project hook (DOC §3.2).

        POST /projects/{id}/hooks with `token` = `secret` (GitLab's shared
        secret is echoed back in the `X-Gitlab-Token` header on delivery).
        Idempotent on (project, target_url): an existing hook with the same
        target is reused rather than duplicated.
        """
        pid = _project_id(repo_ref)
        existing = await self._find_existing_hook(pid, target_url)
        if existing is not None:
            hook_id = existing
        else:
            resp = await self._request(
                "POST",
                f"/projects/{pid}/hooks",
                json={
                    "url": target_url,
                    "token": secret,
                    "push_events": "push" in events,
                    "merge_requests_events": "pull_request" in events,
                    "enable_ssl_verification": True,
                },
            )
            body = resp.json()
            hook_id = str(body.get("id")) if isinstance(body, Mapping) else ""
        return WebhookSubscription(
            provider="gitlab",
            repo_ref=repo_ref,
            webhook_id=hook_id,
            target_url=target_url,
            events=events,
            secret_ref="gitlab-webhook-secret",  # noqa: S106  # pragma: allowlist secret
            created_at=datetime.now(UTC),
        )

    async def _find_existing_hook(self, pid: str, target_url: str) -> str | None:
        resp = await self._request("GET", f"/projects/{pid}/hooks")
        body = resp.json()
        if not isinstance(body, list):
            return None
        for hook in body:
            if isinstance(hook, Mapping) and hook.get("url") == target_url:
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
        """Verify the GitLab `X-Gitlab-Token` shared-secret header (DOC §3.3).

        GitLab's native scheme is *not* an HMAC over the body: the delivery
        carries the registered secret verbatim in `X-Gitlab-Token`, compared
        constant-time against the expected secret. A forged delivery (wrong /
        absent token) returns False; never raises (DOC §7 predicate).

        Note (DOC §3.3 / AC-SCM-03b): because the token is body-independent, the
        per-provider negative test forges the *token* (not a body byte) — a
        body-byte tamper alone cannot be detected by GitLab's native scheme, and
        claiming otherwise would misrepresent the provider's guarantee.
        """
        provided = self._lookup_header(headers, "X-Gitlab-Token")
        if provided is None:
            return False
        return hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8"))

    def sign_webhook(self, *, raw_body: bytes, secret: str) -> dict[str, str]:
        """Test hook: produce the `X-Gitlab-Token` header a genuine delivery carries.

        Used by the conformance harness (`_signature_headers`) to drive the
        positive `verify_webhook` case provider-neutrally. Not a production path.
        The token is body-independent (GitLab's native scheme; DOC §3.3).
        """
        return {"X-Gitlab-Token": secret}

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
        """GET /projects/{id} -> .default_branch (DOC §3.2)."""
        resp = await self._request("GET", f"/projects/{_project_id(repo_ref)}")
        body = resp.json()
        branch = body.get("default_branch") if isinstance(body, Mapping) else None
        if not branch:
            raise SCMNotFoundError(f"no default_branch for {repo_ref.owner}/{repo_ref.name}")
        return str(branch)

    # ---- ABC method 6 : resolve_commit ------------------------------------

    async def resolve_commit(self, repo_ref: RepoRef, *, ref: str) -> str:
        """GET /projects/{id}/repository/commits/{ref} -> .id (DOC §3.2)."""
        encoded_ref = quote(ref, safe="")
        resp = await self._request(
            "GET", f"/projects/{_project_id(repo_ref)}/repository/commits/{encoded_ref}"
        )
        body = resp.json()
        sha = body.get("id") if isinstance(body, Mapping) else None
        if not sha:
            raise SCMNotFoundError(
                f"could not resolve ref {ref!r} in {repo_ref.owner}/{repo_ref.name}"
            )
        return str(sha)

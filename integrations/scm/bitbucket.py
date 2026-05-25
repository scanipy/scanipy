"""CMP-SCM-03 — Bitbucket connector.

Concrete `SCMConnector` subclass for Bitbucket Cloud (Bitbucket Server via
`api_base_url` override) (`SDD.md §3 CMP-SCM-03`; DOC-CMP-SCM-03). Implements
the six abstract methods of `CMP-SCM-01` over the Bitbucket REST 2.0 + webhook
surfaces. No Research-mode helpers (DOC §3.5).

Design mirrors the rest of the SCM subsystem — stdlib-only + injected seams
(see `integrations/scm/_http.py`):

  * **Injected async HTTP transport** (no third-party HTTP dependency).
  * **Injected git runner** for `clone()`.
  * **Shared retry/backoff** via `CMP-SCM-05`'s `with_retry` + `classify_bitbucket`
    (429 + `Retry-After`; `X-Bitbucket-Type: abuse` → secondary; DOC §3.4).

`CMP-SCM-03` emits no findings and threads **no** provenance fields — upstream
of the provenance chain (DOC §5, §8; RULE-6 non-touch).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from integrations.scm._http import (
    BITBUCKET_DEFAULT,
    RetryPolicy,
    classify_bitbucket,
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
    "BitbucketConnector",
    "GitRunner",
    "HTTPResponse",
]


# ---------------------------------------------------------------------------
# Injected transport + git-runner seams (DOC §3.1; client-agnostic per
# DOC-CMP-SCM-05 §3.5). Defined locally per-module (no cross-connector import).
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


class BitbucketConnector(SCMConnector):
    """Bitbucket Cloud (and Server via override). AC-SCM-03a..c."""

    provider_id: ClassVar[str] = "bitbucket"

    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        transport: AsyncHTTPTransport,
        api_base_url: str = "https://api.bitbucket.org/2.0",
        retry_policy: RetryPolicy | None = None,
        git_runner: GitRunner | None = None,
    ) -> None:
        super().__init__(credentials)
        self._transport = transport
        self._api_base_url = api_base_url.rstrip("/")
        self._retry_policy = retry_policy if retry_policy is not None else BITBUCKET_DEFAULT
        self._git_runner: GitRunner = git_runner if git_runner is not None else _default_git_runner

    # ---- internal REST plumbing -------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers from the credential envelope.

        Bitbucket app passwords / access tokens both present a bearer token
        (`Authorization: Bearer`). DOC §4.1.
        """
        payload = self._credentials.payload
        token = payload.get("access_token") or payload.get("token")
        headers: dict[str, str] = {"Accept": "application/json"}
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
        """Perform one retried REST call and map terminal statuses to errors."""
        url = path if path.startswith("http") else f"{self._api_base_url}{path}"
        headers = self._auth_headers()

        @with_retry(policy=self._retry_policy, classify=classify_bitbucket)
        async def _call() -> HTTPResponse:
            resp = await self._transport.request(
                method, url, headers=headers, params=params, json=json
            )
            if resp.status_code >= 500:
                raise SCMTransientError(f"Bitbucket {resp.status_code} on {method} {path}")
            return resp

        resp = await _call()
        self._raise_for_terminal_status(resp, method, path)
        return resp

    @staticmethod
    def _raise_for_terminal_status(resp: HTTPResponse, method: str, path: str) -> None:
        """Map a non-rate-limited terminal status to the SCM error hierarchy (DOC §7)."""
        status = resp.status_code
        if status == 404:
            raise SCMNotFoundError(f"Bitbucket 404 on {method} {path}")
        if status in (401, 403):
            raise SCMAuthError(f"Bitbucket {status} on {method} {path}: {resp.text[:200]}")
        if status >= 400:
            raise SCMTransientError(f"Bitbucket {status} on {method} {path}: {resp.text[:200]}")

    def _repo_ref_from_json(self, obj: Mapping[str, Any]) -> RepoRef:
        """Build a provider='bitbucket' RepoRef from a repository object.

        The HTTPS clone URL lives in `links.clone[]` where `name == 'https'`;
        the workspace slug is `workspace.slug`.
        """
        workspace = obj.get("workspace", {})
        ws_slug = workspace.get("slug") if isinstance(workspace, Mapping) else None
        clone_url = ""
        links = obj.get("links", {})
        if isinstance(links, Mapping):
            clone_list = links.get("clone", [])
            if isinstance(clone_list, list):
                for entry in clone_list:
                    if isinstance(entry, Mapping) and entry.get("name") == "https":
                        clone_url = str(entry.get("href", ""))
                        break
        mainbranch = obj.get("mainbranch", {})
        default_branch = mainbranch.get("name") if isinstance(mainbranch, Mapping) else None
        return RepoRef(
            provider="bitbucket",
            owner=str(ws_slug) if ws_slug is not None else "",
            name=str(obj.get("slug", obj.get("name", ""))),
            clone_url=clone_url,
            default_branch=str(default_branch) if default_branch is not None else None,
        )

    @staticmethod
    def _next_url(resp: HTTPResponse) -> str | None:
        """Bitbucket cursor pagination: the top-level `next` URL in the body."""
        body = resp.json()
        if isinstance(body, Mapping):
            nxt = body.get("next")
            if isinstance(nxt, str) and nxt:
                return nxt
        return None

    # ---- ABC method 1 : list_repos ----------------------------------------

    async def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every repository in the named workspace (DOC §3.2).

        GET /repositories/{workspace}?pagelen={page_size}; cursor-paginates via
        the body's `next` URL until it is absent.
        """
        url: str | None = f"/repositories/{org_or_workspace}"
        params: Mapping[str, str] | None = {"pagelen": str(page_size)}
        while url is not None:
            resp = await self._request("GET", url, params=params)
            body = resp.json()
            values = body.get("values", []) if isinstance(body, Mapping) else []
            if isinstance(values, list):
                for obj in values:
                    if isinstance(obj, Mapping):
                        yield self._repo_ref_from_json(obj)
            url = self._next_url(resp)
            params = None  # the next URL already carries its query string

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
            provider="bitbucket",
            repo_ref=repo_ref,
            commit_sha=resolved,
            parent_shas=parents,
            cloned_at=datetime.now(UTC),
            bytes_on_disk=self._tree_bytes(dest_dir),
            shallow=shallow,
        )

    def _authed_clone_url(self, clone_url: str) -> str:
        """Inject a token into an HTTPS clone URL's userinfo (in-memory only; DOC §4.3).

        Bitbucket uses `x-token-auth:<token>@host`. SSH URLs returned unchanged.
        """
        payload = self._credentials.payload
        token = payload.get("access_token") or payload.get("token")
        if not token or not clone_url.startswith("https://"):
            return clone_url
        rest = clone_url[len("https://") :]
        return f"https://x-token-auth:{token}@{rest}"

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
        """Create the repository webhook (DOC §3.2).

        POST /repositories/{ws}/{repo}/hooks with `secret` = `secret`  # pragma: allowlist secret
        (echoed back as an HMAC-SHA256 over the body in `X-Hub-Signature` on
        delivery). Idempotent on (ws, repo, target_url).
        """
        ws, repo = repo_ref.owner, repo_ref.name
        existing = await self._find_existing_hook(ws, repo, target_url)
        if existing is not None:
            hook_id = existing
        else:
            resp = await self._request(
                "POST",
                f"/repositories/{ws}/{repo}/hooks",
                json={
                    "description": "Scanipy",
                    "url": target_url,
                    "active": True,
                    "secret": secret,
                    "events": list(self._map_events(events)),
                },
            )
            body = resp.json()
            hook_id = str(body.get("uuid")) if isinstance(body, Mapping) else ""
        return WebhookSubscription(
            provider="bitbucket",
            repo_ref=repo_ref,
            webhook_id=hook_id,
            target_url=target_url,
            events=events,
            secret_ref="bitbucket-webhook-secret",  # noqa: S106  # pragma: allowlist secret
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _map_events(events: tuple[str, ...]) -> tuple[str, ...]:
        """Map provider-neutral event names to Bitbucket event keys."""
        mapping = {"push": "repo:push", "pull_request": "pullrequest:created"}
        return tuple(mapping.get(e, e) for e in events)

    async def _find_existing_hook(self, ws: str, repo: str, target_url: str) -> str | None:
        resp = await self._request("GET", f"/repositories/{ws}/{repo}/hooks")
        body = resp.json()
        values = body.get("values", []) if isinstance(body, Mapping) else []
        if not isinstance(values, list):
            return None
        for hook in values:
            if isinstance(hook, Mapping) and hook.get("url") == target_url:
                uuid = hook.get("uuid")
                return str(uuid) if uuid is not None else None
        return None

    # ---- ABC method 4 : verify_webhook ------------------------------------

    def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        secret: str,
    ) -> bool:
        """Verify the Bitbucket `X-Hub-Signature` HMAC-SHA256 signature (DOC §3.3).

        Scheme: header value = "sha256=" + HMAC-SHA256(secret, raw_body), hex.
        Constant-time comparison via `hmac.compare_digest`. Returns False on any
        mismatch / missing / malformed header; never raises (DOC §7 predicate).
        """
        provided = self._lookup_header(headers, "X-Hub-Signature")
        if not provided or not provided.startswith("sha256="):
            return False
        digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        expected = "sha256=" + digest
        return hmac.compare_digest(provided, expected)

    def sign_webhook(self, *, raw_body: bytes, secret: str) -> dict[str, str]:
        """Test hook: produce the `X-Hub-Signature` header a genuine delivery carries.

        Used by the conformance harness (`_signature_headers`). Not production.
        """
        sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return {"X-Hub-Signature": sig}

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
        """GET /repositories/{ws}/{repo} -> .mainbranch.name (DOC §3.2)."""
        resp = await self._request("GET", f"/repositories/{repo_ref.owner}/{repo_ref.name}")
        body = resp.json()
        mainbranch = body.get("mainbranch", {}) if isinstance(body, Mapping) else {}
        branch = mainbranch.get("name") if isinstance(mainbranch, Mapping) else None
        if not branch:
            raise SCMNotFoundError(f"no mainbranch for {repo_ref.owner}/{repo_ref.name}")
        return str(branch)

    # ---- ABC method 6 : resolve_commit ------------------------------------

    async def resolve_commit(self, repo_ref: RepoRef, *, ref: str) -> str:
        """GET /repositories/{ws}/{repo}/commit/{ref} -> .hash (DOC §3.2)."""
        resp = await self._request(
            "GET", f"/repositories/{repo_ref.owner}/{repo_ref.name}/commit/{ref}"
        )
        body = resp.json()
        sha = body.get("hash") if isinstance(body, Mapping) else None
        if not sha:
            raise SCMNotFoundError(
                f"could not resolve ref {ref!r} in {repo_ref.owner}/{repo_ref.name}"
            )
        return str(sha)

"""CMP-SCM-03 — Azure DevOps connector.

Concrete `SCMConnector` subclass for Azure DevOps Services
(`SDD.md §3 CMP-SCM-03`; DOC-CMP-SCM-03). Implements the six abstract methods
of `CMP-SCM-01` over the Azure DevOps REST + service-hook surfaces. No
Research-mode helpers (DOC §3.5).

Design mirrors the rest of the SCM subsystem — stdlib-only + injected seams
(see `integrations/scm/_http.py`):

  * **Injected async HTTP transport** (no third-party HTTP dependency).
  * **Injected git runner** for `clone()`.
  * **Shared retry/backoff** via `CMP-SCM-05`'s `with_retry` +
    `classify_azure_devops` (429; max(Retry-After, X-RateLimit-Delay) wins;
    DOC §3.4).

`CMP-SCM-03` emits no findings and threads **no** provenance fields — upstream
of the provenance chain (DOC §5, §8; RULE-6 non-touch).

Webhook signature: DOC-CMP-SCM-03 §3.3 and DOC-API §2.4 state ADO "pins
HMAC-SHA-256" but do not name the signature *header* (`X-Vss-Activityid` is an
activity id, not a signature). The interim scheme below pins HMAC-SHA-256 over
the raw body under an `X-Hub-Signature-256` header (the GitHub-style scheme the
DOC says ADO mirrors on algorithm). This is tracked by CLAR-SCM-02 — see the
`# TODO: CLAR-SCM-02` markers; the negative test (`AC-SCM-03b`) holds for any
HMAC-over-body header, so the choice does not affect forgery rejection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from integrations.scm._http import (
    AZURE_DEVOPS_DEFAULT,
    RetryPolicy,
    classify_azure_devops,
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
    "AzureDevOpsConnector",
    "GitRunner",
    "HTTPResponse",
]

# Azure DevOps REST API version query parameter (pinned).
_API_VERSION = "7.1"


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


class AzureDevOpsConnector(SCMConnector):
    """Azure DevOps Services. AC-SCM-03a..c."""

    provider_id: ClassVar[str] = "azure-devops"

    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        organization: str,
        transport: AsyncHTTPTransport,
        api_base_url: str = "https://dev.azure.com",
        retry_policy: RetryPolicy | None = None,
        git_runner: GitRunner | None = None,
    ) -> None:
        super().__init__(credentials)
        self._organization = organization
        self._transport = transport
        self._api_base_url = api_base_url.rstrip("/")
        self._retry_policy = retry_policy if retry_policy is not None else AZURE_DEVOPS_DEFAULT
        self._git_runner: GitRunner = git_runner if git_runner is not None else _default_git_runner

    # ---- internal REST plumbing -------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers from the credential envelope.

        ADO PATs authenticate via HTTP Basic with an empty username and the PAT
        as the password (base64 of `:<token>`); OAuth uses a bearer. DOC §4.1.
        """
        payload = self._credentials.payload
        headers: dict[str, str] = {"Accept": "application/json"}
        token = payload.get("token")
        access_token = payload.get("access_token")
        if token:
            basic = base64.b64encode(f":{token}".encode()).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"
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
        """Perform one retried REST call and map terminal statuses to errors.

        The pinned `api-version` query parameter is added to every relative
        request (absolute follow-on URLs are sent verbatim).
        """
        if path.startswith("http"):
            # Absolute follow-on URLs already carry their own query string
            # (including api-version); send them verbatim.
            url = path
            merged: Mapping[str, str] | None = params
        else:
            url = f"{self._api_base_url}{path}"
            built: dict[str, str] = {"api-version": _API_VERSION}
            if params:
                built.update(params)
            merged = built
        headers = self._auth_headers()

        @with_retry(policy=self._retry_policy, classify=classify_azure_devops)
        async def _call() -> HTTPResponse:
            resp = await self._transport.request(
                method, url, headers=headers, params=merged, json=json
            )
            if resp.status_code >= 500:
                raise SCMTransientError(f"AzureDevOps {resp.status_code} on {method} {path}")
            return resp

        resp = await _call()
        self._raise_for_terminal_status(resp, method, path)
        return resp

    @staticmethod
    def _raise_for_terminal_status(resp: HTTPResponse, method: str, path: str) -> None:
        """Map a non-rate-limited terminal status to the SCM error hierarchy (DOC §7)."""
        status = resp.status_code
        if status == 404:
            raise SCMNotFoundError(f"AzureDevOps 404 on {method} {path}")
        if status in (401, 403):
            raise SCMAuthError(f"AzureDevOps {status} on {method} {path}: {resp.text[:200]}")
        if status >= 400:
            raise SCMTransientError(f"AzureDevOps {status} on {method} {path}: {resp.text[:200]}")

    def _repo_ref_from_json(self, obj: Mapping[str, Any], *, project: str) -> RepoRef:
        """Build a provider='azure-devops' RepoRef from a repository object.

        ADO `owner` is encoded as `org/project` so downstream REST paths can be
        reconstructed; the HTTPS clone URL is `remoteUrl`.
        """
        return RepoRef(
            provider="azure-devops",
            owner=f"{self._organization}/{project}",
            name=str(obj.get("name", "")),
            clone_url=str(obj.get("remoteUrl", "")),
            default_branch=self._short_branch(obj.get("defaultBranch")),
        )

    @staticmethod
    def _short_branch(default_branch: object) -> str | None:
        """Strip the `refs/heads/` prefix ADO returns on `defaultBranch`."""
        if not default_branch:
            return None
        name = str(default_branch)
        prefix = "refs/heads/"
        return name[len(prefix) :] if name.startswith(prefix) else name

    def _split_owner(self, repo_ref: RepoRef) -> tuple[str, str]:
        """Split a `org/project` owner into (org, project); fall back to the connector org.

        A bare owner (no `/`, e.g. an externally-constructed RepoRef) is a project
        name; the organization is the connector's configured org — never the
        project name itself, which would build `dev.azure.com/{proj}/{proj}/...`.
        """
        if "/" in repo_ref.owner:
            org, project = repo_ref.owner.split("/", 1)
            return org, project
        return self._organization, repo_ref.owner

    # ---- ABC method 1 : list_repos ----------------------------------------

    async def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every git repository in the named project (DOC §3.2).

        GET /{org}/{project}/_apis/git/repositories. `org_or_workspace` is the
        ADO project. The git-repository list endpoint returns the full set in
        one `value` array (no cursor), so no pagination loop is required.
        """
        project = org_or_workspace
        resp = await self._request("GET", f"/{self._organization}/{project}/_apis/git/repositories")
        body = resp.json()
        values = body.get("value", []) if isinstance(body, Mapping) else []
        if isinstance(values, list):
            for obj in values:
                if isinstance(obj, Mapping):
                    yield self._repo_ref_from_json(obj, project=project)

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
            provider="azure-devops",
            repo_ref=repo_ref,
            commit_sha=resolved,
            parent_shas=parents,
            cloned_at=datetime.now(UTC),
            bytes_on_disk=self._tree_bytes(dest_dir),
            shallow=shallow,
        )

    def _authed_clone_url(self, clone_url: str) -> str:
        """Inject a PAT into an HTTPS clone URL's userinfo (in-memory only; DOC §4.3).

        ADO accepts `pat:<token>@host` over HTTPS. SSH URLs returned unchanged.
        """
        payload = self._credentials.payload
        token = payload.get("token") or payload.get("access_token")
        if not token or not clone_url.startswith("https://"):
            return clone_url
        rest = clone_url[len("https://") :]
        return f"https://pat:{token}@{rest}"

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
        """Create a service-hook subscription (DOC §3.2).

        POST /{org}/_apis/hooks/subscriptions with the web-hooks consumer,
        consumerInputs.url = `target_url`, consumerInputs.basicAuthPassword =
        `secret` (the subscription consumer secret used to HMAC deliveries).
        Idempotent on (project repo, target_url).
        """
        org, project = self._split_owner(repo_ref)
        existing = await self._find_existing_subscription(org, target_url)
        if existing is not None:
            sub_id = existing
        else:
            resp = await self._request(
                "POST",
                f"/{org}/_apis/hooks/subscriptions",
                json={
                    "publisherId": "tfs",
                    "eventType": "git.push",
                    "resourceVersion": "1.0",
                    "consumerId": "webHooks",
                    "consumerActionId": "httpRequest",
                    "publisherInputs": {"projectId": project, "repository": repo_ref.name},
                    "consumerInputs": {
                        "url": target_url,
                        "basicAuthPassword": secret,
                    },
                },
            )
            body = resp.json()
            sub_id = str(body.get("id")) if isinstance(body, Mapping) else ""
        return WebhookSubscription(
            provider="azure-devops",
            repo_ref=repo_ref,
            webhook_id=sub_id,
            target_url=target_url,
            events=events,
            secret_ref="azure-devops-webhook-secret",  # noqa: S106  # pragma: allowlist secret
            created_at=datetime.now(UTC),
        )

    async def _find_existing_subscription(self, org: str, target_url: str) -> str | None:
        resp = await self._request("GET", f"/{org}/_apis/hooks/subscriptions")
        body = resp.json()
        values = body.get("value", []) if isinstance(body, Mapping) else []
        if not isinstance(values, list):
            return None
        for sub in values:
            if not isinstance(sub, Mapping):
                continue
            inputs = sub.get("consumerInputs", {})
            if isinstance(inputs, Mapping) and inputs.get("url") == target_url:
                sub_id = sub.get("id")
                return str(sub_id) if sub_id is not None else None
        return None

    # ---- ABC method 4 : verify_webhook ------------------------------------

    def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        secret: str,
    ) -> bool:
        """Verify the service-hook HMAC-SHA256 signature over the raw body (DOC §3.3).

        # TODO: CLAR-SCM-02 — DOC-CMP-SCM-03 §3.3 / DOC-API §2.4 pin HMAC-SHA-256
        # but do not name the ADO signature header. Interim: GitHub-style
        # `X-Hub-Signature-256` = "sha256=" + HMAC-SHA256(secret, raw_body), hex.
        # The connector pins HMAC-SHA-256 and rejects anything else (DOC §3.3
        # "rejects subscriptions configured otherwise"). The negative test holds
        # for any HMAC-over-body header, so the header-name choice is non-binding
        # on AC-SCM-03b.

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
        """Test hook: produce the header a genuine service-hook delivery carries.

        Used by the conformance harness (`_signature_headers`). Not production.
        # TODO: CLAR-SCM-02 — header name pending the ADO scheme decision.
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
        """GET /{org}/{project}/_apis/git/repositories/{name} -> .defaultBranch (DOC §3.2)."""
        org, project = self._split_owner(repo_ref)
        resp = await self._request(
            "GET", f"/{org}/{project}/_apis/git/repositories/{repo_ref.name}"
        )
        body = resp.json()
        raw = body.get("defaultBranch") if isinstance(body, Mapping) else None
        branch = self._short_branch(raw)
        if not branch:
            raise SCMNotFoundError(f"no defaultBranch for {repo_ref.owner}/{repo_ref.name}")
        return branch

    # ---- ABC method 6 : resolve_commit ------------------------------------

    async def resolve_commit(self, repo_ref: RepoRef, *, ref: str) -> str:
        """Resolve `ref` to a 40-hex commit id (DOC §3.2).

        GET /{org}/{project}/_apis/git/repositories/{name}/commits with
        `searchCriteria.itemVersion.version` = `ref`, top 1 → `.value[0].commitId`.
        """
        org, project = self._split_owner(repo_ref)
        resp = await self._request(
            "GET",
            f"/{org}/{project}/_apis/git/repositories/{repo_ref.name}/commits",
            params={
                "searchCriteria.itemVersion.version": ref,
                "searchCriteria.$top": "1",
            },
        )
        body = resp.json()
        values = body.get("value", []) if isinstance(body, Mapping) else []
        if isinstance(values, list) and values and isinstance(values[0], Mapping):
            sha = values[0].get("commitId")
            if sha:
                return str(sha)
        raise SCMNotFoundError(f"could not resolve ref {ref!r} in {repo_ref.owner}/{repo_ref.name}")

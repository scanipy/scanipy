"""CMP-SCM-01 — SCMConnector abstract base + provider-neutral value types.

Provider-neutral interface for repository access and webhook lifecycle
(SDD.md §3 CMP-SCM-01; DOC-CMP-SCM-01). This module declares:

  * the `SCMCredentials` value type and `SCMAuthMode` enum (DOC §3.1, §4.1);
  * the `RepoRef`, `WebhookSubscription`, `CloneMetadata` value types (DOC §3.2, §4.2);
  * the `SCMConnector` ABC with exactly six typed abstract methods (AC-SCM-01a);
  * the `SCMError` hierarchy (DOC §7).

`CMP-SCM-01` emits no findings and threads no provenance fields — it is upstream
of every finding-emitting component (DOC §5, §8; RULE-6 non-touch).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import ClassVar, Literal

__all__ = [
    "CloneMetadata",
    "RepoRef",
    "SCMAuthError",
    "SCMAuthMode",
    "SCMConnector",
    "SCMCredentials",
    "SCMError",
    "SCMNotFoundError",
    "SCMRateLimitError",
    "SCMSignatureMismatch",
    "SCMTransientError",
    "WebhookSubscription",
]

# ---------------------------------------------------------------------------
# Error hierarchy (DOC-CMP-SCM-01 §7)
# ---------------------------------------------------------------------------


class SCMError(Exception):
    """Base class for every SCM-connector error (DOC §7)."""


class SCMAuthError(SCMError):
    """Credentials are wrong or revoked. Not retryable; propagate to caller."""


class SCMNotFoundError(SCMError):
    """Repo, ref, or commit does not exist (or is invisible to credentials)."""


class SCMRateLimitError(SCMError):
    """Shared retry budget (CMP-SCM-05) exhausted. Escalated after budget."""


class SCMSignatureMismatch(SCMError):  # noqa: N818 — name fixed verbatim by DOC-CMP-SCM-01 §7
    """Webhook signature did not match.

    Note: `verify_webhook` returns ``False`` rather than raising this — the
    predicate contract is boolean (DOC §7). The class exists for completeness
    and for callers that wish to surface a mismatch as a fault elsewhere.
    """


class SCMTransientError(SCMError):
    """Transient 5xx / connection reset. Retryable under CMP-SCM-05."""


# ---------------------------------------------------------------------------
# Credential value type (DOC-CMP-SCM-01 §3.1, §4.1)
# ---------------------------------------------------------------------------


class SCMAuthMode(str, Enum):  # (str, Enum) fixed verbatim by DOC-CMP-SCM-01 §3.1
    """Authentication mode carried by an `SCMCredentials` envelope."""

    PAT = "pat"  # personal access token (string secret)
    APP = "app_installation"  # GitHub App / GitLab App installation
    OAUTH = "oauth"  # 3-legged OAuth bearer (with refresh)
    SSH_KEY = "ssh_key"  # SSH private key for clone-over-ssh


@dataclass(frozen=True, slots=True)
class SCMCredentials:
    """Provider-neutral credential envelope.

    All four auth modes share a single representation that round-trips through
    encryption at rest (`CMP-CP-02`; mocked by `T-CMP-SCM-01-04` until that
    component is available). `AC-SCM-01b`.

    `payload` is an opaque, mode-dependent mapping of string keys to string
    values (no binary). The required keys per mode are documented in
    DOC-CMP-SCM-01 §4.1.
    """

    provider: Literal["github", "gitlab", "bitbucket", "azure-devops"]
    mode: SCMAuthMode
    payload: Mapping[str, str]
    # Set by the storage layer; absent on freshly constructed in-memory instances.
    encrypted_at: str | None = None  # RFC3339; populated by CMP-CP-02
    key_version: int | None = None  # KMS CMK version that wrapped payload


# ---------------------------------------------------------------------------
# Repository / webhook / clone value types (DOC-CMP-SCM-01 §3.2, §4.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RepoRef:
    """Identifies a repository across providers."""

    provider: str  # 'github' | 'gitlab' | 'bitbucket' | 'azure-devops'
    owner: str  # GH org / GL group / BB workspace / ADO org-project
    name: str
    clone_url: str  # provider-native HTTPS or SSH clone URL
    default_branch: str | None = None


@dataclass(frozen=True, slots=True)
class WebhookSubscription:
    """Server-side record of a registered webhook."""

    provider: str
    repo_ref: RepoRef
    webhook_id: str  # provider-issued id
    target_url: str  # public Scanipy endpoint (DOC-API §4.6)
    events: tuple[str, ...]  # ('push', 'pull_request', 'repository')
    secret_ref: str  # opaque ref to encrypted secret in CMP-CP-02
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CloneMetadata:
    """Clone-time provenance feed-forward for CMP-SNAP-01 (DOC §4.2)."""

    provider: str
    repo_ref: RepoRef
    commit_sha: str  # 40 hex; resolved value, not the requested ref
    parent_shas: tuple[str, ...]
    cloned_at: datetime  # RFC3339 UTC; provenance input for CMP-SNAP-01
    bytes_on_disk: int
    shallow: bool


# ---------------------------------------------------------------------------
# Abstract base class (AC-SCM-01a — exactly six methods, no more, no fewer)
# ---------------------------------------------------------------------------


class SCMConnector(ABC):
    """Abstract base for all SCM providers. AC-SCM-01a.

    Concrete connectors (CMP-SCM-02 GitHub, CMP-SCM-03 GL/BB/ADO) implement the
    six abstract methods below and must pass the conformance suite
    (`integrations.scm.conformance.run_conformance_suite`) before being wired
    into orchestration.
    """

    provider_id: ClassVar[str]  # set by subclass; e.g. 'github'. NOT abstract.

    def __init__(self, credentials: SCMCredentials) -> None:
        self._credentials = credentials

    # ---- 1 -----------------------------------------------------------------
    @abstractmethod
    def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every repository visible to `credentials` under the named
        org/workspace. Paginates internally; caller iterates to exhaustion.

        Raises `SCMAuthError` if credentials are invalid, `SCMRateLimitError`
        when the shared retry budget (CMP-SCM-05) is exceeded.
        """

    # ---- 2 -----------------------------------------------------------------
    @abstractmethod
    async def clone(
        self,
        repo_ref: RepoRef,
        *,
        commit_sha: str,  # 40-hex Git commit SHA
        dest_dir: Path,
        shallow: bool = True,
    ) -> CloneMetadata:
        """Materialise the working tree at `commit_sha` into `dest_dir`.

        Returns CloneMetadata recording the commit SHA, parent SHAs, and
        clone-time provenance fields (DOC §4.2).
        """

    # ---- 3 -----------------------------------------------------------------
    @abstractmethod
    async def register_webhook(
        self,
        repo_ref: RepoRef,
        *,
        target_url: str,
        events: tuple[str, ...],
        secret: str,  # plain shared secret; encrypted at rest
    ) -> WebhookSubscription:
        """Create or replace the webhook subscription for this repo.

        Idempotent on `(repo_ref, target_url)`.
        """

    # ---- 4 -----------------------------------------------------------------
    @abstractmethod
    def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        secret: str,
    ) -> bool:
        """Verify the provider-specific signature on an inbound webhook
        delivery. Returns True iff the payload is authentic.

        Per-provider signature scheme: see DOC-API.md §2.4. This method is a
        boolean predicate, not a fault path — a mismatch returns False and
        raises nothing (DOC §7). AC-SCM-03b (negative test) is discharged at
        the concrete-connector level — this method only declares the contract.
        """

    # ---- 5 -----------------------------------------------------------------
    @abstractmethod
    async def get_default_branch(self, repo_ref: RepoRef) -> str:
        """Return the canonical default-branch name (e.g. 'main', 'master',
        'trunk') as the provider currently records it.
        """

    # ---- 6 -----------------------------------------------------------------
    @abstractmethod
    async def resolve_commit(
        self,
        repo_ref: RepoRef,
        *,
        ref: str,  # branch name | tag | short SHA | symbolic
    ) -> str:
        """Resolve `ref` to a 40-hex commit SHA.

        Same `ref` MUST resolve to the same SHA across providers when the repo
        is mirror-identical (AC-SCM-03c). Raises `SCMNotFoundError` on unknown
        ref.
        """

# DOC-CMP-SCM-01 — SCMConnector abstract base

> **Source-of-truth:** `SDD.md §3 CMP-SCM-01`. Where this document diverges from `SDD.md` / `PLAN.md`, the upstream document wins; correct this file rather than the upstream.
> **Status contract:** This doc satisfies `AC-DOC-04` — a code-writing agent reading only this file plus the cross-cutting refs can implement `CMP-SCM-01` without re-reading the SDD.

---

## 1. Component identity

| Field | Value |
|---|---|
| CMP-ID | `CMP-SCM-01` |
| Name | `SCMConnector` abstract base |
| Subsystem | SCM Integration (`SDD.md §3`) |
| Staging | `cross-cutting` (no language gate) |
| Depends-On | none — `CMP-CP-02` is mockable until available (`SDD.md` line 66; `WBS.md §5`) |
| WBS phase | Phase 2 — Generalise SCM (`WBS.md §5`) |
| Owning maintainer | unassigned — tracked under [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) (DEFERRED) |

---

## 2. Mandate

**Verbatim `Purpose:` (`SDD.md` line 62):**
> Provider-neutral interface for repository access and webhook lifecycle.

**Operational role.** `CMP-SCM-01` is the contract between the rest of Scanipy and every supported source-control provider (GitHub / GHE, GitLab, Bitbucket, Azure DevOps — `SDD.md §1.1`). It (i) declares the abstract methods every concrete connector (`CMP-SCM-02`, `CMP-SCM-03`) must implement; (ii) defines the `SCMCredentials` value type that uniformly encapsulates PAT, app installation, OAuth, and SSH-key authentication modes so credentials can be round-tripped through the encrypted-at-rest store (`CMP-CP-02`); and (iii) defines the **conformance test suite** that every concrete connector must pass before it is wired into orchestration. By holding the interface and the conformance harness at the same address, this component is the single point at which a new SCM is added: adding a fifth provider means writing one subclass and passing the same suite, with no upstream caller change. `CMP-SCM-01` does **not** emit findings, does **not** stamp `origin`, `S_version`, `env_digest`, or `cpg_order_hash`, and does **not** drive HTTP I/O directly — that lives in `CMP-SCM-05` (shared retry/backoff) and the concrete subclasses.

---

## 3. Interface contract

All signatures are Python 3.11+ with `from __future__ import annotations`. Module path: `integrations/scm/base.py` (`PLAN.md` line 157).

### 3.1 `SCMCredentials` value type

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Mapping

class SCMAuthMode(str, Enum):
    PAT             = "pat"               # personal access token (string secret)
    APP             = "app_installation"  # GitHub App / GitLab App installation
    OAUTH           = "oauth"             # 3-legged OAuth bearer (with refresh)
    SSH_KEY         = "ssh_key"           # SSH private key for clone-over-ssh

@dataclass(frozen=True, slots=True)
class SCMCredentials:
    """Provider-neutral credential envelope.

    All four auth modes share a single representation that round-trips through
    encryption at rest (`CMP-CP-02`; mocked by `T-CMP-SCM-01-04` until that
    component is available). `AC-SCM-01b`.
    """
    provider:        Literal["github", "gitlab", "bitbucket", "azure-devops"]
    mode:            SCMAuthMode
    # Opaque, mode-dependent payload. Mode-specific shape documented in §4.1.
    payload:         Mapping[str, str]
    # Set by the storage layer; absent on freshly constructed in-memory instances.
    encrypted_at:    str | None = None       # RFC3339; populated by CMP-CP-02
    key_version:     int  | None = None      # KMS CMK version that wrapped payload
```

### 3.2 The abstract base class

`AC-SCM-01a` mandates **six** typed methods. No more, no fewer.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Mapping

@dataclass(frozen=True, slots=True)
class RepoRef:
    """Identifies a repository across providers."""
    provider:  str            # 'github' | 'gitlab' | 'bitbucket' | 'azure-devops'
    owner:     str            # GH org / GL group / BB workspace / ADO org-project
    name:      str
    clone_url: str            # provider-native HTTPS or SSH clone URL
    default_branch: str | None = None

@dataclass(frozen=True, slots=True)
class WebhookSubscription:
    """Server-side record of a registered webhook."""
    provider:    str
    repo_ref:    RepoRef
    webhook_id:  str                    # provider-issued id
    target_url:  str                    # public Scanipy endpoint (DOC-API §4.6)
    events:      tuple[str, ...]        # ('push', 'pull_request', 'repository')
    secret_ref:  str                    # opaque ref to encrypted secret in CMP-CP-02
    created_at:  datetime

class SCMConnector(ABC):
    """Abstract base for all SCM providers. AC-SCM-01a."""

    provider_id: str                    # set by subclass; e.g. 'github'

    def __init__(self, credentials: SCMCredentials) -> None:
        self._credentials = credentials

    # ---- 1 -----------------------------------------------------------------
    @abstractmethod
    async def list_repos(
        self,
        *,
        org_or_workspace: str,
        page_size: int = 100,
    ) -> AsyncIterator[RepoRef]:
        """Yield every repository visible to `credentials` under the named
        org/workspace. Paginates internally; caller iterates to exhaustion.
        Raises `SCMAuthError` if credentials are invalid, `SCMRateLimitError`
        when the shared retry budget (CMP-SCM-05) is exceeded."""

    # ---- 2 -----------------------------------------------------------------
    @abstractmethod
    async def clone(
        self,
        repo_ref: RepoRef,
        *,
        commit_sha: str,                # 40-hex Git commit SHA
        dest_dir: Path,
        shallow: bool = True,
    ) -> "CloneMetadata":
        """Materialise the working tree at `commit_sha` into `dest_dir`.
        Returns CloneMetadata recording the commit SHA, parent SHAs, and
        clone-time provenance fields (§4.2)."""

    # ---- 3 -----------------------------------------------------------------
    @abstractmethod
    async def register_webhook(
        self,
        repo_ref: RepoRef,
        *,
        target_url: str,
        events: tuple[str, ...],
        secret: str,                    # plain shared secret; encrypted at rest
    ) -> WebhookSubscription:
        """Create or replace the webhook subscription for this repo. Idempotent
        on `(repo_ref, target_url)`."""

    # ---- 4 -----------------------------------------------------------------
    @abstractmethod
    def verify_webhook(
        self,
        *,
        raw_body: bytes,
        headers:  Mapping[str, str],
        secret:   str,
    ) -> bool:
        """Verify the provider-specific signature on an inbound webhook
        delivery. Returns True iff the payload is authentic.
        Per-provider signature scheme: see DOC-API.md §2.4.
        AC-SCM-03b (negative test) is discharged at the concrete-connector
        level — this method only declares the contract."""

    # ---- 5 -----------------------------------------------------------------
    @abstractmethod
    async def get_default_branch(self, repo_ref: RepoRef) -> str:
        """Return the canonical default-branch name (e.g. 'main', 'master',
        'trunk') as the provider currently records it."""

    # ---- 6 -----------------------------------------------------------------
    @abstractmethod
    async def resolve_commit(
        self,
        repo_ref: RepoRef,
        *,
        ref: str,                       # branch name | tag | short SHA | symbolic
    ) -> str:
        """Resolve `ref` to a 40-hex commit SHA. Same `ref` MUST resolve to the
        same SHA across providers when the repo is mirror-identical
        (AC-SCM-03c). Raises `SCMNotFoundError` on unknown ref."""
```

### 3.3 Conformance test suite (`AC-SCM-01c`)

Module path: `integrations/scm/conformance.py`. Exposes:

```python
@dataclass(frozen=True, slots=True)
class ConformanceFailure:
    method:    str              # ABC method name that failed
    reason:    str              # short description (e.g. "wrong type returned")
    detail:    str              # full repr / traceback excerpt

@dataclass(frozen=True, slots=True)
class ConformanceReport:
    provider:  str                                # connector.provider_id
    passed:    tuple[str, ...]                    # names of methods that passed
    failures:  tuple[ConformanceFailure, ...]     # empty ⇒ conformant
    @property
    def is_conformant(self) -> bool:
        return not self.failures

async def run_conformance_suite(
    connector: SCMConnector,
    *,
    fixture_repo: RepoRef,
    canary_commit_sha: str,
) -> ConformanceReport:
    """Drive `connector` through a fixed sequence of operations (list, clone,
    register_webhook, verify_webhook positive + negative, get_default_branch,
    resolve_commit) and assert provider-neutral behaviour. The same suite is
    invoked by TST-AC-SCM-02a (GitHub) and TST-AC-SCM-03a (GL/BB/ADO)."""
```

The suite is **declarative** and lives next to the ABC so that adding a fifth provider is one subclass and one suite invocation.

---

## 4. Inputs and outputs

### 4.1 `SCMCredentials.payload` shape per mode

| Mode | Required keys | Notes |
|---|---|---|
| `pat` | `token` | Provider PAT or GHE PAT. |
| `app_installation` | `app_id`, `installation_id`, `private_key_pem` | Used to mint installation tokens at call time. |
| `oauth` | `access_token`, `refresh_token`, `expires_at` | Refreshed via CMP-CP-02 on `expires_at` proximity. |
| `ssh_key` | `private_key_pem`, `known_hosts` | Used only for `clone()`; never for REST. |

All payload values are strings (no binary). The encryption-at-rest contract (`AC-SCM-01b`) requires that any `SCMCredentials` instance can be serialised, encrypted by `CMP-CP-02`, persisted, retrieved, decrypted, and deserialised to an instance equal to the original under structural equality — for all four modes.

### 4.2 `CloneMetadata` (returned by `clone()`)

```python
@dataclass(frozen=True, slots=True)
class CloneMetadata:
    provider:        str
    repo_ref:        RepoRef
    commit_sha:      str            # 40 hex; resolved value, not the requested ref
    parent_shas:     tuple[str, ...]
    cloned_at:       datetime       # RFC3339 UTC; provenance input for CMP-SNAP-01
    bytes_on_disk:   int
    shallow:         bool
```

`CloneMetadata.commit_sha` is the single value `CMP-SNAP-01` uses to populate `provenance_records.commit_sha` (see [`DOC-PROVENANCE` §3](../cross-cutting/DOC-PROVENANCE.md#3-full-chain-schema-provenance_records-table)). `provider` is what populates `provenance_records.scm_provider`.

### 4.3 Side effects and persisted artifacts

- `register_webhook()` creates a provider-side resource (cleanup is the concrete subclass's responsibility on deregister).
- `clone()` writes to `dest_dir`; the caller (`CMP-SNAP-01` worker) owns the directory lifecycle.
- `SCMCredentials` round-trips through the encrypted `scm_credentials` table (`SDD.md` line 167; schema deferred to `CMP-CP-03` / [`DOC-DB`](../cross-cutting/DOC-DB.md)).
- No SARIF, no findings, no provenance records are written by this component.

---

## 5. Invariants touched

The discharge here is largely **non-touch**: this component does not emit a finding, so it does not set the four required provenance fields (RULE-6).

| Invariant | This component | Discharge |
|---|---|---|
| [INV-1](../cross-cutting/DOC-INV.md#3-inv-1--determinism-partition) | does not touch | `origin` is set by `CMP-ORCH-03` at finding emission; SCM never reads or writes `origin`. |
| [INV-2](../cross-cutting/DOC-INV.md#4-inv-2--versioned-parameters) | does not touch | `S_version` is supplied by the scan submitter via `CMP-ORCH-01`; `env_digest` is computed from the container image digest by `CMP-SNAP-01`. SCM **does** stamp `commit_sha` and `provider` (4.2 above) but these are not `S_version` / `env_digest`. |
| [INV-3](../cross-cutting/DOC-INV.md#5-inv-3--llm-off-the-detection-path) | does not touch | No LLM on this code path. |
| [INV-4](../cross-cutting/DOC-INV.md#6-inv-4--one-sided-undecidable-approximations) | does not touch | No undecidable approximations are made by the connector. |
| [INV-5](../cross-cutting/DOC-INV.md#7-inv-5--conditional-labels-are-self-describing) | does not touch | `cpg_order_hash` is set by `CMP-CORE-03`; SCM never sees it. |
| [INV-6](../cross-cutting/DOC-INV.md#8-inv-6--per-language-honesty) | does not touch | No detection happens here. |

The corresponding `TST-INV-*` tests are owned by the components above; **no `TST-INV-*` is attached to `CMP-SCM-01`** (`WBS.md §5` records "Invariants threaded: none direct"). The code-review checklist in `.claude/rules/02-provenance.md §"How to verify threading"` confirms the non-touch.

---

## 6. Dependency contract

`CMP-SCM-01 → []` (`WBS.md §20`).

- **`CMP-CP-02` (Credential encryption service)** is the eventual home of the key service that `SCMCredentials` round-trips through. Until `CMP-CP-02` lands, `T-CMP-SCM-01-04` wires `SCMCredentials` through a deterministic mock encryption layer that satisfies the round-trip property of `AC-SCM-01b`. The interface (encrypt/decrypt by `(provider, mode)` envelope) is identical; only the implementation is swapped at integration time.
- The `target_url` consumed by `register_webhook()` is the public Scanipy webhook endpoint defined by [`DOC-API` §4.6](../cross-cutting/DOC-API.md#46-scm-webhooks). The ABC does not validate the URL; concrete connectors trust it.

---

## 7. Failure modes and error contracts

| Error type | Raised by | Retryable? | Resolution |
|---|---|---|---|
| `SCMAuthError` | every method | no — propagate to caller | Credentials are wrong or revoked; surface to the dashboard for the org admin to fix. |
| `SCMNotFoundError` | `resolve_commit`, `clone`, `get_default_branch` | no | Repo, ref, or commit does not exist (or is invisible to credentials). |
| `SCMRateLimitError` | every network method | yes — handled by `CMP-SCM-05` shared retry/backoff; only escalates after the budget is exhausted | See `CMP-SCM-05` for the curve. |
| `SCMSignatureMismatch` | `verify_webhook` | no — return `False`, do not raise | `verify_webhook` is a boolean predicate, not a fault path; `AC-SCM-03b` (negative test) asserts the return-value contract. |
| `SCMTransientError` | every network method | yes | Transient 5xx / connection reset; retry under `CMP-SCM-05`. |

All errors inherit from `SCMError(Exception)`.

No undecidable approximations live here, so **INV-4's "safe direction" clause does not apply** to this component. (The closest neighbouring concern — webhook signature verification — is a deterministic cryptographic check, not an approximation; see `verify_webhook` failure semantics above.)

---

## 8. Provenance threading

`CMP-SCM-01` writes **no provenance fields** to a finding row. It is upstream of every finding-emitting component (`CMP-ORCH-03`, `CMP-FND-01`, `CMP-TRI-01`, `CMP-SNAP-04`).

What `CMP-SCM-01` **does** feed forward (via `CloneMetadata`, §4.2) for downstream provenance:

| Downstream consumer | Field consumed | Where it appears |
|---|---|---|
| `CMP-SNAP-01` | `CloneMetadata.commit_sha` | `provenance_records.commit_sha` ([`DOC-PROVENANCE` §3](../cross-cutting/DOC-PROVENANCE.md#3-full-chain-schema-provenance_records-table), `snapshots.commit_sha`) |
| `CMP-SNAP-01` | `CloneMetadata.provider` | `provenance_records.scm_provider` |
| `CMP-SNAP-01` | `CloneMetadata.cloned_at` | informational; not part of the signed chain |

The connector **must not** stamp `origin`, `S_version`, `env_digest`, or `cpg_order_hash` on any record it produces. A code-review finding that this rule is violated is a hard invariant failure (RULE-6, [`.claude/rules/02-provenance.md`](../../.claude/rules/02-provenance.md)).

---

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md` lines 65–67:

| AC | Statement (verbatim) | Test spec | Status |
|---|---|---|---|
| **AC-SCM-01a** | ABC defines all six methods with typed signatures and a documented contract for each. | `TST-AC-SCM-01a` (`WBS.md §4.2` line 350) | spec [FORTHCOMING] in Phase 1 |
| **AC-SCM-01b** | `SCMCredentials` round-trips all four auth modes through encryption at rest (depends on `CMP-CP-02` for the key service; until then, mock). | `TST-AC-SCM-01b` (`WBS.md §4.2` line 351) | spec [FORTHCOMING] in Phase 1 |
| **AC-SCM-01c** | A conformance test suite exists that any concrete connector must pass. | `TST-AC-SCM-01c` (`WBS.md §4.2` line 352) | spec [FORTHCOMING] in Phase 1 |

The conformance suite (`AC-SCM-01c`) is itself the harness that drives `TST-AC-SCM-02a` and `TST-AC-SCM-03a` against the concrete connectors.

---

## 10. Open questions

The standing CLAR items that bear on this component:

| CLAR | Status | Bearing |
|---|---|---|
| [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) | DEFERRED | Subsystem maintainer for SCM Integration is unassigned. |

No SCM-specific CLAR items are currently open against `CMP-SCM-01`. (The byte-for-byte regression question affects `CMP-SCM-02` only; see `CLAR-SCM-01` in [`DOC-CMP-SCM-02`](./DOC-CMP-SCM-02.md).)

---

*Cross-references: [`DOC-INV`](../cross-cutting/DOC-INV.md) · [`DOC-GLOSSARY`](../cross-cutting/DOC-GLOSSARY.md) · [`DOC-API §2.4, §4.6`](../cross-cutting/DOC-API.md) · [`DOC-PROVENANCE §3`](../cross-cutting/DOC-PROVENANCE.md) · `SDD.md §3` · `WBS.md §5, §20` · `PLAN.md §"Phase 1 — Generalize SCM"`*

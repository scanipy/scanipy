# DOC-CMP-SCM-02 — GitHub connector

> **Source-of-truth:** `SDD.md §3 CMP-SCM-02`. Where this document diverges from `SDD.md` / `PLAN.md`, the upstream document wins; correct this file rather than the upstream.
> **Status contract:** This doc satisfies `AC-DOC-04` — a code-writing agent reading only this file plus the cross-cutting refs and [`DOC-CMP-SCM-01`](./DOC-CMP-SCM-01.md) can implement `CMP-SCM-02` without re-reading the SDD.

---

## 1. Component identity

| Field | Value |
|---|---|
| CMP-ID | `CMP-SCM-02` |
| Name | GitHub connector |
| Subsystem | SCM Integration (`SDD.md §3`) |
| Staging | `cross-cutting` (no language gate) |
| Depends-On | `CMP-SCM-01` (`WBS.md §20`) |
| WBS phase | Phase 2 — Generalise SCM (`WBS.md §5`) |
| Owning maintainer | unassigned — tracked under [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) (DEFERRED) |

---

## 2. Mandate

**Verbatim `Purpose:` (`SDD.md` line 71):**
> Subsume the existing `integrations/github/github.py`; preserve retry/backoff and tiered-star helpers verbatim; expose `search_code()` for Research mode only.

**Operational role.** `CMP-SCM-02` is the concrete `SCMConnector` subclass for GitHub.com and GitHub Enterprise. It implements the six abstract methods of `CMP-SCM-01` against the GitHub REST and webhook surfaces and additionally exposes `search_code()` — a GitHub-only helper that is restricted to Research mode (`CMP-RES-01`) and is not part of the generic ABC. Two backwards-compatibility commitments dominate the work: (i) the existing retry/backoff curve and the tiered-star repository-listing heuristic from v2's `integrations/github/github.py` must be preserved byte-for-byte against a regression baseline (`AC-SCM-02b`); (ii) the legacy public symbol `integrations.github.search_repositories` must continue to import and behave identically for any v2 caller (`AC-SCM-02c`). The byte-for-byte requirement is what distinguishes this connector from `CMP-SCM-03`: the other three connectors are new code, this one carries forward a measured behaviour. `CMP-SCM-02` emits no findings, sets no `origin` / `S_version` / `env_digest` / `cpg_order_hash` fields, and (like the rest of the SCM subsystem) is upstream of the provenance chain.

---

## 3. Interface contract

Module path: `integrations/scm/github.py` (`PLAN.md` line 157).

### 3.1 Class declaration

```python
from integrations.scm.base import (
    SCMConnector, SCMCredentials, RepoRef, WebhookSubscription, CloneMetadata,
)
from integrations.scm._http import RetryPolicy             # CMP-SCM-05

class GitHubConnector(SCMConnector):
    """GitHub.com / GitHub Enterprise connector. AC-SCM-02a..c."""

    provider_id = "github"

    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        api_base_url: str = "https://api.github.com",   # override for GHE
        retry_policy: RetryPolicy | None = None,        # default = §3.4 curve
    ) -> None: ...
```

### 3.2 ABC method overrides

All six methods are implemented against the GitHub REST API. Each method is run through the shared `CMP-SCM-05` retry decorator (§3.4). The semantics match `DOC-CMP-SCM-01 §3.2` exactly — only the wire calls differ.

```python
async def list_repos(
    self, *, org_or_workspace: str, page_size: int = 100,
) -> AsyncIterator[RepoRef]: ...
    # GET /orgs/{org}/repos?per_page={page_size}; cursor-paginates via Link header.

async def clone(
    self, repo_ref: RepoRef, *, commit_sha: str, dest_dir: Path,
    shallow: bool = True,
) -> CloneMetadata: ...
    # Uses HTTPS clone with installation-token (App mode) or PAT.
    # `shallow=True` ⇒ `git clone --depth=1 --branch <sha-resolved-to-ref>`.

async def register_webhook(
    self, repo_ref: RepoRef, *, target_url: str,
    events: tuple[str, ...], secret: str,
) -> WebhookSubscription: ...
    # POST /repos/{owner}/{repo}/hooks  with config.secret = `secret`,
    # content_type = 'json'. Idempotent on (owner, repo, target_url).

def verify_webhook(
    self, *, raw_body: bytes, headers: Mapping[str, str], secret: str,
) -> bool: ...
    # GitHub signature scheme: X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(secret, raw_body).
    # Constant-time comparison via hmac.compare_digest.
    # See DOC-API.md §2.4 for the canonical scheme.

async def get_default_branch(self, repo_ref: RepoRef) -> str: ...
    # GET /repos/{owner}/{repo} -> .default_branch.

async def resolve_commit(
    self, repo_ref: RepoRef, *, ref: str,
) -> str: ...
    # GET /repos/{owner}/{repo}/commits/{ref} -> .sha.
```

### 3.3 GitHub-only extensions (Research mode)

```python
async def search_code(
    self, query: str, *, page_size: int = 50,
) -> AsyncIterator[CodeSearchHit]:
    """GitHub-only code search (Research mode; CMP-RES-01).

    This method MUST NOT be invoked from production scan paths. The class
    advertises it only because the v2 codebase did; non-GitHub connectors
    do not expose any equivalent. AC-SCM-02b requires that the behaviour
    here (rate-limit honouring, secondary-limit backoff, result shaping)
    is byte-for-byte preserved against the v2 baseline."""

async def list_repos_tiered_star(
    self, *, query: str, star_tiers: tuple[int, ...] = (1000, 100, 10, 0),
) -> AsyncIterator[RepoRef]:
    """Tiered-star repository discovery helper. Preserved verbatim from v2
    `integrations/github/github.py` per AC-SCM-02b. GitHub-only."""
```

Both methods are typed `async def` on `GitHubConnector` only — they are not on `SCMConnector`. A static type-checker rejects a `GitHubConnector` substitution into an `SCMConnector` slot that calls these (the type system itself enforces the "Research mode only" rule per `T-CMP-SCM-02-02`).

### 3.4 Default retry policy

Sourced from `CMP-SCM-05` (see [`DOC-CMP-SCM-05`](./DOC-CMP-SCM-05.md) §3). The GitHub default is:

```python
RetryPolicy(
    initial_backoff_s = 1.0,
    max_backoff_s     = 60.0,
    jitter            = "full",        # AWS-style full jitter
    max_attempts      = 6,
    honor_429         = True,           # primary rate-limit
    honor_secondary   = True,           # X-RateLimit-Remaining=0 with reset
    honor_retry_after = True,           # Retry-After header (seconds | HTTP-date)
)
```

The "secondary" rate-limit honouring is the v2 behaviour that `AC-SCM-02b` regresses against.

### 3.5 Backwards-compatibility shim

Module path: `integrations/github/__init__.py` (`SDD.md` line 75; `T-CMP-SCM-02-03`).

```python
"""Backwards-compatibility shim. AC-SCM-02c.

`search_repositories` is the v2 public symbol; callers (`scanipy --query …`)
continue to import it from this path. The implementation now delegates to
`GitHubConnector.list_repos_tiered_star` but the public signature and
return shape are unchanged.
"""
from integrations.scm.github import GitHubConnector

def search_repositories(*args, **kwargs):
    # Same signature as v2; thin wrapper.
    ...
```

The shim is a caller-transparent re-export (`AC-SCM-02c`); a v2 caller running `scanipy --query extractall --run-semgrep` must not observe any difference.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Source | Field | Notes |
|---|---|---|
| `SCMCredentials` | `mode ∈ {pat, app_installation, oauth}` | SSH is supported for `clone()` only. |
| `api_base_url` | str | `https://api.github.com` (GitHub.com) or `https://{ghe-host}/api/v3` (GHE). |
| Webhook delivery | `X-Hub-Signature-256`, `X-GitHub-Event`, `X-GitHub-Delivery` | Verified via §3.2 `verify_webhook`. |

### 4.2 Outputs

| Method | Output | Notes |
|---|---|---|
| `list_repos` | `AsyncIterator[RepoRef]` | `provider="github"` on every yielded ref. |
| `clone` | `CloneMetadata` | `commit_sha` = resolved 40-hex; feeds `CMP-SNAP-01`. |
| `register_webhook` | `WebhookSubscription` | `webhook_id` is the GitHub-issued integer id. |
| `verify_webhook` | `bool` | `False` on signature mismatch; no exception. |
| `get_default_branch` | `str` | Provider-canonical value. |
| `resolve_commit` | `str` | 40-hex commit SHA. |
| `search_code` (Research) | `AsyncIterator[CodeSearchHit]` | Out-of-band of the SAST scan path. |

### 4.3 Side effects

- `clone()` writes to `dest_dir`; the GitHub installation token (if mode = `app_installation`) is minted just-in-time and never persisted.
- `register_webhook()` creates a server-side resource at GitHub.
- No DB writes by this component; credentials are read-only from the `scm_credentials` table populated by `CMP-CP-02`/`CMP-CP-03`.

---

## 5. Invariants touched

| Invariant | This component | Discharge |
|---|---|---|
| [INV-1](../cross-cutting/DOC-INV.md#3-inv-1--determinism-partition) | does not touch | `origin` is set by `CMP-ORCH-03`; never read or written here. |
| [INV-2](../cross-cutting/DOC-INV.md#4-inv-2--versioned-parameters) | does not touch | `S_version` and `env_digest` are set by `CMP-ORCH-01` and `CMP-SNAP-01` respectively. |
| [INV-3](../cross-cutting/DOC-INV.md#5-inv-3--llm-off-the-detection-path) | does not touch | No LLM on this path. |
| [INV-4](../cross-cutting/DOC-INV.md#6-inv-4--one-sided-undecidable-approximations) | does not touch | No undecidable approximations. |
| [INV-5](../cross-cutting/DOC-INV.md#7-inv-5--conditional-labels-are-self-describing) | does not touch | `cpg_order_hash` is set by `CMP-CORE-03`. |
| [INV-6](../cross-cutting/DOC-INV.md#8-inv-6--per-language-honesty) | does not touch | No detection here. |

`WBS.md §5` records no direct invariant threading for this component. No `TST-INV-*` is attached.

---

## 6. Dependency contract

`CMP-SCM-02 → [CMP-SCM-01]` (`WBS.md §20`).

- **`CMP-SCM-01` (SCMConnector ABC):** `CMP-SCM-02` assumes the ABC's six abstract methods, the `SCMCredentials` value type, and `RepoRef` / `WebhookSubscription` / `CloneMetadata` data classes are present and stable as documented in [`DOC-CMP-SCM-01` §3](./DOC-CMP-SCM-01.md#3-interface-contract). It assumes the conformance suite (`AC-SCM-01c`) is the harness that drives `TST-AC-SCM-02a`.
- **`CMP-SCM-05` (Shared HTTP retry/backoff):** although not listed as a hard dependency in the DAG, `CMP-SCM-02` consumes the `RetryPolicy` value type and the retry decorator from `integrations/scm/_http.py`. The `WBS.md §20` adjacency `CMP-SCM-02 → [CMP-SCM-01]` is preserved literally; the use of `CMP-SCM-05` is a "library reuse" relationship that does not gate scheduling (the GitHub connector's own retry logic is what `CMP-SCM-05` lifts; in practice the two are co-developed).
- **`CMP-CP-02` (Credential encryption service):** mockable per `AC-SCM-01b`; same arrangement as `CMP-SCM-01`.

---

## 7. Failure modes and error contracts

Inherits the error hierarchy from `CMP-SCM-01` (`SCMError`, `SCMAuthError`, `SCMNotFoundError`, `SCMRateLimitError`, `SCMSignatureMismatch`, `SCMTransientError`). GitHub-specific mapping:

| GitHub response | Mapped exception | Retried? |
|---|---|---|
| `401`, `403 with "Bad credentials"` | `SCMAuthError` | no |
| `404` | `SCMNotFoundError` | no |
| `403` with `X-RateLimit-Remaining: 0` | `SCMRateLimitError` after retry budget exhausted | yes, until budget |
| `403` with secondary-limit body | `SCMRateLimitError` after retry budget exhausted | yes, with secondary-limit-specific backoff |
| `5xx` | `SCMTransientError` | yes |
| `200` body with bad SHA-256 signature on inbound webhook | `verify_webhook` returns `False` | n/a (predicate) |

The retry curve is `CMP-SCM-05`'s default GitHub policy (§3.4). No undecidable approximations live here; INV-4's safe-direction clause does not apply.

---

## 8. Provenance threading

`CMP-SCM-02` writes **no provenance fields** to a finding row. It feeds `CloneMetadata` (commit SHA, parent SHAs, clone time, `provider="github"`) into `CMP-SNAP-01`, which populates `provenance_records.commit_sha` and `provenance_records.scm_provider` (see [`DOC-PROVENANCE` §3](../cross-cutting/DOC-PROVENANCE.md#3-full-chain-schema-provenance_records-table)).

The connector **must not** stamp `origin`, `S_version`, `env_digest`, or `cpg_order_hash` on any record (RULE-6).

---

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md` lines 73–75:

| AC | Statement (verbatim) | Test spec | Status |
|---|---|---|---|
| **AC-SCM-02a** | Passes the CMP-SCM-01 conformance suite. | `TST-AC-SCM-02a` (`WBS.md §4.2` line 353) | spec [FORTHCOMING] in Phase 1 |
| **AC-SCM-02b** | Existing retry, rate-limit, and tiered-star behavior is byte-for-byte preserved (regression test against current behavior). | `TST-AC-SCM-02b` (`WBS.md §4.2` line 354) | spec [FORTHCOMING] in Phase 1; baseline source pending `CLAR-SCM-01` |
| **AC-SCM-02c** | `integrations/github/__init__.py` exports `search_repositories` as a shim with no caller-visible change. | `TST-AC-SCM-02c` (`WBS.md §4.2` line 355) | spec [FORTHCOMING] in Phase 1 |

---

## 10. Open questions

| CLAR | Status | Bearing |
|---|---|---|
| [`CLAR-SCM-01`](../../WBS.md#17-clarification-needed-register) | **OPEN** (filed by this doc) | Source location of the legacy v2 GitHub connector against which `AC-SCM-02b` byte-for-byte regression is measured. `SDD.md` line 71 and `WBS.md §5` reference `integrations/github/github.py` as legacy v2 code, but the v3.2 scaffold does not contain this file. Implementation of `AC-SCM-02b` is blocked until a baseline location is named (vendored copy, v2 git history snapshot, or a golden-fixture archive of the v2 behaviour). |
| [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) | DEFERRED | Subsystem maintainer for SCM Integration is unassigned. |

---

*Cross-references: [`DOC-CMP-SCM-01`](./DOC-CMP-SCM-01.md) · [`DOC-CMP-SCM-05`](./DOC-CMP-SCM-05.md) · [`DOC-INV`](../cross-cutting/DOC-INV.md) · [`DOC-API §2.4, §4.6`](../cross-cutting/DOC-API.md) · [`DOC-PROVENANCE §3`](../cross-cutting/DOC-PROVENANCE.md) · `SDD.md §3` · `WBS.md §5, §20` · `PLAN.md §"Phase 1 — Generalize SCM"`*

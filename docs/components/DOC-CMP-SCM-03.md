# DOC-CMP-SCM-03 — GitLab / Bitbucket / Azure DevOps connectors

> **Source-of-truth:** `SDD.md §3 CMP-SCM-03`. Where this document diverges from `SDD.md` / `PLAN.md`, the upstream document wins; correct this file rather than the upstream.
> **Status contract:** This doc satisfies `AC-DOC-04` — a code-writing agent reading only this file plus the cross-cutting refs and [`DOC-CMP-SCM-01`](./DOC-CMP-SCM-01.md), [`DOC-CMP-SCM-05`](./DOC-CMP-SCM-05.md) can implement `CMP-SCM-03` without re-reading the SDD.

---

## 1. Component identity

| Field | Value |
|---|---|
| CMP-ID | `CMP-SCM-03` |
| Name | GitLab / Bitbucket / Azure DevOps connectors |
| Subsystem | SCM Integration (`SDD.md §3`) |
| Staging | `cross-cutting` (no language gate) |
| Depends-On | `CMP-SCM-01`, `CMP-SCM-05` (`WBS.md §20`) |
| WBS phase | Phase 2 — Generalise SCM (`WBS.md §5`) |
| Owning maintainer | unassigned — tracked under [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) (DEFERRED) |
| Note | `CMP-SCM-04` does not exist; numbering jumps `01 → 02 → 03 → 05`. |

---

## 2. Mandate

**Verbatim `Purpose:` (`SDD.md` line 79):**
> Three concrete connectors implementing the ABC against each provider's REST API and webhook signature scheme.

**Operational role.** `CMP-SCM-03` delivers three sibling connector classes — `GitLabConnector`, `BitbucketConnector`, `AzureDevOpsConnector` — that bring multi-SCM coverage to parity with `CMP-SCM-02`. Each subclasses `CMP-SCM-01.SCMConnector` and passes the same conformance suite, so a Scanipy pipeline can be pointed at any of GitHub, GitLab, Bitbucket, or Azure DevOps without upstream code change (`PLAN.md` line 1 framing — "Multi-SCM"; `PLAN.md` line 157). Each connector implements its provider-specific webhook signature scheme (per [`DOC-API §2.4`](../cross-cutting/DOC-API.md#24-scm-webhooks--per-provider-signature-verification-cmp-scm-0103)) and is verified by a negative-test (`AC-SCM-03b`). Identical commit resolution across the four SCMs is verified end-to-end against a single canary repo mirrored to all four (`AC-SCM-03c`). Unlike `CMP-SCM-02`, there is **no byte-for-byte regression baseline** to honour — these are new implementations. `CMP-SCM-03` emits no findings and stamps no provenance fields; it lives entirely upstream of the deterministic detection path.

---

## 3. Interface contract

Module paths (`PLAN.md` line 157):
- `integrations/scm/gitlab.py`
- `integrations/scm/bitbucket.py`
- `integrations/scm/ado.py` (Azure DevOps)

### 3.1 Class declarations

```python
from integrations.scm.base import (
    SCMConnector, SCMCredentials, RepoRef, WebhookSubscription, CloneMetadata,
)
from integrations.scm._http import RetryPolicy             # CMP-SCM-05

class GitLabConnector(SCMConnector):
    """GitLab.com / self-hosted GitLab. AC-SCM-03a..c."""
    provider_id = "gitlab"
    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        api_base_url: str = "https://gitlab.com/api/v4",
        retry_policy: RetryPolicy | None = None,
    ) -> None: ...

class BitbucketConnector(SCMConnector):
    """Bitbucket Cloud (and Server via override). AC-SCM-03a..c."""
    provider_id = "bitbucket"
    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        api_base_url: str = "https://api.bitbucket.org/2.0",
        retry_policy: RetryPolicy | None = None,
    ) -> None: ...

class AzureDevOpsConnector(SCMConnector):
    """Azure DevOps Services. AC-SCM-03a..c."""
    provider_id = "azure-devops"
    def __init__(
        self,
        credentials: SCMCredentials,
        *,
        organization: str,                                 # required for ADO
        api_base_url: str = "https://dev.azure.com",
        retry_policy: RetryPolicy | None = None,
    ) -> None: ...
```

### 3.2 ABC method overrides

All three classes implement the six abstract methods of `SCMConnector` (`list_repos`, `clone`, `register_webhook`, `verify_webhook`, `get_default_branch`, `resolve_commit`) with semantics identical to those documented in [`DOC-CMP-SCM-01 §3.2`](./DOC-CMP-SCM-01.md#32-the-abstract-base-class). Only the wire calls and authentication mechanics differ.

#### Per-provider REST endpoints (sketch — full mapping is implementation detail)

| ABC method | GitLab | Bitbucket Cloud | Azure DevOps |
|---|---|---|---|
| `list_repos` | `GET /groups/{group}/projects` | `GET /repositories/{workspace}` | `GET /{org}/{project}/_apis/git/repositories` |
| `clone` | HTTPS clone with PAT/OAuth in URL | HTTPS clone with App password / OAuth | HTTPS clone with PAT |
| `register_webhook` | `POST /projects/{id}/hooks` (token in `token` field) | `POST /repositories/{ws}/{repo}/hooks` | service-hooks `POST /{org}/_apis/hooks/subscriptions` |
| `get_default_branch` | `GET /projects/{id}` `.default_branch` | `GET /repositories/{ws}/{repo}` `.mainbranch.name` | `GET /{org}/{project}/_apis/git/repositories/{id}` `.defaultBranch` |
| `resolve_commit` | `GET /projects/{id}/repository/commits/{ref}` `.id` | `GET /repositories/{ws}/{repo}/commit/{ref}` `.hash` | `GET …/commits/{ref}` `.commitId` |

### 3.3 `verify_webhook` — per-provider signature scheme

The canonical scheme reference is [`DOC-API §2.4`](../cross-cutting/DOC-API.md#24-scm-webhooks--per-provider-signature-verification-cmp-scm-0103). Each connector implements exactly the scheme below; `AC-SCM-03b` requires a **negative test** per provider (a forged payload must return `False`).

| Provider | Header | Algorithm | Notes |
|---|---|---|---|
| GitLab | `X-Gitlab-Token` | plain shared-secret equality (provider-native) | Constant-time compare via `hmac.compare_digest`. |
| Bitbucket | `X-Hub-Signature` | HMAC-SHA-256 over raw body, key = registered secret; header value prefix `sha256=` | Compare constant-time. |
| Azure DevOps | HMAC via service-hook subscription header `X-Vss-Activityid` and body HMAC where applicable | HMAC-SHA-1 or HMAC-SHA-256 per service-hook config; secret is the subscription consumer secret | ADO is the only provider whose signature scheme depends on the subscription-side configuration; the connector pins HMAC-SHA-256 and rejects subscriptions configured otherwise. |

The GitHub row of `DOC-API §2.4` is the responsibility of `CMP-SCM-02`, not this component.

### 3.4 Default retry policies

All three connectors consume the default `RetryPolicy` from `CMP-SCM-05` ([`DOC-CMP-SCM-05`](./DOC-CMP-SCM-05.md) §3.2) with per-provider rate-limit awareness:

| Provider | 429 / rate-limit response shape | Honouring policy |
|---|---|---|
| GitLab | `429` with `Retry-After` header | Honour `Retry-After`; otherwise exponential with full jitter. |
| Bitbucket | `429` with `Retry-After` header | Honour `Retry-After`; secondary "abuse" responses (`429` body marker) backoff doubled. |
| Azure DevOps | `429` with `Retry-After` header; `X-RateLimit-Resource`, `X-RateLimit-Delay` | Honour `Retry-After` AND `X-RateLimit-Delay`; if both present, the longer wins. |

`AC-SCM-05a` requires unit tests against simulated 429 and secondary-limit responses for each provider.

### 3.5 Research-mode helpers

`search_code()` and `list_repos_tiered_star()` are **GitHub-only** (`CMP-SCM-02`). The three classes in `CMP-SCM-03` do **not** declare these methods; a static type-checker rejects any call site that expects them on a `GitLab|Bitbucket|AzureDevOpsConnector` (`T-CMP-SCM-02-02`'s "type-system enforcement").

---

## 4. Inputs and outputs

### 4.1 Inputs

| Connector | Required `SCMCredentials.mode` payloads |
|---|---|
| GitLab | `pat` (`token`), `oauth` (`access_token`, `refresh_token`, `expires_at`), `ssh_key` for clone. |
| Bitbucket | `pat` (`token` = app password), `oauth` (`access_token`, `refresh_token`, `expires_at`), `ssh_key` for clone. |
| Azure DevOps | `pat` (`token`), `oauth` (`access_token`, `refresh_token`, `expires_at`); SSH supported for clone. |

All three accept the same `RepoRef` shape from `CMP-SCM-01` with `provider` set to the provider-specific value (`gitlab` / `bitbucket` / `azure-devops`).

### 4.2 Outputs

Identical shape to `CMP-SCM-02` outputs:
- `list_repos` → `AsyncIterator[RepoRef]` (provider stamped on each yield).
- `clone` → `CloneMetadata` with `provider` and resolved 40-hex `commit_sha`.
- `register_webhook` → `WebhookSubscription` with `webhook_id` provider-issued.
- `verify_webhook` → `bool`.
- `get_default_branch` → `str`.
- `resolve_commit` → 40-hex `str`.

`AC-SCM-03c` requires that for a canary repo mirrored to all four providers (the four-SCM mirror is `CMP-CORP-CANARY-01`'s deliverable — see `SDD.md` line 328; `WBS.md §16`), `resolve_commit(repo, ref="<canary-ref>")` returns the **same 40-hex value** from all four `SCMConnector` instances.

### 4.3 Side effects

- `clone()` writes to `dest_dir`.
- `register_webhook()` creates a provider-side resource at GitLab / Bitbucket / Azure DevOps.
- No DB writes. No SARIF. No findings.

---

## 5. Invariants touched

| Invariant | This component | Discharge |
|---|---|---|
| [INV-1](../cross-cutting/DOC-INV.md#3-inv-1--determinism-partition) | does not touch | `origin` is set by `CMP-ORCH-03`. |
| [INV-2](../cross-cutting/DOC-INV.md#4-inv-2--versioned-parameters) | does not touch | `S_version` and `env_digest` are set elsewhere. |
| [INV-3](../cross-cutting/DOC-INV.md#5-inv-3--llm-off-the-detection-path) | does not touch | No LLM. |
| [INV-4](../cross-cutting/DOC-INV.md#6-inv-4--one-sided-undecidable-approximations) | does not touch | No undecidable approximations. Webhook signature verification is a deterministic cryptographic check, not an approximation. |
| [INV-5](../cross-cutting/DOC-INV.md#7-inv-5--conditional-labels-are-self-describing) | does not touch | No CPG-derived artifact here. |
| [INV-6](../cross-cutting/DOC-INV.md#8-inv-6--per-language-honesty) | does not touch | No detection here. |

`WBS.md §5` records "Invariants threaded: none direct" for this component. No `TST-INV-*` is attached.

---

## 6. Dependency contract

`CMP-SCM-03 → [CMP-SCM-01, CMP-SCM-05]` (`WBS.md §20`).

- **`CMP-SCM-01` (SCMConnector ABC):** All three classes subclass `SCMConnector` and assume the ABC, value types, and conformance suite are present as documented in [`DOC-CMP-SCM-01 §3`](./DOC-CMP-SCM-01.md#3-interface-contract).
- **`CMP-SCM-05` (Shared HTTP retry/backoff):** All three classes consume the `RetryPolicy` value and the retry decorator from `integrations/scm/_http.py`. Unlike `CMP-SCM-02`, this dependency is in the DAG — `CMP-SCM-05` must reach DONE before `CMP-SCM-03` can be scheduled.
- **`CMP-CORP-CANARY-01` (canary corpus):** `AC-SCM-03c` is verified against the four-SCM mirror of `CMP-CORP-CANARY-01` (see `SDD.md` line 328). The corpus itself is a separate deliverable and is not a hard dependency for the connector code, but the AC is not verifiable until the corpus exists.
- **`CMP-CP-02` (credential encryption):** mockable; same as for `CMP-SCM-01`.

---

## 7. Failure modes and error contracts

Inherits the `SCMError` hierarchy from `CMP-SCM-01`. Per-provider HTTP→exception mappings:

| Response | Mapped exception | Retried? |
|---|---|---|
| `401` / `403` "Unauthorized" / "Forbidden" without rate-limit markers | `SCMAuthError` | no |
| `404` | `SCMNotFoundError` | no |
| `429` + `Retry-After` | `SCMRateLimitError` after retry budget exhausted | yes, honouring `Retry-After` |
| Bitbucket "abuse" 429 | `SCMRateLimitError` | yes, doubled backoff |
| Azure DevOps 429 with `X-RateLimit-Delay` | `SCMRateLimitError` | yes, honouring max(Retry-After, X-RateLimit-Delay) |
| `5xx` | `SCMTransientError` | yes |
| `verify_webhook` bad signature | returns `False` (no exception) | n/a |

`AC-SCM-03b` requires a per-provider **negative** test: a payload with a tampered byte (after the original signature was computed) must cause `verify_webhook` to return `False`. The test asserts boolean return — no exception is raised, no log line of "verified" appears.

No undecidable approximations. INV-4's safe-direction clause does not apply.

---

## 8. Provenance threading

`CMP-SCM-03` writes **no provenance fields** to a finding row. Like `CMP-SCM-02`, it feeds `CloneMetadata` (with `provider ∈ {gitlab, bitbucket, azure-devops}`) into `CMP-SNAP-01`, which populates `provenance_records.scm_provider` and `provenance_records.commit_sha` ([`DOC-PROVENANCE §3`](../cross-cutting/DOC-PROVENANCE.md#3-full-chain-schema-provenance_records-table)).

The connector **must not** stamp `origin`, `S_version`, `env_digest`, or `cpg_order_hash` (RULE-6).

`AC-SCM-03c`'s identical-commit-resolution guarantee is the SCM-level precondition that lets the cross-SCM determinism claim (PLAN.md verification §"End-to-end / multi-SCM / backwards-compat") hold: if four SCMs disagree on what commit `main` points to, downstream determinism cannot be evaluated.

---

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md` lines 81–83:

| AC | Statement (verbatim) | Test spec | Status |
|---|---|---|---|
| **AC-SCM-03a** | Each passes the CMP-SCM-01 conformance suite. | `TST-AC-SCM-03a` (`WBS.md §4.2` line 356) | spec [FORTHCOMING] in Phase 1 |
| **AC-SCM-03b** | Webhook signature verification rejects forged payloads for each provider (negative test). | `TST-AC-SCM-03b` (`WBS.md §4.2` line 357) | spec [FORTHCOMING] in Phase 1 |
| **AC-SCM-03c** | A single canary repository mirrored to all four providers produces identical commit resolution. | `TST-AC-SCM-03c` (`WBS.md §4.2` line 358) | spec [FORTHCOMING] in Phase 1; depends on `CMP-CORP-CANARY-01` deliverable. |

---

## 10. Open questions

| CLAR | Status | Bearing |
|---|---|---|
| [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) | DEFERRED | Subsystem maintainer for SCM Integration is unassigned. |

No SCM-specific CLAR items are open against `CMP-SCM-03`. (`CLAR-SCM-01` exists but is scoped to `CMP-SCM-02` — see [`DOC-CMP-SCM-02 §10`](./DOC-CMP-SCM-02.md#10-open-questions).)

---

*Cross-references: [`DOC-CMP-SCM-01`](./DOC-CMP-SCM-01.md) · [`DOC-CMP-SCM-05`](./DOC-CMP-SCM-05.md) · [`DOC-INV`](../cross-cutting/DOC-INV.md) · [`DOC-API §2.4, §4.6`](../cross-cutting/DOC-API.md) · [`DOC-PROVENANCE §3`](../cross-cutting/DOC-PROVENANCE.md) · `SDD.md §3` · `WBS.md §5, §20` · `PLAN.md §"Phase 1 — Generalize SCM"`*

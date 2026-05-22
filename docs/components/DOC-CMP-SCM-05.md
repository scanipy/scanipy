# DOC-CMP-SCM-05 — Shared HTTP retry/backoff

> **Source-of-truth:** `SDD.md §3 CMP-SCM-05`. Where this document diverges from `SDD.md` / `PLAN.md`, the upstream document wins; correct this file rather than the upstream.
> **Status contract:** This doc satisfies `AC-DOC-04` — a code-writing agent reading only this file plus the cross-cutting refs can implement `CMP-SCM-05` without re-reading the SDD.

---

## 1. Component identity

| Field | Value |
|---|---|
| CMP-ID | `CMP-SCM-05` |
| Name | Shared HTTP retry/backoff |
| Subsystem | SCM Integration (`SDD.md §3`) |
| Staging | `cross-cutting` (no language gate) |
| Depends-On | none (`WBS.md §20`) |
| WBS phase | Phase 2 — Generalise SCM (`WBS.md §5`) |
| Owning maintainer | unassigned — tracked under [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) (DEFERRED) |
| Note | `CMP-SCM-04` does not exist; numbering jumps `01 → 02 → 03 → 05`. |

---

## 2. Mandate

**Verbatim `Purpose:` (`SDD.md` line 87):**
> Lift the retry/backoff/rate-limit pattern into a shared module reused by all connectors.

**Operational role.** `CMP-SCM-05` extracts the exponential-backoff-with-jitter and rate-limit-honouring logic that v2's `integrations/github/github.py` carried inline, and lifts it into a provider-neutral module (`integrations/scm/_http.py` — `PLAN.md` line 157). The module exposes a `RetryPolicy` value type and a retry decorator that every `SCMConnector` subclass wraps around its REST calls. Because each provider has a different rate-limit response shape (GitHub `X-RateLimit-Remaining: 0` + secondary, GitLab/Bitbucket `429 + Retry-After`, Azure DevOps `429 + Retry-After + X-RateLimit-Delay`), the module accepts per-provider response-classification hooks and applies the right backoff curve per provider. The retry curve is exponential with **full jitter** (AWS-style) plus a per-provider rate-limit override. `CMP-SCM-05` is library code with no I/O state; it is unit-tested against simulated 429 / secondary-limit responses (`AC-SCM-05a`). The module is upstream of every finding-emitting component and never touches `origin`, `S_version`, `env_digest`, or `cpg_order_hash`.

---

## 3. Interface contract

Module path: `integrations/scm/_http.py` (`PLAN.md` line 157). Python 3.11+.

### 3.1 `RetryPolicy` value type

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal

class JitterMode(str, Enum):
    NONE  = "none"
    FULL  = "full"        # AWS-style: sleep = random(0, backoff)
    EQUAL = "equal"       # sleep = backoff/2 + random(0, backoff/2)

@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Provider-neutral retry/backoff configuration. AC-SCM-05a."""

    initial_backoff_s: float = 1.0
    max_backoff_s:     float = 60.0
    backoff_factor:    float = 2.0          # exponential base
    jitter:            JitterMode = JitterMode.FULL
    max_attempts:      int = 6              # including the first try
    # Provider-rate-limit semantics
    honor_429:         bool = True          # any 429 → wait + retry (until budget)
    honor_secondary:   bool = True          # GitHub-style abuse / secondary
    honor_retry_after: bool = True          # Retry-After header (seconds | HTTP-date)
    # Per-provider hard cap on the total time spent retrying a single call
    total_deadline_s:  float | None = None  # None ⇒ no deadline (only attempts cap)
```

### 3.2 Default policies (per provider)

```python
GITHUB_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0, max_backoff_s=60.0, max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True, honor_secondary=True, honor_retry_after=True,
    total_deadline_s=None,
)

GITLAB_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0, max_backoff_s=60.0, max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True, honor_secondary=False, honor_retry_after=True,
    total_deadline_s=None,
)

BITBUCKET_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0, max_backoff_s=60.0, max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True, honor_secondary=True, honor_retry_after=True,
    total_deadline_s=None,
)

AZURE_DEVOPS_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0, max_backoff_s=60.0, max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True, honor_secondary=False, honor_retry_after=True,
    total_deadline_s=None,
)
```

Callers may pass a custom `RetryPolicy` to override any of the defaults (constructor arg on every connector, [`DOC-CMP-SCM-02 §3.1`](./DOC-CMP-SCM-02.md#31-class-declaration), [`DOC-CMP-SCM-03 §3.1`](./DOC-CMP-SCM-03.md#31-class-declarations)).

### 3.3 Response classification hook

Each provider's response shape is read by a per-provider classification function:

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class RateLimitVerdict:
    is_rate_limited:  bool
    retry_after_s:    float | None      # provider-honoured wait, if any
    is_secondary:     bool = False      # GitHub abuse / Bitbucket abuse

def classify_github(response) -> RateLimitVerdict: ...
def classify_gitlab(response) -> RateLimitVerdict: ...
def classify_bitbucket(response) -> RateLimitVerdict: ...
def classify_azure_devops(response) -> RateLimitVerdict: ...
```

Each function reads provider-specific headers/body markers:

| Provider | Signal of rate-limited | Retry-after source |
|---|---|---|
| GitHub | `403` + `X-RateLimit-Remaining: 0` (primary); `403` body marker (secondary) | `X-RateLimit-Reset` epoch (primary); `Retry-After` (secondary) |
| GitLab | `429` | `Retry-After` header |
| Bitbucket | `429` (`X-Bitbucket-Type: abuse` indicates secondary) | `Retry-After` header |
| Azure DevOps | `429` | `max(Retry-After, X-RateLimit-Delay)` |

### 3.4 The retry decorator

```python
from typing import Awaitable, Callable, TypeVar
T = TypeVar("T")

def with_retry(
    *,
    policy:    RetryPolicy,
    classify:  Callable[[object], RateLimitVerdict],
    on_attempt: Callable[[int, float, str], None] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async function performing one HTTP call.

    Sleep curve (AC-SCM-05a):
      base[i]   = min(initial_backoff_s * backoff_factor**i, max_backoff_s)
      sleep[i]  = jitter(base[i])               # JitterMode.FULL by default
      override:  if classify returns retry_after_s, use that instead
                 (provider-honoured rate-limit always wins over the curve)

    Stop conditions:
      - attempts ≥ policy.max_attempts            → raise the last exception
      - cumulative sleep ≥ policy.total_deadline_s → raise SCMRateLimitError
      - non-retryable exception (SCMAuthError, SCMNotFoundError, …) → propagate
    """
```

The decorator is used as:

```python
@with_retry(policy=GITHUB_DEFAULT, classify=classify_github)
async def _get_repo(self, owner: str, name: str) -> dict:
    ...
```

### 3.5 Helpers exported by the module

```python
# Public surface of integrations/scm/_http.py
__all__ = [
    "JitterMode",
    "RetryPolicy",
    "RateLimitVerdict",
    "with_retry",
    "classify_github",
    "classify_gitlab",
    "classify_bitbucket",
    "classify_azure_devops",
    "GITHUB_DEFAULT",
    "GITLAB_DEFAULT",
    "BITBUCKET_DEFAULT",
    "AZURE_DEVOPS_DEFAULT",
]
```

No public type alias is exposed from this module for the HTTP client itself; the connector chooses its own client library (`httpx` recommended) and the decorator is client-agnostic.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Source | Field | Notes |
|---|---|---|
| Decorated call | the awaited request | Connector-provided async function. |
| `RetryPolicy` | as in §3.1 | Per-provider default or caller override. |
| Response (post-call) | `response` object passed to `classify` | Implementation-specific (an `httpx.Response`-shaped object). |
| Optional `on_attempt` | `(attempt_index, sleep_s, reason) → None` | Hook for OpenTelemetry / structured logs (`CLAR-DEPLOY-07`). |

### 4.2 Outputs

| Output | Notes |
|---|---|
| Awaited result of the decorated call | Same type as the underlying call. |
| `SCMRateLimitError` (raised) | When `max_attempts` or `total_deadline_s` is exhausted; carries the last `RateLimitVerdict`. |
| `on_attempt(i, sleep_s, reason)` | Per-attempt observability emission; reason ∈ `{"rate-limited-primary", "rate-limited-secondary", "transient-5xx", "transient-network"}`. |

### 4.3 Side effects

None outside the decorated call itself. The module does no I/O of its own.

---

## 5. Invariants touched

| Invariant | This component | Discharge |
|---|---|---|
| [INV-1](../cross-cutting/DOC-INV.md#3-inv-1--determinism-partition) | does not touch | No finding emitted here. |
| [INV-2](../cross-cutting/DOC-INV.md#4-inv-2--versioned-parameters) | does not touch | `S_version` / `env_digest` not relevant. |
| [INV-3](../cross-cutting/DOC-INV.md#5-inv-3--llm-off-the-detection-path) | does not touch | No LLM. |
| [INV-4](../cross-cutting/DOC-INV.md#6-inv-4--one-sided-undecidable-approximations) | does not touch | Retry behaviour is deterministic on the policy; jitter is randomised but bounded and is not an approximation of an undecidable property. |
| [INV-5](../cross-cutting/DOC-INV.md#7-inv-5--conditional-labels-are-self-describing) | does not touch | No CPG artifact. |
| [INV-6](../cross-cutting/DOC-INV.md#8-inv-6--per-language-honesty) | does not touch | No detection. |

`WBS.md §5` records no direct invariant threading for this component. No `TST-INV-*` is attached.

---

## 6. Dependency contract

`CMP-SCM-05 → []` (`WBS.md §20`). Wave-1 component; no upstream dependencies.

Downstream consumers: `CMP-SCM-02`, `CMP-SCM-03` (every concrete connector). When a connector consumes a `RetryPolicy`, the connector assumes:

- `with_retry` is **non-blocking** on the event loop except during `asyncio.sleep` waits.
- `classify_*` is **pure** — same response → same `RateLimitVerdict`.
- `JitterMode.FULL` uses a cryptographically-uninteresting `random` source (deterministic-detection-path-irrelevant: HTTP retries are not on the determinism partition).

---

## 7. Failure modes and error contracts

| Condition | Behaviour |
|---|---|
| Decorated call raises `SCMAuthError` / `SCMNotFoundError` | Propagated immediately; not retried. |
| Decorated call returns a rate-limited response (per `classify`) | Sleep per §3.4 curve; retry until `max_attempts` or `total_deadline_s`. |
| Decorated call raises `SCMTransientError` (network / 5xx mapped by caller) | Sleep per curve and retry. |
| `max_attempts` exhausted on rate-limited responses | Raise `SCMRateLimitError(last_verdict)`. |
| `max_attempts` exhausted on transient errors | Re-raise the last `SCMTransientError`. |
| `total_deadline_s` exceeded mid-curve | Raise `SCMRateLimitError(timeout)`. |

No undecidable approximations live here; INV-4's safe-direction clause does not apply. The module is **pure-library** code — there are no provider calls made directly from `_http.py`; only the connector code that decorates calls makes wire traffic.

---

## 8. Provenance threading

`CMP-SCM-05` writes **no provenance fields** to a finding row and no fields to any provenance record. It is two layers upstream of every finding-emitting component (`CMP-ORCH-03`, `CMP-FND-01`, …). The `on_attempt` hook may emit OpenTelemetry spans (`CLAR-DEPLOY-07`), but those are observability events, not provenance records.

The module **must not** stamp `origin`, `S_version`, `env_digest`, or `cpg_order_hash` anywhere (RULE-6). The retry behaviour itself does not enter any provenance chain.

---

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md` line 89:

| AC | Statement (verbatim) | Test spec | Status |
|---|---|---|---|
| **AC-SCM-05a** | Exponential backoff with jitter and provider-specific rate-limit honoring is unit-tested against simulated 429/secondary-limit responses. | `TST-AC-SCM-05a` (`WBS.md §4.2` line 359) | spec [FORTHCOMING] in Phase 1 |

The test spec must cover, at minimum:
1. Curve shape (exponential, full jitter, `max_attempts` honoured).
2. `Retry-After` (seconds form) overriding the curve.
3. `Retry-After` (HTTP-date form) overriding the curve.
4. GitHub primary rate-limit (`X-RateLimit-Remaining: 0` + `X-RateLimit-Reset`).
5. GitHub secondary rate-limit (body marker).
6. GitLab `429` + `Retry-After`.
7. Bitbucket `429` (abuse vs primary differentiation).
8. Azure DevOps `429` with both `Retry-After` and `X-RateLimit-Delay` (max wins).
9. `total_deadline_s` exhaustion raises `SCMRateLimitError`.
10. Non-retryable exceptions (`SCMAuthError`, `SCMNotFoundError`) propagate without retry.

---

## 10. Open questions

| CLAR | Status | Bearing |
|---|---|---|
| [`CLAR-OWNER-01`](../../WBS.md#17-clarification-needed-register) | DEFERRED | Subsystem maintainer for SCM Integration is unassigned. |

No SCM-specific CLAR items are open against `CMP-SCM-05`.

---

*Cross-references: [`DOC-CMP-SCM-01`](./DOC-CMP-SCM-01.md) · [`DOC-CMP-SCM-02`](./DOC-CMP-SCM-02.md) · [`DOC-CMP-SCM-03`](./DOC-CMP-SCM-03.md) · [`DOC-INV`](../cross-cutting/DOC-INV.md) · [`DOC-API §2.4`](../cross-cutting/DOC-API.md) · `SDD.md §3` · `WBS.md §5, §20` · `PLAN.md §"Phase 1 — Generalize SCM"`*

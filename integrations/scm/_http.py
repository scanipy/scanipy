"""CMP-SCM-05 — Shared HTTP retry/backoff for SCM connectors.

Provider-neutral exponential-backoff-with-jitter and rate-limit-honouring
logic, lifted out of v2's inline GitHub code into a reusable module
(`PLAN.md` line 157; DOC-CMP-SCM-05). Every concrete `SCMConnector`
(`CMP-SCM-02`, `CMP-SCM-03`) decorates its REST calls with `with_retry`,
passing the per-provider `classify_*` hook so the right backoff curve is
applied for each provider's distinct rate-limit response shape.

The retry curve is exponential with **full jitter** (AWS-style) plus a
per-provider rate-limit override: a provider-honoured `Retry-After` /
`X-RateLimit-Reset` wait always wins over the computed curve (DOC §3.4).

`CMP-SCM-05` is **pure-library** code: it performs no I/O of its own and is
two layers upstream of every finding-emitting component. It writes **none** of
the four provenance fields (`origin`, `S_version`, `env_digest`,
`cpg_order_hash`) and touches no `Finding` (DOC §8; RULE-6 non-touch). The
`on_attempt` hook emits observability events only, never provenance records.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import ParamSpec, Protocol, TypeVar, runtime_checkable

from integrations.scm.base import (
    SCMAuthError,
    SCMNotFoundError,
    SCMRateLimitError,
    SCMTransientError,
)

__all__ = [
    "AZURE_DEVOPS_DEFAULT",
    "BITBUCKET_DEFAULT",
    "GITHUB_DEFAULT",
    "GITLAB_DEFAULT",
    "JitterMode",
    "RateLimitVerdict",
    "RetryPolicy",
    "classify_azure_devops",
    "classify_bitbucket",
    "classify_github",
    "classify_gitlab",
    "with_retry",
]


# ---------------------------------------------------------------------------
# Response protocol (DOC-CMP-SCM-05 §3.3, §4.1)
# ---------------------------------------------------------------------------


@runtime_checkable
class HTTPResponseLike(Protocol):
    """Minimal `httpx.Response`-shaped surface read by the `classify_*` hooks.

    The decorator is client-agnostic (DOC §3.5): a connector may use any client
    whose response exposes an integer `status_code`, a case-insensitive
    `headers` mapping, and a text body. Only these three attributes are read.
    """

    status_code: int
    headers: object  # a mapping supporting .get(key, default), case-insensitive
    text: str


# ---------------------------------------------------------------------------
# Jitter + retry policy value types (DOC-CMP-SCM-05 §3.1)
# ---------------------------------------------------------------------------


class JitterMode(str, Enum):  # (str, Enum) per DOC §3.1; see pyproject UP042 note.
    """Jitter strategy applied to the exponential backoff curve."""

    NONE = "none"  # sleep = base
    FULL = "full"  # AWS-style: sleep = random(0, base)
    EQUAL = "equal"  # sleep = base/2 + random(0, base/2)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Provider-neutral retry/backoff configuration. AC-SCM-05a (DOC §3.1)."""

    initial_backoff_s: float = 1.0
    max_backoff_s: float = 60.0
    backoff_factor: float = 2.0  # exponential base
    jitter: JitterMode = JitterMode.FULL
    max_attempts: int = 6  # including the first try
    # Provider-rate-limit semantics
    honor_429: bool = True  # any 429 → wait + retry (until budget)
    honor_secondary: bool = True  # GitHub-style abuse / secondary
    honor_retry_after: bool = True  # Retry-After header (seconds | HTTP-date)
    # Per-provider hard cap on the total time spent retrying a single call
    total_deadline_s: float | None = None  # None ⇒ no deadline (only attempts cap)


# Per-provider default policies (DOC §3.2). Callers may pass an override.
GITHUB_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0,
    max_backoff_s=60.0,
    max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True,
    honor_secondary=True,
    honor_retry_after=True,
    total_deadline_s=None,
)

GITLAB_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0,
    max_backoff_s=60.0,
    max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True,
    honor_secondary=False,
    honor_retry_after=True,
    total_deadline_s=None,
)

BITBUCKET_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0,
    max_backoff_s=60.0,
    max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True,
    honor_secondary=True,
    honor_retry_after=True,
    total_deadline_s=None,
)

AZURE_DEVOPS_DEFAULT = RetryPolicy(
    initial_backoff_s=1.0,
    max_backoff_s=60.0,
    max_attempts=6,
    jitter=JitterMode.FULL,
    honor_429=True,
    honor_secondary=False,
    honor_retry_after=True,
    total_deadline_s=None,
)


# ---------------------------------------------------------------------------
# Rate-limit classification (DOC-CMP-SCM-05 §3.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RateLimitVerdict:
    """Per-provider classification of one response (DOC §3.3)."""

    is_rate_limited: bool
    retry_after_s: float | None = None  # provider-honoured wait, if any
    is_secondary: bool = False  # GitHub abuse / Bitbucket abuse


def _header(response: object, name: str) -> str | None:
    """Read one header case-insensitively from a response-like object.

    `httpx.Headers` is case-insensitive; a plain `dict` is not, so we fall back
    to a manual case-fold scan to keep the hooks pure and client-agnostic.
    """
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is not None:
            return str(value)
        # dict.get is case-sensitive — scan case-insensitively as a fallback.
        items = getattr(headers, "items", None)
        if callable(items):
            lowered = name.lower()
            for key, val in items():
                if str(key).lower() == lowered:
                    return str(val)
    return None


def _parse_retry_after(raw: str | None) -> float | None:
    """Parse a `Retry-After` value: delta-seconds OR an HTTP-date (RFC 7231).

    Returns a non-negative number of seconds, or None if absent/unparseable.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        # Malformed HTTP-date (and not delta-seconds) → treat as absent.
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


def _reset_wait(response: object) -> float | None:
    """Seconds until `X-RateLimit-Reset` (epoch seconds), or None."""
    raw = _header(response, "X-RateLimit-Reset")
    if raw is None:
        return None
    try:
        reset_epoch = float(raw)
    except ValueError:
        return None
    return max(0.0, reset_epoch - datetime.now(UTC).timestamp())


def classify_github(response: object) -> RateLimitVerdict:
    """GitHub: 403 + `X-RateLimit-Remaining: 0` (primary) or a 403/429 body
    abuse marker (secondary). Retry-after from `X-RateLimit-Reset` (primary)
    or `Retry-After` (secondary). DOC §3.3.
    """
    status = getattr(response, "status_code", None)
    body = (getattr(response, "text", "") or "").lower()
    is_secondary = ("secondary rate limit" in body) or ("abuse detection" in body)
    if is_secondary:
        retry_after = _parse_retry_after(_header(response, "Retry-After"))
        return RateLimitVerdict(is_rate_limited=True, retry_after_s=retry_after, is_secondary=True)
    remaining = _header(response, "X-RateLimit-Remaining")
    if status in (403, 429) and remaining == "0":
        return RateLimitVerdict(
            is_rate_limited=True, retry_after_s=_reset_wait(response), is_secondary=False
        )
    return RateLimitVerdict(is_rate_limited=False)


def classify_gitlab(response: object) -> RateLimitVerdict:
    """GitLab: `429` with `Retry-After`. No secondary class. DOC §3.3."""
    if getattr(response, "status_code", None) == 429:
        retry_after = _parse_retry_after(_header(response, "Retry-After"))
        return RateLimitVerdict(is_rate_limited=True, retry_after_s=retry_after)
    return RateLimitVerdict(is_rate_limited=False)


def classify_bitbucket(response: object) -> RateLimitVerdict:
    """Bitbucket: `429`; `X-Bitbucket-Type: abuse` marks secondary. DOC §3.3."""
    if getattr(response, "status_code", None) == 429:
        retry_after = _parse_retry_after(_header(response, "Retry-After"))
        is_secondary = (_header(response, "X-Bitbucket-Type") or "").lower() == "abuse"
        return RateLimitVerdict(
            is_rate_limited=True, retry_after_s=retry_after, is_secondary=is_secondary
        )
    return RateLimitVerdict(is_rate_limited=False)


def classify_azure_devops(response: object) -> RateLimitVerdict:
    """Azure DevOps: `429`; honoured wait = max(`Retry-After`,
    `X-RateLimit-Delay`). DOC §3.3.
    """
    if getattr(response, "status_code", None) == 429:
        retry_after = _parse_retry_after(_header(response, "Retry-After"))
        delay = _parse_retry_after(_header(response, "X-RateLimit-Delay"))
        candidates = [v for v in (retry_after, delay) if v is not None]
        wait = max(candidates) if candidates else None
        return RateLimitVerdict(is_rate_limited=True, retry_after_s=wait)
    return RateLimitVerdict(is_rate_limited=False)


# ---------------------------------------------------------------------------
# The retry decorator (DOC-CMP-SCM-05 §3.4)
# ---------------------------------------------------------------------------

P = ParamSpec("P")
T = TypeVar("T")

# Errors that must propagate immediately without retry (DOC §7).
_NON_RETRYABLE: tuple[type[Exception], ...] = (SCMAuthError, SCMNotFoundError)


def _curve_base(policy: RetryPolicy, attempt_index: int) -> float:
    """base[i] = min(initial * factor**i, max) — DOC §3.4."""
    raw = policy.initial_backoff_s * (policy.backoff_factor**attempt_index)
    return min(raw, policy.max_backoff_s)


def _apply_jitter(base: float, mode: JitterMode, rng: random.Random) -> float:
    """Apply the jitter strategy to a curve `base` value (DOC §3.1, §3.4)."""
    if mode is JitterMode.NONE:
        return base
    if mode is JitterMode.FULL:
        return rng.uniform(0.0, base)
    # EQUAL — base/2 + random(0, base/2)
    half = base / 2.0
    return half + rng.uniform(0.0, half)


def with_retry(
    *,
    policy: RetryPolicy,
    classify: Callable[[object], RateLimitVerdict],
    on_attempt: Callable[[int, float, str], None] | None = None,
    _sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    _rng: random.Random | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate an async function performing one HTTP call (DOC §3.4).

    Sleep curve:
      base[i]  = min(initial_backoff_s * backoff_factor**i, max_backoff_s)
      sleep[i] = jitter(base[i])                  # JitterMode.FULL by default
      override: a provider-honoured `retry_after_s` (from `classify`) always
                wins over the computed curve.

    Stop conditions:
      - attempts ≥ policy.max_attempts             → raise the last exception
        (SCMRateLimitError when the last attempt was rate-limited, else the
        last SCMTransientError).
      - cumulative sleep ≥ policy.total_deadline_s → raise SCMRateLimitError.
      - non-retryable exception (SCMAuthError, SCMNotFoundError) → propagate.

    The decorated function may either raise `SCMTransientError` (network/5xx
    mapped by the caller) or return a response object that `classify` deems
    rate-limited; both are retried. Any other return value is passed through.

    `_sleep` and `_rng` are test seams (deterministic backoff in unit tests);
    they are not part of the caller-facing contract.
    """
    rng = _rng if _rng is not None else random.Random()  # noqa: S311 — retries are off the determinism partition (DOC §6)

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            cumulative_sleep = 0.0
            last_verdict: RateLimitVerdict | None = None
            last_transient: SCMTransientError | None = None

            for attempt in range(policy.max_attempts):
                reason: str
                try:
                    result = await func(*args, **kwargs)
                except _NON_RETRYABLE:
                    raise  # propagate immediately; never retried (DOC §7)
                except SCMTransientError as exc:
                    last_transient = exc
                    last_verdict = None
                    reason = "transient-5xx"
                else:
                    verdict = classify(result)
                    if not verdict.is_rate_limited:
                        return result  # success
                    last_verdict = verdict
                    last_transient = None
                    reason = (
                        "rate-limited-secondary" if verdict.is_secondary else "rate-limited-primary"
                    )

                # This attempt failed retryably. If it was the last allowed
                # attempt, stop now and raise the appropriate terminal error.
                if attempt + 1 >= policy.max_attempts:
                    break

                sleep_s = _next_sleep(policy, attempt, last_verdict, rng)

                # Deadline check: if this sleep would breach the budget, give up.
                if (
                    policy.total_deadline_s is not None
                    and cumulative_sleep + sleep_s >= policy.total_deadline_s
                ):
                    raise SCMRateLimitError(
                        f"total_deadline_s={policy.total_deadline_s}s exhausted "
                        f"after {attempt + 1} attempt(s)"
                    )

                if on_attempt is not None:
                    on_attempt(attempt, sleep_s, reason)
                await _sleep(sleep_s)
                cumulative_sleep += sleep_s

            # Attempts exhausted on a retryable failure (DOC §7).
            if last_verdict is not None:
                raise SCMRateLimitError(
                    f"max_attempts={policy.max_attempts} exhausted while rate-limited"
                )
            if last_transient is not None:
                raise last_transient
            # Unreachable: the loop only breaks after a retryable failure.
            raise SCMRateLimitError("retry budget exhausted")  # pragma: no cover

        return wrapper

    return decorator


def _next_sleep(
    policy: RetryPolicy,
    attempt_index: int,
    verdict: RateLimitVerdict | None,
    rng: random.Random,
) -> float:
    """Compute the sleep before the next attempt (DOC §3.4).

    A provider-honoured `retry_after_s` overrides the jittered curve when the
    policy opts to honour it; otherwise the exponential-with-jitter curve.
    """
    if verdict is not None and verdict.retry_after_s is not None and policy.honor_retry_after:
        return max(0.0, verdict.retry_after_s)
    base = _curve_base(policy, attempt_index)
    return _apply_jitter(base, policy.jitter, rng)

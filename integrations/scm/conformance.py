"""CMP-SCM-01 — provider-neutral conformance suite (AC-SCM-01c).

`run_conformance_suite` drives an `SCMConnector` through a fixed sequence of
operations and asserts provider-neutral behaviour. The same declarative harness
is reused by TST-AC-SCM-02a (GitHub) and TST-AC-SCM-03a (GL/BB/ADO) — adding a
fifth provider is one subclass and one suite invocation (DOC-CMP-SCM-01 §3.3).

The harness is intentionally free of provider-specific assertions: it checks
only the shapes and contracts the ABC promises (return types, the boolean
`verify_webhook` predicate over a genuine vs. tampered body, a 40-hex SHA from
`resolve_commit`, a non-empty default branch).
"""

from __future__ import annotations

import re
import shutil
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

from integrations.scm.base import (
    CloneMetadata,
    RepoRef,
    SCMConnector,
    WebhookSubscription,
)

__all__ = [
    "CONFORMANCE_OPERATIONS",
    "ConformanceFailure",
    "ConformanceReport",
    "run_conformance_suite",
]

# The fixed operation sequence the suite drives (DOC §3.3). `verify_webhook` is
# split into a positive and a negative case so each is independently reported.
CONFORMANCE_OPERATIONS: tuple[str, ...] = (
    "list_repos",
    "clone",
    "register_webhook",
    "verify_webhook_positive",
    "verify_webhook_negative",
    "get_default_branch",
    "resolve_commit",
)

_SHA_RE = re.compile(r"[0-9a-f]{40}")

# A fixed, provider-neutral webhook body + secret used by the positive/negative
# verify_webhook checks. The negative case flips one byte; an authentic
# connector must return True for the genuine body and False for the tampered one.
_WEBHOOK_BODY = b'{"event":"push","ref":"refs/heads/main"}'
_WEBHOOK_TAMPERED = b'{"event":"push","ref":"refs/heads/MAIN"}'
_WEBHOOK_SECRET = "conformance-shared-secret"  # noqa: S105  # pragma: allowlist secret


@dataclass(frozen=True, slots=True)
class ConformanceFailure:
    """A single operation the connector failed to satisfy."""

    method: str  # ABC method name (or split verify_webhook case) that failed
    reason: str  # short description (e.g. "wrong type returned")
    detail: str  # full repr / traceback excerpt


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    """Outcome of driving a connector through the fixed operation sequence."""

    provider: str  # connector.provider_id
    passed: tuple[str, ...]  # names of operations that passed
    failures: tuple[ConformanceFailure, ...]  # empty ⇒ conformant

    @property
    def is_conformant(self) -> bool:
        return not self.failures


async def run_conformance_suite(
    connector: SCMConnector,
    *,
    fixture_repo: RepoRef,
    canary_commit_sha: str,
) -> ConformanceReport:
    """Drive `connector` through the fixed operation sequence and report.

    Each operation that satisfies its contract is recorded in `passed`; each
    that raises or returns the wrong shape becomes a `ConformanceFailure`
    naming the operation. A fully conformant connector yields an empty
    `failures` tuple. The harness is declarative and provider-neutral.
    """
    passed: list[str] = []
    failures: list[ConformanceFailure] = []

    # ---- list_repos --------------------------------------------------------
    try:
        repos: list[RepoRef] = []
        async for repo in connector.list_repos(org_or_workspace=fixture_repo.owner):
            if not isinstance(repo, RepoRef):
                raise TypeError(f"list_repos yielded {type(repo).__name__}, expected RepoRef")
            repos.append(repo)
        passed.append("list_repos")
    except Exception as exc:
        failures.append(_failure("list_repos", exc))

    # ---- clone -------------------------------------------------------------
    clone_dir = Path(tempfile.mkdtemp(prefix="scanipy-conformance-"))
    try:
        meta = await connector.clone(
            fixture_repo,
            commit_sha=canary_commit_sha,
            dest_dir=clone_dir,
            shallow=True,
        )
        if not isinstance(meta, CloneMetadata):
            raise TypeError(f"clone returned {type(meta).__name__}, expected CloneMetadata")
        if not _SHA_RE.fullmatch(meta.commit_sha):
            raise ValueError(f"clone commit_sha not 40-hex: {meta.commit_sha!r}")
        passed.append("clone")
    except Exception as exc:
        failures.append(_failure("clone", exc))
    finally:
        shutil.rmtree(clone_dir, ignore_errors=True)

    # ---- register_webhook --------------------------------------------------
    try:
        sub = await connector.register_webhook(
            fixture_repo,
            target_url="https://scanipy.example/webhooks/scm",
            events=("push", "pull_request"),
            secret=_WEBHOOK_SECRET,
        )
        if not isinstance(sub, WebhookSubscription):
            raise TypeError(
                f"register_webhook returned {type(sub).__name__}, expected WebhookSubscription"
            )
        passed.append("register_webhook")
    except Exception as exc:
        failures.append(_failure("register_webhook", exc))

    # ---- verify_webhook (positive) -----------------------------------------
    try:
        genuine = connector.verify_webhook(
            raw_body=_WEBHOOK_BODY,
            headers=_signature_headers(connector, _WEBHOOK_BODY),
            secret=_WEBHOOK_SECRET,
        )
        if genuine is not True:
            raise AssertionError(f"verify_webhook on a genuine body returned {genuine!r}, not True")
        passed.append("verify_webhook_positive")
    except Exception as exc:
        failures.append(_failure("verify_webhook_positive", exc))

    # ---- verify_webhook (negative) -----------------------------------------
    try:
        forged = connector.verify_webhook(
            raw_body=_WEBHOOK_TAMPERED,
            headers=_signature_headers(connector, _WEBHOOK_BODY),  # sig over original body
            secret=_WEBHOOK_SECRET,
        )
        if forged is not False:
            raise AssertionError(
                f"verify_webhook on a tampered body returned {forged!r}, not False"
            )
        passed.append("verify_webhook_negative")
    except Exception as exc:
        failures.append(_failure("verify_webhook_negative", exc))

    # ---- get_default_branch ------------------------------------------------
    try:
        branch = await connector.get_default_branch(fixture_repo)
        if not isinstance(branch, str) or not branch:
            raise ValueError(f"get_default_branch returned {branch!r}, expected non-empty str")
        passed.append("get_default_branch")
    except Exception as exc:
        failures.append(_failure("get_default_branch", exc))

    # ---- resolve_commit ----------------------------------------------------
    try:
        ref = fixture_repo.default_branch or "main"
        sha = await connector.resolve_commit(fixture_repo, ref=ref)
        if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
            raise ValueError(f"resolve_commit returned {sha!r}, expected 40-hex SHA")
        passed.append("resolve_commit")
    except Exception as exc:
        failures.append(_failure("resolve_commit", exc))

    return ConformanceReport(
        provider=connector.provider_id,
        passed=tuple(passed),
        failures=tuple(failures),
    )


def _failure(method: str, exc: BaseException) -> ConformanceFailure:
    return ConformanceFailure(
        method=method,
        reason=f"{type(exc).__name__}: {exc}",
        detail="".join(traceback.format_exception_only(type(exc), exc)).strip(),
    )


def _signature_headers(connector: SCMConnector, body: bytes) -> dict[str, str]:
    """Build the provider-specific signature header for a genuine body.

    The harness asks the connector to sign so it stays provider-neutral: a
    connector that implements `verify_webhook` for its scheme must accept the
    signature produced by the matching `_sign_webhook` helper. Connectors expose
    an optional `sign_webhook` test hook; absent one, the harness sends no
    signature header and the positive case is the connector's to satisfy.
    """
    signer = getattr(connector, "sign_webhook", None)
    if callable(signer):
        headers = signer(raw_body=body, secret=_WEBHOOK_SECRET)
        if isinstance(headers, dict):
            return {str(k): str(v) for k, v in headers.items()}
    return {}

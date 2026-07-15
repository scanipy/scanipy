"""CMP-SNAP-05 — pinned-image snapshot worker entrypoint (``python -m`` target).

Implementation contract: ``docs/components/DOC-CMP-SNAP-05.md`` (§3.1 env-var
contract, §3.3 argv allowlist, §6 lifecycle, §7 fail-closed). Cross-cutting:
``DOC-INV §4`` (INV-2 ORIGIN — this component is the platform's ``env_digest``
origin), ``.claude/rules/02-provenance.md`` (env_digest threading),
``.claude/rules/00-global.md`` (RULE-6).

This module is the **ECS Fargate container entrypoint**: the worker Dockerfile
(``workers/snapshot/Dockerfile``) runs ``ENTRYPOINT ["python", "-m",
"services.snapshot.worker"]``. Two pieces of worker LOGIC are delivered and
verified hermetically here:

1. **Env-digest binding (``AC-SNAP-05b``, INV-2 ORIGIN).** :func:`resolve_env_digest`
   reads the worker's image digest from ``SCANIPY_ENV_DIGEST`` — the value ECS
   injects from the running task's image metadata (DOC §3.1, §8). It is the
   **authoritative ``env_digest`` for the entire platform**: it is stamped onto
   the snapshot job and threaded into ``report_status``. A missing, empty, or
   malformed digest is **fail-closed** (:class:`EnvDigestMissing`): the worker
   refuses to start, because INV-2 forbids running analysis against an unpinned
   ``Env`` (DOC §7 — "INV-2 absolutely requires a real digest").

2. **Argv allowlist (``AC-SNAP-05a``).** Every pinned-tool (``joern`` / ``codeql``
   / ``git``) invocation routes through :func:`tools.worker.secure_subprocess.secure_run`,
   re-exported here, which rejects any non-sanctioned flag fail-closed before a
   subprocess is spawned (``shell=False`` always).

BUILD-AHEAD (sanctioned, DOC §1 Depends-On ``CMP-SNAP-01``, ``CMP-DEPLOY-02``):
the *real-image* half of CMP-SNAP-05 — the live SQS dequeue → ``CMP-SCM-*`` clone
→ ``CMP-SNAP-03`` CW-DETECT → ``CMP-SNAP-02`` incremental CPG → S3 upload →
HMAC ``report_status`` execute loop (DOC §6.2) — is **env-gated on the AWS
substrate track** (the worker container build, ``workers/pins.json`` digests are
all-zero placeholders the AWS team fills). That loop is intentionally NOT wired
here: it would require unbuilt collaborators and real digests. What ships and is
green hermetically is the worker *bootstrap logic*: the env-digest binding +
fail-closed gate (the INV-2 ORIGIN) and the argv-allowlist call path. The
:func:`main` bootstrap performs exactly the fail-closed boot gate; the per-job
execute loop raises a typed ``NotImplementedError`` naming its unbuilt deps, so
the gating is honest rather than faked.

This module writes NO provenance fields to a ``Finding``; it threads
``env_digest`` (INV-2) into the snapshot pipeline via the SNAP-01 callback
(DOC §8). It MUST NOT touch ``origin`` (CMP-ORCH-03), ``S_version`` (CMP-ORCH-01),
``cpg_order_hash`` (CMP-CORE-03), or ``slice_fingerprint`` (CMP-CORE-02).
"""

from __future__ import annotations

import os
import re
import sys
from typing import TYPE_CHECKING, Literal

from tools.observability.logging import get_logger
from tools.observability.metrics import record_job_completion

# Re-export the argv-allowlist surface so the worker's single import point is
# this module (DOC §3.3 — every secure_run call site lives behind the worker).
from tools.worker.secure_subprocess import (
    ArgvAllowlistViolation,
    UnknownTool,
    secure_run,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# INV-2: env_digest is the worker container image digest. Same format CHECK as
# the shipped ``snapshots.env_digest_chk`` DDL constraint and the SNAP-01 service
# guard (services/snapshot/service.py) — one canonical sha256-image-digest shape.
_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# The env var ECS injects from the running task's image metadata (DOC §3.1).
ENV_DIGEST_VAR = "SCANIPY_ENV_DIGEST"


class EnvDigestMissing(Exception):  # noqa: N818 — name fixed verbatim by DOC-CMP-SNAP-05 §3.4
    """``SCANIPY_ENV_DIGEST`` was unset/empty/malformed at boot (fail-closed).

    DOC-CMP-SNAP-05 §3.4 / §7: INV-2 requires a real ``env_digest`` (the running
    image digest). The worker refuses to start without one — running analysis
    against an unpinned ``Env`` would silently break the reproducibility theorem
    (PLAN property (a)). This is the INV-2 ORIGIN fail-closed gate.
    """


def resolve_env_digest(environ: dict[str, str] | None = None) -> str:
    """Return the authoritative ``env_digest`` from the runtime-injected env var.

    Reads ``SCANIPY_ENV_DIGEST`` (ECS task-metadata injection, DOC §3.1) and
    guards it against the canonical ``^sha256:[0-9a-f]{64}$`` image-digest shape.
    A missing, empty, or malformed value is **fail-closed**:
    :class:`EnvDigestMissing` is raised (INV-2 ORIGIN, DOC §7) — there is no
    default and no fallback, so the worker can never stamp a snapshot with an
    unpinned ``Env``.

    Args:
        environ: an env mapping to read (defaults to :data:`os.environ`); the
            ``None`` default keeps the call hermetic — tests inject a fixture
            digest rather than mutating process state.

    Returns:
        The verbatim image digest string (this exact value is the platform's
        ``env_digest`` per INV-2; it is stamped on the snapshot job and threaded
        into ``report_status``).

    Raises:
        EnvDigestMissing: the var is unset, empty, or not a sha256 image digest.
    """
    env = os.environ if environ is None else environ
    candidate = env.get(ENV_DIGEST_VAR, "")
    if not candidate:
        raise EnvDigestMissing(
            f"INV-2: {ENV_DIGEST_VAR} must be injected from the running image "
            "digest before the worker starts; the worker refuses to run against "
            "an unpinned Env (DOC-CMP-SNAP-05 §7)"
        )
    if not _ENV_DIGEST_RE.fullmatch(candidate):
        raise EnvDigestMissing(
            f"INV-2: {ENV_DIGEST_VAR}={candidate!r} is not a pinned container "
            "image digest matching 'sha256:<64-hex>'; fail-closed (the env_digest "
            "must be a real image digest, never a default or placeholder)"
        )
    return candidate


def boot(environ: dict[str, str] | None = None) -> str:
    """Run the worker boot gate and return the bound ``env_digest``.

    The single fail-closed step the worker performs before *any* job work: bind
    the authoritative ``env_digest`` (INV-2 ORIGIN). Returns the digest so a
    caller (or test) can assert the bound value; raises :class:`EnvDigestMissing`
    if the gate trips. This is the seam ``main`` calls first and the seam the
    AC-SNAP-05b test drives with a fixture digest.
    """
    return resolve_env_digest(environ)


def record_snapshot_job_completion(
    outcome: Literal["success", "failure"],
    duration_ms: float,
    *,
    env_digest: str,
    precondition_status: str,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Emit the CMP-SNAP-05 job-completion metrics (DOC-CMP-DEPLOY-03 §3.4 1-3).

    The CLAR-DEPLOY-20 emission seam the DOC §6.2 execute loop calls **exactly
    once per dequeued SQS message**:

    * ``outcome="failure"`` — the message terminated in
      ``report_status(state='failed')`` (any DOC-CMP-SNAP-05 §7 terminal
      failure path) → ``snapshot_worker.failure_count``.
    * ``outcome="success"`` — the ``report_status(state='ready')`` POST
      returned 2xx → ``snapshot_worker.success_count``.

    Either way ``snapshot_worker.duration_ms`` records ``duration_ms``, the
    dequeue→report wall time measured on the **monotonic clock**
    (``time.monotonic``), never wall-clock arithmetic. Counter attributes are
    ``{region, env_digest}`` (region from ``AWS_REGION``, default
    ``us-east-1``); the duration attribute is ``{precondition_status}`` (the
    CW-DETECT verdict for the job). Retries count per-attempt, intentionally
    (CLAR-DEPLOY-20): the failure-rate alarm denominator is completions.

    Hermetic: a plain function of its inputs plus an injectable ``environ``
    (defaults to :data:`os.environ`), and a no-op without OTel installed — it
    can never take down the job loop.
    """
    env = os.environ if environ is None else environ
    record_job_completion(
        "snapshot_worker",
        outcome,
        duration_ms,
        counter_attributes={
            "region": env.get("AWS_REGION", "us-east-1"),
            "env_digest": env_digest,
        },
        duration_attributes={"precondition_status": precondition_status},
    )


def run_execute_loop(env_digest: str) -> None:
    """The per-job SQS execute loop (DOC §6.2) — env-gated on the AWS substrate.

    BUILD-AHEAD honesty: the live dequeue → ``CMP-SCM-*`` clone → ``CMP-SNAP-03``
    CW-DETECT → ``CMP-SNAP-02`` incremental CPG → S3 upload → HMAC
    ``report_status`` loop requires unbuilt collaborators (``CMP-SNAP-01/02``
    seams, ``CMP-SCM-*``) and a real worker image with non-placeholder
    ``workers/pins.json`` digests (``CMP-DEPLOY-02``). Rather than fake that
    pipeline, this raises a typed refusal naming the unbuilt deps — the boot gate
    (:func:`boot`) and the argv allowlist (:func:`secure_run`) are the parts that
    are real and tested today.

    OBSERVABILITY CONTRACT (CMP-DEPLOY-03 / CLAR-DEPLOY-20): when this loop
    lands it MUST call :func:`record_snapshot_job_completion` exactly once per
    dequeued message, on the ``report_status`` outcome (``success`` on a 2xx
    ``state='ready'`` POST, ``failure`` on any terminal ``state='failed'``
    path), with the dequeue→report duration from the monotonic clock.

    Args:
        env_digest: the bound authoritative ``env_digest`` (INV-2) that every
            ``report_status`` callback in the real loop will thread (DOC §8).
    """
    raise NotImplementedError(
        "CMP-SNAP-05 execute loop is gated on CMP-DEPLOY-02 (worker image build; "
        f"workers/pins.json digests are all-zero placeholders) and CMP-SNAP-01/02 "
        f"seams; env_digest={env_digest!r} is bound and ready to thread once the "
        "AWS substrate track lands. See DOC-CMP-SNAP-05 §6.2."
    )


def main(argv: list[str] | None = None) -> int:
    """Container entrypoint: fail-closed boot gate, then the (gated) execute loop.

    Wired by ``ENTRYPOINT ["python", "-m", "services.snapshot.worker"]``. Step 1
    is the INV-2 ORIGIN gate: bind ``env_digest`` or refuse to start
    (exit non-zero) — exactly the DOC §7 contract ("Refuse to start; ECS task
    exits non-zero"). Step 2 hands off to :func:`run_execute_loop`, which is
    env-gated on the AWS substrate track (see its docstring).

    Returns the process exit code: ``0`` is unreachable while the execute loop is
    substrate-gated; a failed boot gate returns ``1`` (fail-closed).
    """
    _ = argv  # the worker takes no CLI args; ECS injects config via env vars.
    try:
        env_digest = boot()
    except EnvDigestMissing as exc:
        # Fail-closed boot refusals stay on plain stderr: the AC-DEPLOY-03b
        # structured envelope requires a non-empty env_digest, which is exactly
        # what is missing here (the process never serves traffic).
        print(f"FATAL (INV-2 fail-closed): {exc}", file=sys.stderr)
        return 1
    # AC-DEPLOY-03b: every log line from this entrypoint rides the structured
    # JSON envelope (service, build_commit, env_digest) via ScanipyJsonFormatter.
    get_logger("snapshot-worker").info("snapshot worker boot: env_digest bound")
    run_execute_loop(env_digest)
    return 0  # pragma: no cover — unreachable until the substrate track lands.


__all__ = [
    "ENV_DIGEST_VAR",
    "ArgvAllowlistViolation",
    "EnvDigestMissing",
    "UnknownTool",
    "boot",
    "main",
    "record_snapshot_job_completion",
    "resolve_env_digest",
    "run_execute_loop",
    "secure_run",
]


if __name__ == "__main__":  # pragma: no cover — exercised only as the container entrypoint.
    sys.exit(main())

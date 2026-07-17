"""Submit a real detector job directly to the detector-worker SQS queue.

Bypasses the not-yet-deployed HTTP scan API (`CMP-ORCH-01`) entirely — the
same "shortcut path" as ``scripts/submit_snapshot_job.py``, for the
detector-worker side of the pipeline
(``services/scan/detector_worker.py::run_execute_loop``, wired for real in
`CLAR-DEPLOY-24`).

**KNOWN BLOCKER — CLAR-ORCH-11 (WBS.md §17, OPEN):** the snapshot and
detector workers are separately-versioned container images with genuinely
different ``env_digest`` values. A submitted detector job's ``env_digest``
must equal the DETECTOR worker's own boot digest (INV-2 guard,
``services/scan/detector_worker.py:483-488``) to be accepted at all, but
that same value is also used to build the S3 key
(``SnapshotKeyBuilder(..., env_digest=job.env_digest)``,
``detector_worker.py:496-501``) that must resolve to the CPG tarball the
SNAPSHOT worker actually wrote — which it wrote under ITS OWN (different)
boot digest. No single value can satisfy both constraints today. This
script still exists and is directly usable for testing `run_detector_job`
against a **fake/pre-staged S3 object** (e.g. a hermetic rehearsal), but a
job submitted through this script against a *live* queue will currently be
rejected by whichever guard the chosen ``--env-digest`` value doesn't
satisfy, until CLAR-ORCH-11 is ruled.

Reuses the real, shipped :class:`services.substrate.queue.SQSQueue`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "workers" / "env_digest_history.json"


def _active_detector_env_digest() -> str:
    from workers.build.env_digest_registry import active_digest, load_registry

    doc = load_registry(_REGISTRY_PATH)
    return active_digest(doc, "scanipy-detector")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", required=True, help="Org UUID (must match the snapshot job).")
    parser.add_argument(
        "--codebase-id", required=True, help="Codebase UUID (must match the snapshot job)."
    )
    parser.add_argument(
        "--snapshot-id", required=True, help="Snapshot UUID (must match the snapshot job)."
    )
    parser.add_argument(
        "--commit-sha", required=True, help="Commit SHA (must match the snapshot job)."
    )
    parser.add_argument(
        "--detector-id",
        default="java-py-injection",
        help="CMP-DET-02 registry id (default: the Stage-A injection detector).",
    )
    parser.add_argument("--s-version", default="1.4.2", help="Accepted spec-set semver.")
    parser.add_argument(
        "--env-digest",
        default=None,
        help=(
            "Detector-worker env_digest (default: the registry's current "
            "'active' scanipy-detector entry). See CLAR-ORCH-11 — this "
            "value cannot currently also correctly address the snapshot "
            "artifact's S3 key."
        ),
    )
    parser.add_argument("--scm-provider", default="github")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--scan-id", default=None)
    parser.add_argument(
        "--queue-url", default=None, help="Detector SQS queue URL (default: $DETECTOR_QUEUE_URL)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message body and exit without sending anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    job_id = args.job_id or str(uuid.uuid4())
    scan_id = args.scan_id or str(uuid.uuid4())
    env_digest = args.env_digest or _active_detector_env_digest()

    body = {
        "job_id": job_id,
        "scan_id": scan_id,
        "snapshot_id": args.snapshot_id,
        "codebase_id": args.codebase_id,
        "commit_sha": args.commit_sha,
        "detector_id": args.detector_id,
        "S_version": args.s_version,
        "env_digest": env_digest,
        "org_id": args.org_id,
        "scm_provider": args.scm_provider,
    }

    print(json.dumps(body, indent=2), file=sys.stderr)
    print(
        "WARNING: CLAR-ORCH-11 (OPEN) — this env_digest satisfies the "
        "detector's own boot-digest guard but will not correctly address "
        "the snapshot worker's S3 write-side key unless the two worker "
        "images happen to share a digest. See this script's module "
        "docstring.",
        file=sys.stderr,
    )

    if args.dry_run:
        print("(--dry-run: not sent)", file=sys.stderr)
        return 0

    queue_url = args.queue_url or os.environ.get("DETECTOR_QUEUE_URL")
    if not queue_url:
        print(
            "DETECTOR_QUEUE_URL must be set (or pass --queue-url)",
            file=sys.stderr,
        )
        return 1

    from services.substrate.queue import SQSQueue

    queue = SQSQueue(queue_url)
    queue.send(body, dedup_key=job_id)

    print(f"job_id={job_id}", file=sys.stderr)
    print(f"scan_id={scan_id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

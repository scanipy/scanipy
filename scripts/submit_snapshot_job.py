"""Submit a real ``SnapshotJob`` directly to the snapshot-worker SQS queue.

Bypasses the not-yet-deployed HTTP scan API (`CMP-ORCH-01`) entirely — this
is the "shortcut path" for the first real end-to-end scan proof: submit a
job straight onto the queue the worker is already really consuming from
(`services/snapshot/worker.py::run_execute_loop`, wired for real in
`CLAR-DEPLOY-24`/`CLAR-SNAP-03/05`/`CLAR-ORCH-10`).

Reuses the real, shipped :class:`services.substrate.queue.SQSQueue` (not a
hand-rolled ``boto3.client("sqs").send_message`` call) so the message
envelope is guaranteed to match exactly what the worker's own
:class:`services.substrate.queue.SQSQueue.receive` expects to parse back
out (JSON body, ``dedup_key`` message attribute).

``env_digest`` defaults to the registry's current ``active`` entry for
``scanipy-snapshot`` (``workers/env_digest_history.json``, CLAR-DEPLOY-22) —
the snapshot worker refuses any job whose ``env_digest`` does not match its
own bound boot digest (INV-2 guard, ``services/snapshot/worker.py:663-668``),
so submitting anything else against a live worker will always be rejected.

Usage::

    SNAPSHOT_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../scanipy-prod-snapshot-jobs \\
    python -m scripts.submit_snapshot_job \\
        --clone-url https://github.com/michealkeines/Vulnerable-API.git \\
        --commit-sha f7797964e1cd63a1cbcc8ced721fa41db674c8e0

Prints the ``snapshot_id``/``codebase_id`` it generated (or was given) so
the matching detector job (``scripts/submit_detector_job.py``) can be
submitted against the same coordinates once the snapshot completes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# TEST_ORG_ID must match scripts/seed_test_org.py exactly — same obviously-
# synthetic org id, reused so a submitted job's org_id satisfies the
# findings.org_id FK once the detector side inserts a real Finding row.
TEST_ORG_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")

_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "workers" / "env_digest_history.json"


def _active_snapshot_env_digest() -> str:
    from workers.build.env_digest_registry import active_digest, load_registry

    doc = load_registry(_REGISTRY_PATH)
    return active_digest(doc, "scanipy-snapshot")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone-url", required=True, help="Public HTTPS git clone URL.")
    parser.add_argument("--commit-sha", required=True, help="Full 40-char commit SHA to scan.")
    parser.add_argument(
        "--org-id",
        default=str(TEST_ORG_ID),
        help="Org UUID (default: the CLAR-CP-01-02 test org).",
    )
    parser.add_argument(
        "--codebase-id",
        default=None,
        help="Codebase UUID (default: a fresh random UUID, printed on success).",
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help="Snapshot UUID (default: a fresh random UUID, printed on success).",
    )
    parser.add_argument(
        "--env-digest",
        default=None,
        help=(
            "Snapshot-worker env_digest (default: the registry's current "
            "'active' scanipy-snapshot entry)."
        ),
    )
    parser.add_argument(
        "--queue-url",
        default=None,
        help="Snapshot SQS queue URL (default: $SNAPSHOT_QUEUE_URL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message body and exit without sending anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    codebase_id = args.codebase_id or str(uuid.uuid4())
    snapshot_id = args.snapshot_id or str(uuid.uuid4())
    env_digest = args.env_digest or _active_snapshot_env_digest()

    body = {
        "snapshot_id": snapshot_id,
        "org_id": args.org_id,
        "codebase_id": codebase_id,
        "commit_sha": args.commit_sha,
        "env_digest": env_digest,
        "clone_url": args.clone_url,
    }

    print(json.dumps(body, indent=2), file=sys.stderr)

    if args.dry_run:
        print("(--dry-run: not sent)", file=sys.stderr)
        return 0

    queue_url = args.queue_url or os.environ.get("SNAPSHOT_QUEUE_URL")
    if not queue_url:
        print(
            "SNAPSHOT_QUEUE_URL must be set (or pass --queue-url)",
            file=sys.stderr,
        )
        return 1

    from services.substrate.queue import SQSQueue

    queue = SQSQueue(queue_url)
    queue.send(body, dedup_key=snapshot_id)

    print(f"snapshot_id={snapshot_id}", file=sys.stderr)
    print(f"codebase_id={codebase_id}", file=sys.stderr)
    print(f"env_digest={env_digest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

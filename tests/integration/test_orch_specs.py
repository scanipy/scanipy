"""ORCH-family integration specs — TST-AC-ORCH-* (integration / regression /
empirical).

Spec-first TDD: production code for the Orchestration subsystem does not exist
yet, so every spec below is a registered-but-dormant stub. Each carries an
``@pytest.mark.xfail(strict=False)`` so the suite collects and runs without
blocking; the body calls ``pytest.skip`` until the owning CMP is DONE, at which
point the skip is removed and the stubbed assertion goes live.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

Covers (from WBS §4.2):
  - TST-AC-ORCH-01a  [INTEGRATION] — scan creates snapshot if absent, fans one
                                     job per detector
  - TST-AC-ORCH-01c  [REGRESSION]  — `scanipy --query extractall --run-semgrep`
                                     yields CVE-2025-61765 origin=core (Stage A)
  - TST-AC-ORCH-02a  [EMPIRICAL]   — production-shaped replay p95 e2e latency
                                     < 30 min
"""

import pytest


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-ORCH-01 (Scan API) not yet implemented",
    strict=False,
)
def test_orch_01a_scan_creates_snapshot_then_fans_one_job_per_detector() -> None:
    """A scan creates a snapshot if absent, then fans one job per detector.

    Test id:        TST-AC-ORCH-01a
    Maps to AC:     AC-ORCH-01a — "A scan creates a snapshot if absent, then fans
                    one job per detector."
    Kind tag:       [INTEGRATION]
    Inputs:         `POST /api/v1/scans {codebase_id, commit_sha,
                    detector_ids=[d1, d2, d3]}` for a `(codebase_id, commit_sha)`
                    pair with NO existing snapshot (DOC-CMP-ORCH-01 §6 steps 5-7).
    Outputs:        A `scans` row, a resolved/created `snapshot_id`, and the set
                    of per-detector SQS messages enqueued (§4.2.2).
    Pass criteria:  (1) A snapshot is created (CMP-SNAP-01) because none existed,
                    and `scans.snapshot_id` references it. (2) Exactly ONE SQS
                    message is enqueued per `detector_id` (len == len(detector_
                    ids)); each carries `job_id, scan_id, snapshot_id, S_version,
                    env_digest`. (3) Re-submitting the same Idempotency-Key does
                    NOT create a second snapshot or duplicate the fan-out.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-ORCH-01.
    """
    # TODO: import the scan API from services.scan.api when CMP-ORCH-01 is DONE
    # from services.scan.api import post_scans
    # created = post_scans(ScanRequest(codebase_id=cb, commit_sha=sha,
    #                                  detector_ids=["d1", "d2", "d3"]), ...)
    # assert snapshot_was_created(created.snapshot_id)
    # assert len(enqueued_sqs_messages(created.scan_id)) == 3  # one per detector
    pytest.skip("CMP-ORCH-01 not implemented yet")


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-ORCH-01 / CMP-RES-01 (Research-mode shim) not yet implemented",
    strict=False,
)
def test_orch_01c_extractall_yields_cve_2025_61765_core_stage_a() -> None:
    """Backwards-compat: legacy CLI yields CVE-2025-61765 with origin=core.

    Test id:        TST-AC-ORCH-01c
    Maps to AC:     AC-ORCH-01c — "Backwards-compat: `scanipy --query extractall
                    --run-semgrep` via Research mode still yields the
                    CVE-2025-61765 path-traversal finding with
                    `origin=deterministic-core` on a Stage-A language."
    Kind tag:       [REGRESSION]
    Inputs:         The legacy CLI invocation `scanipy --query extractall
                    --run-semgrep` via Research mode (CMP-RES-01, T-CMP-RES-01-03)
                    against the CVE-2025-61765 path-traversal fixture in a Stage-A
                    language (Java or Python).
    Outputs:        The emitted FindingSet for the path-traversal class.
    Pass criteria:  The historical CVE-2025-61765 path-traversal finding is
                    present AND carries `origin == "deterministic-core"` (it flows
                    through the IFDS core path via CMP-ORCH-03, not the Semgrep
                    oracle path). Regression baseline: the finding's
                    rule/spec id + physical location match the v2 historical
                    record. Stage-A language only (Java/Python).
    Frequency:      every CI run
    Hard gate?:     yes — backwards-compat regression gate for CMP-ORCH-01.
    """
    # TODO: drive the Research-mode shim when CMP-ORCH-01 / CMP-RES-01 are DONE
    # findings = run_cli("scanipy --query extractall --run-semgrep", fixture=CVE_2025_61765)
    # pt = [f for f in findings if f.cve == "CVE-2025-61765"]
    # assert pt and all(f.origin == "deterministic-core" for f in pt)
    pytest.skip("CMP-ORCH-01 / CMP-RES-01 not implemented yet")


@pytest.mark.empirical
@pytest.mark.nightly
@pytest.mark.xfail(
    reason="CMP-ORCH-02 (scheduler) not yet implemented",
    strict=False,
)
def test_orch_02a_replay_p95_end_to_end_latency_under_30_min() -> None:
    """Production-shaped replay p95 end-to-end scan latency < 30 min.

    Test id:        TST-AC-ORCH-02a
    Maps to AC:     AC-ORCH-02a — "[Empirical p95] Production-shaped replay at the
                    provisioned worker count yields p95 end-to-end scan latency
                    < 30 min."
    Kind tag:       [EMPIRICAL]
    Inputs:         A production-shaped replay corpus of scans dispatched through
                    SNAP-SCHED-H (Algorithm 4) at the provisioned worker count
                    `m` (DOC-CMP-ORCH-02 §3.3); per-scan `started_at` /
                    `finished_at` from the `scans` table.
    Outputs:        The p95 of the `finished_at - started_at` distribution.
    Pass criteria:  p95 end-to-end scan latency < 30 min (1800 s) at provisioned
                    `m`. On miss, the documented response is one of: re-fit the
                    work-estimate regression, raise `m`, or re-price — NOT a
                    weakening of the threshold. EMPIRICAL: no theorem claimed.
    Frequency:      nightly
    Hard gate?:     yes — published p95 SLA gate for CMP-ORCH-02.
    """
    # TODO: drive the scheduler replay harness when CMP-ORCH-02 is DONE
    # from services.scan.scheduler import schedule
    # latencies = replay_production_shaped_corpus(m=PROVISIONED_WORKERS)
    # assert percentile(latencies, 95) < 1800.0  # seconds; < 30 min
    pytest.skip("CMP-ORCH-02 not implemented yet")

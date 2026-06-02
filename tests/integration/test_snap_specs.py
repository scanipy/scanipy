"""SNAP-family integration / empirical specs + TST-INV-1-SNAP-04.

Spec-first TDD: production code for the Snapshotter subsystem does not exist
yet, so every spec below is a registered-but-dormant stub carrying an
``@pytest.mark.xfail(strict=False)``; the body calls ``pytest.skip`` until the
owning CMP is DONE. Pattern mirrors ``tests/unit/test_dsl_proofs.py``.

The pytest marker encodes EXECUTION/FREQUENCY only (closed marker set under
``--strict-markers``). The richer WBS kind tag lives in each docstring.

Covers (from WBS §4.2 / §4.3):
  - TST-AC-SNAP-01a  [INTEGRATION] — five persisted artifacts at deterministic keys
  - TST-AC-SNAP-02b  [EMPIRICAL]   — open-world median >=5x, p95 >=2x, fallback <=15%
  - TST-AC-SNAP-03b  [EMPIRICAL]   — combined TP+FP routing rate measured/reported
  - TST-AC-SNAP-04b  [EMPIRICAL]   — labeling-correction window vs contractual SLA
  - TST-AC-SNAP-04c  [INVARIANT]   — every re-partition event written to provenance
  - TST-INV-1-SNAP-04 [INVARIANT]  — re-partition flips origin core→oracle correctly
"""

from pathlib import Path

import pytest


@pytest.mark.integration
def test_snap_01a_five_artifacts_at_deterministic_keys() -> None:
    """A snapshot request produces all five persisted artifacts at deterministic keys.

    Test id:        TST-AC-SNAP-01a
    Maps to AC:     AC-SNAP-01a — "A snapshot request for a known commit produces
                    all five persisted artifacts at deterministic S3 keys."
    Kind tag:       [INTEGRATION]
    Inputs:         `POST /snapshots {codebase_id, commit_sha, org_id}` for a known
                    commit; the deterministic S3 key scheme
                    `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/
                    {env_digest}/{artifact_type}` (DOC-CMP-SNAP-01 §4.2).
    Outputs:        Five S3 objects + one `snapshots` row.
    Pass criteria:  Exactly five artifacts persist — `cpg.tar.zst`,
                    `reverse_symbol_index.json.zst`, `dyn_call_graph.json.zst`,
                    `delta_graph.json.zst`, `precondition_status.json` — each at
                    the deterministic key derived byte-for-byte from
                    `(org_id, codebase_id, commit_sha, env_digest, artifact_type)`.
                    Re-running the same request resolves the same keys (idempotent).
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-SNAP-01.

    Hermetic: in-memory object store + queue + snapshot store, injected digest
    (no DB, no AWS). The clone / CW-DETECT / CPG build run in the CMP-SNAP-05
    worker (not built); this drives the SNAP-01 API + persistence seam and
    simulates the worker via `record_completion` (the FND-03 fixtured-signer
    pattern).
    """
    import uuid

    from services.snapshot import SnapshotRequest, SnapshotService
    from services.substrate.object_store import (
        SNAPSHOT_ARTIFACT_TYPES,
        InMemoryObjectStore,
    )

    image_digest = "sha256:" + "a" * 64
    org_id = uuid.uuid4()
    req = SnapshotRequest(
        org_id=org_id,
        codebase_id=uuid.uuid4(),
        commit_sha="b" * 40,
    )

    store = InMemoryObjectStore()
    svc = SnapshotService(
        object_store=store,
        env_digest_provider=lambda: None,  # force the explicit image_digest path
    )

    accepted = svc.create_snapshot(req, image_digest=image_digest)

    # Exactly the five named artifacts at the deterministic key scheme.
    assert set(accepted.artifact_keys) == set(SNAPSHOT_ARTIFACT_TYPES)
    assert len(accepted.artifact_keys) == 5
    for key in accepted.artifact_keys.values():
        assert key.startswith(f"orgs/{org_id}/codebases/{req.codebase_id}/snapshots/")
        assert image_digest in key

    # The simulated CMP-SNAP-05 worker reports completion; the five bodies are
    # PUT to the deterministic keys, so the artifacts literally persist.
    bodies = {t: f"{t}-bytes".encode() for t in SNAPSHOT_ARTIFACT_TYPES}
    svc.record_completion(accepted, req, precondition_status="closed-world", artifact_bodies=bodies)
    for artifact_type, key in accepted.artifact_keys.items():
        assert store.get(str(org_id), key) == bodies[artifact_type]

    # Re-running the same request resolves byte-identical keys (deterministic).
    accepted2 = svc.create_snapshot(req, image_digest=image_digest)
    assert accepted2.artifact_keys == accepted.artifact_keys


@pytest.mark.empirical
@pytest.mark.xfail(
    reason="CMP-SNAP-02 (Incremental CPG, Algorithm 1) not yet implemented",
    strict=False,
)
def test_snap_02b_open_world_speedup_and_fallback_rate() -> None:
    """Open-world median speedup >=5x, p95 >=2x, fallback <=15%.

    Test id:        TST-AC-SNAP-02b
    Maps to AC:     AC-SNAP-02b — "[EMPIRICAL test] On an open-world corpus,
                    measured median speedup >= 5x, p95 >= 2x versus full reparse,
                    fallback rate ≤ 15%."
    Kind tag:       [EMPIRICAL]
    Inputs:         An open-world corpus of commits; per-commit `time(Δ-rebuild)`
                    and `time(full-reparse)`; the route taken per commit
                    (closed-world vs degraded/full-reparse).
    Outputs:        Distribution of speedup = `time(full)/time(Δ)`; fallback rate
                    = fraction of snapshots leaving the closed-world path
                    (CW-DETECT combined TP+FP routing rate, DOC-CMP-SNAP-02 §6.1).
    Pass criteria:  median(speedup) ≥ 5.0 AND p95(speedup) ≥ 2.0 AND
                    fallback_rate ≤ 0.15. Thresholds are verbatim from SDD; do not
                    weaken.
    Frequency:      nightly
    Hard gate?:     yes — empirical performance gate for CMP-SNAP-02.
    """
    # TODO: import the open-world bench harness from analysis.cpg_delta when
    #       CMP-SNAP-02 is DONE; run against tests/corpora open-world fixtures.
    # stats = run_open_world_bench(corpus)
    # assert stats.median_speedup >= 5.0
    # assert stats.p95_speedup >= 2.0
    # assert stats.fallback_rate <= 0.15
    pytest.skip("CMP-SNAP-02 not implemented yet")


@pytest.mark.empirical
def test_snap_03b_combined_routing_rate_measured_and_reported(tmp_path: Path) -> None:
    """Combined TP+FP routing rate measured and reported (≤15% economics signal).

    Test id:        TST-AC-SNAP-03b
    Maps to AC:     AC-SNAP-03b — "False positives are permitted; the combined
                    true-positive + false-positive routing rate is measured and
                    reported (this, not the true reflection rate, is what the
                    ≤15% target governs)."
    Kind tag:       [EMPIRICAL]
    Inputs:         A representative repo population run through CW-DETECT
                    (DOC-CMP-SNAP-03 §9); per-repo verdict (closed-world vs
                    not-closed-world).
    Outputs:        Combined routing rate = fraction of snapshots routed
                    not-closed-world (TP + FP together), reported numerically.
    Pass criteria:  The combined TP+FP routing rate is measured and EMITTED as a
                    numeric report artifact. The ≤15% figure is an economics
                    target, NOT a release blocker — the test asserts the rate is
                    measured and surfaced, never that a single FN is tolerated
                    (FN tolerance is governed by TST-AC-SNAP-03a, which is zero).
    Frequency:      nightly
    Hard gate?:     no — economics signal, not a release blocker.
    """
    from services.snapshot import (
        CwDetectRequest,
        Snapshot,  # noqa: F401  (exported surface check)
        measure_routing_rate,
    )

    # A small representative population: some closed-world repos, some with
    # reflection. The rate is measured + surfaced as a numeric artifact.
    closed = tmp_path / "closed"
    closed.mkdir()
    (closed / "Plain.java").write_text("class Plain { int add(int a, int b){ return a+b; } }\n")

    reflective = tmp_path / "reflective"
    reflective.mkdir()
    (reflective / "Dyn.java").write_text('Class.forName("com.x.Y").newInstance();\n')

    population = [
        CwDetectRequest(source_tree_root=str(closed), language_mix=("java",)),
        CwDetectRequest(source_tree_root=str(reflective), language_mix=("java",)),
    ]

    report = measure_routing_rate(population, clock=lambda: "2026-01-01T00:00:00+00:00")

    # The rate is MEASURED and surfaced as a numeric artifact (the AC contract).
    assert report.total == 2
    assert isinstance(report.combined_tp_fp_rate, float)
    assert 0.0 <= report.combined_tp_fp_rate <= 1.0
    # One reflective repo routed not-closed-world ⇒ rate reflects it numerically.
    assert report.routed_not_closed_world >= 1
    assert report.combined_tp_fp_rate == report.routed_not_closed_world / report.total


@pytest.mark.empirical
@pytest.mark.xfail(
    reason="CMP-SNAP-04 (Differential reflection oracle) not yet implemented",
    strict=False,
)
def test_snap_04b_labeling_correction_window_meets_sla() -> None:
    """Labeling-correction window measured; contractual SLA published.

    Test id:        TST-AC-SNAP-04b
    Maps to AC:     AC-SNAP-04b — "The labeling-correction window (fast decision →
                    async oracle verdict) is measured and a contractual SLA value
                    is produced for it."
    Kind tag:       [EMPIRICAL]
    Inputs:         A population of oracle runs with seeded disagreements; per-run
                    `T_repartition = repartition_record.created_at - enqueued_at`
                    (DOC-CMP-SNAP-04 §6.4); the incident class per run.
    Outputs:        Percentile distribution of `T_repartition` per incident class;
                    a published contractual SLA value.
    Pass criteria:  `T_repartition` is measured and a per-incident-class SLA is
                    published matching CLAR-SLA-01 (RESOLVED): high-impact ≤ 24h,
                    routine ≤ 7d (from SQS enqueue to repartition + notification).
                    Misses are paged. (Numeric SLA finalized at Stage A go-live.)
    Frequency:      pre-customer-enablement
    Hard gate?:     yes — SLA-publication gate for CMP-SNAP-04.
    """
    # TODO: import the oracle SLA harness from services/snapshot oracle when
    #       CMP-SNAP-04 is DONE; CLAR-SLA-01 windows are RESOLVED (24h / 7d).
    # dist = measure_repartition_windows(oracle_runs)
    # assert dist.high_impact_p95 <= timedelta(hours=24)
    # assert dist.routine_p95 <= timedelta(days=7)
    pytest.skip("CMP-SNAP-04 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-SNAP-04 (Differential reflection oracle) not yet implemented",
    strict=False,
)
def test_snap_04c_every_repartition_event_written_to_provenance() -> None:
    """Every re-partition event is written to provenance.

    Test id:        TST-AC-SNAP-04c
    Maps to AC:     AC-SNAP-04c — "Every re-partition event is written to
                    provenance."
    Kind tag:       [INVARIANT]
    Inputs:         A seeded oracle disagreement over a snapshot with N
                    `deterministic-core` findings (engine ∈ {ifds, ide});
                    the `provenance_records` and `snap_oracle_runs` tables.
    Outputs:        Appended `record_type='repartition'` rows.
    Pass criteria:  For every affected finding, exactly one
                    `record_type='repartition'` row is appended, linked to the
                    original `chain` record via `parent_record_id` and to the
                    oracle run via `repartition_oracle_id`. Append-only: the
                    original `chain` record is never UPDATEd. The
                    `snap_oracle_runs` row exists with `agreed=false`.
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 provenance gate for CMP-SNAP-04.
    """
    # TODO: import repartition_snapshot from services/snapshot oracle when
    #       CMP-SNAP-04 is DONE; assert one repartition row per affected finding.
    # result = repartition_snapshot(snapshot_id, oracle_run_id, reason)
    # rows = provenance.repartition_rows(snapshot_id)
    # assert len(rows) == result.affected_finding_count
    pytest.skip("CMP-SNAP-04 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-SNAP-04 (Differential reflection oracle) not yet implemented",
    strict=False,
)
def test_inv_1_snap_04_repartition_flips_origin_core_to_oracle() -> None:
    """Re-partition flips origin deterministic-core→oracle-passthrough correctly (INV-1).

    Test id:        TST-INV-1-SNAP-04
    Maps to AC:     INV-1 (determinism partition) for CMP-SNAP-04 — the sole
                    authorized re-partitioner of an already-stamped `origin`; the
                    flip is append-only and one-way (core → oracle, never reverse)
                    (DOC-CMP-SNAP-04 §5, §6.3).
    Kind tag:       [INVARIANT]
    Inputs:         A snapshot with a mix of `deterministic-core` (engine ∈
                    {ifds, ide}) and `oracle-passthrough` findings; a seeded oracle
                    disagreement; the `provenance_records` + `findings` mirror.
    Outputs:        Re-partition rows + updated `findings` mirror.
    Pass criteria:  Every affected `deterministic-core` finding is flipped to
                    `origin='oracle-passthrough'` exactly once (no double-flip);
                    `oracle-passthrough` findings are untouched; the reverse flip
                    (oracle→core) never occurs; the original record is immutable;
                    `status` is never changed (a finding is never dropped). The
                    `findings` mirror reflects the new origin.
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 invariant gate (per-emitter, WBS §4.3).
    """
    # TODO: import repartition_snapshot + provenance store from services/snapshot
    #       when CMP-SNAP-04 is DONE.
    # repartition_snapshot(snapshot_id, oracle_run_id, reason)
    # for f in core_findings:   assert f.origin == "oracle-passthrough"
    # for f in oracle_findings: assert f.origin == "oracle-passthrough"  # unchanged
    # assert no_finding_dropped()  # status untouched
    pytest.skip("CMP-SNAP-04 not implemented yet")

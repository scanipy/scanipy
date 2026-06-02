"""SNAP-family unit specs — TST-AC-SNAP-* (unit-shaped) + TST-INV-2-SNAP-01.

Spec-first TDD: production code for the Snapshotter subsystem does not exist
yet, so every spec below is a registered-but-dormant stub. Each carries an
``@pytest.mark.xfail(strict=False)`` so the suite collects and runs without
blocking; the body calls ``pytest.skip`` until the owning CMP is DONE, at
which point the skip is removed and the stubbed assertion goes live.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

Covers (from WBS §4.2 / §4.3):
  - TST-AC-SNAP-01b  [UNIT]     — precondition-status is exactly one of three
  - TST-AC-SNAP-01c  [UNIT]     — env_digest from pinned container image digest
  - TST-AC-SNAP-02a  [CONDITIONAL THEOREM, unit-shaped κ-bound] — see CLAR note
  - TST-AC-SNAP-02c  [UNIT]     — function-granularity node-ID preservation
  - TST-AC-SNAP-05a  [NEGATIVE] — argv allowlist rejects non-sanctioned flag
  - TST-AC-SNAP-05b  [UNIT]     — image digest is authoritative env_digest
  - TST-INV-2-SNAP-01 [INVARIANT] — CMP-SNAP-01 stamps env_digest (INV-2)
"""

import pytest


@pytest.mark.unit
def test_snap_01b_precondition_status_is_one_of_three() -> None:
    """The precondition-status record records exactly one of three values.

    Test id:        TST-AC-SNAP-01b
    Maps to AC:     AC-SNAP-01b — "The precondition-status record records exactly
                    one of `closed-world | degraded | full-reparse`."
    Kind tag:       [UNIT]
    Inputs:         A completed snapshot whose worker has reported status; the
                    persisted `precondition_status.json` (DOC-CMP-SNAP-01 §4.3)
                    and the `snapshots.precondition_status` relational column.
    Outputs:        `verdict` field ∈ {closed-world, degraded, full-reparse}.
    Pass criteria:  `precondition_status in {"closed-world","degraded",
                    "full-reparse"}` is True for the row, AND a fourth value is
                    rejected (application-layer mirror of the DDL CHECK, since the
                    shipped schema has `precondition_status` NOT NULL CHECK over
                    the three verdicts — DOC-CMP-SNAP-01 §4.4 / CLAR-SNAP-02).

    Hermetic (no DB): the row is persisted via the simulated worker-completion
    seam (`record_completion`) and read back with `get(...)`.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-SNAP-01.
    """
    import uuid

    from services.scan.provenance import InvariantViolation
    from services.snapshot import SnapshotRequest, SnapshotService

    image_digest = "sha256:" + "a" * 64
    svc = SnapshotService(env_digest_provider=lambda: None)
    req = SnapshotRequest(org_id=uuid.uuid4(), codebase_id=uuid.uuid4(), commit_sha="c" * 40)
    bodies = {
        "cpg_tarball": b"cpg",
        "reverse_symbol_index": b"rsi",
        "dynamic_call_graph": b"dcg",
        "delta_graph": b"dg",
        "precondition_status": b"{}",
    }

    for verdict in ("closed-world", "degraded", "full-reparse"):
        accepted = svc.create_snapshot(req, image_digest=image_digest)
        svc.record_completion(accepted, req, precondition_status=verdict, artifact_bodies=bodies)
        row = svc.get(accepted.snapshot_id)
        assert row is not None
        # Exactly one value present, drawn from the three-verdict enum.
        assert row.precondition_status == verdict
        assert row.precondition_status in {"closed-world", "degraded", "full-reparse"}

    # A fourth value is rejected (application-layer mirror of the DDL CHECK).
    accepted = svc.create_snapshot(req, image_digest=image_digest)
    with pytest.raises(InvariantViolation):
        svc.record_completion(
            accepted, req, precondition_status="not-closed-world", artifact_bodies=bodies
        )


@pytest.mark.unit
def test_snap_01c_env_digest_from_pinned_container_image_digest() -> None:
    """env_digest is computed from the pinned container image digest.

    Test id:        TST-AC-SNAP-01c
    Maps to AC:     AC-SNAP-01c — "`env_digest` is computed from the pinned
                    container image digest and recorded on the snapshot."
    Kind tag:       [UNIT]
    Inputs:         A snapshot creation request; the worker's ECS task image
                    digest exposed via `SCANIPY_ENV_DIGEST` (DOC-CMP-SNAP-05 §3.1).
    Outputs:        `snapshots.env_digest` on the persisted row.
    Pass criteria:  The recorded `env_digest` equals the worker container image
                    digest verbatim, matches the format `^sha256:[0-9a-f]{64}$`,
                    and the row cannot be created with a null env_digest
                    (NOT NULL enforced — DOC-CMP-SNAP-01 §4.4). INV-2.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-SNAP-01 (INV-2).
    """
    import re
    import uuid

    from services.snapshot import SnapshotRequest, SnapshotService

    image_digest = "sha256:" + "a" * 64
    svc = SnapshotService(env_digest_provider=lambda: None)
    req = SnapshotRequest(org_id=uuid.uuid4(), codebase_id=uuid.uuid4(), commit_sha="d" * 40)

    # The explicit image_digest is the stamped env_digest (the accepted result).
    accepted = svc.create_snapshot(req, image_digest=image_digest)
    assert accepted.env_digest == image_digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", accepted.env_digest)

    # It is recorded verbatim on the persisted row (INV-2).
    svc.record_completion(
        accepted,
        req,
        precondition_status="closed-world",
        artifact_bodies={
            "cpg_tarball": b"c",
            "reverse_symbol_index": b"r",
            "dynamic_call_graph": b"d",
            "delta_graph": b"g",
            "precondition_status": b"{}",
        },
    )
    row = svc.get(accepted.snapshot_id)
    assert row is not None
    assert row.env_digest == image_digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", row.env_digest)


@pytest.mark.unit
def test_snap_01c_null_or_malformed_env_digest_is_fail_closed() -> None:
    """A null or malformed image digest is refused fail-closed (INV-2, DOC §7).

    Test id:        TST-AC-SNAP-01c [NEGATIVE]
    Maps to AC:     AC-SNAP-01c / TST-INV-2-SNAP-01 — "a missing digest is a
                    fail-closed condition" (DOC-CMP-SNAP-01 §7). INV-2 requires a
                    real `env_digest`; the row cannot be created without one.
    Kind tag:       [NEGATIVE]
    Pass criteria:  `create_snapshot` raises `InvariantViolation` when (a) the
                    explicit `image_digest` is malformed, and (b) no digest is
                    resolvable (provider returns None, simulating an unset
                    `SCANIPY_ENV_DIGEST`). Mirrors the FND-03 InvariantViolation
                    guard pattern.
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 fail-closed gate for CMP-SNAP-01.
    """
    import uuid

    from services.scan.provenance import InvariantViolation
    from services.snapshot import SnapshotRequest, SnapshotService

    req = SnapshotRequest(org_id=uuid.uuid4(), codebase_id=uuid.uuid4(), commit_sha="e" * 40)

    # (a) malformed explicit image_digest → raises regardless of the provider.
    svc_malformed = SnapshotService(env_digest_provider=lambda: "sha256:" + "a" * 64)
    for bad in ("sha256:deadbeef", "not-a-digest", "sha256:" + "A" * 64, "", "sha1:" + "a" * 40):
        with pytest.raises(InvariantViolation):
            svc_malformed.create_snapshot(req, image_digest=bad)

    # (b) no digest resolvable (provider returns None, SCANIPY_ENV_DIGEST unset)
    #     and no explicit param → fail-closed.
    svc_absent = SnapshotService(env_digest_provider=lambda: None)
    with pytest.raises(InvariantViolation):
        svc_absent.create_snapshot(req)


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-SNAP-02 (Incremental CPG, Algorithm 1) not yet implemented",
    strict=False,
)
def test_snap_02a_closed_world_kappa_bound_regression() -> None:
    """Closed-world κ-bound regression on a per-commit closed-world corpus.

    Test id:        TST-AC-SNAP-02a
    Maps to AC:     AC-SNAP-02a — "[CONDITIONAL THEOREM test] On a closed-world
                    corpus with the precondition asserted per commit,
                    `time(Δ-rebuild) ≤ κ · (|AFFECTED|/|graph|) · time(full-rebuild)`
                    for a frozen `κ`; a regression above `κ` fails."
    Kind tag:       [CONDITIONAL THEOREM]
    Inputs:         A closed-world corpus of ≥1,000 commits (each with the CW
                    precondition asserted); per-commit measured `time(Δ-rebuild)`,
                    `time(full-rebuild)`, `|AFFECTED|`, `|graph|`; the frozen κ.
    Outputs:        Per-commit ratio `time(Δ)/(|AFFECTED|/|graph| · time(full))`.
    Pass criteria:  For every commit, the measured ratio ≤ κ (the frozen bound);
                    any commit above κ is a regression and fails the test.
    Frequency:      nightly
    Hard gate?:     yes — Algorithm 1 conditional-theorem regression gate.

    NOTE: κ is the only genuinely unspecified pass-criterion value in this
    family. Per DOC-CMP-SNAP-02 §9 / CLAR-PARAM-01, κ is "TBD by detector at
    registration; placeholder pinned at Stage A go-live." We do NOT guess it.
    """
    # TODO: import the incremental-CPG bench harness from analysis.cpg_delta
    #       when CMP-SNAP-02 is DONE, and import the frozen κ from the registry.
    # for commit in closed_world_corpus(min_commits=1000):
    #     r = measure_rebuild(commit)
    #     bound = KAPPA_FROZEN * (r.affected / r.graph) * r.full_rebuild_time
    #     assert r.delta_rebuild_time <= bound
    pytest.skip(
        "PASS-CRITERION-UNSPECIFIED: frozen κ for Algorithm 1 Δ-rebuild bound "
        "is pinned only at Stage A go-live (DOC-CMP-SNAP-02 §9 / CLAR-PARAM-01) "
        "— needs CLAR"
    )


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-SNAP-02 (Incremental CPG, Algorithm 1) not yet implemented",
    strict=False,
)
def test_snap_02c_reparse_preserves_node_ids_for_unchanged_decls() -> None:
    """Function-granularity reparse preserves node IDs for unchanged decls.

    Test id:        TST-AC-SNAP-02c
    Maps to AC:     AC-SNAP-02c — "Function-granularity reparse preserves node IDs
                    for unchanged declarations (keyed on enclosing-declaration
                    content hash)."
    Kind tag:       [UNIT]
    Inputs:         A parent CPG and a child commit that changes exactly one
                    declaration; the set of unchanged declarations and their
                    enclosing-declaration content hashes (DOC-CMP-SNAP-02 §6.4).
    Outputs:        The new CPG `G'` with node IDs per declaration.
    Pass criteria:  Every declaration NOT in `AFFECTED` retains its parent node
                    IDs (keyed on enclosing-decl content hash); only declarations
                    in `AFFECTED` get fresh IDs. A node-ID collision between an
                    unchanged decl and a changed decl is a hard failure
                    (`NodeIdCollision`, DOC-CMP-SNAP-02 §3.1).
    Frequency:      every CI run
    Hard gate?:     yes — Algorithm 1 correctness gate (feeds AC-CORE-01c).
    """
    # TODO: import compute_incremental_cpg from analysis.cpg_delta when CMP-SNAP-02 DONE
    # result = compute_incremental_cpg(req)
    # for decl in unchanged_decls:
    #     assert result.new_cpg.node_ids(decl) == parent.node_ids(decl)
    pytest.skip("CMP-SNAP-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-SNAP-05 (Snapshot worker + env pinning) not yet implemented",
    strict=False,
)
def test_snap_05a_argv_allowlist_rejects_non_sanctioned_flag() -> None:
    """The argument allowlist rejects any flag not on the sanctioned list.

    Test id:        TST-AC-SNAP-05a
    Maps to AC:     AC-SNAP-05a — "The argument allowlist rejects any flag not on
                    the sanctioned list (negative test)."
    Kind tag:       [NEGATIVE]
    Inputs:         A call to `secure_run(tool, argv)` (DOC-CMP-SNAP-05 §3.3) with
                    a flag that is NOT in that tool's static allowlist
                    (e.g. `secure_run("joern", argv=["--evil-flag"])`).
    Outputs:        Raised exception / no subprocess spawned.
    Pass criteria:  `secure_run` raises `ArgvAllowlistViolation` for any flag not
                    in the per-tool allowlist (joern/codeql/git); the subprocess
                    is never spawned; `shell=False` always. A sanctioned flag is
                    accepted (positive control).
    Frequency:      every CI run
    Hard gate?:     yes — security-relevant component gate for CMP-SNAP-05.
    """
    # TODO: import secure_run + ArgvAllowlistViolation from workers.snapshot
    #       secure_subprocess when CMP-SNAP-05 is DONE.
    # with pytest.raises(ArgvAllowlistViolation):
    #     secure_run("joern", argv=["--evil-flag"], timeout_s=1, env={}, cwd="/tmp")
    pytest.skip("CMP-SNAP-05 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-SNAP-05 (Snapshot worker + env pinning) not yet implemented",
    strict=False,
)
def test_snap_05b_image_digest_is_authoritative_env_digest() -> None:
    """Container image digest is the authoritative env_digest; tool change moves it.

    Test id:        TST-AC-SNAP-05b
    Maps to AC:     AC-SNAP-05b — "The container image digest is the authoritative
                    `env_digest` and changing any bundled tool changes the digest."
    Kind tag:       [UNIT]
    Inputs:         Two worker images: a baseline build, and a rebuild that bumps
                    exactly one bundled tool pin (`joern` / `codeql` / `git`)
                    (DOC-CMP-SNAP-05 §6.1).
    Outputs:        The two resolved ECR image digests; the worker-resolved
                    `env_digest` (`SCANIPY_ENV_DIGEST` from task metadata).
    Pass criteria:  The `env_digest` equals the running container image digest
                    verbatim; rebuilding with a changed tool pin yields a DIFFERENT
                    digest (digest_baseline != digest_after_tool_bump). A missing
                    `SCANIPY_ENV_DIGEST` at boot refuses to start (EnvDigestMissing).
    Frequency:      pre-release
    Hard gate?:     yes — INV-2 origin gate for CMP-SNAP-05.
    """
    # TODO: import the worker bootstrap / digest resolver from workers.snapshot
    #       when CMP-SNAP-05 is DONE. The two-image build comparison runs in CI
    #       against the built ECR artifact (DOC-CMP-SNAP-05 §9).
    # assert resolve_env_digest() == running_image_digest()
    # assert build_digest(joern="vA") != build_digest(joern="vB")
    pytest.skip("CMP-SNAP-05 not implemented yet")


@pytest.mark.invariant
def test_inv_2_snap_01_snapshot_row_stamps_env_digest() -> None:
    """CMP-SNAP-01 stamps a non-empty env_digest equal to the image digest (INV-2).

    Test id:        TST-INV-2-SNAP-01
    Maps to AC:     INV-2 (versioned parameters) for CMP-SNAP-01 — "Every finding
                    and every provenance record carries `S_version` and
                    `env_digest`." CMP-SNAP-01 is the emitter that stamps
                    `env_digest` at `create_snapshot()` (DOC-CMP-SNAP-01 §5).
    Kind tag:       [INVARIANT]
    Inputs:         A `create_snapshot()` call; the worker container image digest.
    Outputs:        The persisted `snapshots` row.
    Pass criteria:  The row's `env_digest` is non-null, equals the container image
                    digest, and matches `^sha256:[0-9a-f]{64}$`. The schema rejects
                    a null env_digest (NOT NULL). Every downstream finding emitted
                    from this snapshot inherits this exact `env_digest`.
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 invariant gate (per-emitter, WBS §4.3).
    """
    import re
    import uuid

    from services.scan.provenance import InvariantViolation
    from services.snapshot import SnapshotRequest, SnapshotService

    digest = "sha256:" + "f" * 64
    svc = SnapshotService(env_digest_provider=lambda: None)
    req = SnapshotRequest(org_id=uuid.uuid4(), codebase_id=uuid.uuid4(), commit_sha="a" * 40)

    accepted = svc.create_snapshot(req, image_digest=digest)
    svc.record_completion(
        accepted,
        req,
        precondition_status="degraded",
        artifact_bodies={
            "cpg_tarball": b"c",
            "reverse_symbol_index": b"r",
            "dynamic_call_graph": b"d",
            "delta_graph": b"g",
            "precondition_status": b"{}",
        },
    )
    row = svc.get(accepted.snapshot_id)
    assert row is not None
    assert row.env_digest
    assert row.env_digest == digest
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", row.env_digest)

    # Fail-closed: the emitter refuses a null env_digest (INV-2, DOC §7).
    with pytest.raises(InvariantViolation):
        svc.create_snapshot(req)

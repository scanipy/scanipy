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
    reason="frozen κ unspecified — blocked on CLAR-PARAM-01 (κ TBD by detector at "
    "registration; pinned at Stage A go-live). The Algorithm-1 core exists "
    "(analysis/cpg_delta.py); only the κ pass-criterion is missing.",
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

    Non-vacuity: `compute_incremental_cpg` computes AFFECTED itself from the
    graph-level views (it is NOT passed AFFECTED). The fixture changes exactly
    one decl that has a direct caller, so AFFECTED = {changed, caller} via §6.2's
    direct-callers term; the test then asserts BOTH directions — preserved decls
    keep their parent IDs and AFFECTED decls (including the unchanged-content
    caller) get fresh IDs — and that a forced collision raises.
    """
    from analysis.cpg_delta import (
        CPGEdge,
        CPGNode,
        DeclSubgraph,
        GraphView,
        IncrementalCpg,
        IncrementalCpgRequest,
        NodeId,
        NodeIdCollision,
        compute_incremental_cpg,
    )

    env_digest = "sha256:" + "b" * 64

    # --- Parent CPG: three declarations, deterministic insertion-order IDs. ----
    #   util.helper   (ids 0,1)  — unchanged, not a caller of the changed decl
    #   app.target    (ids 2,3)  — the declaration the child commit CHANGES
    #   app.caller    (ids 4,5)  — calls app.target (so it lands in AFFECTED)
    parent = IncrementalCpg()
    n_helper_0 = parent.add_node(
        "METHOD", resolved_fqn="util.helper", enclosing_decl_fqn="util.helper"
    )
    n_helper_1 = parent.add_node("RETURN", enclosing_decl_fqn="util.helper")
    n_target_0 = parent.add_node(
        "METHOD", resolved_fqn="app.target", enclosing_decl_fqn="app.target"
    )
    n_target_1 = parent.add_node("CALL", operator_or_literal="v1", enclosing_decl_fqn="app.target")
    n_caller_0 = parent.add_node(
        "METHOD", resolved_fqn="app.caller", enclosing_decl_fqn="app.caller"
    )
    n_caller_1 = parent.add_node(
        "CALL", operator_or_literal="app.target()", enclosing_decl_fqn="app.caller"
    )
    parent.add_edge(n_helper_0, n_helper_1, "AST")
    parent.add_edge(n_target_0, n_target_1, "AST")
    parent.add_edge(n_caller_0, n_caller_1, "AST")
    parent.add_edge(n_caller_1, n_target_0, "CALL")  # caller -> target

    parent_helper_ids = parent.node_ids("util.helper")
    parent_target_ids = parent.node_ids("app.target")
    parent_caller_ids = parent.node_ids("app.caller")
    assert parent_helper_ids == {NodeId(0), NodeId(1)}
    assert parent_target_ids == {NodeId(2), NodeId(3)}
    assert parent_caller_ids == {NodeId(4), NodeId(5)}

    # Graph-level views: app.caller calls app.target (direct-callers term feeds
    # AFFECTED); util.helper references nothing changed.
    graph = GraphView(
        reverse_symbol_index={},
        call_graph={"app.caller": frozenset({"app.target"})},
        class_hierarchy={},
        decl_to_type={},
    )

    # Injected SNAP-05 reparse seam (a DeclReparser): mints fresh node IDs from
    # the builder-supplied base. With ``collide=True`` it deliberately returns an
    # ID owned by a preserved unchanged decl, forcing the NodeIdCollision path.
    class _FixtureReparser:
        def __init__(self, collide: bool = False) -> None:
            self.collide = collide

        def reparse(self, decl_fqn: str, *, fresh_id_base: int) -> DeclSubgraph:
            if self.collide and decl_fqn == "app.target":
                bad = NodeId(0)  # collides with util.helper's preserved node 0
                return DeclSubgraph(
                    decl_fqn=decl_fqn,
                    nodes=(
                        CPGNode(
                            node_id=bad,
                            kind="METHOD",
                            operator_or_literal="",
                            resolved_fqn=decl_fqn,
                            enclosing_decl_fqn=decl_fqn,
                            structural_path="",
                        ),
                    ),
                    edges=(),
                )
            a = NodeId(fresh_id_base)
            b = NodeId(fresh_id_base + 1)
            return DeclSubgraph(
                decl_fqn=decl_fqn,
                nodes=(
                    CPGNode(
                        node_id=a,
                        kind="METHOD",
                        operator_or_literal="",
                        resolved_fqn=decl_fqn,
                        enclosing_decl_fqn=decl_fqn,
                        structural_path="",
                    ),
                    CPGNode(
                        node_id=b,
                        kind="CALL",
                        operator_or_literal="v2",
                        resolved_fqn="",
                        enclosing_decl_fqn=decl_fqn,
                        structural_path="",
                    ),
                ),
                edges=(CPGEdge(src=a, dst=b, kind="AST"),),
            )

    # --- Child commit changes exactly one decl: app.target. -------------------
    req = IncrementalCpgRequest(
        parent_cpg=parent,
        parent_env_digest=env_digest,
        worker_env_digest=env_digest,
        cw_verdict="closed-world",
        changed_decls=frozenset({"app.target"}),
        changed_types=frozenset(),
        graph=graph,
        reparser=_FixtureReparser(),
        total_files=10,
        changed_files=1,
    )
    result = compute_incremental_cpg(req)

    # AFFECTED computed by the component = changed | direct-callers(changed).
    assert result.affected == frozenset({"app.target", "app.caller"})

    # NOT-AFFECTED decl keeps its parent node IDs verbatim (the AC).
    assert result.new_cpg.node_ids("util.helper") == parent.node_ids("util.helper")

    # AFFECTED decls get FRESH IDs disjoint from every preserved ID — including
    # app.caller, whose source content did NOT change but which is in AFFECTED.
    preserved = parent.node_ids("util.helper")
    assert result.new_cpg.node_ids("app.target").isdisjoint(preserved)
    assert result.new_cpg.node_ids("app.caller").isdisjoint(preserved)
    assert result.new_cpg.node_ids("app.target") != parent.node_ids("app.target")
    assert result.new_cpg.node_ids("app.caller") != parent.node_ids("app.caller")

    # The route actually taken is the closed-world incremental happy path.
    assert result.precondition_status == "closed-world"

    # --- Forced collision is a hard failure (NodeIdCollision, DOC §3.1). ------
    req_collide = IncrementalCpgRequest(
        parent_cpg=parent,
        parent_env_digest=env_digest,
        worker_env_digest=env_digest,
        cw_verdict="closed-world",
        changed_decls=frozenset({"app.target"}),
        changed_types=frozenset(),
        graph=graph,
        reparser=_FixtureReparser(collide=True),
        total_files=10,
        changed_files=1,
    )
    with pytest.raises(NodeIdCollision):
        compute_incremental_cpg(req_collide)


def _minimal_parent_and_reparser() -> tuple[object, object, object, object]:
    """A tiny 2-declaration parent CPG + a reparser that mints one fresh node per
    decl. Shared by the INV-2 and full-reparse SNAP-02 unit tests below."""
    from analysis.cpg_delta import CPGNode, DeclSubgraph, GraphView, IncrementalCpg, NodeId

    parent = IncrementalCpg()
    parent.add_node("METHOD", resolved_fqn="a.one", enclosing_decl_fqn="a.one")
    parent.add_node("METHOD", resolved_fqn="a.two", enclosing_decl_fqn="a.two")

    class _Reparser:
        def reparse(self, decl_fqn: str, *, fresh_id_base: int) -> DeclSubgraph:
            return DeclSubgraph(
                decl_fqn=decl_fqn,
                nodes=(
                    CPGNode(
                        node_id=NodeId(fresh_id_base),
                        kind="METHOD",
                        operator_or_literal="",
                        resolved_fqn=decl_fqn,
                        enclosing_decl_fqn=decl_fqn,
                        structural_path="",
                    ),
                ),
                edges=(),
            )

    graph = GraphView(reverse_symbol_index={}, call_graph={}, class_hierarchy={}, decl_to_type={})
    return parent, _Reparser(), graph, IncrementalCpg


@pytest.mark.unit
def test_snap_02_inv2_env_digest_mismatch_refuses() -> None:
    """INV-2 fail-closed: a parent snapshot from a different Env is refused.

    Maps to AC:     INV-2 (DOC-CMP-SNAP-02 §5/§7) — a snapshot may not be re-used
                    across `env_digest`s (a different `Env`). The guard is the
                    INV-2 discharge the PR checklist claims; it must be tested.
    Pass criteria:  `compute_incremental_cpg` raises `EnvDigestMismatch` when
                    `parent_env_digest != worker_env_digest`, before any build.
    Hard gate?:     yes — INV-2 guard for CMP-SNAP-02.
    """
    from analysis.cpg_delta import (
        EnvDigestMismatch,
        IncrementalCpgRequest,
        compute_incremental_cpg,
    )

    parent, reparser, graph, _ = _minimal_parent_and_reparser()
    req = IncrementalCpgRequest(
        parent_cpg=parent,
        parent_env_digest="sha256:" + "a" * 64,
        worker_env_digest="sha256:" + "b" * 64,  # different Env → must refuse
        cw_verdict="closed-world",
        changed_decls=frozenset({"a.one"}),
        changed_types=frozenset(),
        graph=graph,
        reparser=reparser,
        total_files=10,
        changed_files=1,
    )
    with pytest.raises(EnvDigestMismatch):
        compute_incremental_cpg(req)


@pytest.mark.unit
def test_snap_02_full_reparse_preserves_no_parent_ids() -> None:
    """On the full-reparse route, G' preserves no parent IDs (DOC §6.1/§6.5).

    Maps to AC:     AC-SNAP-02c-adjacent — the route-actually-taken semantics
                    (DOC §6.1). A `full-reparse` verdict means the whole program is
                    reparsed; the result must not be a half-preserved graph.
    Pass criteria:  `precondition_status == "full-reparse"`, and `affected` ==
                    EVERY parent declaration (so the build preserves nothing — no
                    half-preserved graph). On full reparse the worker rebuilds G'
                    from scratch, so node-ID *integers* may legitimately restart at
                    0; the load-bearing property is that all decls are AFFECTED, not
                    that the fresh integers avoid the parent's.
    Hard gate?:     yes — guards the full-reparse output semantics.
    """
    from analysis.cpg_delta import IncrementalCpgRequest, compute_incremental_cpg

    parent, reparser, graph, _ = _minimal_parent_and_reparser()
    req = IncrementalCpgRequest(
        parent_cpg=parent,
        parent_env_digest="sha256:" + "c" * 64,
        worker_env_digest="sha256:" + "c" * 64,
        cw_verdict="full-reparse",
        changed_decls=frozenset({"a.one"}),
        changed_types=frozenset(),
        graph=graph,
        reparser=reparser,
        total_files=10,
        changed_files=1,
    )
    result = compute_incremental_cpg(req)

    assert result.precondition_status == "full-reparse"
    # All declarations AFFECTED ⇒ the preservation loop carries nothing over.
    assert result.affected == frozenset({"a.one", "a.two"})
    assert result.delta_graph.affected_set == frozenset({"a.one", "a.two"})


@pytest.mark.unit
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

    Falsifier discipline (per task brief):
    * Positive control (anti-vacuity): a *sanctioned* flag passes the allowlist
      gate — it does NOT raise; the rejection path is real and not blanket-deny.
      (We monkeypatch the spawn so no real binary is needed; if the gate were a
      blanket reject, this branch would raise and fail the test.)
    * Negative control (MUTATION-VERIFIED): with a permissive allowlist mutation
      (``_enforce_allowlist`` made a no-op / the ``arg.startswith("-") and ... not
      in allowlist`` guard inverted to ``in allowlist``), the
      ``pytest.raises(ArgvAllowlistViolation)`` block below stops raising and the
      test FAILS. Empirically confirmed — see worker StructuredOutput.
    """
    from tools.worker.secure_subprocess import (
        ArgvAllowlistViolation,
        secure_run,
    )

    # --- NEGATIVE: a non-sanctioned flag is rejected fail-closed, no spawn. ---
    # joern has no "--evil-flag"; the allowlist gate must raise BEFORE any binary
    # is resolved (the pinned path does not exist in the test env, so a spawn
    # would raise FileNotFoundError, not ArgvAllowlistViolation — the precise
    # exception type proves the gate fired first).
    with pytest.raises(ArgvAllowlistViolation):
        secure_run("joern", argv=["--evil-flag"], timeout_s=1, env={}, cwd="/tmp")

    # Cross-tool: a flag sanctioned for one tool is still rejected for another
    # (per-tool allowlists are not shared). "--threads" is a codeql flag, not git.
    with pytest.raises(ArgvAllowlistViolation):
        secure_run("git", argv=["--threads", "4"], timeout_s=1, env={}, cwd="/tmp")

    # --- POSITIVE control (anti-vacuity): a sanctioned flag passes the gate. ---
    # Patch the actual spawn so the test stays hermetic (no joern binary on the
    # box). If the allowlist were a blanket-deny, "--language" would raise here
    # and the test would fail — so this branch proves the gate accepts sanctioned
    # flags rather than rejecting everything.
    import subprocess

    import tools.worker.secure_subprocess as ss

    spawned: dict[str, object] = {}

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        spawned["cmd"] = cmd
        spawned["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    orig = ss.subprocess.run
    ss.subprocess.run = _fake_run  # type: ignore[assignment]
    try:
        result = secure_run(
            "joern",
            argv=["--language", "java", "--cpg-only"],
            timeout_s=1,
            env={"PATH": "/opt/joern/bin"},
            cwd="/tmp",
        )
    finally:
        ss.subprocess.run = orig  # type: ignore[assignment]

    assert result.returncode == 0  # the sanctioned call reached (faked) spawn
    # shell=False is a hard invariant of secure_run (DOC §3.3) — never shell=True.
    assert spawned["kwargs"]["shell"] is False  # type: ignore[index]
    # The pinned in-image binary path is used, NOT a bare "joern" from host PATH.
    assert spawned["cmd"][0] == "/opt/joern/joern"  # type: ignore[index]


@pytest.mark.unit
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

    Build-ahead note (per task brief): SNAP-05 Depends-On CMP-DEPLOY-02, whose
    real two-image ECR rebuild + digest diff runs in CI against built artifacts
    (DOC §9) and ``workers/pins.json`` digests are all-zero PLACEHOLDERS (the AWS
    team fills them). So the WORKER LOGIC half is verified hermetically here: the
    worker resolves ``env_digest`` verbatim from the injected ``SCANIPY_ENV_DIGEST``
    (the running image digest), and a missing/malformed digest is fail-closed.
    The "two-tool-bump → different digest" half stays an image-build assertion on
    the substrate track; we model it with two distinct fixture digests to prove
    the worker reads the digest VERBATIM (so a different image really does yield a
    different bound env_digest — the worker never collapses or defaults them).

    Falsifier discipline (per task brief):
    * Positive control (anti-vacuity): the worker binds the injected digest
      VERBATIM and two distinct fixture digests resolve to two distinct bound
      values — the worker neither hard-codes nor normalises them.
    * Negative control (MUTATION-VERIFIED): with a default-digest mutation
      (``resolve_env_digest`` returns a constant / falls back to a default when
      the var is missing, instead of raising), the missing-digest
      ``pytest.raises(EnvDigestMissing)`` block stops raising and the test FAILS.
      Empirically confirmed against that mutation — see worker StructuredOutput.
    """
    from services.snapshot.worker import (
        ENV_DIGEST_VAR,
        EnvDigestMissing,
        boot,
        resolve_env_digest,
    )

    # --- POSITIVE: the worker binds the injected digest VERBATIM (INV-2). ---
    # Hermetic fixture digest injected via the env mapping (no process mutation).
    fixture_digest = "sha256:" + "ab" * 32  # a valid sha256 image digest
    bound = resolve_env_digest({ENV_DIGEST_VAR: fixture_digest})
    assert bound == fixture_digest  # equals the running image digest verbatim
    # boot() is the entrypoint gate; it returns the same bound digest.
    assert boot({ENV_DIGEST_VAR: fixture_digest}) == fixture_digest

    # Two distinct images (different bundled tool pin -> different image digest)
    # resolve to two DISTINCT bound env_digests: the worker reads the digest
    # verbatim, so a digest change really does move env_digest (AC-SNAP-05b). If
    # the worker hard-coded or defaulted the digest, these would be equal.
    digest_baseline = "sha256:" + "11" * 32
    digest_after_tool_bump = "sha256:" + "22" * 32
    assert resolve_env_digest({ENV_DIGEST_VAR: digest_baseline}) == digest_baseline
    assert resolve_env_digest({ENV_DIGEST_VAR: digest_after_tool_bump}) == digest_after_tool_bump
    assert resolve_env_digest({ENV_DIGEST_VAR: digest_baseline}) != resolve_env_digest(
        {ENV_DIGEST_VAR: digest_after_tool_bump}
    )

    # --- NEGATIVE: a MISSING digest at boot refuses to start (fail-closed). ---
    # This is the mutation-killing assertion: a default-digest fallback would
    # return a value here instead of raising.
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({})  # SCANIPY_ENV_DIGEST absent
    with pytest.raises(EnvDigestMissing):
        boot({ENV_DIGEST_VAR: ""})  # present-but-empty is equally fail-closed

    # --- NEGATIVE: a MALFORMED digest (not sha256:<64-hex>) is also refused. ---
    # An unpinned/placeholder-shaped value must never be accepted as env_digest.
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({ENV_DIGEST_VAR: "not-a-digest"})
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({ENV_DIGEST_VAR: "sha256:" + "zz" * 32})  # non-hex


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

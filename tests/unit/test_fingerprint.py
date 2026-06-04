"""CMP-CORE-02 — slice-fingerprint hermetic unit/invariant tests (Algorithm 3).

The hermetic, synthetic-fixture half of CMP-CORE-02's acceptance surface. The
corpus-scale empirical halves stay xfail in their stubs:

    TST-AC-CORE-02a (50 seeded findings, CMP-CORP-REFAC-01)   — xfail, corpus-gated
    TST-AC-CORE-02b (aliasing-changing extract seed)          — xfail, corpus-gated
    TST-AC-CORE-02c (CMP-CORP-CANARY-01 weak-rate roll-up)    — xfail, corpus-gated

(see tests/falsifier/refac/test_core02_falsifier.py — those stubs define NO
in-stub synthetic case, so per the build-ahead contract they remain xfail with
the corpus named; CI's unit job never discovers tests/falsifier/refac/.)

This module carries the four mandated controls — all in tests/unit/ marked
``unit``/``invariant`` so the CI unit job (``pytest tests/unit/ -m
"unit or invariant"``) runs them:

  (a) POSITIVE      — a named refactor (alpha-rename a local; package-rename;
                      independent-statement reorder) leaves slice_fingerprint
                      UNCHANGED, with fingerprint_class == "strong" (invariance
                      cannot be satisfied by the weak fallback).
  (b) NEGATIVE      — a genuine dataflow change (changed sink target; added
                      sanitizer node) CHANGES the fingerprint.
  (c) WEAK-DETERM   — same source ⇒ byte-identical weak hash.
  (d) BUDGET        — forcing B exhaustion yields fingerprint_class == "weak"
                      (never an exception, never a fake "strong").

Plus the §7 error contracts (EmptyWitness / WitnessNotInCPG).

MUTATION-VERIFIED NEGATIVE CONTROL (falsifier doctrine). Test (a) is the
anti-vacuity backbone: it FAILS if ``_alpha_rename_locals`` is reverted to the
identity (the renamed-local content then leaks into the content hash and the two
fingerprints differ). That mutation was run empirically and confirmed to fail
(a); see the IMPL agent's negative_control_verified note.

Source-of-truth: ``DOC-CMP-CORE-02``, ``DOC-ALGS §4``, ``.claude/rules/01-invariants.md §INV-5``.
"""

from __future__ import annotations

import pytest

from analysis.fingerprint import (
    EmptyWitness,
    SliceFingerprintResult,
    WitnessNotInCPG,
    compute_slice_fingerprint,
)
from analysis.ifds.dsl.primitives import AccessPathPattern, Sanitize, Sink, Source
from analysis.ifds.dsl.spec import Spec
from analysis.ifds.solver import Finding, solve
from analysis.ordering import CPG, NodeId, Sha256

_S_VERSION = "1.0.0"
_ENV_DIGEST = Sha256(b"\xab" * 32)
_SRC_PAT = AccessPathPattern("taint_src")
_SINK_PAT = AccessPathPattern("exec_sink")
_SAN_PAT = AccessPathPattern("sanitize")


def _spec(*, with_sanitizer: bool = False, sink_pattern: str = "exec_sink") -> Spec:
    """A Stage-A injection spec: source + sink (+ optional sanitizer clause).

    ``sink_pattern`` lets the negative control point the sink at a different call
    target without changing the source-side seeding.
    """
    clauses: list[object] = [Source(_SRC_PAT), Sink(AccessPathPattern(sink_pattern))]
    if with_sanitizer:
        clauses.append(Sanitize(_SAN_PAT))
    return Spec(
        id="inj.fp.v1",
        class_="injection",
        languages=("python",),
        engine="ifds",
        clauses=tuple(clauses),  # type: ignore[arg-type]
    )


def _solve_one(cpg: CPG, spec: Spec) -> Finding:
    result = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    assert len(result.findings) == 1, "fixture must yield exactly one finding"
    return next(iter(result.findings))


# ---------------------------------------------------------------------------
# Fixture builders (asymmetric two-statement single-proc taint path)
# ---------------------------------------------------------------------------


def _taint_cpg(
    *,
    local_name: str = "x",
    package: str = "com.old",
    sink_call: str = "exec_sink",
    add_sanitizer: bool = False,
) -> CPG:
    """A single-proc taint path ``src -> local(local_name) -> [san] -> sink``.

    Knobs encode the named refactors / dataflow changes the tests exercise:
      - ``local_name``  : alpha-rename a LOCAL (refactor — must NOT flip).
      - ``package``     : the package/FQN prefix (file-move — must NOT flip).
      - ``sink_call``   : the sink call target (dataflow change — MUST flip).
      - ``add_sanitizer``: insert a sanitize node on the path (kills the fact —
                          the solver then emits NO finding, the genuine-fix leg).

    (Independent-statement reordering has its own dedicated fixture,
    :func:`_two_step_taint_cpg`, because off-path independents are excluded from
    the backward cone and would make a reorder assertion vacuous.)
    """
    cpg = CPG()
    decl = f"{package}.Main.run"
    entry = cpg.add_node("METHOD", resolved_fqn=decl, enclosing_decl_fqn=decl)
    src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn=decl, structural_path="0"
    )
    local = cpg.add_node(
        "IDENTIFIER", operator_or_literal=local_name, enclosing_decl_fqn=decl, structural_path="1"
    )

    prev = local
    if add_sanitizer:
        san = cpg.add_node(
            "CALL", operator_or_literal="sanitize", enclosing_decl_fqn=decl, structural_path="2"
        )
        cpg.add_edge(prev, san, "CFG")
        prev = san

    sink = cpg.add_node(
        "CALL", operator_or_literal=sink_call, enclosing_decl_fqn=decl, structural_path="3"
    )
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, local, "CFG")
    cpg.add_edge(prev, sink, "CFG")
    return cpg


def _fingerprint(cpg: CPG, spec: Spec, **kw: object) -> SliceFingerprintResult:
    finding = _solve_one(cpg, spec)
    return compute_slice_fingerprint(finding, cpg, **kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# (a) POSITIVE — named refactors leave slice_fingerprint UNCHANGED (strong)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fingerprint_invariant_under_alpha_rename_local() -> None:
    """A local rename (``x`` -> ``userControlledInput``) does NOT change the
    fingerprint, and both sides are ``strong`` (invariance is not the weak
    fallback masquerading).

    This is the anti-vacuity backbone + the mutation-verified negative control:
    reverting ``_alpha_rename_locals`` to identity makes the renamed local's text
    leak into the content hash and this assertion FAILS (verified empirically).
    """
    spec = _spec()
    base = _fingerprint(_taint_cpg(local_name="x"), spec)
    renamed = _fingerprint(_taint_cpg(local_name="userControlledInput"), spec)

    assert base.fingerprint_class == "strong"
    assert renamed.fingerprint_class == "strong"
    # ANTI-VACUITY: the renamed CPG really does differ pre-normalisation (the
    # local-variable token changed), so equal fingerprints prove the pass fired.
    assert _taint_cpg(local_name="x").nodes != _taint_cpg(local_name="userControlledInput").nodes
    assert base.slice_fingerprint == renamed.slice_fingerprint


@pytest.mark.unit
def test_fingerprint_invariant_under_package_rename() -> None:
    """A file-move / package-rename (``com.old.*`` -> ``com.new.*``) does NOT
    change the fingerprint (FQN-normalisation pass), both sides ``strong``."""
    spec = _spec()
    base = _fingerprint(_taint_cpg(package="com.old"), spec)
    moved = _fingerprint(_taint_cpg(package="com.new"), spec)

    assert base.fingerprint_class == moved.fingerprint_class == "strong"
    assert base.slice_fingerprint == moved.slice_fingerprint


def _two_step_taint_cpg(*, swap_insertion: bool) -> CPG:
    """``src -> {stepA, stepB} -> sink`` — two DATA-INDEPENDENT relay CALLs that
    BOTH reach the sink (so both land in the backward cone, unlike off-path
    independents which the cone excludes). ``stepA``/``stepB`` are distinguishable
    (distinct ``operator_or_literal``). ``swap_insertion`` builds them in the
    opposite construction order — the "independent reordering" a refactor performs
    — WITHOUT changing dataflow. canonical_order re-ranks by content, so the
    content hash is invariant; a hash keyed on insertion order would diverge."""
    cpg = CPG()
    decl = "m.run"
    entry = cpg.add_node("METHOD", resolved_fqn=decl, enclosing_decl_fqn=decl)
    src = cpg.add_node("CALL", operator_or_literal="taint_src", enclosing_decl_fqn=decl)
    sink = cpg.add_node("CALL", operator_or_literal="exec_sink", enclosing_decl_fqn=decl)
    if swap_insertion:
        b = cpg.add_node("CALL", operator_or_literal="stepB", enclosing_decl_fqn=decl)
        a = cpg.add_node("CALL", operator_or_literal="stepA", enclosing_decl_fqn=decl)
    else:
        a = cpg.add_node("CALL", operator_or_literal="stepA", enclosing_decl_fqn=decl)
        b = cpg.add_node("CALL", operator_or_literal="stepB", enclosing_decl_fqn=decl)
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, a, "CFG")
    cpg.add_edge(a, sink, "CFG")
    cpg.add_edge(src, b, "CFG")
    cpg.add_edge(b, sink, "CFG")
    return cpg


@pytest.mark.unit
def test_fingerprint_invariant_under_independent_reorder() -> None:
    """Reordering two data-independent statements does NOT change the fingerprint
    (canonical-topo-sort pass; the content hash consumes canonical order, not
    insertion order).

    Mutation-verifiable: both steps are in the cone and distinguishable, and the
    two CPGs differ in construction order, so a ``_content_hash`` that iterated
    insertion order rather than the canonical rank would make these two diverge —
    i.e. the test BITES (verified by the IMPL agent; see negative_control note)."""
    base = _fingerprint(_two_step_taint_cpg(swap_insertion=False), _spec())
    reordered = _fingerprint(_two_step_taint_cpg(swap_insertion=True), _spec())

    assert base.fingerprint_class == reordered.fingerprint_class == "strong"
    # ANTI-VACUITY: the two source CPGs genuinely differ in node construction order
    # (so equal fingerprints prove the canonical re-rank, not byte-identical input).
    assert (
        _two_step_taint_cpg(swap_insertion=False).nodes
        != _two_step_taint_cpg(swap_insertion=True).nodes
    )
    assert base.slice_fingerprint == reordered.slice_fingerprint


# ---------------------------------------------------------------------------
# (b) NEGATIVE — a genuine dataflow change CHANGES the fingerprint
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fingerprint_changes_on_changed_sink_target() -> None:
    """Changing the sink CALL target is a genuine dataflow change: the fingerprint
    MUST flip (else a real new/changed sink would be wrongly auto-suppressed)."""
    base = _fingerprint(_taint_cpg(sink_call="exec_sink"), _spec(sink_pattern="exec_sink"))
    changed = _fingerprint(
        _taint_cpg(sink_call="os_system_sink"), _spec(sink_pattern="os_system_sink")
    )

    assert base.fingerprint_class == changed.fingerprint_class == "strong"
    assert base.slice_fingerprint != changed.slice_fingerprint


@pytest.mark.unit
def test_genuine_fix_sanitizer_removes_the_finding() -> None:
    """AC-CORE-02b's first seed — a GENUINE FIX that deletes the sink. Inserting a
    sanitizer on the taint path KILLS the fact, so the solver emits NO finding:
    there is nothing left to fingerprint (correct — a fixed flaw must not be
    re-surfaced by a stale fingerprint match).

    This is the honest hermetic mapping of the 'real fix' leg: a sanitizer does
    not flip a fingerprint, it removes the finding entirely. The OTHER 02b leg —
    the aliasing-changing IMPURE extract that must FLIP the fingerprint — needs the
    alias oracle the minimal CPG lacks and is corpus-gated, so it stays xfail in
    tests/falsifier/refac/test_core02_falsifier.py (TST-AC-CORE-02b). The
    fingerprint-FLIP half of (b) is covered by the changed-sink test above."""
    # Without the sanitizer: a real source -> sink finding exists.
    clean = solve(
        _taint_cpg(add_sanitizer=False), _spec(), S_version=_S_VERSION, env_digest=_ENV_DIGEST
    )
    assert len(clean.findings) == 1, "anti-vacuity: the unfixed program HAS a finding"

    # With the sanitizer on the path: the fact is killed, the finding is gone.
    fixed = solve(
        _taint_cpg(add_sanitizer=True),
        _spec(with_sanitizer=True),
        S_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
    )
    assert len(fixed.findings) == 0, "a genuine fix (sanitizer) removes the finding"


# ---------------------------------------------------------------------------
# (c) WEAK-PATH DETERMINISM — same source ⇒ byte-identical weak hash
# ---------------------------------------------------------------------------


def _symmetric_cpg() -> CPG:
    """A diamond of two IDENTICAL ``relay`` CALL nodes: ``src -> {a, b} -> sink``.

    ``a`` and ``b`` share kind, ``operator_or_literal``, FQN and structural_path,
    so they are 2-WL-indistinguishable AND survive alpha-renaming (only IDENTIFIER
    nodes are alpha-renamed; CALL nodes are not). The backward cone from the sink keeps
    BOTH arms (the witness took only one), so the normalised slice carries the
    residual symmetric class ``{a, b}`` that individualisation-refinement must
    resolve — under a tight budget that forces the weak fallback. The full budget
    resolves it ``strong`` (so the weakness is genuinely budget-driven)."""
    cpg = CPG()
    entry = cpg.add_node("METHOD", resolved_fqn="s.main", enclosing_decl_fqn="s.main")
    src = cpg.add_node("CALL", operator_or_literal="taint_src", enclosing_decl_fqn="s.main")
    a = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn="s.main")
    b = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn="s.main")
    sink = cpg.add_node("CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="s.main")
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, a, "CFG")
    cpg.add_edge(src, b, "CFG")
    cpg.add_edge(a, sink, "CFG")
    cpg.add_edge(b, sink, "CFG")
    return cpg


@pytest.mark.unit
def test_weak_path_byte_identical_across_runs() -> None:
    """Same source ⇒ byte-identical weak hash across two independent computations
    (the witness-edge-sequence fallback is a deterministic function of the
    source). ANTI-VACUITY: both must actually be on the weak path."""
    cpg = _symmetric_cpg()
    finding = _solve_one(cpg, _spec())

    r1 = compute_slice_fingerprint(finding, cpg, B=1)
    r2 = compute_slice_fingerprint(finding, cpg, B=1)

    assert r1.fingerprint_class == "weak" and r2.fingerprint_class == "weak"
    assert isinstance(r1.slice_fingerprint, bytes) and len(r1.slice_fingerprint) == 32
    assert r1.slice_fingerprint == r2.slice_fingerprint


# ---------------------------------------------------------------------------
# (d) BUDGET — B exhaustion yields class "weak", never an exception / fake strong
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_budget_exhaustion_yields_weak_never_exception() -> None:
    """Forcing B exhaustion on a symmetric slice yields ``fingerprint_class ==
    "weak"`` + ``budget_exhausted is True`` — never a raised exception, never a
    fabricated ``strong`` (INV-5 self-label truthfulness).

    Non-vacuity: the SAME witness under the full budget canonicalises ``strong``,
    so the weak result is genuinely budget-driven, not an inherently-degenerate
    slice. (We drive weakness through B, not T — per the codebase's own note that
    T-driven weakness is flaky.)"""
    cpg = _symmetric_cpg()
    finding = _solve_one(cpg, _spec())

    # B=1: individualisation-refinement raises BudgetExhausted -> weak.
    weak = compute_slice_fingerprint(finding, cpg, B=1)
    assert weak.fingerprint_class == "weak"
    assert weak.budget_exhausted is True

    # Same witness, full budget: the slice DOES canonicalise strong (non-vacuity:
    # the weakness above is the budget, not the slice).
    strong = compute_slice_fingerprint(finding, cpg)
    assert strong.fingerprint_class == "strong"
    assert strong.budget_exhausted is False
    # The two fingerprints differ (content hash vs witness-edge hash) — expected.
    assert strong.slice_fingerprint != weak.slice_fingerprint


# ---------------------------------------------------------------------------
# §7 error contracts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_empty_witness_raises() -> None:
    """An empty witness is a CMP-CORE-01 bug — EmptyWitness, never a silent
    degenerate fingerprint (DOC §7)."""
    cpg = _taint_cpg()
    finding = _solve_one(cpg, _spec())
    empty = Finding(
        sink=finding.sink,
        fact=finding.fact,
        witness=(),
        spec_id=finding.spec_id,
        origin=finding.origin,
        S_version=finding.S_version,
        env_digest=finding.env_digest,
        cpg_order_hash=finding.cpg_order_hash,
        cpg_order_hash_annotation=finding.cpg_order_hash_annotation,
        fingerprint_class=finding.fingerprint_class,
        engine=finding.engine,
    )
    with pytest.raises(EmptyWitness):
        compute_slice_fingerprint(empty, cpg)


@pytest.mark.unit
def test_witness_node_not_in_cpg_raises() -> None:
    """A witness node id absent from the CPG (stale snapshot) raises
    WitnessNotInCPG, never a silent degrade (DOC §7)."""
    cpg = _taint_cpg()
    finding = _solve_one(cpg, _spec())
    phantom = NodeId(10_000)  # not in cpg
    stale = Finding(
        sink=finding.sink,
        fact=finding.fact,
        witness=(*finding.witness, phantom),
        spec_id=finding.spec_id,
        origin=finding.origin,
        S_version=finding.S_version,
        env_digest=finding.env_digest,
        cpg_order_hash=finding.cpg_order_hash,
        cpg_order_hash_annotation=finding.cpg_order_hash_annotation,
        fingerprint_class=finding.fingerprint_class,
        engine=finding.engine,
    )
    with pytest.raises(WitnessNotInCPG):
        compute_slice_fingerprint(stale, cpg)


# ---------------------------------------------------------------------------
# Purity: same input ⇒ same output (the function is pure)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_is_pure_same_input_same_output() -> None:
    """compute_slice_fingerprint is pure: identical (finding, cpg, B, T) ⇒
    identical SliceFingerprintResult (modulo elapsed_ms telemetry)."""
    cpg = _taint_cpg()
    finding = _solve_one(cpg, _spec())
    r1 = compute_slice_fingerprint(finding, cpg)
    r2 = compute_slice_fingerprint(finding, cpg)
    assert r1.slice_fingerprint == r2.slice_fingerprint
    assert r1.fingerprint_class == r2.fingerprint_class
    assert r1.budget_exhausted == r2.budget_exhausted

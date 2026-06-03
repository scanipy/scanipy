"""CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2).

The principal deterministic-core detection engine. For a detector spec with
``engine in {ifds, ide}`` this solver computes the meet-over-all-valid-paths
(MVP) taint solution at every sink over a CPG, paired with a realising witness
path, and emits one :class:`Finding` per realising ``(sink, fact)`` with the
four required provenance fields threaded (INV-1, INV-2, INV-5).

PR1 SCOPE (this commit).
  This is PR1 of a multi-PR component. It implements RHS'95 Tabulation in the
  ``ifds`` (set-valued) mode over the structural supergraph from
  :mod:`analysis.ifds.supergraph`, with reusable procedure summaries and a
  bounded incremental mode (AC-CORE-01c). It is sufficient to make the
  fixture-scale determinism proxy and the incremental-closure unit green.

  DEFERRED to later PRs (NOT in this commit):
    - the IDE lattice-valued environment-transformer extension
      (``spec.mode == "ide"``; DOC-CMP-CORE-01 §3.2);
    - the corpus-scale determinism gate AC-CORE-01a (needs CMP-CORP-CANARY-01 +
      the CMP-CP-05 Attestor) and the empirical recall claim AC-CORE-01b
      (INV-6 / CMP-CP-06-gated) — their tests stay ``xfail``.

INTERFACE RECONCILE (CLAR-CORE-01 — reported, not invented).
  DOC-CMP-CORE-01 §3.1 sketches a ``Spec`` with
  ``S_version/mode/fact_domain/lattice/flow_factory/source_preds/sink_preds/
  dsl_closure_proof_digest`` and a ``solve(supergraph, ..., canonical_order,
  cpg_order_hash, ...)`` signature. The **shipped** DET-01 ``Spec``
  (``analysis.ifds.dsl.spec.Spec``: ``id/class_/languages/engine/clauses``) has
  none of those fields. This solver therefore:
    1. takes a ``CPG`` and computes ``canonical_order`` / the INV-5 hash trio
       internally via :func:`analysis.ordering.canonical_order`;
    2. takes ``S_version`` and ``env_digest`` as ``solve()`` keyword arguments
       (they are run parameters, not ``Spec`` fields);
    3. builds the clause -> flow-function adapter itself, with an
       ``AccessPathPattern`` matcher (explicitly CORE-01's responsibility per
       ``primitives.py`` lines 24-25);
    4. DROPS the doc's defensive INV-4 ``dsl_closure_proof_digest`` re-check —
       unimplementable against the shipped ``Spec`` and safe because DET-01
       ``parse_spec`` owns INV-4 at registration (CLAR-DET-02 RESOLVED);
    5. DROPS the ``Finding.determinism_partition`` field (DOC §3.1 / §8 thread it
       from ``spec.determinism_partition``) — the shipped ``Spec`` has no such
       field. It is NOT one of the four RULE-6 required provenance fields and is
       stamped downstream by CMP-DET-02/CMP-ORCH-03 (``.claude/rules/02-provenance.md``);
       the four required fields (``origin``, ``S_version``, ``env_digest``,
       ``cpg_order_hash`` + annotation) are all threaded here.
  See ``wbs_writeback_needed`` — the orchestrator files CLAR-CORE-01.

Source-of-truth: ``DOC-CMP-CORE-01``, ``DOC-ALGS §3``, ``.claude/rules/02-provenance.md``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal, NewType

from analysis.ifds.dsl.primitives import (
    AccessPathPattern,
    Sanitize,
    Sink,
    Source,
)
from analysis.ifds.dsl.spec import Spec
from analysis.ifds.supergraph import (
    ExplodedSupergraph,
    ProcId,
    build_supergraph,
)
from analysis.ordering import (
    CPG,
    CPG_ORDER_HASH_ANNOTATION,
    CPGNode,
    NodeId,
    Sha256,
    canonical_order,
)

# A fact is an interned distributive-domain element. In PR1 the only fact is the
# taint token: a fact identifies the source pattern that introduced the taint.
Fact = NewType("Fact", int)


class NonDistributiveSpec(Exception):  # noqa: N818  (named verbatim per DOC §7)
    """Raised if a spec slips the DET-01 closure check. Defensive; PR1 cannot
    reconstruct the doc's ``dsl_closure_proof_digest`` re-check against the
    shipped Spec, so this is currently only the engine-tag guard (CLAR-CORE-01)."""


# ---------------------------------------------------------------------------
# AccessPathPattern matcher (CORE-01's responsibility — primitives.py:24-25)
# ---------------------------------------------------------------------------
#
# PR1 SIMPLIFICATION (CLAR-CORE-01): the access-path matcher is the minimal rule
# that fires the fixture's source -> sink: a pattern matches a CPG node iff the
# pattern string equals the node's ``operator_or_literal`` (the call target /
# literal text). Field-sensitivity, arg/ret/field access-path projection and the
# full PEG semantics (DOC-DSL §2) are explicitly DEFERRED, not invented here.


def _pattern_matches(pattern: AccessPathPattern, node: CPGNode) -> bool:
    """Minimal PR1 matcher: exact match on ``operator_or_literal``."""
    return str(pattern) == node.operator_or_literal and node.operator_or_literal != ""


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One realising ``(sink, fact)`` pair with the four required provenance
    fields threaded (INV-1 / INV-2 / INV-5)."""

    sink: NodeId
    fact: Fact
    witness: tuple[NodeId, ...]
    spec_id: str
    origin: Literal["deterministic-core"]  # INV-1
    S_version: str  # INV-2
    env_digest: Sha256  # INV-2
    cpg_order_hash: Sha256  # INV-5 (paired with annotation)
    cpg_order_hash_annotation: Literal["canonical iff fingerprint_class = strong"]
    fingerprint_class: Literal["strong", "weak"]
    engine: Literal["ifds", "ide"]


@dataclass(frozen=True)
class SolverResult:
    """The tabulation result. ``solution_hash`` is the pre-serialisation hash the
    Attestor (CMP-CP-05) compares for AC-CORE-01a (corpus-scale, later PR)."""

    findings: frozenset[Finding]
    solution_hash: Sha256
    visited_procs: frozenset[ProcId]
    # The procedure summaries built by this run, for cross-run incremental reuse
    # (DOC-CMP-CORE-01 §3.1; CLAR-CORE-01 records this field was previously
    # dropped). Keyed by ``(S_version, env_digest)`` via ``SummaryCache.header`` so
    # a stale cache is rejected. ``frozen=True`` blocks reassignment, not mutation
    # of the (mutable) cache object — nothing hashes a ``SolverResult``. NOTE: this
    # is the cache for incremental reuse; it is NOT what CMP-CORE-02 consumes —
    # CORE-02 backward-slices along ``Finding.witness`` (CLAR-CORE-01's phrase
    # "SummaryCache consumed by CMP-CORE-02" is imprecise: CORE-02 consumes the
    # witness, not the cache).
    summaries: SummaryCache


# ---------------------------------------------------------------------------
# Procedure-summary cache (RHS'95 §4)
# ---------------------------------------------------------------------------


@dataclass
class SummaryCache:
    """Maps a procedure to the set of taint facts that reach its exit given a
    taint fact at entry. PR1 summary = ``proc -> {entry_fact -> frozenset(exit
    facts)}``. Keyed by ``(S_version, env_digest)`` so a stale cache is rejected.
    """

    header: tuple[str, bytes]
    summaries: dict[ProcId, dict[Fact, frozenset[Fact]]]
    visited: set[ProcId]

    def copy(self) -> SummaryCache:
        return SummaryCache(
            header=self.header,
            summaries={p: dict(m) for p, m in self.summaries.items()},
            visited=set(self.visited),
        )

    def invalidate(self, procs: frozenset[ProcId]) -> None:
        for p in procs:
            self.summaries.pop(p, None)
            self.visited.discard(p)


# ---------------------------------------------------------------------------
# Tabulation core
# ---------------------------------------------------------------------------


def _seed_sources(
    sg: ExplodedSupergraph, spec: Spec
) -> tuple[dict[NodeId, set[Fact]], dict[Fact, AccessPathPattern]]:
    """Find every source-matching node and intern one taint fact per (node,
    source-clause). Returns ``node -> {facts seeded there}`` and the fact->pattern
    interning table. Iterates clauses/nodes in canonical order for determinism.
    """
    node_by_id = {n.node_id: n for n in sg.cpg.nodes}
    seeded: dict[NodeId, set[Fact]] = {}
    fact_pattern: dict[Fact, AccessPathPattern] = {}
    next_fact = 0
    sources = [c for c in spec.clauses if isinstance(c, Source)]
    for nid in sorted(node_by_id):  # node ids are construction-order-stable
        node = node_by_id[NodeId(nid)]
        for clause in sources:
            if _pattern_matches(clause.pattern, node):
                fact = Fact(next_fact)
                next_fact += 1
                fact_pattern[fact] = clause.pattern
                seeded.setdefault(node.node_id, set()).add(fact)
    return seeded, fact_pattern


def _sanitized_at(sg: ExplodedSupergraph, spec: Spec, node: CPGNode) -> bool:
    """True if ``node`` matches any sanitize clause (kills taint along this node)."""
    return any(isinstance(c, Sanitize) and _pattern_matches(c.pattern, node) for c in spec.clauses)


def _is_sink(sg: ExplodedSupergraph, spec: Spec, node: CPGNode) -> bool:
    return any(isinstance(c, Sink) and _pattern_matches(c.pattern, node) for c in spec.clauses)


def _tabulate(
    sg: ExplodedSupergraph,
    spec: Spec,
    seeded: dict[NodeId, set[Fact]],
    *,
    restrict_to: frozenset[ProcId] | None,
    summaries: SummaryCache,
    canon_index: dict[NodeId, int],
) -> tuple[
    dict[NodeId, set[Fact]],
    frozenset[ProcId],
    dict[tuple[NodeId, Fact], tuple[NodeId, Fact] | None],
]:
    """Intra+interprocedural taint reachability with reusable summaries.

    Computes, for every node, the set of taint facts holding *at* that node.
    ``restrict_to`` (incremental mode) limits which procedures are (re)tabulated;
    ``None`` means full tabulation. Returns ``(facts_at_node, visited_procs,
    pred)``.

    ``pred`` is the predecessor map for witness reconstruction (DOC §3.3):
    ``pred[(node, fact)]`` is the ``(node, fact)`` from which ``(node, fact)`` was
    **first** discovered, or ``None`` for a seeded source (a path root). It is
    written exactly once, co-located with the worklist dedup guard, so the chain
    points strictly backwards in discovery time and a backtrack always terminates
    at a seed (never loops, even on a cyclic CPG). Because the worklist pops the
    canonical-minimum item and ``cfg_succ``/``call_succ`` are canonical-sorted, the
    *first* discoverer of any ``(node, fact)`` — hence the whole witness path — is a
    deterministic function of the source (DOC §3.3: "deterministic given
    canonical_order").

    Worklist order is fixed by ``(canonical-order index, fact)`` — ``canon_index``
    is the CMP-CORE-03 canonical order — so the fixpoint is reached identically on
    every run (DOC §3.2 step 4).
    """
    node_by_id = {n.node_id: n for n in sg.cpg.nodes}
    facts_at: dict[NodeId, set[Fact]] = {n.node_id: set() for n in sg.cpg.nodes}
    visited: set[ProcId] = set()
    pred: dict[tuple[NodeId, Fact], tuple[NodeId, Fact] | None] = {}

    def proc_in_scope(pid: ProcId | None) -> bool:
        if pid is None:
            return False
        if restrict_to is None:
            return True
        return pid in restrict_to

    # Worklist of (node, fact) "a taint fact holds AT node", ordered by the
    # CMP-CORE-03 canonical order (DOC §3.2 step 4).
    order_index = canon_index
    worklist: list[tuple[NodeId, Fact]] = []

    def add(nid: NodeId, fact: Fact, pred_key: tuple[NodeId, Fact] | None) -> None:
        if fact not in facts_at[nid]:
            facts_at[nid].add(fact)
            # Write-once predecessor: the FIRST discoverer wins (and is
            # deterministic, given the canonical worklist order). This keeps the
            # backtrack chain acyclic — pred always points to an earlier-discovered
            # item — so _witness terminates at a seed (DOC §3.3).
            pred[(nid, fact)] = pred_key
            worklist.append((nid, fact))
            pid = sg.proc_of_node.get(nid)
            if pid is not None:
                visited.add(pid)

    # Seed: a source node introduces its taint fact at that node, if in scope.
    # A seed is a path root: pred_key=None.
    for nid, facts in seeded.items():
        pid = sg.proc_of_node.get(nid)
        if proc_in_scope(pid):
            for fact in sorted(facts):
                add(nid, fact, None)

    while worklist:
        # Pop the canonical-minimum item for a stable fixpoint trajectory.
        worklist.sort(key=lambda item: (order_index.get(item[0], 1 << 30), int(item[1])))
        nid, fact = worklist.pop(0)
        node = node_by_id[nid]

        # Sanitizer kills the fact: it does not propagate past this node.
        if _sanitized_at(sg, spec, node):
            continue

        # Intraprocedural CFG successors carry the fact forward.
        for succ in sg.cfg_succ.get(nid, ()):  # already canonical-sorted
            add(succ, fact, (nid, fact))

        # Interprocedural CALL: enter the callee at its entry with the same fact
        # (PR1 models full taint pass-through; access-path projection deferred).
        for callee_pid in sg.call_succ.get(nid, ()):  # canonical-sorted
            if not proc_in_scope(callee_pid):
                continue
            callee = sg.procs[callee_pid]
            add(callee.entry, fact, (nid, fact))
            # Splice the summary: facts known to reach the callee exit flow back
            # to the caller's CFG successors (the return site). The return site is
            # a CFG successor of the call node, so (nid, fact) -> (ret, exit_fact)
            # keeps the witness path connected through the call.
            summary = summaries.summaries.get(callee_pid, {})
            for exit_fact in sorted(summary.get(fact, frozenset())):
                for ret in sg.cfg_succ.get(nid, ()):
                    add(ret, exit_fact, (nid, fact))

    # Record per-procedure summaries: entry fact -> facts reaching any node of the
    # callee (PR1 over-approximation; a precise exit-node summary is a later PR).
    for pid in visited:
        proc = sg.procs[pid]
        entry_facts = sorted(facts_at[proc.entry])
        body = (proc.entry, *proc.body_nodes)
        reach: dict[Fact, set[Fact]] = {ef: set() for ef in entry_facts}
        for ef in entry_facts:
            for bn in body:
                reach[ef].update(facts_at[bn])
        summaries.summaries[pid] = {ef: frozenset(reach[ef]) for ef in entry_facts}
        summaries.visited.add(pid)

    return facts_at, frozenset(visited), pred


def _witness(
    pred: dict[tuple[NodeId, Fact], tuple[NodeId, Fact] | None],
    sink: NodeId,
    fact: Fact,
) -> tuple[NodeId, ...]:
    """The realising source -> sink path for ``(sink, fact)`` (DOC §3.3).

    Backtracks the write-once ``pred`` map from ``(sink, fact)`` to its seeded
    source (the ``pred=None`` root), then reverses to **source-first** order so the
    result is a connected path through the supergraph: each consecutive
    ``(prev, cur)`` is a CFG/CALL edge that the tabulation propagated along. This
    is the path CMP-CORE-02 backward-slices along and the SARIF ``codeFlows``
    payload renders (``DOC-CMP-CORE-02 §4.1``, ``DOC-SARIF``).

    Determinism (DOC §3.3 "deterministic given canonical_order") comes entirely
    from the write-once ``pred``: the canonical worklist order fixes the first
    discoverer of every ``(node, fact)``, so the path is a deterministic function
    of the source. The nodes are **not** re-sorted by canonical index — sorting
    would break edge-adjacency; the path is already deterministic.

    A ``visited`` guard is redundant insurance against a malformed (cyclic) ``pred``
    — write-once already guarantees acyclicity — but it makes the bound explicit.
    """
    path: list[NodeId] = []
    seen: set[tuple[NodeId, Fact]] = set()
    cur: tuple[NodeId, Fact] | None = (sink, fact)
    while cur is not None and cur not in seen:
        seen.add(cur)
        path.append(cur[0])
        cur = pred.get(cur)
    path.reverse()  # source-first (path[0] is the seeded source, path[-1] == sink)
    return tuple(path)


def _build_findings(
    sg: ExplodedSupergraph,
    spec: Spec,
    facts_at: dict[NodeId, set[Fact]],
    pred: dict[tuple[NodeId, Fact], tuple[NodeId, Fact] | None],
    *,
    S_version: str,  # noqa: N803  (INV-2 provenance field name — normative, DOC §3.1)
    env_digest: Sha256,
    cpg_order_hash: Sha256,
    fingerprint_class: Literal["strong", "weak"],
    canon_index: dict[NodeId, int],
) -> list[Finding]:
    """Read out one Finding per realising ``(sink, fact)`` in canonical order."""
    node_by_id = {n.node_id: n for n in sg.cpg.nodes}
    # Iterate sinks in CMP-CORE-03 canonical order (DOC §3.2 step 5).
    canon = sorted(
        (n.node_id for n in sg.cpg.nodes),
        key=lambda nid: (canon_index.get(nid, 1 << 30), int(nid)),
    )
    findings: list[Finding] = []
    for nid in canon:
        node = node_by_id[nid]
        if not _is_sink(sg, spec, node):
            continue
        for fact in sorted(facts_at.get(nid, set())):
            findings.append(
                Finding(
                    sink=nid,
                    fact=fact,
                    witness=_witness(pred, nid, fact),
                    spec_id=spec.id,
                    origin="deterministic-core",  # INV-1 (engine in {ifds, ide})
                    S_version=S_version,  # INV-2
                    env_digest=env_digest,  # INV-2
                    cpg_order_hash=cpg_order_hash,  # INV-5
                    cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,  # INV-5
                    fingerprint_class=fingerprint_class,  # INV-5 (conditional)
                    engine=spec.engine,
                )
            )
    return findings


def _hash_solution(findings: list[Finding], canonical_order_index: dict[NodeId, int]) -> Sha256:
    """Pre-serialisation hash over the canonical-order-sorted ``(sink, fact,
    witness)`` tuples (DOC §3.2 step 6). Byte-identical across runs on the same
    source for fixed ``(S_version, env_digest)`` (AC-CORE-01a foundation)."""
    ordered = sorted(
        findings,
        key=lambda f: (canonical_order_index.get(f.sink, 1 << 30), int(f.fact)),
    )
    h = hashlib.sha256()
    for f in ordered:
        h.update(int(f.sink).to_bytes(8, "big", signed=False))
        h.update(int(f.fact).to_bytes(8, "big", signed=False))
        for w in f.witness:
            h.update(int(w).to_bytes(8, "big", signed=False))
        h.update(b"|")
    return Sha256(h.digest())


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _require(value: str | bytes, name: str) -> None:
    """INV-2 fail-fast: never silently default a missing versioned parameter."""
    if not value:
        raise ValueError(f"{name} is required (INV-2); refusing to run with an unpinned value")


def solve(
    cpg: CPG,
    spec: Spec,
    *,
    S_version: str,  # noqa: N803  (INV-2 provenance field name — normative, DOC §3.1)
    env_digest: Sha256,
) -> SolverResult:
    """Full-tabulation entry point (DOC-CMP-CORE-01 §3.1, reconciled per CLAR-CORE-01).

    Builds the exploded supergraph, computes the canonical order + INV-5 hash trio
    from ``cpg`` (via CMP-CORE-03), runs RHS'95 Tabulation, and emits one Finding
    per realising ``(sink, fact)`` with the four provenance fields threaded.

    Raises ``ValueError`` if ``S_version`` or ``env_digest`` is empty (INV-2).
    """
    _require(S_version, "S_version")
    _require(env_digest, "env_digest")
    if spec.engine not in ("ifds", "ide"):  # defensive INV-1/INV-4 (CLAR-CORE-01)
        raise NonDistributiveSpec(spec.id)

    order_result = canonical_order(cpg)
    canon_index = {nid: i for i, nid in enumerate(order_result.canonical_order)}
    sg = build_supergraph(cpg, order_result.canonical_order)
    summaries = SummaryCache(header=(S_version, bytes(env_digest)), summaries={}, visited=set())
    seeded, _facts = _seed_sources(sg, spec)
    facts_at, visited, pred = _tabulate(
        sg, spec, seeded, restrict_to=None, summaries=summaries, canon_index=canon_index
    )

    findings = _build_findings(
        sg,
        spec,
        facts_at,
        pred,
        S_version=S_version,
        env_digest=env_digest,
        cpg_order_hash=order_result.cpg_order_hash,
        fingerprint_class=order_result.fingerprint_class,
        canon_index=canon_index,
    )
    solution_hash = _hash_solution(findings, canon_index)
    return SolverResult(
        findings=frozenset(findings),
        solution_hash=solution_hash,
        visited_procs=visited,
        summaries=summaries,
    )


def incremental_solve(
    cpg: CPG,
    spec: Spec,
    affected_set: frozenset[ProcId],
    prior_summaries: SummaryCache,
    *,
    S_version: str,  # noqa: N803  (INV-2 provenance field name — normative, DOC §3.1)
    env_digest: Sha256,
) -> SolverResult:
    """Bounded incremental mode (AC-CORE-01c).

    Re-tabulates only procedures in ``affected_set`` and their transitive callers;
    summaries outside that closure are reused verbatim from ``prior_summaries``.
    ``SolverResult.visited_procs`` is a subset of
    ``affected_set | transitive_callers(affected_set)`` — that is the AC-CORE-01c
    guarantee the unit test asserts.

    Raises ``SummaryCacheVersionMismatch`` semantics via ``ValueError`` if the
    prior cache was keyed under a different ``(S_version, env_digest)``.
    """
    _require(S_version, "S_version")
    _require(env_digest, "env_digest")
    if spec.engine not in ("ifds", "ide"):
        raise NonDistributiveSpec(spec.id)
    if prior_summaries.header != (S_version, bytes(env_digest)):
        raise ValueError(
            "SummaryCacheVersionMismatch: prior summaries keyed under a "
            "different (S_version, env_digest)"
        )

    order_result = canonical_order(cpg)
    canon_index = {nid: i for i, nid in enumerate(order_result.canonical_order)}
    sg = build_supergraph(cpg, order_result.canonical_order)

    callers = sg.transitive_callers(affected_set)
    closure = affected_set | callers
    summaries = prior_summaries.copy()
    summaries.invalidate(closure)

    seeded, _facts = _seed_sources(sg, spec)
    facts_at, visited, pred = _tabulate(
        sg, spec, seeded, restrict_to=closure, summaries=summaries, canon_index=canon_index
    )

    findings = _build_findings(
        sg,
        spec,
        facts_at,
        pred,
        S_version=S_version,
        env_digest=env_digest,
        cpg_order_hash=order_result.cpg_order_hash,
        fingerprint_class=order_result.fingerprint_class,
        canon_index=canon_index,
    )
    solution_hash = _hash_solution(findings, canon_index)
    return SolverResult(
        findings=frozenset(findings),
        solution_hash=solution_hash,
        visited_procs=visited,
        summaries=summaries,
    )

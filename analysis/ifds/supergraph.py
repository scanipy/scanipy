"""CMP-CORE-01 — Exploded-supergraph construction (Algorithm 2, build phase).

The RHS'95 Tabulation algorithm runs over an *exploded supergraph* derived from
a CPG (``analysis.ordering.CPG``) plus a distributive flow-function spec
(``analysis.ifds.dsl``). This module is the **structural** half of CMP-CORE-01:
it turns the minimal CPG surface into the interprocedural control-flow skeleton
(per-procedure CFG nodes + ``CALL`` / ``ENTRY`` / ``RETURN`` edge kinds) that
``analysis.ifds.solver`` tabulates over. It deliberately introduces **no edit**
to ``analysis.ordering`` (CMP-CORE-03, DONE): edge *kinds* are read off
``CPGEdge.kind`` rather than added to the node model (DOC-CMP-CORE-01 §3.1).

Procedure model (PR1).
  - A CPG node with ``kind == "METHOD"`` is a *procedure entry*. Its
    ``resolved_fqn`` names the procedure; ``ProcId`` is the node id of the entry
    node (so proc ids are canonical-order-stable, an INV-5 consumer).
  - Every other node belongs to the procedure named by its
    ``enclosing_decl_fqn`` (matched against a method's ``resolved_fqn``).
  - Edge kinds are interpreted as:
        "CFG"    intraprocedural control flow within a procedure
        "CALL"   call site (caller node) -> callee METHOD entry
        "RETURN" callee exit -> caller return site
    Any other edge kind (e.g. "AST", "PDG") is structural and ignored by the
    interprocedural skeleton.

This PR1 build is intentionally minimal — exactly what the fixture-scale
determinism proxy and the AC-CORE-01c incremental closure test require. The
full IDE lattice-valued supergraph (DOC-CMP-CORE-01 §3.2, ``spec.mode == "ide"``)
is a later PR; see CLAR-CORE-01.

Source-of-truth: ``DOC-CMP-CORE-01 §3``, ``DOC-ALGS §3``, ``analysis/ordering.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NewType

from analysis.ordering import CPG, NodeId

# A procedure id: the NodeId of the procedure's METHOD entry node, re-exported as
# a distinct semantic alias (it IS a node id, by construction — DOC §3.1).
ProcId = NewType("ProcId", int)

# Interprocedural edge kinds read off CPGEdge.kind (NOT added to the node model).
CALL_EDGE = "CALL"
RETURN_EDGE = "RETURN"
CFG_EDGE = "CFG"


@dataclass(frozen=True)
class Procedure:
    """One procedure: its entry node id and the node ids that belong to it."""

    proc_id: ProcId
    entry: NodeId
    fqn: str
    body_nodes: tuple[NodeId, ...]


@dataclass
class ExplodedSupergraph:
    """Interprocedural control-flow skeleton over a CPG (PR1 structural form).

    Not the materialised ``(node, fact)`` exploded graph — the solver materialises
    fact-level path-edges lazily (RHS'95). This object carries the procedure
    partition + the call/return/cfg adjacency the tabulation walks.
    """

    cpg: CPG
    procs: dict[ProcId, Procedure] = field(default_factory=dict)
    # proc of each node id (every node belongs to at most one procedure).
    proc_of_node: dict[NodeId, ProcId] = field(default_factory=dict)
    # intraprocedural CFG successors, per node.
    cfg_succ: dict[NodeId, list[NodeId]] = field(default_factory=dict)
    # call edges: caller-site node -> callee ProcId.
    call_succ: dict[NodeId, list[ProcId]] = field(default_factory=dict)
    # static call graph: caller ProcId -> set of callee ProcIds and the reverse.
    callees: dict[ProcId, set[ProcId]] = field(default_factory=dict)
    callers: dict[ProcId, set[ProcId]] = field(default_factory=dict)

    def transitive_callers(self, seed: frozenset[ProcId]) -> frozenset[ProcId]:
        """Reverse-reachability over the static call graph (AC-CORE-01c closure).

        Returns every procedure that can (transitively) call any procedure in
        ``seed``. ``seed`` itself is *not* included — the solver unions it back in
        (DOC-CMP-CORE-01 Appendix A: ``affected_set | callers``).
        """
        out: set[ProcId] = set()
        stack = list(seed)
        while stack:
            p = stack.pop()
            for caller in self.callers.get(p, set()):
                if caller not in out:
                    out.add(caller)
                    stack.append(caller)
        return frozenset(out)


def build_supergraph(cpg: CPG, canonical_order: list[NodeId]) -> ExplodedSupergraph:
    """Build the interprocedural skeleton from ``cpg``.

    ``canonical_order`` (from CMP-CORE-03) fixes the iteration order so the
    procedure partition and adjacency lists are byte-stable across runs — the
    foundation of ``solution_hash`` determinism (DOC §3.2 step 4).
    """
    sg = ExplodedSupergraph(cpg=cpg)
    node_by_id = {n.node_id: n for n in cpg.nodes}
    order_index = {nid: i for i, nid in enumerate(canonical_order)}

    def okey(nid: NodeId) -> int:
        # Nodes absent from canonical_order sort last but deterministically by id.
        return order_index.get(nid, len(order_index) + int(nid))

    # 1. Procedures: every METHOD node is an entry. fqn = resolved_fqn (fallback
    #    to enclosing_decl_fqn so a method always has a stable name key).
    method_nodes = sorted(
        (n for n in cpg.nodes if n.kind == "METHOD"), key=lambda n: okey(n.node_id)
    )
    fqn_to_proc: dict[str, ProcId] = {}
    for n in method_nodes:
        pid = ProcId(int(n.node_id))
        fqn = n.resolved_fqn or n.enclosing_decl_fqn
        sg.procs[pid] = Procedure(proc_id=pid, entry=n.node_id, fqn=fqn, body_nodes=())
        sg.callees[pid] = set()
        sg.callers[pid] = set()
        if fqn:
            fqn_to_proc[fqn] = pid

    # 2. Assign every node to its procedure (by enclosing_decl_fqn; the METHOD
    #    entry belongs to itself).
    body: dict[ProcId, list[NodeId]] = {pid: [] for pid in sg.procs}
    for n in cpg.nodes:
        if n.kind == "METHOD":
            pid = ProcId(int(n.node_id))
        else:
            pid = fqn_to_proc.get(n.enclosing_decl_fqn, ProcId(-1))
        if pid != ProcId(-1):
            sg.proc_of_node[n.node_id] = pid
            if n.kind != "METHOD":
                body[pid].append(n.node_id)
        sg.cfg_succ.setdefault(n.node_id, [])
        sg.call_succ.setdefault(n.node_id, [])

    for pid, members in body.items():
        entry = sg.procs[pid].entry
        ordered = tuple(sorted(members, key=okey))
        sg.procs[pid] = Procedure(
            proc_id=pid, entry=entry, fqn=sg.procs[pid].fqn, body_nodes=ordered
        )

    # 3. Edges: CFG (intraprocedural), CALL (caller -> callee entry), RETURN.
    for e in cpg.edges:
        if e.kind == CFG_EDGE:
            sg.cfg_succ[e.src].append(e.dst)
        elif e.kind == CALL_EDGE:
            callee = node_by_id.get(e.dst)
            if callee is not None and callee.kind == "METHOD":
                callee_pid = ProcId(int(callee.node_id))
                sg.call_succ[e.src].append(callee_pid)
                caller_pid = sg.proc_of_node.get(e.src)
                if caller_pid is not None:
                    sg.callees[caller_pid].add(callee_pid)
                    sg.callers[callee_pid].add(caller_pid)
        # RETURN and other kinds carry no extra structure in the PR1 skeleton:
        # the solver returns to the call site's CFG successors directly.

    # 4. Deterministic adjacency: sort every successor list by canonical order.
    for nid in sg.cfg_succ:
        sg.cfg_succ[nid].sort(key=okey)
    for nid in sg.call_succ:
        sg.call_succ[nid].sort(key=lambda p: okey(NodeId(int(p))))

    return sg

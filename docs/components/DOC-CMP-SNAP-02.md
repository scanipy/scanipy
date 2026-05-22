# DOC-CMP-SNAP-02 — Incremental CPG maintenance (Algorithm 1)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §4 CMP-SNAP-02` (Purpose, AC-SNAP-02a/b/c)
- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"` (the verbatim formal statement)
- `docs/cross-cutting/DOC-ALGS.md §2` (Algorithm 1 reference)
- `docs/cross-cutting/DOC-GLOSSARY.md` (`AFFECTED`, `precondition-status`)
- `docs/cross-cutting/DOC-PROVENANCE.md §3` (precondition_status persisted on snapshot row)
- `docs/cross-cutting/DOC-INV.md §4, §6` (INV-2; INV-4 hand-off from CW-DETECT)
- `WBS.md §17 CLAR-PARAM-01` (RESOLVED — `θ_cone=0.25`, `θ_files=0.4`, `(B,T)`)
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`

This document is the **implementation contract** for `CMP-SNAP-02`. A code-writing agent given only this file plus the cross-cutting refs above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-SNAP-02` |
| Subsystem | Snapshotter (`SDD.md §4`) |
| Staging | Stage A (Java + Python core classes) |
| Depends-On | `CMP-SNAP-01`, `CMP-SNAP-03` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| INV-* touched | **INV-2** (consumes `env_digest` from parent snapshot, no override); **INV-4 hand-off** (consumes CW-DETECT verdict; routes by it); records `precondition_status` for downstream INV-1 partition logic. |
| Algorithm | **Algorithm 1** (`PLAN.md §"Algorithm 1"`; `DOC-ALGS §2`). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §4 CMP-SNAP-02`):**

> Compute `G'`, `ΔG`, and `AFFECTED` from a parent snapshot when the closed-world precondition holds; otherwise apply the points-to-bounded cone and the `θ_cone`/`θ_files` reparse fallback.

**Operational role.** `CMP-SNAP-02` is the **delta engine** of the Snapshotter. Given a parent snapshot and a new commit, it produces the new CPG `G'`, the structural delta `ΔG`, and the set `AFFECTED` of entry points whose IFDS summaries must be invalidated. It does **not** decide the closed-world precondition (that is `CMP-SNAP-03 CW-DETECT`'s job); it **routes** by the verdict. Three routing paths exist: (i) closed-world incremental, the `O(Δ)` happy path; (ii) degraded, the points-to-bounded cone for `not-closed-world` verdicts that stay within bounds; (iii) full reparse, the unconditional fallback when bounds are exceeded. The verdict and the chosen route are written to `precondition_status` on the snapshot row (via `CMP-SNAP-01`), making the route **publicly auditable** in provenance (`DOC-PROVENANCE §3` link 2 + `claim_label` link).

---

## 3. Interface contract

`CMP-SNAP-02` is invoked **in-process** by the snapshot worker (`CMP-SNAP-05`) — it has no HTTP surface. The contract is therefore a typed function signature.

```typescript
interface IncrementalCpgRequest {
    parent_snapshot: Snapshot;                  // from CMP-SNAP-01 (state='ready')
    current_commit: string;                     // 40-hex Git SHA of the new commit
    cw_verdict: PreconditionStatus;             // from CMP-SNAP-03 over (source@current_commit)
    theta_cone: number;                         // CLAR-PARAM-01 default 0.25
    theta_files: number;                        // CLAR-PARAM-01 default 0.4
    source_tree_root: string;                   // local FS path to checked-out source
}

type PreconditionStatus = "closed-world" | "degraded" | "full-reparse";

interface IncrementalCpgResult {
    new_cpg: CPG;                               // G'
    delta_graph: GraphDelta;                    // ΔG = {added_nodes, removed_nodes,
                                                //       added_edges, removed_edges,
                                                //       affected_set}
    affected: Set<NodeId>;                      // entry points whose IFDS summaries invalidate
    precondition_status: PreconditionStatus;    // the route actually taken
    cone_size_ratio?: number;                   // |cone|/|G'| when not closed-world
    changed_files_ratio: number;                // |changed files|/|files|
    reflection_sites?: ReflectionSite[];        // from CW-DETECT; empty on closed-world
}

interface GraphDelta {
    added_nodes:   NodeId[];
    removed_nodes: NodeId[];
    added_edges:   Edge[];
    removed_edges: Edge[];
    affected_set:  NodeId[];   // same set as IncrementalCpgResult.affected
}
```

**Concrete entry point** (Python; binding for the worker):

```python
def compute_incremental_cpg(req: IncrementalCpgRequest) -> IncrementalCpgResult: ...
```

### 3.1 Error contracts

| Error | Cause | Response |
|---|---|---|
| `MissingParentSnapshot` | `parent_snapshot.state != 'ready'` or artifacts missing in S3 | Worker fails the job; SQS retry. Caller may force `parent_snapshot=None` to invoke full reparse. |
| `NodeIdCollision` | New CPG produces a `NodeId` that collides with an unchanged-declaration node ID inherited from parent (violates `AC-SNAP-02c`) | Hard failure; this is an algorithm bug. Alarm. |
| `BoundedReparseTimeout` | Points-to cone computation exceeds wall-clock budget on the degraded path | Fall back to full reparse; record `precondition_status='full-reparse'` and reason `degraded-timeout`. |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `parent_snapshot` | `CMP-SNAP-01` (relational row + S3 artifacts) | Must be `state='ready'`. Its `env_digest` MUST equal the current worker's `env_digest` (re-using a snapshot across `env_digest`s is forbidden — that is a different `Env` per INV-2). |
| `cw_verdict` | `CMP-SNAP-03` over `source@current_commit` | One of `closed-world | degraded | full-reparse`. Per INV-4, the verdict is one-sided: zero FN. |
| `theta_cone`, `theta_files` | Configuration (CLAR-PARAM-01) | Defaults 0.25 and 0.4 respectively (RESOLVED 2026-05-23). |
| Source tree at `current_commit` | Cloned by worker via `CMP-SCM-{02,03}` | A local filesystem checkout. |
| Parent CPG, reverse-symbol index, dynamic call graph | S3 artifacts of `parent_snapshot` (per `DOC-CMP-SNAP-01 §4.2`) | Read-only. |

### 4.2 Outputs

`CMP-SNAP-02` produces five **persisted** artifacts that flow back to `CMP-SNAP-01` for S3 upload at the deterministic keys defined in `DOC-CMP-SNAP-01 §4.2`:

1. **CPG tarball** — the new `G'`.
2. **Reverse-symbol index** — symbol → declaration → use-sites map over `G'`.
3. **Dynamic call graph** — Andersen-style points-to bound (always computed; on the closed-world path the bound is trivial / equals the static CG).
4. **`ΔG`** — the `GraphDelta` structure above.
5. **Precondition-status record** — populates the `precondition_status.json` shape from `DOC-CMP-SNAP-01 §4.3`.

The relational `snapshots.precondition_status` column is set to the **route actually taken** by this component, not the bare `cw_verdict`. The two can differ on the **degraded → full-reparse** transition (a `degraded` verdict that fails the `θ_cone`/`θ_files` check produces a `full-reparse` actual route).

---

## 5. Invariants touched

| Invariant | How `CMP-SNAP-02` discharges it | Test |
|---|---|---|
| **INV-2** | Consumes `parent_snapshot.env_digest` unchanged; the new snapshot inherits the worker's `env_digest` from `CMP-SNAP-01`. Refuses to operate if parent and worker env digests differ. | `TST-INV-2-SNAP-01` (`CMP-SNAP-01` row carries `env_digest`) |
| **INV-4 hand-off** | Consumes the one-sided `CW-DETECT` verdict from `CMP-SNAP-03`. **Never overrides** the verdict in the unsafe direction — a `not-closed-world` verdict is honored even when economically painful. Routing rules in §6. The undecidable-property approximation is owned by `CMP-SNAP-03`; this component is its operational consumer. | `TST-AC-SNAP-03a` (zero-FN of CW-DETECT, the upstream gate); `TST-INV-4-SNAP-03` |
| **INV-5 hand-off** | Records `precondition_status` faithfully so the auditor can decide whether closed-world economics applied. The conditional-canonicality annotation itself lives on `cpg_order_hash` (set by `CMP-CORE-03`, not here). | (indirect; `TST-INV-5-CORE-03`) |

---

## 6. Algorithm / data flow

### 6.1 Routing decision

```
input:  cw_verdict, parent_snapshot, current_commit, theta_cone, theta_files

case cw_verdict of:
  closed-world:
      route = CLOSED_WORLD_INCREMENTAL
  degraded:
      changed_files_ratio = |changed files| / |files|
      if changed_files_ratio > theta_files:
          route = FULL_REPARSE
          reason = 'file-ratio-exceeded'
      else:
          compute Andersen-style points-to cone over (parent_snapshot + delta)
          cone_size_ratio = |cone| / |G'|     # G' estimated from parent + |delta|
          if cone_size_ratio > theta_cone:
              route = FULL_REPARSE
              reason = 'cone-ratio-exceeded'
          else:
              route = DEGRADED_BOUNDED_CONE
  full-reparse:
      route = FULL_REPARSE
      reason = 'cw-verdict-full-reparse'
```

`theta_cone = 0.25` and `theta_files = 0.4` are confirmed defaults under `CLAR-PARAM-01` (RESOLVED). The fallback-rate target ≤15% applies to `CW-DETECT`'s **combined TP+FP routing rate** (i.e., the fraction of snapshots that leave the closed-world path), **not** the true reflection rate — per `PLAN.md §"Algorithm 1"` and `DOC-ALGS §2.4`.

### 6.2 Closed-world incremental path — `AFFECTED` set

Per `PLAN.md §"Algorithm 1"` verbatim:

> Call resolution is CHA over a hierarchy closed under the analysis scope. Then:
>
> `AFFECTED = changed-decls ∪ reverse-symbol-closure(changed-decls) ∪ direct-callers(changed-signatures) ∪ CHA-cone(changed-types)`,
>
> and incremental re-evaluation visits `O(|AFFECTED| + frontier)` nodes with `frontier` the constant-bounded boundary summary-edge set; `O(Δ)` with `Δ = Σ|changed function| + |direct callers| + |CHA-cone of changed types|`.

Procedural steps:

1. Compute `changed_decls` from a Git diff of `(parent_commit, current_commit)` restricted to source files under `source_tree_root`.
2. Look up `reverse-symbol-closure(changed_decls)` in `parent_snapshot`'s reverse-symbol index.
3. Compute `direct_callers(changed_signatures)` from the parent's static call graph.
4. Compute `CHA-cone(changed_types)` over the class-hierarchy view of the parent CPG.
5. `AFFECTED := changed_decls ∪ reverse_symbol_closure ∪ direct_callers ∪ CHA_cone`.
6. Materialize the new CPG `G'` by **function-granularity reparse**:
   - For every declaration not in `AFFECTED`: reuse its parent node IDs (keyed on enclosing-declaration content hash; see §6.4).
   - For every declaration in `AFFECTED`: reparse and mint new node IDs.
7. Emit `ΔG = {added_nodes, removed_nodes, added_edges, removed_edges, affected_set=AFFECTED}`.

### 6.3 Degraded bounded-cone path

```
Andersen points-to analysis bounded by theta_cone:
    Start from changed decls; propagate flow-insensitive points-to facts.
    Track |cone| as |reachable nodes through dynamic edges|.
    If |cone|/|G'| > theta_cone during propagation: abort -> full reparse.
    Else: AFFECTED := closure(changed_decls) ∪ cone(changed_decls).
```

The cone is recorded as a **conservatively imprecise dynamic edge set** in the snapshot's `dyn_call_graph.json.zst` artifact (per `PLAN.md §"Algorithm 1"`: *"mark the dynamic edge conservatively imprecise (recorded in provenance)"*).

### 6.4 Function-granularity node-ID preservation (AC-SNAP-02c)

Node IDs for **unchanged declarations** are preserved across snapshots by keying them on the **enclosing-declaration content hash** (a SHA-256 over the canonical AST of the enclosing declaration). The reparse builds a new CPG with the same node IDs for unchanged declarations and fresh IDs only for declarations in `AFFECTED`. This is the property that lets `CMP-CORE-01` invalidate only `AFFECTED` summaries (`AC-CORE-01c`).

### 6.5 Output flow

```
CMP-SNAP-02 emits the five artifacts -> CMP-SNAP-05 worker uploads to S3 at the keys
                                         minted by CMP-SNAP-01 -> CMP-SNAP-01 receives
                                         report_status callback -> snapshots row updated
                                         (state='ready', precondition_status=<route>,
                                         snapshot_digest=<computed>).
```

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Parent snapshot's `env_digest` ≠ worker's `env_digest` | `compute_incremental_cpg` precondition check | Refuse to run; force full reparse against worker env (the parent is a different `Env`, INV-2). |
| `changed_files_ratio > theta_files` | Routing step | Full reparse; route = `full-reparse`, reason = `file-ratio-exceeded`. |
| Bounded cone exceeds `θ_cone · |G'|` | During Andersen propagation | Full reparse; route = `full-reparse`, reason = `cone-ratio-exceeded`. |
| Bounded cone times out | Wall-clock budget | Full reparse; route = `full-reparse`, reason = `degraded-timeout`. |
| Joern / front-end internal error during reparse | Parser exception | Worker fails the job; SQS retry. If it persists 3×, DLQ + alarm. |
| Node-ID collision (`AC-SNAP-02c` violation) | Post-reparse invariant check | Hard fail; this is an algorithm bug. Refuse to publish the snapshot. |
| `CW-DETECT` returns an unrecognized verdict | Input validation | Hard fail; this is an upstream contract break. Alarm. |

**Safe-direction note (INV-4 hand-off).** `CMP-SNAP-02` honors a `not-closed-world` verdict even when it is economically painful; it never silently upgrades to `closed-world`. The only authorized retroactive partition flip is performed by `CMP-SNAP-04` (after a differential-oracle disagreement, **flipping toward `oracle-passthrough`**, not the reverse).

---

## 8. Provenance threading

`CMP-SNAP-02` does not write to `provenance_records` directly (that is `CMP-FND-03`). Its provenance-relevant outputs feed `CMP-SNAP-01`'s persisted snapshot row:

| Field | Set by | Threading rule |
|---|---|---|
| `precondition_status` | `CMP-SNAP-02` (via `CMP-SNAP-01` `report_status`) | One of `closed-world | degraded | full-reparse`; the **actually-taken route**, not the bare CW verdict. |
| `snapshot_digest` | `CMP-SNAP-02` (sha256 over canonical artifact bytes) | Link 2 of the audit chain. |
| `parent_snapshot_id` | `CMP-SNAP-02` (carried from request) | Chains incremental snapshots; the audit chain follows. |

**Must NOT touch:** `origin`, `S_version`, `env_digest` (inherited unchanged from `CMP-SNAP-01` / worker boot), `cpg_order_hash`, `slice_fingerprint`. Those are downstream-owned.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §4 CMP-SNAP-02`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-SNAP-02a** | > **[CONDITIONAL THEOREM test]** On a closed-world corpus with the precondition asserted per commit, `time(Δ-rebuild) ≤ κ · (|AFFECTED|/|graph|) · time(full-rebuild)` for a frozen `κ`; a regression above `κ` fails. | `TST-AC-SNAP-02a` `[FORTHCOMING]` — `[CONDITIONAL THEOREM]`. Per `CLAR-PARAM-01`: `κ` TBD by detector at registration; placeholder pinned at Stage A go-live. |
| **AC-SNAP-02b** | > **[EMPIRICAL test]** On an open-world corpus, measured median speedup ≥ 5×, p95 ≥ 2× versus full reparse, fallback rate ≤ 15%. | `TST-AC-SNAP-02b` `[FORTHCOMING]` — `[EMPIRICAL]`. Fallback rate is on `CW-DETECT`'s combined TP+FP rate. |
| **AC-SNAP-02c** | > Function-granularity reparse preserves node IDs for unchanged declarations (keyed on enclosing-declaration content hash). | `TST-AC-SNAP-02c` `[FORTHCOMING]` — unit; algorithm correctness gate. |

Upstream invariant tests this component depends on:

- `TST-AC-SNAP-03a` — `CW-DETECT` zero FN on the reflection corpus. Gate 2 release blocker (`CLAUDE.md §15`).
- `TST-INV-4-SNAP-03` — INV-4 falsifier of the CW precondition.

Downstream invariant tests this component supports:

- `TST-AC-CORE-01c` — incremental re-tabulation visits only `AFFECTED` (a consumer of the `AFFECTED` set this component computes).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-SNAP-02 |
|---|---|---|---|
| `CLAR-PARAM-01` | `θ_cone`, `θ_files`, `(B, T)`, `κ` | **RESOLVED** (κ TBD per-detector) | `θ_cone=0.25`, `θ_files=0.4` confirmed; `κ` pinned at Stage A go-live. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` field stays DEFERRED. |
| `CLAR-FE-02` | Stage-C points-to scope (Andersen baseline vs richer) | **DEFERRED** | Affects degraded-path cone width for Go; Stage A is unaffected. |

No new CLAR-SNAP-* are filed by this document.

---

## 11. References

- `SDD.md §4 CMP-SNAP-02` — verbatim ACs.
- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"` — algorithm statement.
- `docs/cross-cutting/DOC-ALGS.md §2` — Algorithm 1 reference.
- `docs/cross-cutting/DOC-GLOSSARY.md` — `AFFECTED`, `precondition-status`.
- `docs/cross-cutting/DOC-PROVENANCE.md §3` — snapshot link in the signed chain.
- `docs/cross-cutting/DOC-INV.md §4, §6` — INV-2, INV-4 owner table.
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — API + persistence.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — CW-DETECT (upstream verdict).
- `docs/components/DOC-CMP-SNAP-04.md` (sibling) — differential oracle (downstream re-partition).
- `docs/components/DOC-CMP-CORE-01.md` (forthcoming sibling) — IFDS solver consumer of `AFFECTED`.
- `WBS.md §17 CLAR-PARAM-01` — resolved defaults.
- `.claude/rules/05-determinism.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-SNAP-02`.*

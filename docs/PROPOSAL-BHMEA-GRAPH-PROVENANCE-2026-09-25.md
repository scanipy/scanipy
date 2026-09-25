# Proposed Black Hat MEA graph, extraction, and provenance contracts

| Field | Value |
|---|---|
| Status | D-CLASS and D-PRODUCERS adopted as implementation direction; detailed graph/flow contracts and all verification remain pending |
| Date | 2026-09-25 |
| Audience | Architect, implementation, QA, security, and SRE agents |
| Parent work | R02, R09, R19 in [the remediation backlog](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md) |
| Additional consumers | R03, R04, R06–R08, R10–R13, R16, R18, R20 |
| Inspected code revision | `940d440cb99e23131d28ee5bbb1655ea29d46a58` |
| Decision state | See 2026-09-25 handoff for root engineering decisions; no human approval or implemented/verified claim is inferred |

## 1. Objective and authority

Deliver the full functionality in [the submitted supporting material](blackhat-mea-supporting-material.md), including genuine called-helper extraction, real interprocedural analysis, independently truthful artifact classes, and real signed provenance. This proposal does not select `REDUCED_DEMO`, defer extraction as a substitute for implementation, or redefine successful end-to-end delivery around existing tests.

The submitted pure-extraction guarantee is conditional on purity. The eligibility procedure below makes that condition operational; it is not permission to demonstrate only unused helpers, identity functions, or hand-built graphs. Meaningful Java and Python positive examples, changed-semantics negative examples, and the genuine source-to-sink execution path are required.

The owner clarified on 2026-09-25 that `PLAN.md`, `SDD.md`, and `WBS.md` are old and may contain obsolete architecture. The full Black Hat submission, remediation backlog, and current user instructions are the active authority. Preserve legacy documents and reuse CLAR records for traceability and compatibility; obsolete approvals do not block in-scope implementation. Record replacement engineering decisions in [the current handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md), without claiming the owner explicitly approved an architectural option they did not select. New export semantics must be versioned and tested, not silently presented as the old resolved wire contract.

The handoff adopts D-CLASS's independent classes and conservative historical handling, D-PRODUCERS's truthful nullable oracle states, and D-ENV's separation of actual image identities from a complete analysis manifest. D-GRAPH/D-FLOW/D-EXTRACT describe required semantics; exact real-Joern fields, finite transfer rules, operation registry, and source-based certification still need engineering decisions and evidence. References below to approval mean this current engineering process, not a new human-permission barrier. Corrective issues/PRs are authorized; required review/tests precede merge. Releases and external messages are separately authorized.

All task boxes are initially TODO. Writing this document proves none of the implementation or acceptance requirements. The diagnostic observations in section 3 are narrow, controlled library checks, not real-Joern or language-support evidence.

## 2. Existing decisions, issues, and actual prerequisites

Statuses below were inspected on 2026-09-25. Recheck before claiming work.

| Record | Current state and meaning | Proposal dependency |
|---|---|---|
| `CLAR-CORE-02`, `WBS.md` section 17 | OPEN; exact pure-extract procedure and formatting/model semantics are unspecified | D-EXTRACT: section 6; blocks normalization activation, not corpus review or the currently specified traversal repair |
| `CLAR-CORE-01` | OPEN; solver/DSL interface reconciliation and documented PR1 limitations | D-FLOW: section 5; reconcile actual access-path, summary, and return-flow implementation with the existing DSL, without inventing a new detector language |
| `CLAR-ORCH-03` | OPEN; graph-level class currently replaces the independent slice verdict | D-CLASS: section 7; blocks automated cross-refactor inheritance |
| `CLAR-ORCH-12`, issue [#359](https://github.com/scanipy/scanipy/issues/359) | OPEN; oracle fields have no legitimate producer on CPG-less paths | D-PRODUCERS: section 8; blocks changed shared-output/schema semantics |
| `CLAR-SNAP-05` | RESOLVED 2026-07-16; real-Joern validation amended 2026-07-19; ratifies AST/CFG/CDG/REACHING_DEF export and mapping | D-GRAPH: section 4 is a follow-up expansion. The existing mapper explicitly forbids inventing CALL support inline |
| `CLAR-ORCH-10` / `CLAR-SNAP-08` | RESOLVED; shared single-member `cpg.json` archive contract | D-GRAPH must version and update the shared serializer/deserializer, not create divergent worker formats |
| `CLAR-ORCH-11` | OPEN; snapshot artifact addressing and distinct worker image boot digests conflict | D-ENV: section 9; blocks the split-image production round trip until an explicit identity/addressing contract exists |
| `CLAR-ORCH-04` | OPEN; job-carried versus snapshot-produced precondition status | D-PRODUCERS must identify and validate the actual snapshot verdict; a job default is not a measurement |
| `CLAR-ORCH-09` | OPEN; detector direct persistence versus SARIF/callback ownership, with missing output hash on the shortcut | Resolve with R08/R12 before accepting that route as the permanent signed-output workflow |
| `CLAR-PROC-01` | RESOLVED; permits hermetically testable build-ahead against stable typed interfaces with truthful gated halves and IN-PROGRESS status | Missing dependency completion is not a blanket reason to stop local diagnostics/preparation; it is still a completion gate |
| `CLAR-DEPLOY-25` | RESOLVED; Docker, local software keys, Postgres, self-hosted single tenant | Do not reintroduce an AWS requirement to solve these tasks |
| Existing B/T decisions and R20 | Existing wall-clock behavior conflicts with same-input reproducibility; resolution remains required | D-CLASS/D-ENV consume R20's approved policy; this proposal does not independently choose or change it |

Relevant live board entries were Todo: SNAP-05 #17, CORE-01 #21, CORE-02 #22, FND-01 #24, ORCH-03 #28, CP-06 #37, oracle clarification #359, and refactor follow-up #360. CORE-03 #20, FND-02 #23, and FND-03 #25 were Done. Use follow-up work for defects in completed components; do not silently reopen or reimplement them. Issue [#360](https://github.com/scanipy/scanipy/issues/360) explicitly requires corpus repair #361 first for its refactor comparisons.

No standalone issue title for `CLAR-CORE-02`, `CLAR-ORCH-03`, or `CLAR-SNAP-05` appeared in the inspected issue inventory. Their WBS records remain authoritative; do not create duplicates merely because a separately titled issue is absent. `board.sh check` and the orchestrator's claim process still apply before implementation edits.

Approval gates are engineering decisions assigned to the repository's role agents. They do not inherently require a new human choice. Human input remains necessary for a reduced submitted scope, external publication/visibility changes, new spend or licensing obligations, and other decisions outside the active authorization.

## 3. Current-state defects and what the evidence proves

### 3.1 The backward-cone traversal stops at intermediate witness nodes

`analysis/fingerprint.py::_backward_interprocedural_slice` documents the reverse-reachable cone from the sink, unioned with the witness. It initializes `on_slice = set(witness)` and `stack = [sink]`, then only pushes a predecessor when it is absent from `on_slice`. Consequently a predecessor already on the witness is never traversed, and its incoming dependencies can be omitted.

Controlled diagnostic, run with `python3 -B` on the inspected revision:

```python
from analysis.ordering import CPG
from analysis.fingerprint import _backward_interprocedural_slice

graph = CPG()
src = graph.add_node("CALL", resolved_fqn="example.source")
mid = graph.add_node("CALL", resolved_fqn="example.transform")
sink = graph.add_node("CALL", resolved_fqn="example.sink")
value = graph.add_node("LITERAL", operator_or_literal="sensitive-value")
graph.add_edge(src, mid, "CFG")
graph.add_edge(mid, sink, "CFG")
graph.add_edge(value, mid, "PDG")
result = _backward_interprocedural_slice(graph, (src, mid, sink))
print(len(result.cpg.nodes))
print(any(n.operator_or_literal == "sensitive-value" for n in result.cpg.nodes))
```

Observed: `3` and `False`. The documented cone contains all four nodes. This test does not settle the future dependence-edge contract or pure extraction; it demonstrates an implementation defect under today's stated contract.

Independently actionable repair A-TRAVERSAL:

- [ ] Separate traversed/enqueued state from final slice membership; visit the predecessors of intermediate witness nodes as well as the sink.
- [ ] Preserve the existing invalid/empty witness errors and induced-edge behavior.
- [ ] Test dependencies of the source, intermediate nodes, branch nodes, cycles, and repeated witness nodes; traversal must terminate and must not omit reachable dependencies.
- [ ] Test that an unreachable unrelated node is excluded and that input graphs are not mutated.
- [ ] Record old/new results on valid fixtures; a newly included dependency may legitimately invalidate old scores.

### 3.2 The mapper and solver do not agree on call-pattern inputs

`analysis/cpg_ingest/mapper.py::_operator_or_literal` fills that field for literals and `<operator>` calls, not ordinary calls. Ordinary callee names are in `resolved_fqn`. `analysis/ifds/solver.py::_pattern_matches` nevertheless compares a DSL pattern only with `operator_or_literal`, by exact equality.

Controlled diagnostic:

```python
from analysis.cpg_ingest.mapper import map_export
from analysis.ifds.dsl.primitives import AccessPathPattern
from analysis.ifds.solver import _pattern_matches

raw = {"nodes": [{"id": "call", "label": "CALL",
                  "name": "get", "methodFullName": "flask.request.args.get"}],
       "edges": []}
node = map_export(raw).nodes[0]
print(repr(node.operator_or_literal), node.resolved_fqn)
print(_pattern_matches(AccessPathPattern("flask.request.args.get"), node))
print(_pattern_matches(AccessPathPattern("flask.request.args.get(*)"), node))
```

Observed: `'' flask.request.args.get`, then `False`, `False`. The second pattern is used by shipped detector specifications. This is a synthetic raw-export-shaped object, not an observation of a live Joern target.

Required action A-MATCHER:

- [ ] Add producer/consumer regression cases using ordinary call metadata and the actual shipped DSL patterns.
- [ ] Implement the existing `DOC-DSL` receiver/member/access-path grammar and semantics against a typed graph view under D-FLOW/D-GRAPH.
- [ ] Keep call identity, operator/literal content, and variable binding distinct. Do not stuff a detector pattern into `operator_or_literal` to make a fixture pass.
- [ ] Reject or explicitly classify unsupported/unknown resolution; do not use suffix matching or a rule-name guess as proof of a resolved external API.

Tests exposing this contradiction and inventorying available metadata can proceed now. Activating a new graph/flow contract waits for its approval.

### 3.3 CALL export is necessary but insufficient

The fixed export script and `EDGE_KIND_MAP` intentionally omit CALL. `analysis/ifds/supergraph.py::build_supergraph` only creates a call relation from an explicit CALL edge to a METHOD node. A `resolved_fqn` string does not create that adjacency.

The solver also currently forwards a source token on CFG edges regardless of the data position, sends the same token into callees, ignores RETURN adjacency, and builds imprecise summaries after the worklist has finished. Its tabulation does not consume `Propagate` clauses. The existing interprocedural witness test covers caller source to callee sink on a constructed graph, not callee return to caller sink on parsed source.

Do not accept a patch that only adds CALL edges or a test that only checks the finding count. Sections 4–6 require the data positions, matched return context, actual source witnesses, and semantic negative controls.

### 3.4 Artifact classes are demonstrably conflated

`services/scan/worker.py::_findings_from_core` retains only `compute_slice_fingerprint(...).slice_fingerprint`. The worker later stamps `canonical_order(cpg).fingerprint_class` onto every finding. `DOC-CMP-CORE-02` section 3.3 explicitly permits all four graph/slice verdict combinations and forbids automatic suppression when either verdict is weak.

No inference from a graph-level `strong` value can reconstruct a discarded slice verdict. R18's canonicality repair and R20's budget policy remain prerequisites even after both values are correctly threaded.

## 4. D-GRAPH — Proposed versioned interprocedural graph contract

### 4.1 Representation and ownership

Approve a `graph_schema_version = 2` export/model contract before implementation. The following are proposed semantic fields, not a claim that the pinned Joern API already exports them. The exporter owner must verify the actual v4.0.554 accessors and per-language coverage before finalizing the mapping table.

| Surface | Required semantics |
|---|---|
| Node identity | Export IDs are opaque strings; mapped IDs are deterministic dense IDs. IDs/locations are references, not semantic labels for strong identity |
| Declaration and value nodes | Explicit declaration ownership, method entry/normal exit/exceptional exit, parameter and return roles, local binding identity, and literal/operator content |
| Call nodes | Resolved target candidates, receiver role, dispatch/resolution status, external/internal classification, argument roles, and any type facts used to certify matching or purity |
| Parameter and argument roles | Semantic zero-based positional indices and named-argument/formal binding; receiver must be distinct from ordinary argument zero |
| Type facts | Value/type identity, exactness versus an upper bound/unknown, and the producer of that fact. A user annotation is not proof of an exact runtime Python type |
| Edges | Typed meaning, orientation, and semantic role/index; preserve data/control/effect distinctions and relevant branch/operand ordering |
| Location side table | File, line, column, and lookup ambiguity information, outside the structural hash input |
| Capability/uncertainty record | Which relations were computed, for which language/files, with explicit unresolved or incomplete coverage; absence of an edge is not evidence of absence when coverage is unknown |

The contract must identify which fields are source-derived, exported directly, or derived by a named analysis. Derived relations carry a derivation version. Arbitrary source text, source coordinates, raw Joern IDs, environment digests, and scan UUIDs must not accidentally become the canonical structural identity.

### 4.2 Relations to preserve

Use a reviewed finite vocabulary; these names are proposed and may be reconciled at ratification, but none of their semantics may be omitted:

| Relation | Direction and required context |
|---|---|
| AST | Parent → child, with semantic child role/order where it determines operands, arguments, or control meaning |
| CFG | Predecessor → successor, identifying normal/exceptional and branch roles where relevant |
| DATA_DEP | Definition/value → dependent use/value, preserving binding and operand role |
| CONTROL_DEP | Controlling predicate/region → dependent operation, preserving relevant branch condition |
| CALL | Call site → candidate METHOD entry, paired with explicit target-resolution status |
| ACTUAL_FORMAL | Actual receiver/argument value → the corresponding callee formal, tied to a specific call site and target |
| RETURN_RESULT | Callee return value → caller result value, tied to the same call site and target |
| EFFECT_ORDER | Effectful operation → operation whose relative order cannot be erased, with a named conservative derivation |

Do not simply rename all current PDG edges. The v1 collapse of CDG and REACHING_DEF has already lost information; re-export fresh graphs to recover it. Do not infer semantic argument order from line numbers or raw insertion order. Adding a new edge kind requires corresponding consumer support or an explicit unsupported error.

A per-call binding record should carry at least:

```text
call_site, target_method, resolution_status,
receiver_binding, ordered_actual_formal_bindings,
normal_return_bindings, exceptional_successors,
coverage_status, derivation_version
```

Call-binding information must survive serialization. Security-relevant roles must also affect the canonical graph representation, either through role-labeled edges/nodes or an explicitly canonical-indexed encoding. Keeping them only in an unhashed side table would make swapped arguments or return bindings invisible to identity. Source-location lookup metadata remains a separate, unhashed concern.

### 4.3 Unknown and dynamic calls

- An unresolved target is not an empty complete target set and is not a fabricated local callee.
- Preserve known candidates and uncertainty separately. Pure-extract certification requires a proven eligible target; otherwise retain the call boundary and mark certification unavailable.
- The analysis must either apply a reviewed conservative unknown-call summary or report the relevant analysis/certification coverage as incomplete. Do not turn incomplete analysis into a successful “no finding” result.
- Do not infer CW-DETECT's `closed-world` verdict from the existence of CALL edges. Thread the actual verdict and separately report interprocedural-resolution coverage.
- Java dynamic dispatch and Python rebinding, descriptors, monkey-patching, decorators, star imports, and reflection need explicit coverage rules. Excluding a case from certification is not permission to omit its uncertainty from the resulting evidence.

### 4.4 Wire compatibility and correctness

- [ ] Update the fixed exporter and its authoritative mapping table together.
- [ ] Version the shared `services/substrate/cpg_tarball.py` envelope; producers and consumers import one implementation.
- [ ] Validate the declared format version. Unknown versions, dangling IDs, invalid indices/roles, malformed bindings, and unsupported relation kinds fail closed.
- [ ] Retain v1 read support only if its limited capability is explicitly represented. Never promote a v1 graph to “v2-complete” by adding empty/default metadata.
- [ ] Make every graph clone/normalization preserve the new semantics. This includes `fingerprint.py`, the solver, canonicalization, and snapshot/detector handoff.
- [ ] Verify raw-array permutation invariance, deterministic archive bytes, semantic-role preservation, and source-location exclusion. Separately run R18's arbitrary-node-relabeling checks.
- [ ] Pin the model/export/mapper/serialization versions in section 9's manifest; invalidate any cache entries whose producing semantics differ.
- [ ] Produce real Java/Python traces with raw-export and mapped-graph evidence before accepting this milestone.

## 5. D-FLOW — Proposed solver and witness requirements

This package implements the existing detector DSL and interprocedural solver commitments; it must not introduce a new detector language, bypass the DSL closure gate, or call oracle output `deterministic-core`.

### 5.1 Finite facts and transfer semantics

Ratify the concrete access-path domain and its bounds under `CLAR-CORE-01`. Facts need to identify the taint origin and relevant program value/access-path position, not only “some source was visited.” Define receiver, argument, return, and field positions plus the conservative abstraction used when alias/field depth cannot be resolved. Preserve the existing grammar and its proof obligations.

Required behavior:

- `source` introduces the appropriate output-position fact of a genuinely matched operation.
- `sink` reports only facts reaching the selected input/receiver/field position, not every taint token earlier on CFG.
- `sanitize` kills only the matching fact positions under the approved language/API semantics; it must not erase unrelated taint merely because a sanitizer occurs in the method.
- `propagate` performs each existing argument/field/return transfer against the actual binding. Exercise every supported form.
- Normal, call, return, and call-to-return transfers are explicit. An unrelated tainted variable cannot taint a clean argument just by preceding a call.
- Model summaries are accepted, version-pinned specifications, not LLM output or ad hoc heuristics added while matching a result.

The primitive implementations' algebraic distributivity tests are necessary but not enough: also test the graph-position adapter and actual solver application of those primitives. Reconcile the intended clause-composition behavior with `DOC-DSL` before coding ambiguous cases; do not silently choose a different algebra.

### 5.2 Matched calls, returns, and summary fixpoint

- Maintain the procedure/context information necessary to match a callee return to the caller that supplied the input fact. A global callee-exit→every-caller edge creates spurious paths.
- Compute summaries during a valid tabulation fixpoint and reprocess waiting callers when summaries change. Computing summaries once after termination is not a returned-value analysis.
- Distinguish normal exits, exceptional exits, generated return facts, and killed facts. Do not summarize all body-node facts as exit facts.
- Preserve same-source deterministic worklist and witness tie-breaking under R18/R20's approved policies.
- Recover a real source-to-sink witness across caller, formal, body, return, and caller-result relations. Summary expansion may use a compact witness DAG internally, but the persisted witness must retain verifiable callee evidence.
- A provenance verifier must be able to check each witness hop against the captured graph/model and call context; a line-location tuple is not a substitute.

Incremental summary invalidation must remain version-scoped and correct. The first BHMEA end-to-end proof may use a full scan, but must not claim the known incomplete incremental machinery is repaired as a consequence.

### 5.3 Acceptance matrix

For both Java and Python, use fresh real parsing and the production graph/solver path:

| Case | Required observation |
|---|---|
| Caller source → helper argument → transformed return → caller sink | Nonempty finding and witness include argument, callee body, return, and caller result |
| Caller source → helper containing sink | Witness genuinely crosses CALL into the callee sink |
| Clean argument plus a different tainted local | No invented argument flow; positive control with the tainted actual does report |
| Two arguments, only one selected by the sink | Swapping relevant actual/formal bindings changes the flow/identity as declared |
| Two callers to the same helper | No return to the wrong caller and no merged decision context |
| Sanitized return versus unsanitized return | Correct finding/removal outcome; sanitizer changes are visible in the slice |
| Changed helper body, literal, target, or return | Relevant changed semantics are visible to analysis and fingerprinting |
| Unresolved/ambiguous target | Explicit uncertainty or reviewed conservative behavior, never invented certainty |
| Restart or repeat with identical pinned inputs | Same analysis content under the approved deterministic boundary; operational IDs/timing handled separately |

These are diagnostics until relevant staging gates permit benchmarking. Generic parse success, a zero-finding scan, or a fixture-only call edge does not close R19 or R10.

## 6. D-EXTRACT — Proposed operational pure-extract contract

### 6.1 What is being certified

An eligible extraction replaces existing slice-relevant computation with a call to a helper that performs that computation and reconnects its result, without changing the modeled data, control, alias, and effect relations relevant to the finding. The helper must be called; the existing computation must actually move. Inlining is the inverse case.

The normalized graph substitutes the helper's formal parameters with the correctly bound actual values and the helper's return with the caller result, preserving all meaningful operations and dependencies. It removes only proven call/declaration scaffolding. Never normalize by dropping every CALL/CFG edge, stripping all callee names, discarding constants, or retaining only the sink name.

This is a graph/refactor identity contract under explicitly supported language semantics, not a universal decision procedure for program equivalence or arbitrary purity. Name the observation model, including treatment of exceptions and effect order. Stack-frame/source-location changes inherent to extraction must not secretly enter the identity; code that inspects those frames/locals invalidates a certificate rather than being declared equivalent.

### 6.2 Eligibility certificate

Proposed `PureExtractCertificateV1`:

```text
language, source_snapshot_digest, graph_schema_version,
call_site, uniquely_resolved_helper, body_digest,
actual_formal_bindings, result_return_bindings,
type_evidence, alias_evidence, effect_evidence,
control_and_exception_evidence, supported_operation_ids,
eligibility = proven | not_proven,
reason_codes, certifier_version
```

The certificate is deterministic audit metadata. It is not an external assertion supplied by a fixture, and its source digest/call IDs must not contaminate the cross-refactor fingerprint. The normalizer consumes its verified bindings and supported semantics, not a bare Boolean flag.

Certification requires all of the following:

1. Unique eligible local target with a captured body and binding environment; no unresolved overriding/rebinding or unknown decorator behavior.
2. Exact argument/formal and return/result correspondence; evaluation multiplicity and order are preserved. Argument expressions are evaluated once in the original order before substitution, not textually duplicated.
3. No unmodeled heap/global/nonlocal mutation, aliased writes, I/O, nondeterminism, dynamic execution, or unknown calls. Read/write effects and alias evidence have named producers.
4. Operations are in an explicit versioned semantics registry. “Looks simple” and an annotation saying `pure` are not proof.
5. Branch, loop, exception, and termination behavior is preserved by the supported transformation/model. Unsupported recursion, exceptional effects, or control transfers produce `not_proven` until modeled, not a heuristic pass.
6. The result reconnects to the implicated sink with actual data/effect dependencies under D-GRAPH/D-FLOW. A syntactically moved but irrelevant helper is not acceptance evidence.

A `not_proven` candidate retains its call boundary and all observed semantics. It cannot inherit a suppression based on asserted extract-equivalence. This certificate state is distinct from CORE-02's canonicalization strength: a graph may be canonically ordered while extraction equivalence is not established.

### 6.3 Java and Python operation coverage

The initial required coverage must include nontrivial expression construction and multiple operands; do not satisfy the task only with `return argument`.

For Java, propose support for uniquely resolved local static/private helpers with scalar/String expressions, local assignments, and a returned result, where operand types and dispatch prove that the admitted operations do not invoke unknown user code. Preserve primitive operator semantics, null behavior, operand order, and relevant exceptional behavior. Object-to-string conversion, virtual calls, mutable fields/arrays, synchronization, and aliased writes require additional explicit evidence or remain uncertified.

For Python, propose support for uniquely resolved local/module helpers whose data operations are proved to use exact supported built-in types, including string construction and scalar arithmetic/local assignments with a returned result. Exact type evidence must come from source construction or an approved pinned model, not from an unverified type hint. Unknown operator overloads, descriptors, iteration protocols, formatting hooks, closures with mutable state, rebinding, decorators, and metaprogramming invalidate that certificate unless separately modeled.

The approved semantics registry must enumerate concrete operations, preconditions, alias/effect behavior, and tests. If the available CPG/type evidence cannot establish these meaningful Java/Python cases, implement the missing analysis evidence; do not replace the full required coverage with trivial helpers and mark extraction complete. Clearly report uncertified cases and the conditional scope in release evidence.

### 6.4 Required source fixture families

Positive families, both before and after, must contain the same vulnerability:

- Multi-operand query/path/request string construction moved from the vulnerable caller into a called helper; the returned value reaches the original sink.
- A chain of local scalar/string assignments whose dependence structure matters, extracted with more than one bound input and one returned result.
- The inverse inline operation, plus combinations with local renaming and file/package movement.
- Two call sites to an eligible helper, demonstrating correct per-call parameter/result substitution and decision separation.

Use exact supported primitive/type evidence for these cases. Fixtures remain ordinary analyzable source; do not inject hidden test-only graph annotations or run scanned source to determine the expected result.

Negative and uncertainty families:

- Change a relevant literal/operator, argument position, returned expression, or actual call target.
- Sanitize only one of two tainted arguments; the other must remain distinguishable.
- Introduce an aliased mutation that actually reaches the sink, not an unrelated list/holder written beside an unchanged flow.
- Move an effect across another relevant effect or control condition.
- Return a different value, discard the helper result, or change a relevant branch.
- Use an unknown virtual/dynamic target or a Python overloaded operation with absent exact-type evidence.
- Rebind the helper or mutate a captured/global value affecting the result.
- Remove the vulnerability, including sink-removal and sanitizer-removal outcomes classified separately from structural comparison failures.

For each pair, record the expected certificate state, finding presence, structural comparison/removal case kind, and required semantic evidence before measuring the fingerprint. R03 validates that the source transformation is genuine; R04 enforces the declared outcomes. Reclassifying a failing required positive as unsupported is a scope decision, not a passing implementation.

## 7. D-CLASS — Proposed independent artifact classes and history

### 7.1 New records

Proposed schema/API names:

| Field | Producer and meaning |
|---|---|
| `cpg_order_hash` | CORE-03 over the actual captured graph |
| `cpg_order_class` | CORE-03: `strong` or `weak`; applies only to graph ordering |
| `cpg_order_hash_annotation` | Versioned assertion referring explicitly to `cpg_order_class` |
| `slice_fingerprint` | CORE-02 over the actual relevant slice, or absent with explicit status |
| `slice_fingerprint_class` | CORE-02: `strong` or `weak`; applies only to slice identity |
| `slice_fingerprint_annotation` | Versioned assertion referring explicitly to `slice_fingerprint_class` |
| `fingerprint_processing_status` | Operational `pending`, `running`, `completed`, or `failed`; never encoded as strength |
| `identity_method` / `identity_version` | Distinguishes canonical slice identity from legacy/oracle-native content identity |
| `origin` | Detection partition, independently set by the worker |

Exact names and annotation literals need ratification and coordinated versioning. The old annotation literal is persisted and signed today; changing it globally in place would misinterpret old records.

Completed structural identity has a populated slice hash and its actual verdict. Pending/failed/not-applicable states do not default to `strong` or manufacture a slice hash. An oracle-native ID may be retained under its own name/method; it is not a CORE-02 canonical fingerprint.

### 7.2 Inheritance policy

| Graph class | Slice class | Automatic cross-refactor suppression |
|---|---|---|
| strong | strong | Eligible for further scope/version/ambiguity checks, not automatic proof of a match |
| strong | weak | Prohibited |
| weak | strong | Prohibited under current CORE-02 section 3.3 contract |
| weak | weak | Prohibited |
| missing/unknown/legacy | any | Prohibited |
| any | missing/unknown/legacy | Prohibited |

Additional guards remain required: compatible identity/rule versions, same authorized repository/codebase scope, completed successful analysis, unambiguous finding association, and R18/R20-verified canonicalization. An unproven extraction certificate cannot authorize an equivalence claim simply because both hash classes are strong. `origin` never changes because of a fingerprint's strength.

### 7.3 Migration and compatibility

- [ ] Add a versioned findings/output/provenance schema and compatible readers before producing new records.
- [ ] Preserve existing occurrence IDs, durable decision links, and original signed payload bytes.
- [ ] Historical single-class records are `legacy_ambiguous` unless authoritative retained producer evidence independently establishes both values. Do not copy one class into both columns.
- [ ] Backfill only through a documented evidence-based migration; retain its provenance. Fresh reanalysis is a new occurrence, not a silent rewrite of historical provenance.
- [ ] Prevent old clients from interpreting graph strength as slice strength. Use a versioned response or explicit capability negotiation; an ambiguous legacy field must not be advertised as a safe strong identity.
- [ ] Update worker dataclasses, ORM/migrations, SARIF property/partial-fingerprint fields, API/UI, attestation projections, signed record schemas, verifiers, and baseline matching together.
- [ ] Test all four combinations, unknown classes, pending/failure paths, old payload verification, retries, and restarts.

Changing a signed encoding does not authorize deleting old keys or signatures. R12 retains historical verification material and selects the verifier by explicit signed schema version.

## 8. D-PRODUCERS — Proposed per-path provenance and oracle handling

### 8.1 Producer map

| Artifact | Legitimate producer; verification obligation |
|---|---|
| Source commit | Checkout resolver; verify the checked-out commit, not merely the requested branch string |
| Source-tree digest | Captured immutable input manifest with declared inclusion rules; distinguish it from a commit string and environment identity |
| Snapshot digest | Versioned digest of actual retained snapshot artifacts; retain enough material to recompute the claimed binding |
| `S_version` / accepted spec digest | Accepted version-pinned registry/spec input; include rule/model mappings affecting detection |
| Image/environment identities | Runtime/build manifest described in section 9; do not infer an image digest from its tag |
| Precondition verdict | Actual CW-DETECT result for this source snapshot; preserve uncertainty and its evidence |
| Graph hash/class | CORE-03 result for the captured graph under approved budget/encoding policy |
| Slice hash/class | CORE-02 result plus actual slice/witness or oracle-associated structural slice |
| Witness | Real solver witness; for oracle findings, explicitly distinguish a structural-association witness from a core detection proof |
| Rule/class/CWE | Pinned detector specification or explicit engine-rule mapping; no guessed label |
| Output hash | Digest of retained actual canonical output bytes under its declared schema/projection |
| Origin | Worker partition setter based on the detection engine; never derived from graph/slice strength |
| Signature and attestation links | R12/R10/R11 services over the completed recorded artifacts; retain key identity and schema version |

### 8.2 Recommended oracle shape for ratification

Propose a versioned shared record capable of representing both CPG-backed and CPG-less oracle findings, with explicit applicability and processing status. This is the nullable/not-applicable branch of `CLAR-ORCH-12`, combined with genuine CPG-backed structural identity where the promised demo requires it. It needs explicit approval because today's shared validator/DDL do not permit that shape.

- Core findings require the actual core analysis, graph, witness, and artifact-specific classes. Missing required core evidence is an error, not “not applicable.”
- An oracle finding begins with engine-native detection evidence. If the required structural analysis succeeds for that same snapshot, attach genuine graph and slice metadata while keeping `origin = oracle-passthrough`.
- A CPG-less oracle path records why the artifacts are not applicable, unavailable, pending, or failed. These are distinct states. It cannot demonstrate the full submitted strong-ID refactor workflow.
- A parser or association failure does not erase a genuine oracle finding or become evidence of a successful fix. Preserve detection status independently from identity processing.
- No CPG hash is fabricated from source, rules, finding JSON, or an unrelated graph. No `closed-world` verdict is supplied merely to satisfy a NOT NULL constraint.
- Map rules to vulnerability classes/CWE using a pinned explicit mapping. Preserve native rule IDs. Missing mappings must be represented explicitly or fail the mapping operation with diagnostics; they must not invent class/CWE facts.
- Association of an oracle location with a CPG sink must handle multiple calls per line, nested calls, and ambiguity. Location is lookup evidence, not part of the structural identity.

The proposed nullable shared contract does not make CPG-less findings complete evidence for all submission claims. Final acceptance still requires the real CPG-backed Java/Python oracle workflow, core workflow, signing, and measured oracle reproduction.

## 9. D-ENV — Proposed complete analysis environment identity

The existing per-image `env_digest` registry and boot checks must not be bypassed. `CLAR-ORCH-11` is a real conflict for different snapshot/detector images, not a reason to stamp the snapshot hash on the detector or set both to a made-up shared image digest.

Propose separate typed identities:

| Identity | Proposed role |
|---|---|
| `snapshot_env_digest` | Actual pinned image that parsed/exported the snapshot; part of its artifact address and producer evidence |
| `detector_env_digest` | Actual pinned detector image; checked against that worker's boot identity |
| Existing `env_digest` | Preserve its versioned image-digest meaning pending explicit CLAR-ORCH-11 ruling; do not silently replace it with a manifest hash |
| `analysis_env_digest` | Domain-separated digest of a canonical versioned manifest covering the complete executed analysis environment |

The manifest must identify snapshot/detector/other relevant worker images, actual mounted analysis code if any, Joern/parser binaries, fixed export script, graph mapper/model/serializer, fingerprint/canonicalization algorithm, approved R20 budget/output policy, rule and accepted-model inputs, detection engines, and relevant configuration. Record the exact canonicalization and inclusion rules of the manifest. Separate source identity from environment identity and explicitly show where `S_version` and its content digest participate rather than ambiguously duplicating them.

The full environment governing a reproducibility claim must include all affecting components. A manifest hash is not an OCI image digest and cannot be compared directly with a container's boot digest. Ratification must reconcile this expanded environment contract with the existing glossary/invariants through the permitted decision process.

Required implementation behavior:

- [ ] Snapshot artifact addressing uses the snapshot producer's verified identity, carried explicitly to the detector.
- [ ] Each worker independently validates its own image/code identity before work; the combined manifest is validated separately.
- [ ] The detector rejects an artifact whose source, producer identity, or declared graph version does not match the job/manifest.
- [ ] A shared-image deployment may use equal image digest values, but must still preserve distinct semantic roles. Do not depend on accidental equality to hide a broken split-image contract.
- [ ] Mounted development code is content-identified and labeled; a container tag/digest alone does not identify overwritten code.
- [ ] Historical manifests, image identities, algorithm versions, and signed records remain available after rollover.
- [ ] Test different image digests, stale/replayed jobs, changed mapper/script/rules, unknown manifest versions, and unchanged-input replay.

CW-DETECT's diagnostic timestamp and other operational timing/IDs must be explicitly allocated to either the reproducible output or operational metadata by R10/R20. Do not silently remove them during comparison to obtain a passing result.

## 10. Implementation milestones and non-circular dependencies

The identifiers below belong to this proposal, not new WBS status codes. Each completion requires its named evidence and the repository's gates.

| Milestone | Prerequisites | Evidence to produce |
|---|---|---|
| M0 — current defects captured | Read-only current-state check | Regression cases for section 3 and corrected task dependencies |
| M1 — approved contracts | Explicit Architect decisions D-GRAPH, D-FLOW, D-EXTRACT, D-CLASS, D-PRODUCERS, D-ENV; SRE/Security review where applicable; R20 policy for budget-related fields | Signed-off decision records and synchronized derivative contracts; no fabricated WBS resolution |
| M2 — graph component verified | D-GRAPH approval | Real Java/Python export/model/archive relation traces and malformed-input controls |
| M3 — flow component verified | D-FLOW approval, M2 interfaces implemented; final evidence uses M2-verified inputs | Nonempty real-source witnesses, matched return/argument controls, correct DSL adapter behavior |
| M4 — extraction component verified | D-EXTRACT approval, valid R03 fixtures, M2/M3, R18/R20 prerequisites | Nontrivial certified Java/Python extract/inline positives and semantic negatives |
| M5 — metadata component verified | D-CLASS/D-PRODUCERS/D-ENV approvals | Schema/producer/verifier tests, four class combinations, old-history compatibility, split-image addressing |
| Early G1 integration | First implemented real graph/flow and metadata seams; no requirement that all M4 refactor cells already pass | Real nonempty scan/output/signature diagnostic with explicit incomplete gates |
| Final G2 integration | M2–M5 verified plus the parent backlog's R07/R08/R10–R13 prerequisites | Actual compose scan/refactor/rescan, safe history retention, distinct partitions, persistent signing and independent verification |

The traversal repair can proceed independently under the existing specified cone contract; it does not wait for M1. Hermetic preparation may proceed under `CLAR-PROC-01`, but cannot assert missing producer values are real. Final integrated acceptance is a shared gate, not a requirement that every participating task wait for the others to be wholly DONE before exposing its interface.

## 11. Approval and verification checklist

### Decision actions

- [ ] Architect reviews D-GRAPH and identifies the follow-up record to `CLAR-SNAP-05`, including wire format and uncertainty semantics.
- [ ] Architect reconciles D-FLOW with `CLAR-CORE-01` and the existing DSL grammar/transfer semantics.
- [ ] Architect approves an operational D-EXTRACT semantics registry and meaningful Java/Python certification domain under `CLAR-CORE-02`.
- [ ] Architect and migration reviewer approve D-CLASS, historical ambiguity handling, and schema/output/signature compatibility under `CLAR-ORCH-03`.
- [ ] Architect approves D-PRODUCERS under `CLAR-ORCH-12` and resolves snapshot-verdict ownership without invented defaults.
- [ ] Architect/SRE approve D-ENV under `CLAR-ORCH-11`, preserving image guards and complete-environment evidence.
- [ ] Security reviews unknown-call/effect approximations, type-model trust, suppression boundaries, source non-execution, and signature/history changes as applicable.
- [ ] Reconcile R08/R12 persistence/output ownership with `CLAR-ORCH-09`; an absent `sarif_hash` is not a verified output binding.

### Evidence actions

- [ ] Retain commands, tool/build identities, input digests, raw outputs, typed graph traces, witnesses, and independent verification results.
- [ ] Preserve the original malformed-fixture evidence and corrected corpus manifest; do not overwrite historical scores.
- [ ] Separate synthetic-library, real-parser integration, component verification, staging/benchmark, and deployed acceptance evidence.
- [ ] Treat unavailable evidence as incomplete, not as a success inferred from a zero exit code or a green unrelated test.
- [ ] Re-run R18 relabeling/negative controls and R20 budget checks after changes to graph roles, normal forms, or serialization.
- [ ] Verify all four artifact-class combinations through every real consumer; include legacy, missing, and parser-failed paths.
- [ ] Prove a real source→helper→return→sink witness and real extract/inline equality while relevant semantic changes remain distinguishable.
- [ ] Verify source non-execution using R16's actual tool paths, not merely the absence of an explicit `python target.py` call in one function.
- [ ] Complete the parent backlog's full claim audit. This proposal and its component milestones alone do not complete the end-to-end goal.

## 12. Primary local references

- [CORE-02 contract](components/DOC-CMP-CORE-02.md), especially sections 3.2–3.3 and 6–9.
- [CORE-01 contract](components/DOC-CMP-CORE-01.md) and [DSL contract](cross-cutting/DOC-DSL.md).
- [SNAP-05 contract](components/DOC-CMP-SNAP-05.md), section 6.3.
- [ORCH-03 contract](components/DOC-CMP-ORCH-03.md).
- [Partition contract](cross-cutting/DOC-PARTITION.md), [provenance contract](cross-cutting/DOC-PROVENANCE.md), [SARIF contract](cross-cutting/DOC-SARIF.md), and [database contract](cross-cutting/DOC-DB.md).
- [Role ownership decision](DECISION-PART3-ownership-2026-06-03.md) and [Docker/self-hosted decision](DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md).
- `analysis/cpg_ingest/mapper.py`, `workers/snapshot/joern-scripts/export_cpg.sc`, `services/substrate/cpg_tarball.py`.
- `analysis/ifds/supergraph.py`, `analysis/ifds/solver.py`, `analysis/fingerprint.py`, `analysis/ordering.py`.
- `services/scan/worker.py`, `services/scan/detector_worker.py`, `services/scan/oracle_attestor.py`, `services/snapshot/worker.py`, `services/snapshot/cw_detect.py`.
- `tests/unit/test_cpg_ingest.py`, `tests/unit/test_core_specs.py`, `tests/unit/test_fingerprint.py`, `tests/unit/test_orch_specs.py`, `tests/unit/test_oracle_attestor.py`, and `tests/integration/test_composition_core_lane.py`.

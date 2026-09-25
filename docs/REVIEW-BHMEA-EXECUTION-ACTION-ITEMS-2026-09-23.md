# Black Hat MEA execution-plan review and remediation backlog

| Field | Value |
|---|---|
| Date | 2026-09-23 |
| Audience | An LLM revising or implementing the Black Hat MEA execution plan |
| Revision | 11 — 2026-09-25 accepted R05/source/typed-transport foundations; 17:29 UTC evidence snapshot with explicit 17:45 UTC update, full acceptance unresolved |
| Status | Execution started; no full R01–R20 task or submitted claim is yet accepted as complete |
| Initial review code revision | `940d440cb99e23131d28ee5bbb1655ea29d46a58` |

## 0. Current instructions — read before executing this backlog

The owner's 2026-09-25 replies supersede conflicting assumptions in the older
plan and this review's historical observations:

- Acceptance/RSVP is confirmed. Do not send another RSVP or escalate the old
  September deadline.
- There is **no October 23 demo-lock deadline**. The presentation is on
  **December 2 or 3, 2026**; its exact date remains unconfirmed. Do not drop
  functionality to fit the old October schedule.
- Complete the **full Black Hat submission**, using this R01–R20 backlog.
  `PLAN.md`, `SDD.md`, and `WBS.md` are old and may describe obsolete
  architecture. Preserve them as historical references; do not let their
  obsolete architecture or approval gates veto the current goal. Existing
  contracts still explain compatibility obligations and useful tests.
- The live demo will run **locally using Docker on this development machine**,
  as confirmed by the owner. The [stage-machine record](evidence/2026-09-25-stage-machine/README.md)
  captures Ubuntu 22.04.5/x86_64, 32 VMware-exposed CPUs, about 62.75 GiB total
  RAM and 101.91 GiB shared free disk. Only about 7.37 GiB RAM was available in
  the latest recorded sample and swap was nearly full. Recheck resources and
  measure actual demo budgets; no offline/performance readiness is established.
  Earlier reference-only diagnostics retain their original limited scope.
- Corrective issues and pull requests in `scanipy/scanipy` are authorized;
  merge only after required review and tests pass. This does not authorize
  publishing releases, sending external messages, new spending, or reducing
  the submitted scope. The repository was observed public on 2026-09-25;
  another visibility flip is not needed.

Use [the current execution handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md) for
decisions, ownership, milestones, next actions, and the machine-readable ledger.
Issue [#362](https://github.com/scanipy/scanipy/issues/362) tracks end-to-end
completion. The original 2026-09-22 plan remains an input being corrected, not
an independent authority to reinstate its deadlines or reduced-demo fallback.

All unchecked acceptance items below remain required unless explicitly
classified optional. An adopted design, recovered historical report, or one
successful Joern parse does not complete a task or verify a submitted claim.

Reviewed foundations have now landed through main `6f1ebc8`: independent
artifact metadata, typed report checking, corrected corpus and dependency
locks, board/fail-closed hook tooling, the occurrence/decision contract, and
the bounded canonical identity/budget foundation, Java static invocation
safety, opt-in raw Joern transport, the pure continuity module, stage/handoff
documentation, fail-closed legacy Git/application containment and bounded
Semgrep observation parsing, Revision 10 documentation (#405), the R05 campaign
producer (#380) and bounded local source custody (#406). The accepted source
head `b005eaa` and merge `6f1ebc8` have the same tree. Narrow #392 is Done;
filesystem custody is not actual Git acquisition, a database seal, runtime
authority or a delivered scan. Occurrence storage and integrated producers
remain pending. See the
[bounded merge/evidence record](evidence/2026-09-25-foundation-merges/README.md)
for exact heads, checks and limitations. Initial defect observations below
remain historical evidence; do not assume every described defect is still
present, or mistake a narrow repair for full R-task acceptance.

The handoff preserves the earlier external canonical-review session limit and
the observed successful recovery: #390, #382 and #389 now have successful exact-head
canonical APPROVE actions and are merged. Remaining candidates still need their
own successful review.
Successful unit/CI checks or an APPROVE word inside a failed review action do
not satisfy that gate. Continue safe, assigned local work without merging until
the exact-head review actually completes successfully. Do not weaken feature
acceptance or retry an exhausted service continuously.

This revision's local evidence cutoff is **17:29 UTC on 2026-09-25**. Later
checks or publication require a separate update, not silent promotion of this
snapshot. The merged R05 producer passed 1,894 tests with 51 existing optional
skips at `9be0579`; source custody passed 1,958/51 at `b005eaa`. Both have
successful exact-head canonical APPROVE actions. The first #406 procedural
REQUEST-CHANGES remains recorded: only title/body scope, actual CI links and
prep-test mapping changed before approval, not the three reviewed files.
No gate was bypassed and no historical component AC was declared complete.

Local-only occurrence storage and typed CPG checkpoints remain separate from
merged acceptance. Git containment #402, application containment #403 and
Semgrep parser #404 are merged; their narrow issues #395/#396/#394 are Done.
Tests from one branch do not validate the combined deployment. Refusing unsafe scans is containment, not delivery
of the promised scan workflow. The next source/authority/semantic contracts
must bind exact verified capture bytes, accepted rule/model bytes, current
durable authorization and actual native observations before a real core/oracle
run can support G1. No caller boolean, fixture signature, graph label or local
test count satisfies those producer obligations. Shared bounded process
transport, runtime-file verification and a pin-relative low-level profile loader
now have reviewed local code; the pure Docker create renderer has three
independent/author runs of the same 288 checks, not 864 distinct tests.
Source-syntax parsing, offline Git capture and signature verification have
reviewed local implementations with separately bounded evidence. Typed CPG
head `83b9ec6` passed 2,103/51 after incorporating accepted main; its actual
push was running and no PR existed at the cutoff. Offline Git head `7dccd5e`
preserves all ten authored files after the same integration; its fresh full
run was pending, and the prior 2,211/51 belongs only to `c2c2078`.
Runtime checkpoint `d51c5f3` includes a reviewed pure process-evidence codec
and a 2,971/51 full run. The overlapping root/author 483-case and corpus
480-case selections are not additive. Its earlier path and loss-accounting
failures remain preserved. The corrected 1,477-line runtime-store design has
scoped wire/replay approval, but its exact pure-journal API is still being
specified and no store implementation exists. Physical capacity, filesystem
installation, database orphan barriers and operational authority are not
accepted. The actual Docker controller, trusted current-anchor factory,
durable journal/admission, kernel enforcement, real operator authority and
API/UI integration remain TODOs.
The source-bound projection review reproduced 13 failing negative controls, then
eight additional closure/wrapper failures after the first correction. A later
368-pass controlled run was followed by four reproduced scope-multiplicity/order
failures. The final correction has root and independent corpus approval after
387 selected checks, 206 independently rerun projection checks and root's same
four negatives passing. The configured full suite passed 2,469 tests with 51
existing optional skips on that earlier projection tree. The later seven-file
compiler/declaration/raw-solver slice is frozen but uncommitted atop `e6c4a2e`.
Its compiler/declaration files have scoped approval. Six genuine raw binding
UUID-coercion negatives were corrected; root's 126-case run and the independent
128-case run pass with scoped raw-solver approval. The earlier 500-case and
2,469/51 results do not validate this newer slice; no new whole-suite run or
commit exists at the cutoff. Complete current-tree tests, normal gates and
remote review, then actual source/native/model/authority/durable integration.
No native fidelity, full Java/Python semantics or G1 acceptance follows from
these controlled checks. Preserve the contrary results and remaining work.
All unchecked TODOs below
remain required; the handoff records exact checkpoints and remaining work.

**Later update — 17:45 UTC:** the earlier 17:29 local snapshot above is retained
as history. Typed transport #407 is now merged at `1b29100` from exact reviewed
`83b9ec6`, with identical tree, all seven remote test checks and successful
canonical APPROVE; only narrow #393 is Done. The scalar seven-file slice was
normally committed at `c4f85c5`, then accepted main was integrated at `f6903cf`;
its new full run is in progress, not yet a passing result. Offline Git `7dccd5e`
passed 2,265/51; its subsequent typed-main integration `3abf021` still needs
fresh affected checks and publication gates. The pure journal API was approved
after correcting authorization-domain versus raw-hash linkage and accounting;
only its two pure source/test files are now allocated and in progress. No
filesystem store, trusted authority, Docker controller or native acceptance is
established. Use the handoff's latest update for immediate next actions.

## 1. Objective and document boundaries

Make the implementation and its evidence satisfy the functionality promised in
[the submitted supporting material](blackhat-mea-supporting-material.md).
Correct [the original execution plan](PLAN-BHMEA-EXECUTION-2026-09-22.md) through
the current handoff and the action items below before treating plan completion
as fulfillment of the submission.

The execution plan is useful but incomplete. It correctly identifies the weak-ID
demo path and proposes integrating structural fingerprints. However, it permits
dropping promised features, its corpus repairs do not establish the advertised
refactors, and it lacks complete workstreams for finding continuity, real-source
attestation, measured oracle reproduction, persistent provenance, and CodeQL.

Re-evaluation also found foundational correctness blockers: an isomorphic-graph
counterexample produces different fingerprints all labeled `strong`; the worker
discards the slice's own strength verdict; exported graphs omit the CALL edges
the interprocedural solver expects; and elapsed time can change fingerprint
content/class with otherwise identical declared inputs. These are explicit
prerequisites below, not issues to discover only during the final demo.

This document records source/document review, before/after fixture diffs, and two
controlled synthetic-graph library diagnostics reproduced on 2026-09-23. Section
8 contains their commands, observed results, and limitations. They are not
real-Joern corpus or end-to-end acceptance runs. The long Joern campaign, Docker
demo, submitted video, public-repository accessibility, and release publication
were not revalidated. Historical scores quoted in the execution plan are
reported observations, not freshly reproduced results.

The reviewed submission and execution-plan files were untracked in the working
tree at review time. The code revision above therefore identifies the code
baseline, not a committed version of those documents. Record their content
digests when producing the revised plan and evidence manifest.

This is a review and implementation backlog. Writing this document does not
complete its TODOs or authorize external messages, publication, or a visibility
change. Follow the active user's authorization and applicable repository rules.
The owner's current instructions in section 0 override the old architecture
hierarchy. Reuse existing decisions and CLAR records for traceability; do not
falsely mark them resolved, create duplicate clarification requests, or repeat
decisions already settled by the owner.

## 2. Rules for the consuming LLM

1. Read the submission, execution plan, this document, and applicable repository
   instructions before revising the plan. For implementation, also read the
   affected component contracts and acceptance tests.
2. Revalidate code locations before acting. Symbol names in the evidence index
   are more durable than the review-time line numbers.
3. Preserve existing user changes. Add remediation tasks to the plan without
   deleting the historical submission or overwriting original evidence.
4. Treat task ownership below as proposed work allocation. Reconcile it with
   repository ownership and the active session's delegation permissions.
5. Separate a correct implementation, a passing test, and a supported public
   claim. None automatically establishes the other two.
6. A synthetic source fixture parsed by real Joern is legitimate real-CPG
   evidence. A hand-built graph proves a narrower mechanism. Neither establishes
   a refactor that the fixture never actually performs.
7. Never improve a score by weakening a comparison, relabeling a failing pair,
   counting missing fingerprints as flips, or silently removing required cases.
   Correct invalid fixtures to match their intended labels and preserve an audit
   trail of those corrections.
8. Keep `origin` independent of `fingerprint_class`. A strong fingerprint on a
   Semgrep or CodeQL finding remains `oracle-passthrough`. Also keep whole-CPG
   ordering strength separate from per-slice fingerprint strength; one verdict
   cannot stand in for both artifacts. Implement and verify the adopted
   artifact-specific contract addressing `CLAR-ORCH-03` before enabling
   cross-refactor decision inheritance.
9. Do not claim universal reproducibility from finite tests. Keep the theorem's
   stated assumptions explicit and separately report empirical checks of the
   implemented pipeline under those assumptions.
10. A task is DONE only when its acceptance criteria have evidence. A decision
    memo, successful process exit, skipped test, or documented deferral is not
    feature completion.
11. A library's `strong` label is not itself proof of canonicality. R18's
    counterexample must be addressed before relying on that label for submitted
    claims or automated cross-refactor suppression. Likewise, passing repeated
    runs does not resolve R20's time-dependent output contract.
12. Use milestone-qualified dependencies, not mutually dependent whole-task
    DONE states. Distinguish component verification from integrated acceptance.
    Preserve relevant correctness/staging gates. Obsolete architectural
    approvals are not blockers under section 0; record replacement decisions.
13. Keep structural comparisons, successful finding removals, and analysis
    failures separate in manifests and reports. Missing data is never a
    computed fingerprint flip or proof that a vulnerability was fixed.

## 3. Completion modes and claim ledger

Two outcomes must remain distinct:

- `FULL_SUBMISSION`: every submitted capability has an implemented path and
  appropriate evidence. All required claim rows are satisfied.
- `REDUCED_DEMO`: the owner has accepted an explicitly smaller public scope.
  Omitted submitted capabilities remain unfulfilled. A rewritten document or a
  recorded fallback does not change their fulfillment status.

Default the revised plan to `FULL_SUBMISSION`. Do not silently select the smaller
scope because the schedule is tight. Prepare a concrete scope-difference memo
when a capability cannot be delivered. Reuse any existing owner decision.

Report stage readiness separately from submission fulfillment. Offline rehearsal
is an execution-plan requirement, not an additional promise inferred from "no
cloud account." Optional tooling is not a prerequisite merely because it appears
in this backlog. Section 5 classifies these obligations explicitly.

The submission does not enumerate every language or every legal variant of
extract-method. Make the supported language and transformation boundaries
explicit. At minimum, assess Java and Python because the execution plan uses
both as its evidence. A newly restricted subset must be disclosed; do not
present it as an unrestricted guarantee from the original wording.

| Claim ID | Submitted capability | Submission section | Review assessment | Required remediation |
|---|---|---|---|---|
| C01 | Local-variable rename preserves identity | 3, 4 | Existing measured claim; revalidate corpus and canonicalization foundation | R03, R04, R06, R08, R18 |
| C02 | Formatting preserves identity | 4 | Tested formatting scope needs limits; canonicalization foundation is unverified | R03, R04, R06, R08, R18 |
| C03 | Independent statement reordering preserves identity | 4 | Current fixture inserts a statement; actual reordering behavior is not established | R03, R04, R06, R18 |
| C04 | Extract-method preserves identity | 4 | Fixture adds unused code; real interprocedural connectivity is also missing | R02, R03, R06, R18, R19 |
| C05 | File move/package rename preserves identity | 4 | Python fixture adds a comment; generated filenames do not move | R03, R04, R06, R18 |
| C06 | A genuine fix changes the implicated structural identity | 4 | Historical 7/8 score; successful finding removal needs a separate evidence type | R03, R04, R06, R07, R18 |
| C07 | Structural hashing; location only locates the node; truthful strong/weak labels | 2, 3, 4 | Strong-label counterexample, graph/slice class conflation, and location-hash demo path | R06, R08, R09, R18, R20 |
| C08 | Triage history and suppression decisions survive harmless refactors | 1, 3 | Lifecycle missing; class-conflation hazard must be resolved before inheritance | R07, R08, R09, R18 |
| C09 | Core output is byte-identical under the stated reproducibility assumptions | 2 | Real-source rerun path missing; elapsed time can change output at fixed declared inputs | R09, R10, R18, R19, R20 |
| C10 | Oracle findings carry a measured reproduction rate | 2 | No execution card produces and exposes a real measurement | R09, R11 |
| C11 | Signed, independently verifiable provenance for actual findings | 2, 5 | Real cryptography exists; persisted scan-to-export integration is underspecified | R09, R12 |
| C12 | One-command, self-hosted, single-tenant deployment with Postgres and no cloud account | 5, 6, 7 | Covered in intent; new worker and release must preserve it | R08, R15, R17 |
| C13 | Pasting a repository produces real findings labeled with CWE and origin | 5 | T0.4 covers a smoke check; retain it through the new path | R08, R13, R17 |
| C14 | Detection uses Semgrep and a CodeQL adapter | 2, 6 | Semgrep demo exists; no demonstrated CodeQL adapter task | R13 |
| C15 | Demo compares Scanipy identity with actual incumbent IDs after refactoring | 3, 5 | No task captures actual comparator output | R14 |
| C16 | Scanned repository code is analyzed, never executed | 6 | Java dependency-fetch/preprocessing defaults and arbitrary JVM environment need explicit safety controls; full runtime proof remains missing | R16 |
| C17 | Apache-2.0 open-source tool, publicly reproducible release | 6, 7 | Release/publication gates exist; ownership and final checks need completion | R17 |
| C18 | Runnable Joern-backed validation harness and published evidence artifacts | 4, 7 | Harness exists; command packaging, corpus validity, and evidence gates need work | R03, R04, R05, R17 |

The ticket reference in the submission illustrates continuity. Preserve attached
reference metadata if represented in the product; this does not require building
a new Jira, email, or other external ticketing integration.

## 4. Evidence index

These references support the review findings. Read the implementation, not only
its docstring, when designing a correction.

| Evidence ID | Source and review-time locator | Observation |
|---|---|---|
| E01 | `docs/PLAN-BHMEA-EXECUTION-2026-09-22.md`: T2 line 453, T4 line 478, TD-1 option C line 397, section 8 | Tasks can complete through deferral or a smaller demo. |
| E02 | `tests/corpora/refactor/pipeline/refactor_transforms.py`: `_reorder_independent` line 122 | Adds `unrelated = 7 + 35` or its Java equivalent. |
| E03 | Same file: `_pure_extract` line 135 | Adds an unused helper without extracting existing code or calling the helper. |
| E04 | Same file: `_fqn_move` line 152; `pipeline/build_corpus.py`: `generate_seeds` line 87 | Python adds a comment; all after trees retain `base.filename`. Java changes package text. |
| E05 | Same transform file: `_aliasing_changing_extract` line 241, `_first_body_index` line 280 | Holder does not feed the original sink; Java insertion can select the class body. |
| E06 | `deploy/scanipy_oracle/app.py`: `finding_tbl` line 101, `_map_findings` line 188 | Separate rows per scan; fingerprint hashes commit, rule, file, line; demo table has no triage/suppression fields. |
| E07 | `deploy/scanipy_oracle/static/index.html`: `check` line 189, `render` line 229 | Polling stops when the scan stops running; individual results do not display fingerprint identity/class. |
| E08 | `deploy/scanipy_oracle/app.py`: `_run_scan` line 226, `post_scan` line 319 | Clone is deleted after detection; API accepts only public GitHub URLs. |
| E09 | `tests/falsifier/attestor/test_cp05_attestor.py`: lines 14–19; `services/scan/attestor.py`: `_FailClosedScanRunner` | Existing falsifier uses an injected runner and synthetic CPG; default production rerun port raises. |
| E10 | `services/scan/oracle_attestor.py`: module contract and `OracleScanProvenance`; `WBS.md`: CLAR-ORCH-12 | Oracle emission/attestation requires fields without agreed producers on the current demo path. |
| E11 | `tools/provenance_demo.py`: `DemoProvenanceStore`, `build_chain_record`, `run_demo`; `services/scan/software_kms_signer.py`: `SoftwareKMSSigner.__init__` | Caller supplies chain values; defaults use memory-only records and a fresh key; artifact checks are optional. |
| E12 | `deploy/scanipy_oracle/app.py`: `_compute_env_digest` line 128 | Digest currently covers Semgrep version and rules, not the proposed Joern/fingerprint worker. |
| E13 | `services/scan/worker.py`: `_FailClosedOracleAdapter` line 320; `workers/snapshot/Dockerfile` | A CodeQL binary is bundled, but the default adapter raises; bundling is not adapter delivery. |
| E14 | `scripts/validate_refactor_fingerprints.py`: `main` line 1023, `evaluate_pair`, `RealFingerprinter` | Contrary results can exit 0; missing/weak results are differentiated; parsing is cached. |
| E15 | `analysis/fingerprint.py`: `_backward_interprocedural_slice`, `_normalise`, `_content_hash`, `eligible_for_baseline_suppression` | CFG participates in slicing and hashing; normalization and canonical ranking interact; weak suppression guard exists as a library predicate. |
| E16 | `services/scan/oracle_fingerprint.py`: `locate_sink_node` line 116 | Exact file/line lookup with CALL/column/node-ID tie-breaking; no caller-provided column/range. |
| E17 | `analysis/cpg_ingest/mapper.py`: `EDGE_KIND_MAP` line 199 | Control dependence and reaching definitions both map to `PDG`; data/effect reasoning needs care. |
| E18 | Execution plan: T0.1/T0.2, T4/D3, dependency graph, Appendix B | Ownership overlaps, a D3/T4 dependency loop, a TD-2 reference without a card, and no T4 ownership entry. |
| E19 | `analysis/ordering.py`: `_individualise_refine` line 269, `_digest_order` line 328; section 8 diagnostic | Individualisation selects the lowest raw node ID and hashes that ID into a label. Six insertion orders of the same three-node graph yield two different slice fingerprints, all `strong`. |
| E20 | `services/scan/worker.py`: `_findings_from_core` line 556, `run_detector` lines 703–721; `WBS.md`: CLAR-ORCH-03; `DOC-CMP-CORE-02` section 3.3 | Slice class is discarded and replaced by whole-CPG class. The contract permits all four graph/slice class combinations; the existing CLAR records the latent suppression hazard. |
| E21 | `workers/snapshot/joern-scripts/export_cpg.sc`: lines 34–41 and edge emitters; mapper `EDGE_KIND_MAP`; `analysis/ifds/supergraph.py`: `build_supergraph` lines 151–165 | Exporter/mapper omit CALL edges; the solver builds caller/callee adjacency from CALL-to-METHOD edges. A call name string does not supply that missing adjacency. |
| E22 | `analysis/ordering.py`: `_individualise_refine`, `canonical_order`; section 8 diagnostic | With fixed graph and default B/T, a module-local simulated clock changes the slice result from strong to weak and changes its hash. This demonstrates a timing dependency, not a measured production failure rate. |

## 5. Prioritized task inventory

Priority describes urgency, not whether an item was promised. P0 blocks
trustworthy evidence or a central capability; P1 covers remaining delivery and
readiness work; P2 is optional efficiency work. Current execution state is in
the handoff ledger; no task has yet reached accepted end-to-end completion.

Classify each action as one or more of:

- `S` — `submission_requirement`: directly supports a C01–C18 promise.
- `P` — `correctness_prerequisite`: needed to trust a selected implementation or
  its evidence; not a new advertised product feature.
- `D` — `release_stage_requirement`: required by the selected release/demo plan,
  such as offline rehearsal. Retain selected requirements unless the owner
  explicitly changes them; report readiness separately from claim fulfillment.
- `O` — `optional_efficiency`: an optimization/convenience that may be omitted
  with a reason. Cache correctness becomes mandatory if that cache is used.

`FULL_SUBMISSION` requires all claim rows and their correctness prerequisites,
not every optional action. R05's command packaging is required; persistent
caching and a dedicated debug utility are not. R15's attendee installation
checks support C12; its offline stage preparation is a separate D obligation.

Dependency milestones have these meanings:

- `design_ready`: required decisions/contracts are recorded through the allowed
  process; this does not imply working code.
- `implementation_ready`: a runnable implementation of the stated path exists;
  correctness tests may still fail and must be reported.
- `component_verified`: the card's scoped checks pass without waiting for
  downstream integrated acceptance. Record the exact languages/engines covered.
- `integration_verified`: shared checks pass on the merged artifact at G2 or the
  applicable G3 gate. This is not a prerequisite for building its own consumers.

The inventory lists entry prerequisites and expressly marked verification
prerequisites, not whole-task DONE dependencies. Section 6 defines shared
acceptance gates. R01 must expand these into an acyclic milestone DAG while
retaining applicable correctness dependencies and staging under section 0.

| ID | Priority / scope | Task | Primary owner role | Entry prerequisites | Existing cards affected |
|---|---|---|---|---|---|
| R01 | P0 / P | Repair execution contract, milestones, schedule, ownership | Plan maintainer | None | Sections 0, 4, 6–8, Appendix B |
| R02 | P0 / P | Resolve pure-extract semantics | Architecture | R01.design_ready; existing D3/CLAR process | T4, D3 |
| R03 | P0 / S,P | Correct and validate corpus transformations | Corpus/QA | R01.design_ready; R02.design_ready for extraction | T0.2; prepares G0 |
| R04 | P0 / P | Enforce typed harness/report acceptance | QA | R01.design_ready; checker tests need no completed G0 | R1, G0, T1–T4, L0 |
| R05 | P1 / S,P; P2 / O | Package reproduction commands; optional caching/diagnostics | Analysis tooling | R01.design_ready | T0.1 |
| R06 | P0 / S,P | Validate all advertised fingerprint invariances | Analysis | G0; R02.design_ready; R18.component_verified, R19.component_verified, R20.component_verified for trusted acceptance | T1, T2, T3a, T3b, T4 |
| R07 | P0 / S | Persist finding continuity and decisions | Findings/API | R09.design_ready; safety gates before enabling inheritance | New lifecycle card |
| R08 | P0 / S | Complete asynchronous fingerprint demo integration | Deployment/API/UI | D2 resolution; R09.design_ready | TD-1, TD-2 |
| R09 | P0 / P | Resolve artifact-specific classes, provenance, environment identity | Architecture/provenance | R01.design_ready; existing CLAR process | CLAR-ORCH-03/12; TD/attestation/provenance |
| R10 | P0 / S,P | Wire early real-source core runs and attest them | Analysis/attestation | R09.design_ready; R20.design_ready for output contract | T0.4, R1(d), G1, L0 |
| R11 | P0 / S | Measure real oracle reproduction per engine | Attestation/API | R09.design_ready; R13.component_verified only for CodeQL measurement | New oracle-attestation card |
| R12 | P0 / S | Persist and independently verify finding provenance | Provenance/API | R09.design_ready; runnable scan producer for component evidence | T0.4, G1, TD provenance |
| R13 | P0 / S | Deliver the CodeQL adapter | Detection adapters | R09.design_ready; R16.design_ready before enabling engine modes | New adapter card |
| R14 | P1 / S | Measure actual incumbent-ID comparisons | Evaluation | R03.component_verified for selected pairs; real comparator engines | Demo beat 3, DOC-3, DOC-4 |
| R15 | P1 / S,D | Verify attendee installation and offline stage readiness separately | Deployment/demo | D2 resolution; runnable R08 path for measurements | DEMO-1, REL, FALL |
| R16 | P0 / S,P | Preserve never-execute-scanned-code contract | Worker/security | R01.design_ready; review enabled implementations at verification | TD-1, adapter and deployment work |
| R17 | P1 / S,D | Aggregate evidence, lock claims, validate authorized release | Release/docs/QA | Evidence conventions may start now; final gates in section 6 | T0.5, L0, DOC-1–4, DEMO-1, REL, FALL |
| R18 | P0 / P | Repair and verify canonicalization and strong-label correctness | Analysis/architecture | R01.design_ready; applicable canonicalization contract review | New prerequisite to T1–T4 and suppression |
| R19 | P0 / P | Deliver real caller/callee and argument/return connectivity | Ingest/core analysis | R02.design_ready; existing exporter/model decision process; R16.design_ready | Prerequisite to T4 and interprocedural core evidence |
| R20 | P0 / P | Resolve time-budget dependence in the determinism contract | Architecture/analysis | R09.design_ready; existing budget/reproducibility decisions | Prerequisite to R10 acceptance and theorem wording |

### R01 — Repair the execution contract, schedule, and ownership

Evidence: E01, E18. Scope: the execution plan and a proposed machine-readable
claim/acceptance manifest. Preserve the submitted material as a historical input.

TODO:

- [ ] Map every C01–C18 claim to an owner, runnable path, acceptance criterion,
  evidence artifact, and current fulfillment status.
- [ ] Classify each action using S/P/D/O, independently of priority. Do not make
  an optional cache or offline stage rehearsal an inferred submission promise.
- [ ] Define `FULL_SUBMISSION` and `REDUCED_DEMO` separately in the plan. Mark
  feature deferral as unfulfilled against the original submission.
- [ ] Replace whole-task dependency edges with explicit design, implementation,
  component-verification, and integration milestones. Validate the expanded DAG
  for cycles, missing milestones, and scope mismatches.
- [ ] Make G0 a separate baseline gate after corpus/checker preparation, not
  part of R03's completion. Make CodeQL adapter verification a prerequisite to
  its rate measurement, never dependent on that same measurement completing.
- [ ] Schedule R18 canonicality, R09 class ownership, R19 call connectivity, and
  R20 budget semantics as early blockers. Run a thin real-source core/oracle/
  provenance path at G1 before waiting for all R06 invariance work to finish.
- [ ] Assign integrated lifecycle checks once to G2. R07 and R08 must not each
  wait for the other's final acceptance. Likewise, R09's contract/producer
  milestone must not require all downstream attestation/export workflows first.
- [ ] Replace aggregate phrases such as "four of five" with a language-by-refactor
  matrix and declared preconditions. Do not assume a Python result covers Java.
- [ ] Move the pure-extract decision memo out of gated T4 into an early task.
  D3 must receive its memo before T4 depends on it.
- [ ] Define TD-2 as a concrete task or remove it consistently from the graph.
  Recommended split: TD-1 owns worker infrastructure; TD-2 owns the complete
  API/UI lifecycle and acceptance scenario.
- [ ] Extend fingerprint ownership through T4. Allocate the new worker loop,
  migrations, schema, lifecycle, attestation, signing, and test files explicitly.
- [ ] Resolve T0.1/T0.2 overlap on the corpus README and harness. Resolve the
  `deploy/**` versus DOC-2 ownership overlap. Serialize shared-file edits.
- [ ] Reestimate the schedule with all remediation work toward the December 2
  or 3 presentation. Remove the October 23 lock and automatic October scope
  reductions. Use evidence-gated milestones and report forecast uncertainty;
  do not leave extraction design until the same week as its implementation.
- [ ] Preserve useful original work: T0.3 tracker correction, T0.5 historical
  evidence recovery, slice diagnosis, independent verification, rehearsal, and
  failure drills.
- [ ] Replace stale "today" wording with dated actions. Check existing D1–D6
  decisions before asking again. Do not infer permission to send an RSVP email
  or change repository visibility from this backlog.

Acceptance: every submitted claim and every task reference resolves; no circular
dependencies or unassigned shared-file edits remain; the revised schedule shows
technical uncertainty, early integration evidence, and separate full-submission,
reduced-scope, release-readiness, and stage-readiness outcomes.

### R02 — Resolve pure-extract semantics early

Evidence: E03, E15, E18, E21; existing `CLAR-CORE-02`. Scope: the decision memo and
applicable component contracts through the repository's permitted process.

TODO:

- [ ] Read `docs/components/DOC-CMP-CORE-02.md` and the existing CLAR before
  drafting anything new.
- [ ] Define the supported extract/inline operation: which statements move, how
  arguments and returns reconnect to the sink, and which effects/aliases must be
  preserved. State Java and Python support explicitly.
- [ ] Identify the actual CPG information needed to establish purity and alias
  stability. Distinguish available information from information requiring new
  mapper/exporter/model work.
- [ ] Account for the known missing CALL-edge path in E21. Specify the caller,
  callee, argument/return, and effect information R19 must deliver before R06
  can normalize a genuine extraction. A method name alone is not connectivity.
- [ ] Define conservative behavior when purity cannot be established. Such cases
  must not inherit a suppression merely because a heuristic guessed equivalence.
- [ ] Specify genuine called-helper positive fixtures and changed-effect/alias
  negative fixtures for R03 and R06.
- [ ] Obtain the required architecture decision using the existing authorization
  and decision process. Record exactly which subset is supported and which
  submitted wording needs qualification, if any.

Acceptance (`design_ready`): an operational, implementable contract exists
before T4 starts; R19's prerequisites and supported extraction subset are explicit.
Deferring extraction may resolve a planning decision, but leaves C04 unfulfilled.

### R03 — Correct the corpus before establishing G0

Evidence: E02–E05. Scope: `tests/corpora/refactor/**`; coordinate any harness
metadata/locator changes with R04/R05. Do not change comparison semantics to
compensate for invalid fixtures.

TODO:

- [ ] Fix Java insertion so statements enter the intended method with the
  relevant variables in scope, not the class body or an unrelated constructor.
- [ ] Replace the reorder transform with a real permutation of existing,
  independent statements. Keep the same statement set on both sides.
- [ ] Replace pure-extract fixtures with movement of existing slice-relevant
  logic into a helper that the original method actually calls. Reconnect the
  helper's result to the same sink according to R02.
- [ ] Implement actual file moves in both languages and package/module renames
  where applicable. Update imports/references and actual paths. A comment is not
  a module rename; separate parent fixture directories are not sufficient proof
  of a source-file move.
- [ ] Make aliasing-changing extracts alter the alias/effect relation feeding
  the sink. An unused container next to the original flow is insufficient.
- [ ] Audit genuine-fix fixtures to ensure the intended security-relevant change
  is real. Explicitly document any trusted dependency or sanitizer contract; a
  safe-sounding class name alone does not establish a fix.
- [ ] Assign each case an evidence type and expected outcome before running the
  detector: `structural_comparison` with `stay`/`flip`, `finding_removal`, or a
  deliberately seeded `analysis_failure` control. Use R04's separate criteria;
  do not require an after-fingerprint for a valid removal case.
- [ ] Independently validate fixture syntax, intended transformation, and
  ground-truth rationale. Successful parsing alone does not prove semantics.
  Add tests that fail on the currently vacuous transformations.
- [ ] Record before/after source locations or an unambiguous finding locator
  where actual moves/extraction require them. Fail explicitly on ambiguity.
- [ ] Regenerate affected variants, increment the corpus version, update the
  lock and README, and retain a manifest of corrected pairs. Preserve intended
  labels; if a label cannot be substantiated, report the case as invalid pending
  correction rather than silently rewriting its expected outcome.
- [ ] Run corpus pipeline tests explicitly; they are excluded from the global
  pytest collection. Deliver versioned fixtures, expected inventory, and
  validation evidence as inputs to the later, separately owned G0 gate.
- [ ] Retain the eight-topology limitation in reports. Larger counts from the
  same templates do not increase structural diversity. Add targeted, distinct
  counterexamples for newly discovered normalization risks and report them
  separately from the historical corpus.

Acceptance (`component_verified`): every transformation case performs its named
operation, has reviewable ground truth, parses through the intended frontend,
and identifies the intended source/sink correspondence or expected post-fix
absence. Seeded parser-failure controls are explicitly separate. Validation does
not require the current detector/fingerprinter to produce the expected answer.
R03 completes before G0; it does not depend on G0 or an invariance pass. Old 4/4
or 8/8 values are not carried forward as proof after this correction.

### R04 — Enforce acceptance by reading report contents

Evidence: E14; execution-plan R1/R2. Scope: a separate acceptance checker,
versioned gate configuration, and tests; keep the reporting harness's honest
reporting behavior.

TODO:

- [ ] Add a report-consumer command that returns nonzero when required semantic
  acceptance criteria fail. This is a new tool to implement, not a command that
  already exists.
- [ ] Pin the expected corpus version/digest, required pair IDs, language cells,
  evidence types, preconditions, and comparison-strength requirements in the
  gate configuration.
- [ ] Bind reports to the semantic policy content, not its name alone. A changed
  namespace/strength policy must not erase previously protected passes. Preserve
  an append-only, reviewed baseline/improvement registry without a hash cycle.
- [ ] For acceptance and nonregression, require an independently supplied
  expected analysis-code revision. Do not accept an older green report merely
  because it is still fresh, or confuse the analyzed repository's commit with
  the analysis implementation's commit.
- [ ] Require every expected pair to appear exactly once. Reject missing,
  duplicate, malformed, or unexpected-version reports.
- [ ] Require correct strong/strong comparisons for claimed refactor invariance.
  Report weak, failed-parse, and unresolved-location cases separately; do not
  improve the denominator by excluding them from required acceptance.
- [ ] Separate baseline-report validity from feature acceptance. G0 may record
  honest failing/unevaluated results on valid fixtures; accepting that baseline
  artifact does not pass those claims. The final gate must reject required
  failing or unevaluated cases according to their declared evidence type.
- [ ] Default G0 requires fresh real Joern execution and an evidenced processing
  attempt for every before/after side. Historical, synthetic, cached or
  all-not-run diagnostic reports cannot pass that gate. Missing purity,
  detection or lifecycle semantics may remain explicit red baseline results.
- [ ] Enforce no regression per pair and per language, including all relevant
  should-flip cases. One repaired case cannot offset a newly broken case in an
  unchanged total. Protect both the G0 record and improvements already accepted
  in later merges.
- [ ] Set final full-submission targets on the corrected corpus for both Java
  and Python. Replace historical hardcoded denominators if the inventory changes.
- [ ] Distinguish structural fingerprint flips from detector disappearance.
  For a `structural_comparison`, a missing after-fingerprint is unevaluated, not
  a flip. For a `finding_removal`, require a previously observed finding and a
  completed, sufficiently scoped after-scan that establishes its expected
  absence; consume R07's lifecycle evidence rather than inventing a second hash.
- [ ] Never reinterpret an unexpected parser/engine failure as a removal case.
  Keep the original manifest type and report the failure against it. A seeded
  `analysis_failure` test can pass its error-handling criterion but contributes
  no positive evidence for invariance, a computed flip, or a successful fix.
- [ ] Test the checker with a passing report and reports containing a wrong
  result, missing case, weak-only match, denominator reduction, stale corpus,
  a newly regressed pair hidden by an aggregate improvement, valid removal
  without an after-hash, and a failed scan incorrectly reported as a removal.
- [ ] Add the exact checker invocation to every relevant task's done-when gate
  and to L0. Interpret skipped/xfail integration cases explicitly.

Use these non-interchangeable acceptance records:

| Evidence type | Required observation | What must not count as a pass |
|---|---|---|
| `structural_comparison` | Two corresponding fingerprints, declared strength requirements, expected equality/inequality | Missing after-result, weak-only canonical claim, or unrelated sink |
| `finding_removal` | Baseline finding present; successful after-scan with required coverage confirms expected absence; lifecycle resolved correctly | Parser/engine failure, skipped rule/file, timeout, or merely missing fingerprint |
| `analysis_failure` | Deliberately induced failure remains visible and does not falsely resolve/inherit decisions | Counting correct error handling as a refactor/fix success |

Acceptance (`component_verified`): the checker passes positive/negative fixture
reports independently of G0. At G0 it validates the complete baseline record;
at G2 it enforces the declared semantic targets. Contrary results cannot pass
the release gate merely because the harness exited 0. Report denominators and
outcomes separately by evidence type; do not collapse disappearance into flips.

### R05 — Package reproduction commands; make caching optional and safe

Evidence: E14; T0.1. Scope: reproduction documentation and required command
packaging; optional cache/debug tooling if selected. R06 does not require a new
persistent cache. An uncached, reproducible path is sufficient.

TODO — required S/P work:

- [ ] Provide exact build and in-image run commands, including pins, mounts,
  workdir, output directory permissions, and required dependencies. Verify the
  entrypoint on a small fixture without waiting for a green refactor campaign;
  verify the complete attendee workflow again at release.
- [ ] Provide an explicit fresh/no-reuse execution mode and record cache mode,
  toolchain/corpus identities, and relevant diagnostics in run evidence.
- [ ] Ensure final lock/release includes fresh-parse confirmation. R10's
  independent reruns must not share cached parsed graphs.
- [ ] If any existing cache is used, audit its identity and stale-data behavior
  against the criteria below, or disable it for acceptance runs.

TODO — optional O work; mark `NOT_SELECTED` with a reason if omitted:

- [ ] If implementing persistent caching, key raw exports by source-tree content
  including relative paths, language, relevant parse flags, toolchain/image
  identity, and export-script identity.
  Exclude incidental absolute checkout paths from the cache key.
- [ ] Re-map raw exports using current mapper code, or include mapper/schema
  identity in any mapped-graph cache key. Never reuse cached fingerprints while
  evaluating fingerprint implementation changes.
- [ ] Handle location/root-sensitive metadata explicitly on cache reuse. Verify
  cached and fresh results agree when identical trees are checked out under
  different absolute directories. Do not merge distinct relative file layouts.
- [ ] Validate cache completeness and metadata; do not consume partial or stale
  exports as valid hits.
- [ ] Implement the slice dump against the actual production normalization and
  hashing inputs. Avoid a duplicate normalization implementation that can drift.
  Include node labels, graph edges, ranks, class, and the reason for any fallback.
- [ ] Record hit/miss counts and measure iteration-time improvement if claiming
  the optimization. A dedicated dump utility is optional if existing output
  exposes sufficient production inputs to diagnose R06/R18/R19 failures.

Acceptance: `commands_verified` means the documented fresh-run entrypoint works
and required evidence metadata is available. This is the only R05 milestone G0
requires. `cache_verified` is required only for runs relying on a cache: its
invalidation works for source/path-layout/toolchain/exporter/mapper changes and
cached/fresh results agree. A cache may be selected for later optimization while
remaining disabled in acceptance runs; it must not block G0/R06. Do not label an
unimplemented optimization DONE merely because it was optional.

### R06 — Fix the mechanism against valid evidence

Evidence: E15–E17, E19, E21. Scope: the serial fingerprint lane and associated
meaningful tests. Coordinate canonicalization with R18, ingest/model changes
with R19, and budget semantics with R20; do not hide those prerequisites inside
the extraction implementation.

TODO:

- [ ] Re-diagnose file-move, reorder, extraction, and genuine-fix failures against
  corrected G0. Treat the original plan's proposed causes as hypotheses, not an
  exhaustive list of allowed explanations.
- [ ] Require R18's canonicality checks before treating a strong/strong match as
  trusted evidence. Require R19's real caller/callee connectivity before pure
  extraction acceptance. A passing malformed/empty slice is not a substitute.
- [ ] Preserve the early G1 core/oracle/provenance workflow while implementing
  the remaining invariances. Do not make runner wiring wait for all T1–T4 cells.
- [ ] Preserve rename/formatting behavior while fixing each target cell. Validate
  both languages, including Java reorder/extract failures exposed by R03.
- [ ] For reordering, inspect slice membership, normalization, node labels,
  canonical ranks, and hashed edges together. Removing edges only at final hash
  time may leave order-dependent slice membership or canonical labels intact.
- [ ] Do not equate "no direct data-dependence edge" with safe independence.
  Preserve relevant control, alias, call, and side-effect relations; E17 shows
  that the current mapped PDG vocabulary also conflates edge origins.
- [ ] Normalize package moves without conflating semantically different external
  APIs that share a short method name. Include signature/type-sensitive and
  changed-target counterexamples.
- [ ] Implement the approved pure-extract subset with real interprocedural
  fixtures using R19's verified argument/return and effect relations. A decision
  memo or adding CALL edges alone does not supply a purity/alias analysis.
- [ ] Verify that source location is only a lookup input for the claimed strong
  identity. Exercise real path/line movement and label all weak fallbacks.
- [ ] Exercise correct sink association on multiple calls per line, nested calls,
  and moved/extracted code. If the current location seam cannot distinguish
  findings, extend the lookup contract or report ambiguity; do not silently
  assign another sink's identity.
- [ ] Test negative controls: changed sanitizer placement, dependent statement
  order, control conditions, aliasing, side effects, call targets, and distinct
  findings with otherwise similar slices.
- [ ] Run R04, R18's relabeling/negative controls, R20's budget checks, and the
  existing unit/determinism checks after each accepted change. Keep shared
  fingerprint edits serial through T4 and retain evidence for failed approaches.

Acceptance (`component_verified`): all declared Java/Python refactor cells pass
on valid strong comparisons; required fixes and semantic changes remain
distinguishable; no previously accepted pair regresses; budgets/fallbacks remain
honest. Unsupported cases are explicit limitations, not inferred green cells.
G2 separately verifies these results through the deployed workflow; R06 does
not wait for R08's final integration to establish its library/corpus milestone.

### R07 — Implement finding continuity and decision retention

Evidence: E06, E15, E19, E20; C08. Scope: finding storage/migrations, lifecycle
service, API/UI, and integration tests.

Current implementation contract: [occurrence/decision lifecycle](bhmea/OCCURRENCE-DECISION-CONTRACT.md)
under #378. Contract review does not establish runtime acceptance.

TODO:

- [ ] Separate immutable scan-occurrence identity from a finding's persistent
  cross-scan identity. Define how provisional fingerprints become final without
  breaking references to the occurrence.
- [ ] Define matching scope using repository/codebase and rule semantics as well
  as the structural identity. Do not use the commit or source location as the
  cross-refactor identity for a claimed strong match.
- [ ] Persist triage/suppression decisions, actor/reason metadata where supported,
  and attached reference metadata against the appropriate durable entity.
- [ ] Define ambiguity handling for multiple identical slices or several findings
  at the same sink. Never merge unrelated decisions solely because a hash matches.
- [ ] Seal comparison groups before filtering eligible identities. A strong pair
  plus a weak/failed potential competitor is not a unique match. Bind group
  coverage independently of fingerprint value, class and processing status.
- [ ] Preserve separate human verdict (including false-positive), suppression
  and machine lifecycle dimensions; revoking suppression must not erase verdict
  or reference history. Prevent both database and API-mediated LLM write access.
- [ ] Support trusted policy revocation and re-evaluate effective inherited
  decisions. Validate lineage, decision and active-policy revisions atomically
  so a concurrent human revocation cannot be overwritten by stale inheritance.
- [ ] Integrate the existing weak-suppression rule into the actual matching path.
  Pending, weak, ambiguous, and unresolved findings must not inherit a decision
  on an unsupported cross-refactor match.
- [ ] Gate inheritance on the artifact-specific classes resolved in R09, not
  the current worker's single run-level class. Test all four graph/slice class
  combinations. Under the current CORE-02 contract, either weak verdict blocks
  automatic suppression; missing/unknown class must fail closed as well.
- [ ] Do not enable automatic cross-refactor matching until the R09 class
  contract and R18/R20 correctness prerequisites are verified. A `strong` string
  from the currently defective canonicalizer is insufficient authorization to
  copy a user's suppression.
- [ ] Define transitions for unchanged, changed, resolved, reappearing, and
  analysis-failed findings. Distinguish successful absence after a fix from a
  scan failure or parser failure. Specify decision behavior when a bug returns.
- [ ] Bind links to a monotonic lifecycle generation and bind each inherited
  decision dimension to its own fresh human authorization generation. An old
  link created while open must not regain suppression after resolved/reappeared
  or uncertain states return to open. A fresh verdict/reference event must not
  reauthorize old suppression. Test old links, newly proposed links, repeated
  reopen cycles and replayed authorization events; enforce this in real storage,
  not only a pure snapshot validator.
- [ ] Define fingerprint-algorithm/rule-version compatibility. Historical
  decisions must not be silently migrated across incompatible identities.
- [ ] Test scan → triage/suppress → harmless refactor → rescan → same decision;
  changed vulnerability → no accidental inherited suppression; successful fix
  → resolved state; failure → not falsely resolved; restart → retained history.

Acceptance: `component_verified` covers durable storage, matching scope,
class-policy guards, and lifecycle transitions with persistence tests. At G2,
R07 and R08 jointly establish `integration_verified`: a user observes retained
triage history after real refactor/rescan. Neither card waits for the other's
whole-task DONE state. Hash equality alone does not satisfy either milestone.

### R08 — Complete the asynchronous demo flow

Evidence: E06–E08, E16. Scope: compose, deployment app/UI, the new worker loop,
storage handoff, and integration tests. Consume the fingerprint implementation
through the agreed seam.

TODO:

- [ ] Implement the selected D2 architecture. Option C remains a reduced demo;
  it does not satisfy the pasted-repository identity workflow.
- [ ] Make detection and fingerprinting consume the same immutable checkout and
  commit. Retain shared source until all required consumers finish; define
  cleanup and retry ownership.
- [ ] Normalize detection and Joern lookup paths through an explicit adapter,
  preserving the rule that location is not part of the structural hash.
- [ ] Introduce explicit processing state separate from fingerprint strength:
  pending/running/completed/failed, with completed fingerprints either strong or
  weak. A permanently weak result is not an eternally pending strong result.
- [ ] Persist immutable detection occurrences before per-finding identity work.
  The current worker computes a slice before appending its finding; an identity
  exception can discard already detected results. Separate occurrence records
  from identity attempts and completed, identity-bearing finding/provenance
  projections. A later timeout must leave the occurrence visible with its
  original origin and `identity_failed`, not disappear or become an oracle.
- [ ] Separate raw detection from whole-graph canonicalization too: the current
  worker computes ordering before detector dispatch. Persist raw detections
  before all identity operations; a wrapper around `run_detector` is insufficient.
  Test a global canonicalization failure as well as a later slice failure.
- [ ] Preserve the completed-record constraints of R09 through that staged
  boundary. Do not manufacture strong metadata or silently relax signed-final
  record guarantees to represent pending work. Test failure on a later finding
  after earlier results, retry/idempotency and restart recovery.
- [ ] Continue API/UI polling through fingerprint completion. Handle terminal
  parse failures, unresolved sinks, budget exhaustion, timeouts, and retries.
- [ ] Display each finding's actual stored fingerprint, class, origin, and relevant
  status. Provide an observable before/after comparison and retained decision
  history rather than changing only the footer text.
- [ ] Preserve separate graph-order and slice-identity strength/annotations from
  R09 through the worker, database, API, and UI. Never display a weak slice as
  strong because the whole graph had a strong ordering verdict.
- [ ] Make worker claims and writes retry-safe. A worker restart must not produce
  duplicate findings, lose triage links, or leave the UI waiting indefinitely.
- [ ] Fence source cleanup against new consumers using an atomic retiring state,
  not an unlocked no-active-lease check followed by deletion.
- [ ] Give the worker appropriate database/migration dependencies, pinned build
  arguments, health reporting, resource limits, and source-volume permissions.
- [ ] Test the full workflow on real engine output and actual refactored checkouts,
  including weak/failure outcomes. Preserve CWE and origin labeling.

Acceptance: `implementation_ready` exposes a real scan/worker path for early G1
checks. `component_verified` covers compose startup, same-source handoff,
processing states, metadata, polling, and retries without requiring all refactors
to pass first. G2 jointly verifies compose → scan → truthful final classes →
refactor/rescan → stable strong identity and retained decisions. Genuine
fix/removal and failure paths have their separately defined outcomes.

### R09 — Resolve artifact-specific classes, provenance, and environment identity

Evidence: E10, E12, E20; existing `CLAR-ORCH-03`, `CLAR-ORCH-12`, and applicable
oracle class-mapping records. Scope: decisions, schema/migrations, versioned
contracts, metadata producers, and compatibility tests.

TODO:

- [ ] Create a producer map for commit, snapshot digest, `S_version`,
  `env_digest`, `cpg_order_hash` and its own annotation/class, `slice_fingerprint`
  and its own class, witness, rule/spec ID, output hash, origin, and attestation
  links. Identify fields missing on each real execution path.
- [ ] Resolve `CLAR-ORCH-03` explicitly before R07's inheritance is enabled.
  `_findings_from_core` currently discards the slice verdict and `run_detector`
  stamps the graph verdict on every finding. Retain both verdicts with
  unambiguous ownership and names approved by the contract process.
- [ ] Do not "fix" this by blindly replacing the graph verdict with the slice
  verdict: that would detach the `cpg_order_hash` annotation from its producer.
  Specify schema/API/output/signature versioning and migration behavior for
  historical records whose single class cannot establish both properties.
- [ ] Test graph/slice `(strong, strong)`, `(strong, weak)`, `(weak, strong)`, and
  `(weak, weak)` through producers and serializers. Each artifact keeps its own
  annotation; either weak blocks automatic suppression under the current
  CORE-02 contract. Null/unknown states never default to strong.
- [ ] Resolve the existing oracle NOT-NULL conflict through the permitted
  architecture process. Choose legitimate producers or explicitly permitted
  nullable/not-applicable semantics. Do not invent a CPG hash or closed-world
  verdict for a computation that did not run.
- [ ] Map engine rules to required finding classes and CWE metadata explicitly.
  Unknown mappings must have defined behavior rather than guessed labels.
- [ ] Specify a versioned environment identity covering the actual detection,
  parsing, export, mapping, fingerprinting, and serialization components and
  relevant configuration, including R20's approved budget/output policy.
  Persist a manifest explaining the identity.
- [ ] Keep source commit identity separate from environment/spec identity. Ensure
  reruns reference the original pinned environment and accepted specification.
- [ ] Define treatment of code mounts/local development builds so the environment
  manifest identifies the code actually executed, not only an older image tag.
- [ ] Define identity rollover and retain original metadata on historical scans.
  Changing Joern, fingerprint code, rules, or canonicalization policy must not
  appear to be the same environment by accident.
- [ ] Verify nullable/conditional annotations across storage, API, output,
  attestation, and signed export for both partitions.

Acceptance: `design_ready` is the approved field/producer, class-ownership,
compatibility, and environment contract. `component_verified` adds implemented
producers/schema/serialization checks, including all four class combinations;
it does not wait for every consuming workflow to finish. G2 checks end-to-end
agreement across R07/R08/R10/R11/R12/R13. No consumer fabricates metadata or
confuses CPG canonicality, slice canonicality, and detection origin.

### R10 — Verify real-source core reproducibility

Evidence: E09, E21, E22. Scope: the actual core scan-runner integration, attestation
commands/artifacts, and tests. A CLI fixture runner is acceptable if it runs the
real production analysis components and its scope is documented.

TODO:

- [ ] Wire a thin real-source path early, once the required interfaces and
  repository component gates permit it. Record its first actual success or
  failure before waiting for the complete R06 invariance matrix. Do not relabel
  an early diagnostic run as full attestation acceptance.
- [ ] Provide a runnable path from source checkout through real Joern parsing,
  real core analysis/fingerprinting, and canonical core output. Use nonempty
  core findings; an empty core partition from Semgrep is not evidence.
- [ ] Include a real called-helper case after R19's connectivity verification;
  do not extrapolate an intraprocedural example to interprocedural core support.
- [ ] Resolve and implement R20's timing/output contract before declaring C09
  fulfilled. Two fast equal runs do not repair a branch that produces different
  results at the same declared inputs when scheduling changes.
- [ ] Pin source, accepted spec, policy, full environment identity, and
  `LLM_TRIAGE=off` as required by the contract.
- [ ] Run at least two independent analyses with fresh parse workspaces and no
  shared parsed-graph cache. Cover the declared Java/Python scope.
- [ ] Compare the canonical core output bytes at the contracted boundary.
  Do not strip arbitrary differences after the fact to manufacture equality.
  Specify whether repeated executions share logical scan/snapshot identifiers
  or how those fields belong outside the byte-comparison boundary. Randomized
  signatures and elapsed-time telemetry must be outside that boundary according
  to the approved contract, not removed ad hoc after a mismatch.
- [ ] Persist both outputs, digests, nonempty finding counts, manifests,
  commands, and any byte-difference artifact.
- [ ] Keep the existing synthetic falsifier as a separate negative control.
  Verify that intentionally perturbed core output fails and oracle differences
  do not contaminate the core verdict.
- [ ] Exercise weak/budget-boundary behavior under the supported conditions;
  do not assume the fast strong-only corpus validates all fallback behavior.
- [ ] Wire a nonzero failure into the claimed CI/release gate for relevant engine,
  parser, fingerprint, environment, and serializer changes.

Acceptance: `implementation_ready` provides the real-source runner for G1.
`component_verified` requires independent real-source reruns, including declared
Java/Python coverage, identical canonical bytes under R20's approved conditions,
and a failing negative control. It does not require every R06 refactor first.
G2 repeats affected checks on the merged final implementation. Evidence states
tested coverage and theorem assumptions without conflating them.

### R11 — Measure and expose oracle reproduction

Evidence: E10; `services/scan/attestor.py`:
`_oracle_reproduction_rate`, `_attest_oracle`. Scope: real oracle scan runners,
attestation storage, API/UI/export, and evidence.

TODO:

- [ ] Wire actual engine reruns on the same source/spec/environment into the
  oracle attestor. Start with Semgrep for G1; `FULL_SUBMISSION` also requires
  CodeQL measurements after R13's adapter component is verified. Track the two
  engine milestones separately. Do not substitute recorded JSON or hand-built
  findings for the real-engine evidence run.
- [ ] Use the existing reproduction metric and document it. The current metric
  is reproduced canonical result projections divided by baseline projections;
  do not silently substitute Jaccard similarity or hash stability.
- [ ] Record run count, baseline size, reproduced count, additions, losses,
  failures, engine versions, and comparison basis. Explain empty-baseline
  behavior; use nonempty baselines for positive demonstration evidence.
- [ ] Persist the measured rate and its scope. Make it accessible from the
  findings/scan UI, API, and relevant export. A scan-level rate may be referenced
  by a finding; do not mislabel it as per-finding repeated-trial confidence.
- [ ] Emit `rate-only`/empirical semantics even at 100% reproduction. Strong
  graph identity never changes the finding's oracle origin.
- [ ] Retain tests where dropped or changed oracle results affect the measurement
  without failing an unrelated core-byte comparison.

Acceptance: real oracle findings link to an actual repeat-run measurement with
its denominator and scope. The number is reproducible from published artifacts
and is never described as a determinism theorem. Establish `component_verified`
per engine using its real runner; final API/UI/export propagation is verified
jointly at G2. R13's adapter component must not depend on R11's completed rate
integration; the direction is adapter → measurement → shared integration gate.

### R12 — Connect persistent provenance to actual scan findings

Evidence: E11. Scope: signing provider/store adapters, retained artifacts,
scan integration, export/verifier commands or endpoints, and tests.

TODO:

- [ ] Build provenance from the producers agreed in R09 for the actual finding
  being displayed. Do not satisfy the demo by manually supplying plausible
  values to `provenance_demo.py`.
- [ ] Exercise one real scan → persisted signed record → export → fresh-process
  verification path at G1, before the complete refactor/lifecycle matrix is
  ready. Keep that narrow evidence separate from final release acceptance.
- [ ] Persist signed records and the relevant output/artifact references.
  Define signing time relative to asynchronous fingerprint finalization.
  An upgrade must not mutate an already signed record in place.
- [ ] Provide a persistent local software-key provider appropriate to the
  self-hosted architecture. Retain public-key versions needed to verify old
  records; explain the local software key honestly.
- [ ] Export the signed record, canonicalization/signature metadata, required
  artifacts, and public-key identification/material needed for independent
  verification. Document how the verifier identifies the trusted signing key;
  do not ship a private key inside an evidence export.
- [ ] Verify an exported finding in a fresh process after the scanning/signing
  process exits. Verification must not require rerunning analysis or retaining
  the original in-memory signer.
- [ ] Verify both record integrity and the promised output/artifact bindings.
  Enable artifact checking when claiming those bindings. State exactly which
  artifacts are independently hashed and which links are signed assertions.
- [ ] Test altered record fields, modified output bytes, missing artifacts,
  unavailable/wrong key material, restart, and historical-key lookup. Respect
  distinct verifier verdicts rather than reporting every failure as success.
- [ ] Keep RSASSA-PSS verification as verification, not re-sign-and-compare;
  signatures themselves are not required to reproduce byte-for-byte.
- [ ] Reuse the existing crypto implementation and provenance smoke tool as
  component checks while adding the missing end-to-end storage/export path.

Acceptance: actual demo findings export a persistent signed chain; a fresh
verifier checks it with retained public-key material; record and covered-output
tampering are detected without analysis reruns. Component checks use a runnable
scan producer and the R09 contract, not R07/R08's completed refactor acceptance.
G2 verifies signing/finalization and historical linkage in the merged workflow.

### R13 — Deliver the CodeQL adapter promised by the submission

Evidence: E13. Scope: adapter implementation, packaging/configuration, supported
query sets, tests, and documentation.

TODO:

- [ ] Define what the adapter accepts and runs: source analysis with a supported
  database-creation mode, or an explicitly documented external-result import.
  An import-only path must not be presented as built-in source scanning.
- [ ] Specify supported languages, query/rule versions, engine invocation, result
  schema, failures/timeouts, and configuration. Reuse an existing real adapter if
  subsequent code changes have already supplied it.
- [ ] Implement real invocation/import and map rule IDs, locations, CWE/class,
  origin, fingerprints, and provenance through the agreed contracts.
- [ ] Reconcile setup and database creation with C16 before enabling a mode that
  could invoke repository build scripts. Resolve any incompatibility explicitly.
- [ ] Package or document the engine prerequisites and permitted distribution
  path. Distinguish the tool's Apache-2.0 source from external engine terms;
  verify those terms before deciding how release artifacts include the engine.
- [ ] Run a real known-positive fixture through the adapter, observe the result
  at its declared entrypoint, and verify rule/location/CWE/origin and required
  metadata mappings. This establishes the adapter's component milestone without
  waiting for R11 rate measurement or R12's final provenance integration.
- [ ] Supply the runnable adapter and captured real output to R11/R12/R14.
  Verify final UI, identity, provenance, and measured-rate integration jointly
  at G2 after those consumers exist; do not add reverse completion dependencies.
- [ ] Demonstrate defined behavior when the engine is unavailable or fails.

Acceptance: a documented, reproducible CodeQL adapter works on real output;
`engine`/`origin` and its supported user path are truthful. A bundled binary,
protocol, fake adapter, or permanently raising default does not fulfill C14.
`component_verified` covers real invocation/import, mapping, and failures;
`integration_verified` is awarded by G2, not used to unblock R11's implementation.

### R14 — Measure actual incumbent identities

Evidence: C15; absence of a comparator workstream in the execution plan.
Scope: comparator runner, versioned fixtures/configuration, and evidence.

TODO:

- [ ] Enumerate each engine and exact identity field named in the public
  comparison. The submitted diagram names SpotBugs, CodeQL, and Semgrep
  `match_based_id`; verify each retained claim or explicitly narrow the wording.
- [ ] Pin engine versions/rules and capture original output for both sides of
  the same genuine refactor pair. Keep location changes separate from changes
  in the identity field actually used by the engine.
- [ ] Compare real emitted identifiers, not a home-grown location/text hash
  labeled as an incumbent result.
- [ ] Report cases where comparator identities remain stable as well as where
  they change. Do not choose a fictional result to match the submitted narrative.
- [ ] Publish a per-refactor table with Scanipy ID/class, comparator identity,
  engine/rule version, finding correspondence, and raw-output references.
- [ ] Make demo narration and slides exactly match the measured examples. A
  result from one engine/version/refactor is not a claim about all incumbents.

Acceptance: every comparative claim retained in the talk has directly
reproducible engine output. Unsupported broad comparison claims remain
unverified until corrected, even if Scanipy's own invariance is proven.

### R15 — Verify installation and offline stage readiness separately

Evidence: E07, E08; TD-1, DEMO-1, REL. Scope: trusted local demo fixtures,
deployment packaging, measured budgets, and rehearsal scripts.

TODO — S: attendee installation (`install_verified`):

- [ ] Verify the advertised one-command online installation from a clean
  checkout/machine with documented engine prerequisites, Postgres, single-tenant
  defaults, and no cloud account. Record actual commands and release identity.
- [ ] Keep this result separate from offline-stage readiness. Network access
  for downloading an open-source release is not itself a cloud-account
  dependency; "no cloud account" does not mean "no network on first install."

TODO — D: selected stage requirements (`stage_verified`):

- [ ] Separate the online attendee installation path from offline stage runtime.
  A clean machine cannot download source, base images, packages, or query packs
  with networking disabled. Document what is prepared in advance.
- [ ] Bundle or preseed versioned local repository fixtures containing the real
  before/after commits. Add an explicit supported local-fixture input path;
  current public-GitHub URL validation does not accept `file://` inputs.
- [ ] Restrict local-fixture access to the intended mounted fixture area. Do not
  broadly expose arbitrary host paths merely to support the stage demo.
- [ ] Preload all images, rules/query packs, fixtures, and required runtime
  dependencies. Prove runtime does not need registry or source-host access.
- [ ] Measure image sizes, peak memory, parse latency, fingerprint latency,
  full scan latency, and UI completion time on the intended demo machine.
  Separate cold and warm measurements.
- [ ] Record numerical limits chosen for D2/demo acceptance from those
  measurements. "Within budget" is not testable without a stated budget.
- [ ] Run all promised stage beats offline twice after resetting demo state
  through a documented, scoped procedure. Do not use a successful preloaded
  stage run as evidence that clean attendee installation works.
- [ ] Prepare a failure drill and recording from the exact accepted build and
  fixtures. A recording does not substitute for unimplemented functionality.

Acceptance: `install_verified` proves the submitted deployment path and feeds
the release gate. `stage_verified` proves preloaded offline operation within
explicit budgets and feeds the stage gate. Offline preparation remains selected
by the existing execution plan unless the owner changes it; it is not an extra
C12 promise. Neither milestone may be silently substituted for the other.

### R16 — Preserve static-analysis-only execution

Evidence: C16; worker subprocess contracts and the current deployment posture.
Scope: new worker/adapter subprocess paths and deployment integration.

Pinned Java source review identified additional concrete hazards; corrective
issue [#386](https://github.com/scanipy/scanipy/issues/386) covers a restricted
invocation/environment profile. Its source audit is recorded in the
[foundation evidence note](evidence/2026-09-25-foundation-merges/README.md#parser-safety-audit).
It is not a parser-exploit or complete runtime no-execution proof.

TODO:

- [ ] Review every newly introduced execution path, including frontend plugins,
  query/database setup, repository hooks, build detection, and helper scripts.
  State which trusted analysis tools run and confirm scanned source is not
  imported, executed, or used as a build/setup script.
- [ ] Preserve the existing sanctioned-tool/argument handling and trusted export
  script model. Resolve actual adapter limitations rather than quietly enabling
  repository-controlled execution.
- [ ] For the pinned Java frontend, enforce the exact trusted suffix
  `--frontend-args --delombok-mode no-delombok` using a value-aware grammar;
  do not admit arbitrary frontend forwarding. Force the exact dependency-fetch
  disable value `JAVASRC_FETCH_DEPENDENCIES=no-fetch`. Values such as `false`
  and `0` enable fetching upstream and are not safe aliases.
- [ ] Validate a closed, versioned Java subprocess environment for both parse
  and export: pinned tool paths, private writable directories, approved locale
  and explicit fetch disable. Reject unknown JVM/native-loader/build overrides
  before binary resolution/spawn. Verify the adapter and observer report actual
  effective options; do not expose secrets or mutate the caller's environment.
- [ ] Verify expected-versus-processed file coverage, including `test/` defaults,
  parser omissions and unavailable generated-member semantics with Delombok
  disabled. Successful exit, raw CALL edges and network isolation do not prove
  full coverage, safe static-only behavior, or absence of findings.
- [ ] Verify timeout/cancellation contains all descendant processes. Repeat
  sentinel and process-evidence checks on the final merged container/Compose
  path; never run an unsafe target-build positive control to validate a sentinel.
- [ ] Add a controlled fixture with repository execution hooks/sentinels and
  confirm the declared scan path never triggers them. Run only the intended
  scanner against it; do not execute the sentinel as part of setup.
- [ ] Carry appropriate existing container restrictions into the worker service:
  non-root operation, controlled writable work areas, read-only source handoff,
  resource limits, and no unnecessary privileges.
- [ ] Verify this property on the final compose/adapter configuration, not only
  by reviewing the old two-service deployment.

Acceptance: the promised analysis paths do not execute scanned repository code.
Any incompatible engine mode is disabled or treated as a disclosed scope
conflict, not silently included under C16. `design_ready` reviews permitted tool
invocations and modes before enabling them; `component_verified` tests the actual
enabled implementations; G2 repeats the relevant checks on the merged build.
The early design milestone never depends on a completed adapter implementation.

### R17 — Complete evidence, public material, and release acceptance

Evidence: original T0.5, L0, DOC-1–4, DEMO-1, REL, FALL. Scope: evidence artifacts,
release manifests, relevant documentation/slides/video disposition, and release
checks. Publication follows the existing owner authorization requirements.

TODO:

- [ ] Create the evidence convention and recover the historical run verbatim if
  available. If unavailable, label the old table as reported/unreproduced and
  superseded by corrected G0. Do not recreate missing raw evidence by hand.
- [ ] Keep raw tool output immutable. Keep human-written summaries, diagnoses,
  decision memos, and reproduction notes as clearly separate documents; the
  plan's "all evidence files are tool outputs" wording must not obscure this
  necessary distinction.
- [ ] For every run, record code revision, dirty-worktree/patch identity if any,
  source commit, corpus/fixture digest, spec/policy/environment identities,
  commands, exit codes, cache mode, actual counts, and known limitations.
- [ ] Replace L0's fingerprint-only lock with acceptance of C01–C18: corrected
  corpus, real application flow, decision continuity, both attestation paths,
  provenance export/verification, engine support, and comparator evidence.
  Include R18's canonicality, R19's call connectivity, R09's independent class
  annotations, and R20's approved determinism/budget contract.
- [ ] Own the shared G2 integration gate and separate G3 release/stage gates.
  Consume verified component milestones, not an impossible prerequisite that
  every R-task has already completed its own shared integration acceptance.
- [ ] Create a machine-readable claim status report. A deferred feature remains
  unfulfilled in `FULL_SUBMISSION`, even after its documentation is updated.
- [ ] Update the supporting material/PDF, README, deployment docs, slides, and
  other public abstract/form text that repeats affected claims. Preserve the
  historical submitted version and explain any owner-approved scope change.
- [ ] Audit the submitted video against the final capabilities before deciding
  whether to retain, annotate, or replace it. This review did not inspect the
  video's actual frames or behavior.
- [ ] Assign and complete OSS-01 readiness work if still outstanding, including
  the existing secret/history scrub and license/public-preparation checks.
  Confirm OSS-02/D6 status through the authorized process before public flip.
- [ ] Verify clean-machine installation and evidence reproduction against the
  actual release tag/images, including image verification and any required
  adapter prerequisites. Do not rely only on a developer-mounted worktree.
- [ ] If release code, rules, schema, parser, or environment changes after L0,
  rerun affected gates and publish evidence for the new release identity.
- [ ] Rehearse the accepted demo and record the fallback from that same release.

Acceptance: every fulfilled claim links to reproducible evidence for the
released artifact; public wording matches that evidence; historical reports are
not presented as new measurements; publication and attendee access are checked
when authorized. Report submission fulfillment, release readiness, and stage
readiness separately. A ready slide deck cannot close a correctness blocker;
an omitted optional cache cannot create a false product shortfall.

### R18 — Repair canonicalization before trusting strong identity

Evidence: E19; section 8. Scope: `analysis/ordering.py`, fingerprint normalization
and hashing consumers, canonicalization contracts, and regression/property tests.
This is a correctness prerequisite, not another optional refactor improvement.

TODO:

- [ ] Reproduce the six-permutation counterexample in section 8 on the recorded
  baseline and preserve it as a regression test. With ample canonicalization
  budget, all six must produce one strong slice fingerprint after correction.
- [ ] Audit individualisation/refinement against the accepted canonical-form
  contract. The current lowest-ID choice and hashing of `int(target)` are not
  justified by repeatability on one numbering. Resolve any missing algorithm
  specification through the existing architecture process before implementation.
- [ ] Check arbitrary node renumberings, insertion/edge enumeration order, and
  symmetric graph families. Verify that an equivariant order/encoding is used
  throughout normalization and content hashing, not only in the last digest.
- [ ] Audit `_digest_order`, which currently hashes raw node IDs, against the
  precise meaning of `cpg_order_hash` and its conditional-canonicality annotation.
  Distinguish a same-source enumeration digest from a canonical graph encoding;
  resolve any contract mismatch without silently changing public semantics.
- [ ] Add distinct non-isomorphic controls with changed node labels, edge kinds,
  direction, and dependency structure. Isomorphic positive tests alone could
  be passed by an over-collapsing representation that merges different bugs.
- [ ] Check auxiliary canonicalization calls in normalization, including local
  alpha-renaming, for raw-ID dependence and discarded class/budget outcomes.
  Coordinate their budget handling with R20 rather than hiding a weak internal
  result beneath an unjustified final strong label.
- [ ] Preserve conservative outcomes when canonicalization cannot be established
  under the approved budget. Returning weak for everything avoids a false label
  but does not fulfill the advertised strong-identity behavior.
- [ ] Review the implemented algorithm and its proof obligations separately from
  the finite tests. R09 must propagate the actual artifact-specific verdict;
  R07 must not enable unsupported cross-refactor inheritance.

Acceptance (`component_verified`): the recorded counterexample no longer fails;
supported relabelings preserve a strong canonical identity, selected distinct
negative controls remain distinct, and budget/fallback behavior is correctly
classified. The accepted algorithm/encoding contract explains these properties;
a finite passing suite is not labeled a universal theorem. This milestone does
not depend on G0 or the complete R06 refactor matrix and should be addressed early.

### R19 — Establish real interprocedural graph connectivity

Evidence: E17, E21. Scope: pinned Joern export, mapper/model, solver supergraph,
slice construction, and real-source connectivity tests. Consult the existing
`CLAR-SNAP-05` export contract and related records before proposing a follow-up.

TODO:

- [ ] Trace a real Java and Python called-helper example from raw export through
  mapped CPG, supergraph, solver witness, and backward slice. Record the missing
  relations at each boundary; do not substitute a hand-constructed CPG for this
  integration evidence.
- [ ] Resolve and implement the model/export contract needed for actual
  caller-to-callee edges and argument/parameter, return/result, and relevant
  effect relations. The current exporter/mapper omit CALL while the solver
  expects CALL-to-METHOD adjacency; a resolved call-name string does not fill it.
- [ ] Preserve edge meaning and orientation across the exporter/mapper/solver.
  Adding a CALL edge without the data/effect connections required by R02 is not
  sufficient evidence that extraction preserves the implicated slice.
- [ ] Define unresolved/dynamic-call handling conservatively. Do not fabricate a
  callee or mark incomplete coverage as closed-world. Preserve unknown-edge and
  malformed-export fail-closed behavior for unsupported input.
- [ ] Demonstrate source → called helper → returned value → sink connectivity,
  plus a helper containing the sink where supported. Inspect real nonempty
  witnesses and slice membership, not only finding counts.
- [ ] Add changed-callee, argument/return, alias/effect, and ambiguous-target
  controls. Prove a security-relevant callee change is not invisible to the
  analysis/fingerprint path used by the claimed extraction case.
- [ ] Version changed export/model semantics and environment identity with R09.
  Invalidate any selected caches using R05's rules; cache implementation is not
  a prerequisite for delivering the fresh-parse path.
- [ ] Honor C16 and repository staging rules, including CMP-CP-06 before
  Algorithm 2 benchmarking. Label initial graph-connectivity diagnostics as
  diagnostics, not a recall or full-language-support campaign.

Acceptance (`component_verified`): the declared Java/Python helper cases have
real caller/callee and data/effect connectivity through all relevant consumers;
nonempty witnesses/slices and negative controls demonstrate it. R06 may then
use that foundation for pure-extract acceptance. Generic parse success or
intraprocedural-only results do not close this task.

### R20 — Make budget behavior consistent with reproducibility claims

Evidence: E22; section 8; CORE-02/CORE-03 purity contracts and existing B/T
decisions. Scope: architecture decision, budget implementation, output boundary,
environment/policy identity, and deterministic-fallback tests.

TODO:

- [ ] Reproduce the controlled-clock diagnostic. Record that identical graph,
  finding, and default B/T produce different class/hash when elapsed time changes.
  This is a concrete contradiction to unconditional same-input purity at that
  boundary, not a measured production timeout frequency.
- [ ] Audit all output-affecting deadline checks, early-return paths, and nested
  canonicalization calls. Include normalization calls using their own default
  B/T and any discarded weak/budget result. Distinguish telemetry from values
  that alter graph traversal, identity, classification, or serialized findings.
- [ ] Resolve the determinism/budget contract before R10 acceptance. Options for
  architectural consideration include deterministic work-bounded results with
  wall-clock limits causing an explicit run failure, or an explicitly qualified
  guarantee with precisely defined timeout eligibility/failure semantics. This
  backlog does not select a new policy or override the existing B/T decisions.
- [ ] State all theorem assumptions and the treatment of weak results. If the
  approved outcome narrows the submission's guarantee, record the original claim
  as unfulfilled/qualified and use the owner scope process. Do not silently add
  "only on a fast unloaded machine" to make a failing guarantee appear satisfied.
- [ ] Implement the approved policy consistently across graph and slice
  canonicalization. A numeric T value in `env_digest` does not fix the actual
  elapsed-time trace. Increasing T only for tests is not a production fix.
- [ ] Define the exact canonical-output boundary with R09/R10: scan/snapshot
  identifiers, timestamps, elapsed telemetry, budget status, and signatures
  must have explicit inclusion/exclusion and rerun semantics. Do not remove
  inconvenient bytes after comparing outputs.
- [ ] Test controlled fast/slow clocks, deterministic work-limit exhaustion,
  weak-path repeatability, nested calls, and failed-run handling. Compare real
  independent runs under supported conditions as additional evidence; finite
  stress tests do not establish a universal theorem.
- [ ] Persist/version the approved policy and relevant environment/configuration
  identities. Ensure a timeout/failure cannot falsely resolve a finding or pass
  an attestation through R07/R10/R11.

Acceptance: `design_ready` is a coherent approved budget/output/guarantee
contract. `component_verified` requires its implementation and passing positive,
negative, and boundary checks, coordinated with R18 and R09. Equivalent declared
inputs cannot silently produce conflicting successful results inside the claimed
byte-identical boundary. Any approved exclusions or scope reduction remain
explicit; the old controlled-clock contradiction cannot be dismissed by two
successful fast reruns.

## 6. Corrected execution order and integration gates

Use this dependency order when revising the original schedule. Tasks that touch
shared files must still be serialized even when their concepts are independent.

1. **Resolve contracts early:** establish R01's milestone plan; prepare R02's
   pure-extract contract, R09's class/provenance contract, R18's canonicalization
   review, and R20's budget/output decision. Start R16's permitted-tool review.
2. **Build independent foundations:** verify R03's corpus and R04's checker;
   package R05's required fresh-run command; then capture G0 as a separate
   baseline artifact. Address R18/R19/R20 foundations without waiting for G0 to
   become green on the advertised refactors. Optional caching cannot block this.
3. **Run a thin real-source path early:** wire R08/R10/R11/R12 as soon as their
   design/component prerequisites permit it. Record initial failures promptly;
   do not wait for all R06 invariances. G1 verifies at least one real, nonempty
   core path and Semgrep path, correct class/origin metadata, core-byte and
   oracle-rate checks under the agreed contract, and persisted provenance
   exported and verified in a fresh process. This is limited-scope integration,
   not full-submission acceptance. CodeQL joins after its adapter is ready.
4. **Finish scoped component work:** R06 proceeds serially through T4 while
   R07/R08 complete lifecycle/UI behavior, R10/R11 expand real-run evidence,
   R12 completes signing/failure cases, R13 supplies CodeQL, and R14 measures
   incumbents. Respect repository dependencies and ownership throughout.
5. **Verify merged claims at G2:** R17 coordinates the single integrated
   acceptance run after the relevant component milestones. Repeat affected
   R10/R11/R12/R14/R16 checks on that merged artifact, including CodeQL. G2 is
   the strengthened technical claim lock; pending public-access/release actions
   stay pending rather than being marked fulfilled prematurely.
6. **Validate release and stage separately:** G3_RELEASE verifies installation,
   evidence access, license/public-source state, and authorized release actions.
   G3_STAGE verifies offline operation, budgets, and fallback on the same
   accepted artifact. Revalidate changes made after G2.

The shared gate dependencies below are proposed manifest content, not a tool or
configuration file already present in the repository. Milestone evidence must
declare languages/engines/cases: G1 may be deliberately narrow; G2 must cover the
full declared submission scope. A partial milestone never satisfies a broader
gate. R01 must expand card-internal milestones into a complete acyclic DAG.

```yaml
integration_gates:
  G0:
    owner_role: Corpus/QA
    requires: [R03.component_verified, R04.component_verified, R05.commands_verified]
    purpose: complete_honest_baseline_not_feature_acceptance
  G1:
    owner_role: Integration/QA
    requires:
      - R08.implementation_ready
      - R09.component_verified
      - R10.implementation_ready
      - R11.implementation_ready
      - R12.implementation_ready
      - R16.design_ready
      - R18.component_verified
      - R19.component_verified
      - R20.component_verified
    scope: declared_nonempty_real_core_and_semgrep_cases
  G2:
    owner_task: R17
    requires:
      - G0
      - G1
      - R06.component_verified
      - R07.component_verified
      - R08.component_verified
      - R09.component_verified
      - R10.component_verified
      - R11.component_verified
      - R12.component_verified
      - R13.component_verified
      - R14.component_verified
      - R16.component_verified
      - R18.component_verified
      - R19.component_verified
      - R20.component_verified
    scope: all_declared_submission_languages_engines_and_required_cases
  G3_RELEASE:
    owner_task: R17
    requires: [G2, R15.install_verified]
    additional_checks: [authorized_release, public_source_license_and_evidence_access]
  G3_STAGE:
    owner_task: R17
    requires: [G2, R15.stage_verified]
    additional_checks: [same_accepted_artifact_for_live_demo_and_fallback]
```

Anti-cycle rules for the expanded plan:

- R03's component milestone supplies fixtures to G0; it never requires G0.
- R04 verifies checker behavior using controlled reports before G0; running the
  checker on G0 is gate execution, not a prerequisite for writing that baseline.
- G0 needs only R05.commands_verified. Optional R05.cache_verified and debug
  utility work cannot delay the fresh-run baseline or fingerprint repairs.
- R09 supplies contracts/producers before consumers; all-consumer verification
  belongs to G2, not a prerequisite for R09.design_ready/component_verified.
- R13.component_verified → R11's CodeQL measurement → G2. R13's component
  milestone does not require that measurement, final UI, or final signed export.
- R07/R08 and R11/R12 share final integration at G2; no participant requires
  another participant's integration_verified milestone to implement itself.
- R16.design_ready precedes enabling engine/worker modes. R16's actual-path
  verification follows implementation and feeds G2; the early review does not
  depend on the final adapter verification.
- R18's canonicality milestone can be checked under controlled sufficient work
  budgets without awaiting R06. R20 then verifies the complete timing/fallback
  contract and reruns those controls. R19 verifies graph connectivity before
  R06 requires extraction invariance; it does not require that invariance first.
- R17 owns the shared gates and does not require its participants to be DONE
  before it runs the integration checks that make them DONE.

G2 and the applicable G3 gates must establish all of the following, without
mixing implementation evidence, public release checks, and stage-only checks:

- [ ] Canonicalization passes R18's isomorphic-graph and distinct-graph controls;
  no unsupported strong label authorizes cross-refactor decision inheritance.
- [ ] Graph-order and slice-fingerprint classes remain independently correct
  across worker, persistence, API/UI, attestation, and signed export.
- [ ] Real interprocedural caller/callee/data-flow connectivity supports the
  extraction and core cases actually claimed.
- [ ] Valid, versioned transformation fixtures and correct language-specific
  strong-comparison results for every advertised invariant.
- [ ] Required semantic-change controls pass with no hidden per-pair regression.
- [ ] Real scan/refactor/rescan retains intended identity and triage decisions.
- [ ] Missing findings, scan failures, ambiguity, and weak fingerprints have
  distinct, tested behavior and separately typed evidence; missing hashes never
  masquerade as flips or successful fixes.
- [ ] The implemented time-budget/output contract is coherent; real-source core
  reruns are byte-identical under its explicit assumptions and eligibility rules.
- [ ] Real oracle reruns produce a published empirical measurement.
- [ ] Actual findings export persistent provenance verifiable in a fresh process.
- [ ] Semgrep and the declared CodeQL adapter path work as documented.
- [ ] Retained incumbent comparisons use real, pinned engine output.
- [ ] One-command deployment, CWE/origin labeling, no-cloud operation, and the
  no-execution contract hold on the release artifact.
- [ ] Release installation is independently reproducible; selected offline
  stage requirements pass separately with prepared resources/measured budgets.
- [ ] Public source, license, documentation, video disposition, and evidence
  accessibility match the authorized release state.

## 7. Required task reports and claim status

Each implementation task must return this information. The orchestrator or
reviewer verifies the evidence rather than accepting a DONE string alone.

```yaml
task_id: Rxx
status: TODO  # TODO | IN_PROGRESS | BLOCKED | DONE
claims_addressed: []
requirement_kinds: []
# submission_requirement | correctness_prerequisite |
# release_stage_requirement | optional_efficiency
original_plan_cards: []
implementation_revision: null
files_changed: []
milestones:
  design_ready: {status: TODO, scope: [], evidence_paths: []}
  implementation_ready: {status: TODO, scope: [], evidence_paths: []}
  component_verified: {status: TODO, scope: [], evidence_paths: []}
  integration_verified: {status: TODO, scope: [], gate: null, evidence_paths: []}
# Design-only cards may mark inapplicable milestones with a reason.
# R05 reports commands_verified and optional cache_verified separately.
# R15 reports install_verified and stage_verified separately.
dependencies:
  satisfied: []  # Milestone IDs, not an unqualified task DONE string.
  pending: []
optional_items:
  - item: "Optional optimization, if any"
    selection: UNDECIDED  # SELECTED | NOT_SELECTED | UNDECIDED
    reason: null
decisions:
  reused: []
  resolved: []
  pending: []
acceptance:
  - criterion: "Concrete expected behavior"
    evidence_type: null  # structural_comparison | finding_removal | analysis_failure, where relevant
    scope: []  # Required languages, engines, cases, or artifact paths.
    result: NOT_RUN  # PASS | FAIL | NOT_RUN | NOT_APPLICABLE_WITH_REASON
    evidence_paths: []
commands:
  - command: "Exact reproducible command"
    exit_code: null
limitations: []
blocking_reason: null
next_action: null
```

For each claim, record both original-submission fulfillment and current public
scope. This prevents a reduced claim set from erasing the original shortfall.

```yaml
claim_id: Cxx
original_submission_status: UNVERIFIED
# UNVERIFIED | PARTIAL | FULFILLED | UNFULFILLED
included_in_current_public_scope: true
supported_languages: []
supported_conditions: []
implementation_paths: []
evidence_paths: []
correctness_prerequisites: []
owner_scope_decision: null
known_limitations: []
```

Report shared gate and readiness status independently of the task list:

```yaml
target_mode: FULL_SUBMISSION  # FULL_SUBMISSION | REDUCED_DEMO
submission_fulfillment: UNVERIFIED
release_readiness: NOT_VERIFIED
stage_readiness: NOT_VERIFIED
gates:
  G0: {status: NOT_RUN, artifact_revision: null, scope: [], evidence_paths: []}
  G1: {status: NOT_RUN, artifact_revision: null, scope: [], evidence_paths: []}
  G2: {status: NOT_RUN, artifact_revision: null, scope: [], evidence_paths: []}
  G3_RELEASE: {status: NOT_RUN, artifact_revision: null, scope: [], evidence_paths: []}
  G3_STAGE: {status: NOT_RUN, artifact_revision: null, scope: [], evidence_paths: []}
# Gate status: NOT_RUN | PASS | FAIL | BLOCKED.
# G0 PASS means the baseline record is valid, not that its feature results pass.
# G1 PASS is limited to its declared cases and never implies C01–C18 fulfillment.
unfulfilled_claims: []
pending_owner_decisions: []
```

Manifest/checker filenames and commands must be documented when they are
actually created. Do not fabricate their existence or mark these templates as
passing evidence. Read the current handoff ledger for execution status. No
submitted claim has yet been newly verified through its full acceptance workflow.

## 8. Reproducible review diagnostics — not acceptance evidence

These controlled library checks ran against the code revision in the header,
including a repeat while preparing revision 2. They do not scan a target
repository, invoke Joern/Docker/an engine, or create test/result files. The
excerpts below record review observations, not an archived full-corpus campaign.
An implementing LLM must create regression tests and retain fresh evidence under
R18/R20.

Run from the repository root with Python 3. The graph has two identically labeled
source CALL nodes pointing by CFG edges to one distinct sink CALL. Its labels
and directed topology do not change when insertion order changes; the finding's
witness always points at that same sink role.

```bash
python3 -B - <<'PY'
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import patch

import analysis.ordering as ordering
from analysis.fingerprint import compute_slice_fingerprint


def make_graph(insertion):
    graph = ordering.CPG()
    ids = {}
    for name in insertion:
        ids[name] = graph.add_node(
            'CALL',
            resolved_fqn='example.sink' if name == 'sink' else 'example.source',
            enclosing_decl_fqn='example.handler',
        )
    graph.add_edge(ids['left'], ids['sink'], 'CFG')
    graph.add_edge(ids['right'], ids['sink'], 'CFG')
    return graph, SimpleNamespace(witness=(ids['sink'],))


strong_hashes = set()
for insertion in permutations(('left', 'right', 'sink')):
    graph, finding = make_graph(insertion)
    result = compute_slice_fingerprint(finding, graph, T=ordering.Duration(10.0))
    value = result.slice_fingerprint.hex()
    print('permutation:', insertion, result.fingerprint_class, value)
    if result.fingerprint_class == 'strong':
        strong_hashes.add(value)
print('distinct_strong_fingerprints:', len(strong_hashes))


class ControlledClock:
    def __init__(self, step):
        self.value = 0.0
        self.step = step

    def monotonic(self):
        current = self.value
        self.value += self.step
        return current


graph, finding = make_graph(('left', 'right', 'sink'))
for label, step in [('within deadline', 0.000001), ('deadline elapsed', 1.0)]:
    with patch.object(ordering, 'time', ControlledClock(step)):
        result = compute_slice_fingerprint(finding, graph)
    print('clock:', label, result.fingerprint_class, result.slice_fingerprint.hex())
PY
```

### 8.1 Observed relabeling result (E19 / R18)

All six results were labeled `strong`. The four permutations where the sink was
not inserted first produced hash A; the two where it was first produced hash B:

```text
A = f314ca14270fa89efa24c79d301849f7ca8159673c733e8be5f0df0c9ae52e3b
B = 6099ab99ff39fa353de3a460f6c7ce3ada84321d8ca86e3be997d8943f6d3452
distinct_strong_fingerprints: 2
```

This is a counterexample to the claimed canonical slice identity at the library
boundary. It does not measure how often real Joern exports trigger the defect.
The generous `T=10.0` here isolates the relabeling issue from ordinary deadline
pressure; the implementation still needs correctness at its approved defaults.

### 8.2 Observed controlled-clock result (E22 / R20)

For the same graph and default B/T, replacing only `analysis.ordering.time` with
the scoped clock stub produced:

```text
clock: within deadline strong f314ca14270fa89efa24c79d301849f7ca8159673c733e8be5f0df0c9ae52e3b
clock: deadline elapsed weak e6d70b22f27dbcf7748b8d90c5ad69da07a45020f3b99af5157e480986d8444c
```

This demonstrates that elapsed time is an output-affecting input not captured
by the graph and numeric B/T alone. It is not a production-load benchmark or a
claim that the tiny graph normally times out. The patch is process-local and
restored immediately; no global clock or repository code is changed.

The command intentionally prints observations rather than asserting that the
old defects must persist. After a fix, R18/R20 tests must assert the approved
correct behavior; new hashes or failure semantics must be assessed against the
versioned contract, not copied from these baseline outputs.

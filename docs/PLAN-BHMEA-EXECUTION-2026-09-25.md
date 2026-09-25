# Black Hat MEA — active execution handoff

| Field | Value |
|---|---|
| Updated | 2026-09-25 |
| Target | FULL_SUBMISSION; all C01–C18 claims and applicable R01–R20 acceptance items |
| Tracking | [Umbrella issue #362](https://github.com/scanipy/scanipy/issues/362) |
| Presentation | December 2 or 3, 2026; exact date unconfirmed |
| Demo | Local Docker on this development machine, confirmed by owner; capacity recorded, readiness unverified |
| Technical acceptance | NOT VERIFIED; no shared gate has passed |
| Release / stage readiness | NOT VERIFIED / NOT VERIFIED |

## 1. Instructions to the executing LLM

Read [the current review](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md),
[the original submission](blackhat-mea-supporting-material.md), and
[the execution ledger](bhmea/execution-state.json). The review contains all
task-level TODOs and acceptance criteria; this handoff updates authority,
decisions, dependencies, ownership, and execution state without deleting them.

[DECISION-BHMEA-01](DECISION-BHMEA-01-current-execution-authority-2026-09-25.md)
is the standalone record of the actual owner directions, specific current
engineering extensions and preserved compatibility/review obligations.

Precedence: latest user direction → submitted full scope plus the review/current
handoff → compatible component contracts and tests → historical plans. The owner
explicitly said `PLAN.md`, `SDD.md`, and `WBS.md` are old and may have obsolete
architecture. Preserve them, but do not use obsolete architecture/CLAR approvals
to block the current target. Do not falsely resolve historical records. Necessary
schema/version/migration decisions still need explicit engineering records and
tests; old data and signatures must remain verifiable.

Acceptance/RSVP is confirmed. There is no October 23 lock, October 11 automatic
architecture downgrade, or authorization to reduce scope. The old plan's date
and fallback instructions are historical only. Full technical fulfillment,
public release, and offline stage readiness are different outcomes.

Corrective issues/PRs are authorized. Preserve the review/test merge gates,
including `claude-review` APPROVE. Do not publish releases/images, change
visibility, spend money, or send external messages without separate authority.
The repository was already public when checked on 2026-09-25. Preparing release
artifacts and checking public access are not publication approval.

Never execute scanned source, target build hooks/tests, or commands supplied by
scanned repositories. Keep the existing development app/DB intact; use isolated projects,
containers, temporary directories, and test databases for diagnostics. The owner
has confirmed the current host as the presentation machine. Use the
[measured stage profile and remaining checks](evidence/2026-09-25-stage-machine/README.md);
do not infer dedicated capacity, safe parallel native runs or offline readiness.

## 2. Decisions and remaining design work

These are root-agent engineering decisions within the authorized task, not
claims that the owner explicitly selected an architectural option.

| Decision | Current direction | Remaining action before acceptance |
|---|---|---|
| D1 — acceptance | Confirmed by owner | No RSVP action; retain confirmation in this record |
| D2 — deployment | Separate Joern analysis worker in Compose, immutable shared source, explicit asynchronous identity status | Implement API/UI/worker/storage seam; measure resource/latency on actual stage machine; no identity-lab substitute |
| D3 — extraction | Genuine moved computation, called helper, actual/formal and return/result substitution under a verifiable purity certificate | Finalize exact operation/type/effect registry and graph/flow semantics; prove meaningful Java and Python cases; unknowns stay uncertified |
| D4 — video | Existing video is historical submitted material | Audit against accepted implementation; ask owner about any replacement/publication action |
| D5 — claim acceptance | Evidence-gated G2 for all submitted claims; no October freeze | Record failures honestly; owner approval needed for any scope reduction |
| D6 — public repository | Already public when checked | Verify public source/license/evidence and clean install; do not perform a redundant visibility flip |
| D-CANON / D-BUDGET | Content-binding v2 encoding; exact direction-aware WL refinement plus complete bounded individualisation; deterministic work-budget fallback; time expiry is a failed analysis | Preserve merged #369 foundation; extend/verify remaining R18/R20, prove any new symmetry pruning, run real semantic graphs, thread versions/status to every new consumer |
| D-CLASS | Independent graph/slice hash, class, annotation, and identity version; either weak/unknown blocks automatic inheritance | Preserve/extend merged #371/#369 four-combination, schema and history guarantees for new producers and semantic versions; never copy one legacy class into both fields |
| D-PRODUCERS | Real producer for every provenance field; CPG-less oracle metadata nullable with explicit reason/status, never fabricated | Verify actual snapshot/spec/output bindings and CPG-backed full-demo path; retain detection separately from identity failure |
| D-OCCURRENCE | Persist immutable detection observations before identity attempts; completed identity-bearing records are a separate projection | R08 must retain core detections through later slice failures without changing origin, inventing metadata or weakening final-record constraints; R07 durable decisions reference stable occurrence/entity IDs |
| D-ENV | Distinct actual snapshot/detector image identities plus canonical full-analysis environment manifest | Finalize manifest/addressing contract; retain per-image boot guards; mounted code must be content-identified |

Detailed canonical direction is in
[the canonical/budget contract](PROPOSAL-BHMEA-CANONICAL-BUDGET-2026-09-25.md).
The initial model encodes the existing semantic node labels and directed typed
multiedges. New graph roles must be versioned and included in identity; a v1
graph is not silently upgraded by supplying empty metadata. The algorithm is
direction-aware 1-WL plus exact search, not an unsupported claim of 2-WL.

The time limit is a cooperative watchdog covering the complete invocation,
including normalization. Timeout cannot return a different successful identity.
Deterministic B exhaustion can return weak; incomplete search cannot return
strong. A source-aware weak slice requires the real captured source-tree
digest. Source-less old callers remain explicitly legacy, not secretly v2.

[The graph/provenance design](PROPOSAL-BHMEA-GRAPH-PROVENANCE-2026-09-25.md)
defines D-CLASS/D-PRODUCERS/D-ENV direction and the required D-GRAPH/D-FLOW/
D-EXTRACT behavior. Its graph vocabulary is not yet a verified Joern API map.
Finalize the actual exporter accessors, finite facts/transfer rules, matched
returns, and nontrivial purity registry early. CALL export alone is not R19.
Do not replace full positive extraction requirements with unsupported/trivial
cases to obtain green tests.

R09's merged scoped schema PR protects completed identity-bearing core records; it does
not implement asynchronous observation retention. The current worker can lose
solver results when a later slice computation raises. D-OCCURRENCE requires a
persisted pre-identity stage with visible failure/retry state before this is
accepted as the live demo pipeline. A parser failure before detection is a
different event from an identity failure after detection; neither establishes
successful finding absence.

The merged [occurrence/decision contract](bhmea/OCCURRENCE-DECISION-CONTRACT.md)
requires closed comparison cohorts, current policy authority, explicit lineage
and append-only human decisions. Its pure matcher is still review-stage work,
with an empty production policy registry. A lifecycle-generation correction
prevents old links or unchanged suppression from reviving after reopening;
fresh authorization is per dimension, not implied by a new verdict/reference.
Neither a design nor a pure module supplies the required PostgreSQL/API/UI path.

Before further Java source probes, complete #386's restricted parse/export
invocation and environment profile. The pinned frontend can enable dependency
build execution through an environment override, and automatic Delombok can
lead to partial source coverage. See the [source audit and remaining checks](evidence/2026-09-25-foundation-merges/README.md#parser-safety-audit).
No-delombok and no-fetch are safety controls, not evidence that missing generated
semantics or all-language coverage has been solved.

The follow-up Git audit found a live gap: the legacy argument guard admits
arbitrary `-c` values, bare subcommands and unsafe URL forms, while the snapshot
execution loop already performs clone/checkout. Its old deferred-warning comment
is stale. A separate GitHub default runner also inherits unbounded/unpinned
execution behavior. No unsafe command was run. Correct these controls and use a
reviewed data-only commit/tree/blob capture path before enabling the new worker;
source custody alone does not make an unsafe checkout trustworthy. See the
[active safety findings](evidence/2026-09-25-foundation-merges/README.md#other-active-falsifiers-and-next-actions).

## 3. Work ownership and next actions

Use independent worktrees/branches for independent PRs. Existing user untracked
files and running containers belong to the user. Shared files require explicit
handoff; do not cherry-pick or overwrite another agent's in-flight edits.

| Workstream | Owner | Exclusive active files / boundary | Immediate action |
|---|---|---|---|
| R01/R17 handoff and evidence | Root; [#362](https://github.com/scanipy/scanipy/issues/362); initial #365 closed | Current handoff, review, execution ledger, evidence inventory | Reconcile reviewed merges and new findings; preserve all remaining TODOs and original evidence |
| R18/R20 foundations; traversal defect | Canonical agent; narrow [#364](https://github.com/scanipy/scanipy/issues/364) closed | Bounded foundation merged in #369, including combined producer/default/deadline regressions | Verify richer semantic graphs, shared invocation budgets and all advertised normalizations; narrow closure is not full R18/R20 acceptance |
| R09 class propagation | Schema agent; narrow [#363](https://github.com/scanipy/scanipy/issues/363) closed | Completed worker/findings/SARIF/schema correction merged in #371 | Preserve compatibility; full environment/source-only snapshot/final workflow producers remain under #362 |
| R03 corpus correction | Corpus agent; [#361](https://github.com/scanipy/scanipy/issues/361) | Source correction merged in #372; fixture/manifest validation remains assigned | Finish remaining transformation/precondition/correspondence and real-frontend validation, preserve topology limitations and supply G0 inputs; component acceptance does not require a completed G0 |
| R04 typed gate | Root accountable; narrow [#367](https://github.com/scanipy/scanipy/issues/367) closed | Checker/policy/contract merged in #375 | Integrate fresh real producer; retain honest G0 and protected history; full R04/G2 remains open |
| R05 real campaign producer | Corpus agent; [#374](https://github.com/scanipy/scanipy/issues/374) | #380 local integration checkpoint incorporates main and pending #390; shared safety files unchanged | After #390 is approved/merged, refresh #380 and obtain review; verify bounded readiness before 844 uncached side attempts. No native campaign has run |
| R19-A raw semantic export | Schema agent; [#376](https://github.com/scanipy/scanipy/issues/376) | #382 opt-in v2 exporter/schema frozen for canonical review; existing v1/default unchanged | Review and merge exact tested head, then integrate typed transport; raw CALL/property export does not certify correct binding or purity |
| R19-B typed observations | Canonical agent; [#393](https://github.com/scanipy/scanipy/issues/393) | Independently reviewed local typed model/wire/tests/contract checkpoint on pending #382 | Obtain exact-head CI/canonical review after dependencies; preserve original bytes, observed-only semantics and legacy-reader refusal. Source-bound semantics remain #397 |
| R07/R08 occurrence and decisions | Schema agent persistence; root integration; [#378](https://github.com/scanipy/scanipy/issues/378) | Local store checkpoint with 89 passing dedicated PostgreSQL checks; #389 pure matcher remains separate | Review/merge then attach actual producers, durable decisions and API/UI. SQL/crypto/fence assertions and test fixtures do not establish live accepted inputs or operational continuity |
| R08/R10 raw core detections | Canonical agent; [#391](https://github.com/scanipy/scanipy/issues/391) | Isolated raw CFG/CALL observation kernel and tests, local checkpoint only | Review/merge bounded scope, then implement actual typed semantic producer. The narrow kernel rejects ordinary AST/PDG mapper exports and is not G1 |
| R08/R16 source custody | Root; [#392](https://github.com/scanipy/scanipy/issues/392) | Isolated descriptor-based source capture/verification and tests, local checkpoint only | Review/merge, then bind verified raw Git objects without checkout, database receipts, read-only mounts and lifecycle leases. Owner-asserted commit is not SCM proof |
| R08/R11 Semgrep observations | Root; [#394](https://github.com/scanipy/scanipy/issues/394) | Independently reviewed bounded parser checkpoint with 194 focused checks; no legacy adapter changes | Obtain CI/canonical review, then implement closed native runner, coverage and durable source-bound projection. Parser output always has unverified coverage |
| R16 legacy Git containment | Corpus agent; [#395](https://github.com/scanipy/scanipy/issues/395) | Generic Git refusal, snapshot/default SCM route containment and tested snapshot package-copy correction; local checkpoint | Obtain exact-head review/CI after #390 dependency. This disables unsafe paths; it does not implement safe acquisition or certify a rebuilt image |
| R08/R16 legacy demo containment | Root; [#396](https://github.com/scanipy/scanipy/issues/396) | Seven-file local checkpoint: constant scan-unavailable API, truthful health/UI, preserved historical reads, focused tests and narrow hook prerequisites | Obtain CI/canonical review; leave user's running containers untouched. Re-enable only through the reviewed actual capture/authority/worker/store path |
| R19 source-bound scalar producer | Canonical agent; [#397](https://github.com/scanipy/scanipy/issues/397) | Python-first contract/codecs reviewed; bounded local implementation started; Java remains a required extension | Implement/test real nonempty raw witnesses and actual shared dependencies. Reject local calls into any selected entry in the initial profile. Rule isolation, model acceptance and actual native fidelity remain separate obligations |
| R16 raw Git producer and process transport | Corpus agent; [#398](https://github.com/scanipy/scanipy/issues/398) | Shared bounded transport implemented locally and under independent review; raw Git producer remains design work | Finish transport tests/review and review the complete Git profile plus enforceable outer isolation before domain implementation. Hashes, caller flags and process-group kill alone do not authenticate SCM provenance or OS egress |
| R08/R09 accepted input authority | Schema agent; [#399](https://github.com/scanipy/scanipy/issues/399) | Exact verifier contract/codecs reviewed; local implementation authorized with private bytecode-cache isolation; later durable registry and per-attempt authorization remain open | Implement bounded verifier with test-only keys and actual shared types/transport. Actual owner-installed trust, durable publication and live execution authorization remain separate |
| R16 Java invocation safety | Schema agent; [#386](https://github.com/scanipy/scanipy/issues/386) | #390 shared subprocess grammar/profile and coordinated frontend/observer hunk, frozen for canonical review | Obtain successful exact-head review before new real Java probes; no-fetch/no-delombok controls alone do not prove source coverage |
| Repository workflow prerequisite | Root; narrow [#377](https://github.com/scanipy/scanipy/issues/377) closed | Bounded board helper merged in #379 | Continue serialized exact-item state changes; never infer ownership or Todo from failure |
| R15 dependency prerequisite | Root; [#366](https://github.com/scanipy/scanipy/issues/366); narrow #370/#381 closed | Runtime declarations (#373) and snapshot lock/gate (#383) merged | Verify actual image installation/startup only after resource review; no build, publication or active environment promotion yet |
| Hook fail-closed correction | Root; narrow [#384](https://github.com/scanipy/scanipy/issues/384) closed | Corrected hooks/declared YAML tool/tests merged in #387 | Use the current worktree's reviewed hooks and declared yamllint 1.35.1; do not rely on an older shared hook path or ambient CLI |
| Remaining implementation | Root accountable; specialist assigned before first edit | R02, R06–R08, R10–R16, later R19 stages | Finalize graph/flow and occurrence/decision contracts, then assign real producer/integration work in dependency order |

Project-board prechecks found the corrective scopes available. Initial claim
updates encountered GitHub GraphQL rate limiting. On September 25, root
reconciled #361–365, #367 and #374 to In Progress through `scripts/board.sh`.
The narrow dependency issue #370 became Done only after PR #373 merged with
required checks and canonical review passing. Keep remote status current; do
not use that narrow closure to mark a full R-task, claim or gate complete.
The first #376/#377 synchronization encountered the rate limit again. After
quota recovery, the merged bounded helper verified membership/field metadata
and real status changes. Narrow #365/#367/#363/#377/#381/#384/#364 are Done after approved
merges; #376/#378/#386 and #391–#399 remain In Progress. Initial synchronization failures
are not rewritten as successful preflight checks. GitHub unexpectedly closed
#378 on wording containing a negated closing keyword; root removed the trigger,
reopened the issue and restored In Progress. Use “#N remains open,” not a
negated closing-keyword phrase, for partial PRs. Do not treat failed API access
as permission to duplicate another owner's work.

No full R-task is DONE. Subtasks implemented on branches remain pending required
review, merge, and the acceptance scope they actually address. Closing a narrow
corrective issue must not close umbrella #362 or an entire R-task prematurely.

### Branch/PR handoff snapshot

Snapshot base: main `2709177afff1c78f06532e0298dd5ee4d608237f`.
[Exact merge/check records](evidence/2026-09-25-foundation-merges/README.md)
distinguish landed corrections from review-stage work. Check newer heads and
rerun integration on the combined tree. Local test totals do not prove the
submitted functionality is complete.

| PR / scope | Observed local progress | Merge / remaining condition |
|---|---|---|
| [#368](https://github.com/scanipy/scanipy/pull/368), handoff/ledger/evidence | MERGED after current-head CI and canonical APPROVE; 26 ledger tests and preserved historical bytes | Continue full backlog/evidence reconciliation; narrow #365 closed, not R01/R17 acceptance |
| [#369](https://github.com/scanipy/scanipy/pull/369), canonical identity/budget foundation | MERGED after exact-head CI, supplemental Gate 3 and successful canonical APPROVE; 55 dedicated new tests; combined local run 1,235 passed/48 skipped | Narrow #364 closed; richer semantic roles, all refactor normalizations and real-source acceptance remain |
| [#371](https://github.com/scanipy/scanipy/pull/371), independent artifact classes/provenance | MERGED after all seven test checks and canonical APPROVE; 1,015 passed/48 skipped locally, isolated PostgreSQL checks retained | Narrow #363 closed; source-only snapshot producer, full environment and live persistence orchestration remain |
| [#372](https://github.com/scanipy/scanipy/pull/372), genuine typed corpus | MERGED after current-head CI and canonical APPROVE; 422 cases, 85 corpus and 31 harness-compatibility tests; Java/Python syntax checks | #361 stays open; fixture preconditions are demands, not purity observations; no corrected real G0 run yet |
| [#373](https://github.com/scanipy/scanipy/pull/373), fresh dependency compatibility | MERGED after CI, supplemental Gate 3 and canonical APPROVE; fresh declared install: 862 tests pass, 47 existing skips | Narrow #370 closed; broader R15 clean Docker install and stage acceptance remain |
| [#375](https://github.com/scanipy/scanipy/pull/375), typed report gate | MERGED after CI and canonical APPROVE; 76 controlled checker tests, exact corpus/policy/revision/history checks | Narrow #367 closed; fresh real producer and G0 still missing |
| [#379](https://github.com/scanipy/scanipy/pull/379), bounded board helper | MERGED with required checks/review; 95 hermetic tests, live post-reset metadata/mutations verified | Narrow #377 closed; root still serializes transitions; no atomic ownership-lock claim |
| [#383](https://github.com/scanipy/scanipy/pull/383), snapshot lock | MERGED after seven test checks and canonical APPROVE; exact lock bytes bound, 1,043 passed/47 skipped locally | Narrow #381 closed; no corrected image build/install/startup or registry promotion performed |
| [#385](https://github.com/scanipy/scanipy/pull/385), occurrence/decision contract | MERGED after CI and canonical APPROVE; no product code changed | #378 remains open; exact schema/grants, persistence and real workflow still required |
| [#387](https://github.com/scanipy/scanipy/pull/387), fail-closed developer hooks | MERGED after CI and canonical APPROVE; 33 focused tests and fresh declared toolchain | Narrow #384 closed; current hooks must propagate failures without partial-mypy fallback |
| [#388](https://github.com/scanipy/scanipy/pull/388), progress reconciliation | MERGED after CI and canonical APPROVE; documentation/ledger only | Its earlier evidence cutoff is superseded by this snapshot; no feature acceptance |
| [#380](https://github.com/scanipy/scanipy/pull/380), real campaign producer | DRAFT remotely; newer local checkpoint `11dba036cc6241a00a8100c4918b5e8bec18ef7b` incorporates main and pending #390; actual local pre-push selection 1,351 passed/11 skipped | Wait for reviewed #390, then integrate approved main, publish/review exact candidate and run bounded readiness. No full 844-side campaign or G0 yet |
| [#382](https://github.com/scanipy/scanipy/pull/382), raw Joern v2 transport | Ready for review at `9035359e548ac210c3d101f24df76b7df2ebc32d`; all seven test checks pass, canonical action failed on external session limit | Retry after capacity reset; do not merge on peer approval alone. Typed mapping, precise bindings/purity and matched-return solver remain R19-B/C/D |
| [#389](https://github.com/scanipy/scanipy/pull/389), pure continuity matcher | Ready for review at `2fd67cb58f2850dd0d0e8c0a4966ad1ee70fdbc0`; all seven test checks pass, canonical action failed on external session limit | Successful canonical review remains required; no durable decisions/API/UI or accepted production policy |
| [#390](https://github.com/scanipy/scanipy/pull/390), Java invocation safety | Ready for review at `16252b21db172b967f13a815ca9bd8fe3078dd19`; all seven test checks pass, canonical action failed on external session limit | Review first when capacity returns; a comment containing APPROVE with an action error is not approval. No new Java probe before merge |

Local build-ahead is intentionally separate from the remote merge queue:

| Issue / local-only scope | Retained checkpoint | Next acceptance action |
|---|---|---|
| [#391](https://github.com/scanipy/scanipy/issues/391), raw core observation kernel | `278734bc9482f46f8b48d48aef3867479a885a1b`; 168 focused checks, full local run 1,403 passed/48 skipped, normal hooks passed; scoped independent review | Submit after review capacity returns. Exact CFG/CALL profile is intentionally narrower than real mapper output; no full IFDS/IDE or G1 claim |
| [#392](https://github.com/scanipy/scanipy/issues/392), local source custody | `e3d318b3c24f9509560b07bae04066dd370bf9e0`; 64 focused checks, full local run 1,313 passed/51 skipped, normal hooks passed; scoped independent review | Submit after review capacity returns. Filesystem readback/receipt is not SCM verification, a database seal or protection against the same OS user |
| [#378](https://github.com/scanipy/scanipy/issues/378), occurrence storage | `fe61c9cdcf4ae56cf5c7fd682b3a73c3502f1808`; 89 dedicated real PostgreSQL checks passed/zero skips; full configured run 1,344 passed/140 optional skips; normal hooks passed | Obtain exact-head review/CI. Dedicated test database and restricted roles are not live app integration; actual accepted authority/source/native producers, decisions and API/UI remain required |
| [#393](https://github.com/scanipy/scanipy/issues/393), typed observed CPG | `b7dfaba503b9d58262999ddd0850ae45145687ba`; 145 focused checks, full run 1,466 passed/48 skipped, normal hooks and independent review passed | Based on pending #382. Preserve bounded lossless wire, observed-only interpretation and legacy refusal; full semantic mapping/solver remains #397 and later work |
| [#394](https://github.com/scanipy/scanipy/issues/394), Semgrep observations | `5f47b07dc59e46bf39b2aed03be59921c3991773`; 194 focused checks, full run 1,443 passed/51 skipped; normal hooks and independent production-code review passed | Native execution, accepted rules, coverage, durable binding, measured rate and signed provenance remain unimplemented in this slice |
| [#395](https://github.com/scanipy/scanipy/issues/395), legacy Git containment | `9b9091faf1f22b216aca74c87e7711da33d40390`; 60 focused checks, fresh full run 1,403 passed/51 skipped, normal hooks and independent review passed; root independently reran both packaging controls | Includes the missing integrations Docker COPY correction. Isolated package-import testing cannot certify third-party image installation or safe acquisition; reviewed #390 base and exact-head CI/review remain required |
| [#396](https://github.com/scanipy/scanipy/issues/396), legacy demo containment | `5fd2000c6298afebfa78cb2fa5e5a5326898930b`; 27 focused checks, full run 1,276 passed/51 skipped; normal commit/pre-push and independent seven-file review passed | Constant 503 for new scans; historical schema/GETs preserved. User app/DB untouched. Review/merge then implement the actual cutover, not an unsafe enablement flag |
| [#397](https://github.com/scanipy/scanipy/issues/397), source-bound scalar semantics | Contract and worker/projection/result codecs reviewed; local implementation started, without a reviewed implementation checkpoint yet | No accepted real witness, operational model or fresh native run. The Python-first subset does not reduce the full Java/Python/corpus obligations |
| [#398](https://github.com/scanipy/scanipy/issues/398), raw Git acquisition | Shared transport code and controlled Python-child tests are local and under independent review; Git domain companion is still design work | No native Git invocation, image build or raw Git producer code. Online egress enforcement and trusted SCM-to-capture evidence must be real, not a boolean |
| [#399](https://github.com/scanipy/scanipy/issues/399), accepted-byte authority verifier | Exact verifier/runtime protocol reviewed and bounded local implementation authorized; no reviewed implementation checkpoint yet | Pure signature checks cannot prove durable publication or authorize a process. Actual publisher/root/operator/admission installation and registry/launcher integration remain open |

At approximately 10:59 UTC on September 25 the canonical reviewer reported a
session limit, with a reported reset at **13:40 UTC / 18:40 Asia/Karachi**. This
is not GitHub API quota exhaustion and is not a guarantee that the service will
recover at that time. Do not launch repeated reviews before that time without
independent evidence of recovery. Retry #390 first, then #382/#389 serially;
recheck exact heads, required tests, actual action success and the final APPROVE
verdict before each merge. Preserve any new corrective review findings.
Continue safe, assigned local work meanwhile; do not bypass review or describe
the full Black Hat goal as blocked while meaningful in-scope work remains.

Fresh-install CI exposed an AnyIO/Starlette warning-as-error incompatibility and
SQLAlchemy driver-default drift. The narrow corrective dependency issue fixes
project declarations; temporary development-environment pins are not the product
fix. Review-stage branches must incorporate the reviewed correction and rerun
required checks. Old CI failures must not be relabeled as passing.

## 4. Milestones and schedule

The ledger expands design → implementation → component milestones into a DAG.
Integration milestones follow shared gates; they are never prerequisites for
their own components. Its status values describe execution, not proof of a
claim. Validate it with:

```bash
python3 scripts/check_bhmea_execution_state.py docs/bhmea/execution-state.json
```

That command checks the planning ledger, not source correctness or report
acceptance. R04 supplies the separate semantic report gate.

| Sequence | Completion event | Scheduling rule |
|---|---|---|
| Now — foundations | R01 plan; R02/R09/R18/R20 contracts; R16 tool-mode review; parallel R03/R04/R05 preparation | Do not wait for a green refactor score to fix invalid canonicality/corpus |
| G0 | Corrected corpus + verified report checker + required fresh-run command; retain complete honest baseline | Red feature results may form a valid baseline; optional cache/debug tools cannot delay it |
| G1 — early vertical slice | Real nonempty core and Semgrep runs, proper classes/origin, reproducibility/rate checks, persisted export verified in a fresh process | Start after usable foundations/producers; do not wait for every R06 refactor to pass |
| Component closure | All required refactors, lifecycle/UI, CodeQL, provenance, comparator, safety and deployment paths | Parallelize non-overlapping files; CodeQL adapter verification precedes its rate measurement |
| G2 — technical acceptance | All declared Java/Python and engine cases on one merged artifact | No reduced denominators, hidden weak results, synthetic provenance, or zero-finding core substitute |
| G3_RELEASE | Clean attendee install, public source/license/evidence, separately authorized release actions | Pending publication remains pending; check release artifact rather than local checkout only |
| G3_STAGE | Same accepted artifact, offline rehearsal twice, measured budgets, recovery drills and fallback | Use actual presentation machine; local Docker does not prove offline readiness |

Aim to complete all technical and stage work before the earliest possible
presentation, December 2. There is no invented hard internal lock. Reforecast
after the first corrected G0 and G1: record measured durations, resource limits,
remaining critical-path tasks, and contingency time. Current reference parsing
cost is not an end-to-end estimate. Raise forecast risk early without dropping
claims or assuming confirmed hardware meets unmeasured budgets.

## 5. Current evidence and limitations

Baseline code: `940d440cb99e23131d28ee5bbb1655ea29d46a58`. Input documents were
untracked at initial review. Their pre-update SHA-256 values were:

| Input | SHA-256 |
|---|---|
| Submitted supporting material | `87563ee5ebf7f621694649720589a6d38f53ffd4808033f443fa48a5311f3d62` |
| Original 2026-09-22 execution plan, before supersession banner | `830c748757d252d3f3b4a3a0b7460a5b663c5c8281360ed4501809d55fd2772d` |
| Review revision 2, before current updates | `b600201c370e4dd66e24847b5366d647c8133a66e93c50b8755e41cfc7c12d43` |

Retained evidence:

- [Historical August 31 report](evidence/historical/2026-08-31/README.md):
  original bytes recovered; 56 cases, 52 evaluated, 40 matching declared
  expectations, 12 contrary, 4 unevaluated. Invalid/vacuous transformations and
  unverified strong labels make this neither corrected G0 nor fresh acceptance.
- [September 25 frontend diagnostic](evidence/2026-09-25-r05-readiness/README.md):
  one fresh real Python parse/export/map, 38.785 seconds, 222 nodes/500 edges.
  No Java/refactor/detection/fingerprint/signing run. Existing image and explicit
  environment only; not clean packaging or presentation-hardware evidence.
- Canonical relabeling, graph-content hash, time-dependence, witness-cone, and
  call-matcher defects are described in the review/designs. Controlled library
  counterexamples establish defects, not feature or language acceptance.

Follow [evidence conventions](evidence/README.md). Preserve contrary results,
exact invocations, code/source/tool identities and raw bytes. Every PASS needs
its actual scope and artifact references. No G0/G1/G2/G3 PASS is recorded yet.

On the then-reference host at 10:12 UTC, approximately 6.5 GiB RAM was available
and the 2 GiB swap was fully used; disk had 107 GiB free. This is a transient
resource check, not a stage budget. Do not launch parallel image builds or
Java/Python campaigns on that observation. Recheck resources and use bounded
sequential probes only after the relevant safety/packaging changes are reviewed.

The owner subsequently confirmed this host as the actual presentation machine.
The [13:21 UTC stage observation](evidence/2026-09-25-stage-machine/README.md)
records Ubuntu 22.04.5/x86_64, 32 VMware-exposed CPUs, 62.75 GiB total RAM,
7.37 GiB currently available, nearly full swap and 101.91 GiB free on the shared
workspace/tmp/Docker filesystem. These transient values do not establish a safe
worker allocation or stage budget. Earlier diagnostic results keep their
original scope; do not promote them to offline or feature acceptance.

## 6. Non-negotiable acceptance and remaining owner input

All 18 claims remain UNVERIFIED in the ledger. The full review's TODOs still
apply, including real CodeQL/SpotBugs/Semgrep comparisons, persistent local keys
and public-key-only verification, durable decisions, no-execution tests,
one-command install, and offline fallback. A production repair plus unit tests
is progress, not end-to-end completion.

Ask only when needed; do not repeatedly ask settled questions:

- Confirm the exact presentation date when scheduled. Machine identity is
  settled: do not ask for the same hardware choice again. Recheck resources,
  measure fresh/warm latency and peak use on this machine, then assign budgets
  and complete the two offline rehearsals and recovery/fallback checks.
- Ask separately before publishing a release/image or replacing submitted
  video/external material, incurring new costs, or contacting organizers.
- A technically narrower scope requires an explicit owner decision and remains
  unfulfilled against the original submission. No such reduction is selected.

Update the ledger and issue links as work lands. Re-run affected checks after
merges; do not carry evidence across incompatible schema, corpus, tool, source,
policy, or identity-version changes.

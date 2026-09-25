# Black Hat MEA — active execution handoff

| Field | Value |
|---|---|
| Updated | 2026-09-25 |
| Snapshot | Revision 14; observed 2026-09-25 22:25 UTC plus explicit 22:30 update; accepted main `4911f656`, earlier cutoffs preserved |
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
and append-only human decisions. Its pure matcher is merged in #389,
with an empty production policy registry. A lifecycle-generation correction
prevents old links or unchanged suppression from reviving after reopening;
fresh authorization is per dimension, not implied by a new verdict/reference.
The occurrence store is now merged in #411, but neither it nor the pure matcher
supplies the live producer, durable decision or API/UI integration by itself.

The restricted Java parse/export profile is now merged in #390 (narrow #386
closed). Before further Java probes, verify the actual compatible installed
profile, outer runtime controls and source coverage. The pinned frontend can enable dependency
build execution through an environment override, and automatic Delombok can
lead to partial source coverage. See the [source audit and remaining checks](evidence/2026-09-25-foundation-merges/README.md#parser-safety-audit).
No-delombok and no-fetch are safety controls, not evidence that missing generated
semantics or all-language coverage has been solved.

The follow-up Git audit found a then-live gap: the legacy argument guard admitted
arbitrary `-c` values, bare subcommands and unsafe URL forms, while the snapshot
execution loop already performed clone/checkout. Its old deferred-warning comment
was stale. Default provider runners also inherited unbounded/unpinned execution
behavior. No unsafe command was run. Merged #402 now refuses generic Git and
default snapshot/provider acquisition before staging; merged #403 removes the
legacy app's native scan route and returns unavailable for new submissions.
These are containment, not safe acquisition or deployed cutover. Use a reviewed
data-only commit/tree/blob capture path before enabling the new worker;
source custody alone does not make an unsafe checkout trustworthy. See the
[active safety findings](evidence/2026-09-25-foundation-merges/README.md#other-active-falsifiers-and-next-actions).

## 3. Work ownership and next actions

### Revision 14 execution queue — observed at 22:25 UTC

Accepted main `4911f6568a85206651adbf40428529eb090c389f` now includes inventory
#414, Revision 13 documentation #415, rule #416 and metadata-loader #417. The
[Revision 14 evidence index](evidence/2026-09-25-foundation-merges/README.md#revision-14--observed-2225-utc-september-25)
records exact review/test links and retained failures. The earlier queues below
are historical; do not repeat completed merges or promote full acceptance.

1. **Root — publication and evidence:** resolver B `b0717452` has 804 affected
   passes and its normal push is running, not assumed complete. The pre-C full
   3,549/51 belongs only to `c365e129`. Open/review it only after real push
   success; require exact-head CI/canonical and merged-artifact checks. Keep
   all broad/full/pre-push runs serialized and canonical reviews serialized.
2. **Runtime owner — narrow dependency packaging:** D `6bf0651` has 856 affected
   passes and needs fresh full then normal push/remote gates. E `257336c` has
   479 owned passes and normal commit hooks, but requires accepted-parent
   refresh and its own gates. Package complete reviewed F journal unit after E,
   then G packet/controller dependencies; do not import a stale baseline or
   reconstruct selected semantics from a large combined branch.
3. **Accepted-input owner — real database verification:** AL-03 SQL/validation/
   reads now include reviewed stored-error, generated-denial precharge and
   backward-time corrections. Its 147 unit/source checks and five-resource
   scoped security approval are not PostgreSQL evidence. Finish independent
   facade review, then use a separately owned bounded cluster and reviewed
   fixture. Do not reuse the application's DB or the occurrence fixture's
   global roles. Preserve every real failure; no provider or key is installed.
4. **Root/provenance — compatibility before producers:** `de17aa06` has 702
   affected passes; 3,391/51 full belongs to pre-C `1a349f22`. Complete its
   normal push/current-head gates. Then finish every producer/finalization/
   persistent-key/export TODO in the compatibility contract; synthetic signed
   examples authenticate neither a source scan nor an operator.
5. **Physical runtime and delivered workflow:** RES `3194baa1` has 4,720/51 full
   on its recorded combined tree, not on a later publication composition.
   Qualified storage, event/spool/full-reader, current six-role owner closure,
   DB orphan barriers, kernel/Docker/controller and actual native producers
   remain required. Wire raw detections before identity, durable decisions,
   final provenance, API/UI, all-source campaigns and independent rehearsal.

All recorded skips stay skips; repeated focused runs are not additive distinct
coverage. No full R/C/G state changes. Acceptance/RSVP remains done, presentation
December 2 or 3, no October lock, this development machine as Docker target.
Release/image publication, spending and external messages still need authority.

**Later update — observed 22:30 UTC:** B normal push passed and the independently
verified remote `b0717452` is now [PR #418](https://github.com/scanipy/scanipy/pull/418).
Its current CI/canonical gates remain pending, not accepted. AL's final unit
selection is 185 on each Python version (149 AL +36 unchanged occurrence);
138 PostgreSQL cases were collected only. A new root-owned, network-none,
1.5 GiB-limited PostgreSQL container is ready on a private task socket; no AL
SQL test has run. Finish facade review before the separately granted three-case
smoke, then expanded SQL tests. Existing app/DB and occurrence cluster are
untouched; D full remains queued. Earlier 147-case evidence retains its own scope.

### Revision 13 execution queue — historical observation at 20:51 UTC

Accepted main `075f92fe9d6aa1afb0a16494769e9cc96ba0df16` includes CodeQL
parser #413 and occurrence store #411. Their exact reviewed trees, successful
checks/reviews and retained contrary evidence are in the
[Revision 13 evidence index](evidence/2026-09-25-foundation-merges/README.md#revision-13--observed-2051-utc-september-25).
This queue replaces earlier pending instructions; historical tables below do
not require repeating completed merges. No full task/claim/gate state changes.

1. **Root — publication and evidence:** preserve accepted #413/#411 bytes;
   complete the inventory `d59c427` and rule `2f1b3f7` normal-push/current-head
   CI/canonical queue. They have 647 and 714 focused passes and no PR at this
   cutoff. Prior full 2,536/51 and 2,603/51 belong to older heads, respectively.
   Root's inventory push is running, not assumed successful. Then finish the
   runtime/packet and remaining semantic/authority dependency gates.
2. **Runtime owner — integrate, do not enable:** local packet `a9e8011` and
   controller `ccaf7e5` have identical tree `7976bbd4`. The configured full
   run passed **5,662 /51 existing skips**, zero failures/errors, 483.365s;
   it includes 89 actual occurrence-store PostgreSQL tests with no skips.
   Reviewed packet commit `639a6c9` has 760 owned plus 16 independent pure
   controls on both Python versions. The combined focused selection was 1,946.
   Preserve the original controller **3,772/51/one-failure** and separately
   established ancestor mechanism; reviewed `5c57897` retains full selected
   file/direct-parent checks. None of this supplies current owner authority,
   installed kernel controls, supervised Docker lifecycle or native acceptance.
3. **Schema/authority owner — implement the approved boundary:** AL-02 is a
   locally committed/reviewed input codec. AL-03 `be3c00d` has 56 draft
   shapes/facade checks, not SQL/PG acceptance. At 20:49 UTC root and peer
   approved WORK02 `85174198` after replay `14A` and census `N-seen+1`
   corrections. Incorporate those exact logical raw/image/history/canonical
   accounting rules before affected helper implementation. A new detector
   run is RUNNING; initial denial must be atomic. Keep configured trust,
   current-use authority, operator/restore decisions and actual DB bridges
   distinct; logical ceilings do not prove RSS or workload capacity.
4. **RES owner/reviewers — finish frozen non-event core review:** 110 controls
   pass on each Python 3.11/3.12, with both genuine draft reds preserved.
   Independent review is pending. The private byte-custody core does not
   install/qualify storage, provide a full history/event/spool writer, satisfy
   DB orphan barriers or enable an operational constructor. Preserve retained
   publication-ID mapping, staged role plans and failure-invalidated writers;
   do not bypass the deferred full-reader work-accounting boundary.
5. **Producer/integration owners — deliver the actual workflow:** #413 is a
   lossless supplied-report parser, not real CodeQL acquisition/invocation.
   #411 provides tested persistence, not native/raw-detection producers,
   accepted current authority or the final Finding/R09 bridge. Wire the
   merged source custody, exact accepted inputs, runtime evidence and raw
   detections before any identity operation, then durable decisions and
   truthful API/UI. Keep CLAR-BHMEA-02 open and no fake snapshot/env/hash.
6. **After qualified runtime and explicit run approval:** bounded sequential
   readiness probes, all 844 uncached R05 sides, real nonempty core/Semgrep,
   CodeQL reproduction/comparators and full Java AND Python evidence precede
   G0/G1/G2 and the separate release/stage gates. No native run is authorized
   by this queue. The owner-confirmed machine still needs capacity/rehearsal
   proof; the 20:32 observation was about 8.3 GiB available RAM, full swap and
   96 GiB free on a shared device.

**Later update — 20:54 UTC:** inventory normal push passed (Ruff/249 formatted
files/mypy 99/configured unit selection); [PR #414](https://github.com/scanipy/scanipy/pull/414)
is now open at exact `d59c427`, with CI `36188497922` and canonical
`36188497794` running. Rule `2f1b3f7` push remains running. RES root review
reproduced the double-begin thread race on `2fd1297a`; the narrow lifetime
correction has interim 111 passing checks and five additional focused controls,
not final acceptance. Finish the corrective peer/fault review and gates before
any new checkpoint. These later facts supersede items 1/4 only as stated;
old-source 110-pass results remain historical.

### Historical Revision 12 execution queue — observed at 19:00 UTC

At its cutoff this queue superseded corresponding pending statuses in the older
ownership/checkpoint rows below. It does not change their full acceptance
obligations. Root retains issue/merge coordination; local code review is not
the required remote canonical review.

1. Complete #409's corrected canonical re-review on `acbd9d6`. Its full
   2,437/51, normal push and exact-head five-job CI are green; review run
   `36176791343` is still running. The initial failed action remains evidence.
   Do not merge an APPROVE word inside a failed action.
2. Integrate accepted dependencies into #411 and push its correction. Its
   source/SQL/CI bytes are unchanged at local `e08ac41`; the new OPEN
   `CLAR-BHMEA-02` tracks the final-record/R09 bridge. Initial `2fec34d` full
   2,287/51 includes 89 actual PostgreSQL cases with no skips, and all eight
   remote tests passed. That head's failed canonical review is not acceptance.
   Preserve both new WBS CLAR rows when merging concurrent branch additions.
3. Publish reviewed narrow foundations with actual combined-head gates: rule
   codec `6ae81ad` (full 2,269/51), inventory `980c5ef` (full 2,202/51), then
   their runtime/accepted-input/scalar consumers. Original owned bytes must be
   compared across integrations; a normal merge-hook skip is not a fresh test.
4. Finish #410's CodeQL pure parser gates: `93ae0aa` contains the unchanged
   three reviewed files plus exact `acbd9d6` dependencies; first full is running.
   Publish as a three-file slice only after the Git dependency is accepted.
   Next implement the truthful runnable real-output adapter and required
   rule/location/CWE/origin mapping. R11/R12/R14/G2 are downstream, not substitutes.
5. Preserve journal `0dbee6e` / source `51e56785`: pure 331-case runs on both
   Python versions and independent review are green; 434 affected tests pass
   after main/inventory integration. Next: combined/remote gates and actual
   physical publication/capacity/owner adapters/DB barriers/controller. New
   authority-codec files (`bc361a8f` source) have 286-case runs on both runtimes;
   independent review is ongoing. Both remain data-only, not live permission.
6. Continue scalar `c8fb75c` from its 3,365/140 full-tested tree, preserving all
   negative-control corrections. Merge the real dependencies, obtain remote
   gates and establish actual nonempty source/native/model/authority evidence;
   full Java AND Python and full refactor/fidelity requirements remain open.

The 741-line authority design and 544-line amendment have scoped design
approval. Actual namespace operation history, no-retrospective-adoption,
restricted SQL roles/bridges, current providers and real operator/restore choices
remain implementation or owner prerequisites. AL-02 input validation does not
create those rows or grant current execution authority.

Physical publication planning exposed two design gaps: retired intents lose
the publication-ID mapping needed for exact recovery, and the full journal
helper's 512 MiB hash ceiling is not proof it fits the reader's 256 MiB allowance.
Resolve retention/accounting and delegated work before implementing affected
APIs. No quota increase, fake reserved capacity, generic event writer or
operational fallback is authorized by identifying these gaps. Database barrier
claims still need actual positive current authority and namespace-first locking;
lease expiry or a structural journal record cannot prove native cleanup.

All scratch XML/local hashes below are scoped diagnostics, not immutable public
acceptance artifacts. No full R-task, C-claim, gate, release or stage readiness
is promoted. Root preserves the original app/DB, submitted bytes and old evidence.

### Earlier ownership and checkpoint detail

**Later update — 19:05 UTC:** #409 is now accepted at main `595484b`, tree
identical to reviewed `acbd9d6`, after successful canonical action
`36176791343` / final APPROVE and the five green corrected-head CI jobs.
The first queue item above is therefore complete only for that narrow merge;
#398 and all online/runtime/sealing work remain open. CodeQL's first combined
full subsequently passed 2,864/51 on `93ae0aa`. AL-02's independent 291-case
run and full source review approved its unchanged two files, then normal
commit `66607b9` passed hooks. These are local-only component results, not
real adapter/current-authority/full-task acceptance. Integrate accepted main
and recheck exact bytes before their remaining push/remote gates.

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
| R05 real campaign producer | Corpus agent; [#374](https://github.com/scanipy/scanipy/issues/374) | #380 merged at `3e2773e` from reviewed `9be0579`; combined full 1,894/51, required CI and successful canonical APPROVE | Integrate #400's actual bounded controller and verified image/runtime readiness before 844 uncached side attempts. No native campaign or corrected G0 has run; #374 remains open |
| R19-A raw semantic export | Schema agent; [#376](https://github.com/scanipy/scanipy/issues/376) | #382 opt-in v2 exporter/schema merged after combined-head tests and canonical APPROVE | Integrate typed transport and runtime/source semantics; raw CALL/property export does not certify correct binding or purity |
| R19-B typed observations | Canonical agent; narrow [#393](https://github.com/scanipy/scanipy/issues/393) Done | #407 merged at `1b29100` from reviewed `83b9ec6`, identical tree, full 2,103/51, normal push, all seven tests and canonical APPROVE | Preserve original bytes, observed-only semantics and legacy-reader refusal. Integrate actual source-bound semantics under #397; full R19 remains open |
| R07/R08 occurrence and decisions | Schema agent persistence; root integration; [#378](https://github.com/scanipy/scanipy/issues/378) | #411 merged at `075f92f`, identical to reviewed `1c2f3b7`, eight green test checks including 89 actual PG cases/no skips and successful canonical APPROVE; #389 matcher merged | Attach actual producers/current authority, final Finding/R09 bridge, durable decisions and API/UI. Tested persistence is not an enabled workflow; #378/#362 stay open |
| R08/R10 raw core detections | Canonical agent; [#391](https://github.com/scanipy/scanipy/issues/391) | Isolated raw CFG/CALL observation kernel and tests, local checkpoint only | Review/merge bounded scope, then implement actual typed semantic producer. The narrow kernel rejects ordinary AST/PDG mapper exports and is not G1 |
| R08/R16 source custody | Root; narrow [#392](https://github.com/scanipy/scanipy/issues/392) Done | Three-file custody primitive merged in #406 at `6f1ebc8`; reviewed `b005eaa` has the identical tree, full 1,958/51 and successful exact-head CI/review | Bind verified raw Git objects without checkout, actual database seals/receipts, read-only mounts and lifecycle leases. Owner-asserted commit is not SCM proof; full #378/#362 remain open |
| R08/R11 Semgrep observations | Root; narrow [#394](https://github.com/scanipy/scanipy/issues/394) Done | Bounded parser merged in #404 after combined tests, all seven remote test checks and successful canonical APPROVE | Implement closed native runner, coverage and durable source-bound projection. Parser output always has unverified coverage; full R08/R11/R16 remain open |
| R16 legacy Git containment | Corpus agent; narrow [#395](https://github.com/scanipy/scanipy/issues/395) Done | Generic Git refusal, snapshot/default SCM containment and package-copy correction merged in #402 | Preserve refusal until actual approved acquisition exists. This does not certify safe acquisition or a rebuilt image |
| R08/R16 legacy demo containment | Root; narrow [#396](https://github.com/scanipy/scanipy/issues/396) Done | Seven-file containment merged in #403: unavailable new scans, truthful health/UI and preserved historical reads | User's running app/DB remain untouched. Re-enable only through the reviewed capture/authority/worker/store path; retain the nonblocking review follow-ups below |
| R19 source-bound scalar producer | Canonical agent; [#397](https://github.com/scanipy/scanipy/issues/397) | Local committed `c8fb75c` retains `f6903cf` tree with full 3,365/140; compiler/raw corrections and earlier genuine rejection failures remain retained | Complete current dependency/remote gates and actual native/source/model/authority/durable producers. Prior 500 and 2,469/51 results belong to earlier heads; full Java/Python scope and G1 remain unaccepted |
| R16 raw Git producer and process transport | Corpus agent; [#398](https://github.com/scanipy/scanipy/issues/398) | Offline/transport slice merged in #409 at `595484b`; receipt/cleanup corrections and earlier contrary tests retained | Bind the actual source seal/runtime and online acquisition path. Online Git needs an approved profile and enforceable egress/runtime controller; offline consistency is not SCM-origin authentication |
| R08/R09 accepted input authority | Schema agent; [#399](https://github.com/scanipy/scanipy/issues/399) | Local bounded verifier committed with test-only keys and private bytecode-cache isolation; later durable registry and per-attempt authorization remain open | Integrate the actual loader/controller and durable authority. Owner-installed trust, durable publication and live execution authorization remain separate from diagnostic verification |
| R16 Java invocation safety | Schema agent; [#386](https://github.com/scanipy/scanipy/issues/386) | #390 merged with successful exact-head canonical APPROVE and all seven test checks; narrow issue/board Done | Verify actual runtime/profile and coverage before new Java probes; no-fetch/no-delombok alone does not prove source coverage |
| R08/R15/R16 runtime enforcement | Root; [#400](https://github.com/scanipy/scanipy/issues/400) | Local `ccaf7e5` shares packet `a9e8011` tree `7976bbd4`, full 5,662/51; pure journal/packet/ancestor corrections reviewed. Separate frozen RES core has 110 checks per runtime, independent review pending | Obtain remote gates; qualify storage/installer/work limits, finish event/spool/full-reader and parent DB orphan barriers, current-anchor factory, kernel readers, supervised Docker lifecycle/recovery and actual authority. No operational controller exists |
| R13 CodeQL observations and adapter | Canonical agent parser; root integration; [#410](https://github.com/scanipy/scanipy/issues/410) | Three-file pure observation parser merged in #413 at `5118c93` from `4be0c28`; seven green checks and canonical APPROVE | Implement bounded real-output/import/native adapter, accepted rule/source/CWE/origin mapping, coverage, reproduction and comparator evidence; no native CodeQL or R13 acceptance |
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
and real status changes. Narrow #365/#367/#363/#377/#381/#384/#364/#386/#376/#395/#396/#394/#392/#393 are Done
after approved merges; #374/#378/#391 and #397–#400 remain In Progress. Initial synchronization failures
are not rewritten as successful preflight checks. GitHub unexpectedly closed
#378 on wording containing a negated closing keyword; root removed the trigger,
reopened the issue and restored In Progress. Use “#N remains open,” not a
negated closing-keyword phrase, for partial PRs. Do not treat failed API access
as permission to duplicate another owner's work.

No full R-task is DONE. Subtasks implemented on branches remain pending required
review, merge, and the acceptance scope they actually address. Closing a narrow
corrective issue must not close umbrella #362 or an entire R-task prematurely.

### Historical branch/PR handoff snapshot

Merged snapshot base: main `1b29100ad9c96ebab9a4ac1a439fc2a5b19ac2ee`
at 17:42:32 UTC on September 25. The local-only table retains its 17:29 UTC
checkpoint except the now-merged #393 row; the explicit 17:45 update below
supersedes pending-status statements for subsequent work. New heads require
their own affected checks and gates.
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
| [#375](https://github.com/scanipy/scanipy/pull/375), typed report gate | MERGED after CI and canonical APPROVE; 76 controlled checker tests, exact corpus/policy/revision/history checks | Narrow #367 closed; #380 producer now merged, but verified runtime execution and G0 still missing |
| [#379](https://github.com/scanipy/scanipy/pull/379), bounded board helper | MERGED with required checks/review; 95 hermetic tests, live post-reset metadata/mutations verified | Narrow #377 closed; root still serializes transitions; no atomic ownership-lock claim |
| [#383](https://github.com/scanipy/scanipy/pull/383), snapshot lock | MERGED after seven test checks and canonical APPROVE; exact lock bytes bound, 1,043 passed/47 skipped locally | Narrow #381 closed; no corrected image build/install/startup or registry promotion performed |
| [#385](https://github.com/scanipy/scanipy/pull/385), occurrence/decision contract | MERGED after CI and canonical APPROVE; no product code changed | #378 remains open; exact schema/grants, persistence and real workflow still required |
| [#387](https://github.com/scanipy/scanipy/pull/387), fail-closed developer hooks | MERGED after CI and canonical APPROVE; 33 focused tests and fresh declared toolchain | Narrow #384 closed; current hooks must propagate failures without partial-mypy fallback |
| [#388](https://github.com/scanipy/scanipy/pull/388), progress reconciliation | MERGED after CI and canonical APPROVE; documentation/ledger only | Its earlier evidence cutoff is superseded by this snapshot; no feature acceptance |
| [#380](https://github.com/scanipy/scanipy/pull/380), real campaign producer | MERGED at `3e2773e2a1f6578c2a712a1b85b5a45d172503eb` from reviewed `9be0579cd745fff4c4115c1f241a93926113a9be`; configured full 1,894/51, normal push, five required CI jobs and successful canonical action 36162235882 / APPROVE 5835971061 | Prior full 1,613/51 and `652f1ee` 1,700/51 remain tied to their earlier trees. #374 stays open; #400 and actual image/runtime readiness precede native attempts. No G0, detection/purity/lifecycle/full-environment acceptance |
| [#382](https://github.com/scanipy/scanipy/pull/382), raw Joern v2 transport | MERGED at `02933f1` from combined head `2f0ebef`; 1,429 local tests passed/51 existing skips, all seven remote checks and successful canonical APPROVE | Narrow #376 closed; typed mapping, precise bindings/purity and matched-return solver remain R19-B/C/D. No new native probe during integration |
| [#389](https://github.com/scanipy/scanipy/pull/389), pure continuity matcher | MERGED at `e79dc54` from combined head `4b5b514`; 1,559 full-suite passes/51 existing skips, all seven remote test checks and successful canonical APPROVE | #378 remains open. Empty production registry; no durable decisions/API/UI or operational continuity. Earlier failed reviews are preserved |
| [#390](https://github.com/scanipy/scanipy/pull/390), Java invocation safety | MERGED at `8d38c06` from `16252b21db172b967f13a815ca9bd8fe3078dd19`; all seven checks and subsequent successful canonical APPROVE | Narrow #386 closed; safe Git acquisition, other engines, actual profiles/controls and source coverage remain R16 work. Earlier failed action is preserved, not treated as approval |
| [#401](https://github.com/scanipy/scanipy/pull/401), stage/handoff reconciliation | MERGED at `69f7f48` from reviewed `604d21c`; all five CI jobs and successful canonical action | Documentation and owner-confirmed machine identity, not stage or feature acceptance |
| [#402](https://github.com/scanipy/scanipy/pull/402), legacy Git containment | MERGED at `cfadaa2` from reviewed `b25c180`; CI/Gate 3 and final canonical action succeeded; initial checklist-only review failure retained | Narrow #395 Done. Packaging correction included; no image build, safe acquisition or operational source proof |
| [#403](https://github.com/scanipy/scanipy/pull/403), legacy app containment | MERGED at `4cf10d0` from reviewed `286d6b9`; combined full 1,646/51, all five CI jobs and successful canonical APPROVE | Narrow #396 Done; user app/DB untouched. Refusal is not delivered scan functionality; exact CI link is attached and nonblocking review follow-ups remain |
| [#404](https://github.com/scanipy/scanipy/pull/404), bounded Semgrep observations | MERGED at `6ae30df64678bf916062fa67dde98704d0c36153` from reviewed `ed55bfc833be031934be079dfa47916ff3e1f29b`; 194 focused checks, combined full 1,840/51, normal push, all seven remote test checks and successful canonical APPROVE | Narrow #394 Done. No native execution, accepted rule/source binding, verified coverage, measured rates or durable provenance; full R08/R11/R16 remain open |
| [#405](https://github.com/scanipy/scanipy/pull/405), Revision 10 handoff | MERGED at `2ee3fc026a5f77894355470922a5f399a330f4d6` from `90a89c9500f5004d2028b0b4b6b586fd4ec466c0`; five CI jobs and successful canonical action 36159730401 / APPROVE 5835660379 | Documentation-only; prior 16:07 UTC cutoff is superseded here, not reclassified as feature acceptance |
| [#406](https://github.com/scanipy/scanipy/pull/406), source-custody prep extension | MERGED at `6f1ebc8720cac8f2bbba20a061c0cba7ca8ff792` from `b005eaa5e7081a3920a97b01be0281430f5ef74f`, identical tree `2a9d914d226f27d36a1111b2c1488068ceb9e4a1`; full 1,958/51, normal push, seven test checks and successful canonical APPROVE | Narrow #392 Done only. The three authored files remain byte-identical to `e3d318b3`; 64 focused, historical 1,313/51 and earlier 1,710/51 retain their original attribution. No actual acquisition, DB seal, operational authority or historical CMP-SNAP-05 AC completion |
| [#407](https://github.com/scanipy/scanipy/pull/407), typed observed transport | MERGED from `83b9ec6cc96e2d1283be87d12ea85de50ddef50b`, identical tree `01ad138a6e67b1816b5db6b35c3d37ed38d10954`; full 2,103/51, normal push, seven test checks and canonical action 36167975158 SUCCESS / APPROVE 5836718691 | Narrow #393 Done only; all five authored files unchanged from reviewed `b7dfaba`. Actual binding, flow, purity, semantic identity and G1 remain required. Prior `0929e47` full 2,039/51 and original 145 focused checks retain their own attribution |

The following local build-ahead table retains its earlier checkpoint; the
Revision 13 queue supersedes its completed/pending instructions:

| Issue / local-only scope | Retained checkpoint | Next acceptance action |
|---|---|---|
| [#391](https://github.com/scanipy/scanipy/issues/391), raw core observation kernel | `278734bc9482f46f8b48d48aef3867479a885a1b`; 168 focused checks, full local run 1,403 passed/48 skipped, normal hooks passed; scoped independent review | Integrate accepted main, verify current-head gates and submit for serialized canonical review. Exact CFG/CALL profile is intentionally narrower than real mapper output; no full IFDS/IDE or G1 claim |
| [#378](https://github.com/scanipy/scanipy/issues/378), occurrence storage | `fe61c9cdcf4ae56cf5c7fd682b3a73c3502f1808`; 89 dedicated real PostgreSQL checks passed/zero skips; full configured run 1,344 passed/140 optional skips; normal hooks passed | Obtain exact-head review/CI. Dedicated test database and restricted roles are not live app integration; actual accepted authority/source/native producers, decisions and API/UI remain required |
| [#397](https://github.com/scanipy/scanipy/issues/397), source-bound scalar semantics | Base `e6c4a2e26de4b195ee541670d76ee56f20fe6dc0` plus seven frozen uncommitted files. Compiler/declaration scope approved; raw `2a1043b0` corrected six genuine UUID-slot coercion failures; root 126 checks and independent 128 checks pass with scoped approval | Run current combined full suite, normal commit/current-main/remote gates. Earlier 500-case and 2,469/51 checks do not validate this newer slice. Actual native/source/model/authority/durable integration and full Java/Python scope remain unaccepted |
| [#398](https://github.com/scanipy/scanipy/issues/398), raw Git acquisition | Current `7dccd5e8ecef5a5bd3d4cada49d4d9152a0c373d`, tree `7791ee03c49cbd5b480b722d1e9e8d7743680a6a`, incorporates accepted `6f1ebc8` with all ten authored files unchanged; current full pending. Prior `c2c2078` full 2,211/51 remains scoped to that tree. Earlier offline `6dbbfec` 177 focused/1,746 full and transport `d3ce731` 130 focused on Python 3.11/3.12 plus 1,774/51 are retained | Complete fresh combined tests and exact-head remote gates. Preserve the earlier 1,726/51/one-deadline-failure run; no budget weakening, native Git, image build, online controller or SCM-origin authentication |
| [#399](https://github.com/scanipy/scanipy/issues/399), accepted-byte authority verifier | Reviewed 13-file `0f4d2dc`: 236 focused and 2,297 full passes/140 optional skips; normal gates. Inventory merge `58b552c` now has 309 combined focused passes, not a new whole-suite/native result | Operational verifier still refuses absent actual current authority/controller. Operator/root/admission installation, durable registry publication and launcher/API integration remain open |
| [#400](https://github.com/scanipy/scanipy/issues/400), runtime metadata and pure process evidence | `d51c5f33a0c929bd95be9107a1b46f73b5690652`, tree `233e603344d8391709df301b2a50eaa4177b8b33`; combined full 2,971/51. Pure PE codec source `601fef04` / tests `14178e56`: root/author 483 and corpus 480 overlapping checks pass, not additive. Earlier loader 235/1,793 and renderer 288/2,298 results retain their own scope | Remote gates remain pending. Corrected 1,477-line runtime-store design `42d31451` has scoped wire/replay approval; exact pure-journal API in progress, no store code. Capacity/installer qualification, parent DB orphan barriers, trusted factory/current anchors, kernel readers, Docker lifecycle/recovery, real authority and native integration remain required |

### Historical local delta — 17:45 UTC

This explicit update supersedes only the older pending-status statements above;
it does not reassign an old test result to a newer head or promote acceptance.

- #397: reviewed seven-file slice normally committed as
  `c4f85c530af0528e2e138da3c1260b1042c37b17`; accepted main `6f1ebc8`
  integrated at `f6903cfe7c3154001267b7a9bdec30c72a364675`, tree
  `d6f6bb8938944eb96bc03971e64012dbc937c26d`. All seven owned files unchanged.
  New configured full run `/tmp/scanipy-397-raw-main-combined-full.xml` is
  running. Finish it, integrate newer main, and obtain required remote gates.
- #398: `7dccd5e` full run passed **2,265/51**, zero failures, 275.96s
  (`/tmp/scanipy-398-r05-source-combined-full.xml`). Subsequent normal merge
  of accepted typed main is `3abf021886b4bfb00af67ca96117804a1709e169`, tree
  `bbbcd5527378e23fc7c66e8afa0aee3fb94ead0a`; owned ten files unchanged.
  Verify this new combined artifact and normal/remote gates. #398 stays open
  after an offline prep merge because online acquisition remains required.
- #400: root/peer approved exact structural-only journal API checkpoint
  `47731c42ef90efbdbadeadf5f1a7c510838786bd65dee0264feef21c04703ca1`
  after fixing raw/domain authority linkage, inclusive retained-byte limits,
  repeated-reference accounting and missing/unknown-output distinctions.
  Only `runtime_journal.py` and its unit tests are allocated/in progress.
  The actual FS store, physical reservation, current authority/owner-codec
  adapters, DB barrier, installer and Docker controller remain unimplemented.
- #407's review noted pending CI from its earlier snapshot; all tests finished
  at 17:40:36 and the checklist/links were updated before canonical success at
  17:42:06. Its optional linear-lookup indexing suggestion is a later measured
  optimization, not a blocker or a reason to alter the accepted five files.

At approximately 10:59 UTC on September 25 the canonical reviewer reported a
session limit, with a reported reset at **13:40 UTC / 18:40 Asia/Karachi**. This
was not GitHub API quota exhaustion or a guarantee of recovery. Recovery was
subsequently observed: #390's canonical action succeeded at 13:46 UTC and
#382's at 14:04 UTC and #389's at 14:28 UTC, all with final APPROVE. Those PRs
are now merged. Continue remaining candidates serially;
recheck exact heads, required tests, actual action success and the final APPROVE
verdict before each merge. Preserve any new corrective review findings.
Continue safe, assigned local work meanwhile; do not bypass review or describe
the full Black Hat goal as blocked while meaningful in-scope work remains.

Follow-ups from the #389 review, owned by root under #378: map its 130 pure
controls to current R07/R08 acceptance IDs before end-to-end acceptance; ensure
future adapters validate output proposals instead of trusting caller-constructed
dataclasses. Optional hygiene: replace three proven type-only assertions with
explicit narrowing guards. These are not new production permissions or evidence
that durable decision/API work has passed.

Follow-ups from the [#403 review](https://github.com/scanipy/scanipy/pull/403#issuecomment-5834988173),
owned by root under the future cutover scope: map the containment checks to
current `TST-AC-*` IDs before full component acceptance; consider a precise shared
fixture tuple annotation and `NoReturn` on unconditional compatibility refusals.
These nonblocking items are not implemented by this documentation update.
The review's pending CI-link observation was resolved before merge: all five
jobs in [CI36154521403](https://github.com/scanipy/scanipy/actions/runs/36154521403)
succeeded at `286d6b9`, and the canonical action also succeeded. Historical rows
and public development-default limitations remain unchanged; no app/DB rollout occurred.

The [#404 review](https://github.com/scanipy/scanipy/pull/404#issuecomment-5835302857)
optionally suggested removing parser limit revalidation on the premise that a
frozen dataclass cannot be mutated. Root disproved that premise using
`object.__setattr__`: the existing guard correctly refused an altered over-limit
policy. Keep that guard; this is a rejected optional suggestion, not an unresolved
requirement to weaken validation. Any private-snapshot cleanup needs separate
review. Pending CI checklist links were resolved before merge.

The [#406 first review](https://github.com/scanipy/scanipy/pull/406#issuecomment-5836335604)
and failed action 36164994933 remain evidence, not a discarded gate. The
[successful re-review](https://github.com/scanipy/scanipy/pull/406#issuecomment-5836441907)
accepted the unchanged three-file source-custody extension after the title/body
made prep scope explicit, mapped real tests and linked actual CI/Gate 3 results.
Historical AC-SNAP-05a/b were not claimed satisfied. Only narrow #392 is Done;
#378/#362 and full R08/R16 remain open. The optional traceability suggestion is
not an invented new approval blocker or permission to edit historical WBS here.

Immediate integration TODOs, not satisfied by these local checks:

- Preserve accepted typed observations, offline Git, CodeQL observations and
  occurrence storage; finish current-head gates for accepted-input verification,
  runtime helpers and the new scalar slice before real producer integration.
- Bind actual acquired source bytes to the accepted custody receipt and DB
  seal; preserve the acquisition trust distinction and irreversible retirement.
- Implement durable runtime evidence with explicit visible-prefix versus
  durable-ack semantics, immutable replay and registered spool ownership.
  Qualify physical block/inode/name and host-work capacity; neither `statvfs`
  nor a guessed scratch split proves reserved terminal/cleanup space.
- Add the parent DB's non-expiring runtime orphan barrier and exact recovery/
  cleanup release protocol before allowing capture retirement. Ordinary worker
  lease expiry is not evidence that a native descendant stopped using source.
- Implement the genuine current-anchor factory, installed runtime/kernel
  observations, bounded Docker lifecycle and actual authority admission.
  Pure loader/renderer/PE records and fixture keys cannot authorize a launch.
- Wire qualified accepted rule/model bytes, lossless native observations and
  the matched-call raw solver to durable raw detections before any identity
  operation; then verify final identities, decisions, signing and API/UI.
- Only after reviewed runtime/image readiness and explicit bounded-run approval,
  perform sequential real probes, all 844 uncached R05 sides, real nonempty
  core/Semgrep integration and fresh provenance/reproduction checks. Preserve
  the full Java/Python, CodeQL, comparator and G2/G3 requirements.

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
7.37 GiB available at that time, nearly full swap and 101.91 GiB free on the shared
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

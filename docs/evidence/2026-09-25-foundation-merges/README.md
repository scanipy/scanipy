# September 25 — reviewed foundation corrections

Scope: repository correction evidence, not Black Hat feature acceptance.
Snapshot main: `e79dc54d56a740ae49015b598e21074cc0beb2ac` on 2026-09-25 at 14:29:55 UTC.
Owner: root engineering coordinator, umbrella #362.

Every merged row below had the required tests and canonical `claude-review`
APPROVE checked at the exact head before a normal PR merge. These are links to
observed repository records, not an offline archive of the workflow logs.
Release evidence retention and tests on the final combined artifact remain
R17 obligations. No full R-task, C01–C18 claim, or shared gate is accepted here.

## Merged correction records

| PR / bounded scope | Reviewed head | Squash merge | Required check records |
|---|---|---|---|
| [#373](https://github.com/scanipy/scanipy/pull/373), fresh runtime dependency compatibility | `dc09a3d318a4fd7ced1b8b50d111ab228df54c52` | `89ed803defd738529cd6e99691055c474d805e8c` | [CI](https://github.com/scanipy/scanipy/actions/runs/36116205813), [supplemental Gate 3](https://github.com/scanipy/scanipy/actions/runs/36116428734), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36116205892) |
| [#372](https://github.com/scanipy/scanipy/pull/372), genuine typed corpus | `d9aabdb69fac6c65ef2ecf2b4677e94782ac76d5` | `c3444e715d289962d1787a3ad43ea75d868ffeff` | [CI](https://github.com/scanipy/scanipy/actions/runs/36117376484), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36117888421) |
| [#379](https://github.com/scanipy/scanipy/pull/379), bounded board queries | `1b97355528e68fbf0bc3c5a2d640167154b98110` | `e0dac3851851afbff1fad21a19bf9003776589f7` | [CI](https://github.com/scanipy/scanipy/actions/runs/36119452650), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36119452690) |
| [#368](https://github.com/scanipy/scanipy/pull/368), full-scope handoff/ledger/evidence | `c61895323744e6ded99649e9697af057113e3aff` | `2b9078bffeb9325b7826cc73df1a24f7b9afbebf` | [CI](https://github.com/scanipy/scanipy/actions/runs/36120689432), [reopened CI](https://github.com/scanipy/scanipy/actions/runs/36121062472), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36121062430) |
| [#383](https://github.com/scanipy/scanipy/pull/383), snapshot Python lock and byte gate | `04c140116a42126592b4329e3bfe66d673841e5c` | `85a96008f8ae2503351998ab8b6a80b4afdf0549` | [CI](https://github.com/scanipy/scanipy/actions/runs/36121981534), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36121981591), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36121981551) |
| [#375](https://github.com/scanipy/scanipy/pull/375), typed report consumer | `53e035ad1567961ef5f8e1c770b0ba3e5ddc6d94` | `cd62f5f457a13f89d3691d77af347f4cde562cf1` | [CI](https://github.com/scanipy/scanipy/actions/runs/36121862891), [reopened CI](https://github.com/scanipy/scanipy/actions/runs/36122255169), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36122255289) |
| [#371](https://github.com/scanipy/scanipy/pull/371), independent artifact metadata | `a1da17bb51c7e4d29c413f54620207620dc67d52` | `c54064424435b4c8e25b10a52e5a68f45764b278` | [CI](https://github.com/scanipy/scanipy/actions/runs/36122357038), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36122357005), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36122357014) |
| [#385](https://github.com/scanipy/scanipy/pull/385), occurrence/decision design | `e74914847205e61962ec97ba8814e9c1f045b29b` | `51da8a6fbbde6545ce7cb9f24c6554aea101c3df` | [CI](https://github.com/scanipy/scanipy/actions/runs/36122489350), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36122489330) |
| [#387](https://github.com/scanipy/scanipy/pull/387), fail-closed developer hooks | `9d5f8574f83e9d238951aa62592c3a5409d0d2dc` | `022365123d0a14127e2039dc005606a7401bc358` | [CI](https://github.com/scanipy/scanipy/actions/runs/36123526095), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36123526023) |
| [#369](https://github.com/scanipy/scanipy/pull/369), bounded canonical identity/budget foundation | `2cfbd32b45aae5ce98b6d000a77a8ac9959016ce` | `bcce692fa4377ab3cc21ff100370a7a7cb13a409` | [CI](https://github.com/scanipy/scanipy/actions/runs/36124379740), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36124379755), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36124379760) |
| [#388](https://github.com/scanipy/scanipy/pull/388), progress documentation/ledger | `7d085043a65275187e2e9b1cf62669245086b355` | `2709177afff1c78f06532e0298dd5ee4d608237f` | [CI](https://github.com/scanipy/scanipy/actions/runs/36124763427), [APPROVE](https://github.com/scanipy/scanipy/actions/runs/36124763511) |
| [#390](https://github.com/scanipy/scanipy/pull/390), Java static invocation safety | `16252b21db172b967f13a815ca9bd8fe3078dd19` | `8d38c06addc49f382b36d17fee4125fdf4628b3d` | [CI](https://github.com/scanipy/scanipy/actions/runs/36126058316), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36126058265), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36142432527) |
| [#382](https://github.com/scanipy/scanipy/pull/382), opt-in raw Joern transport | `2f0ebef5db636c14051efb3aa20980667b982a13` | `02933f1a08587a7f9f266d47320f5d614ade57ba` | [CI](https://github.com/scanipy/scanipy/actions/runs/36144380242), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36144380239), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36144557544) |
| [#389](https://github.com/scanipy/scanipy/pull/389), pure continuity/policy module | `4b5b5149f306b81a66b696b792a902fcf8aa6a4e` | `e79dc54d56a740ae49015b598e21074cc0beb2ac` | [CI](https://github.com/scanipy/scanipy/actions/runs/36146742685), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36146742856), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36147217350) |

### What this establishes—and does not

- #372 has 422 cases: 370 structural comparisons (270 stay / 100 flip),
  50 removals and two intentional failures. There are 468 fixture tree paths
  representing 384 distinct framed content digests, and 844 uncached case-side
  attempts are required. The seeds still repeat eight base topologies; case
  count does not establish independent topology diversity. Fixture purity/preconditions are
  expectations, not observed certificates. No corrected G0 has run.
- #375 has 76 controlled checker tests and verifies actual locked corpus bytes,
  policy content, candidate analysis revision and protected report history.
  The default history is empty; no G0 is invented. A valid report schema does
  not authenticate its producer or prove a real scan/purity/lifecycle observation.
- #371 preserves independent artifact verdicts and historical bytes; its
  final local suite was 1,015 passed / 48 skipped, plus isolated PostgreSQL
  checks. Consumer tests and a separate actual synthetic-graph four-way probe
  are not real Java/Python semantic acceptance. Merged #369 now makes the combined
  actual-producer/deadline regressions permanent. Source-only snapshot/final
  persistence, full environment production and async occurrence retention remain.
- #383 fixes the stale lock-byte declaration and adds missing Python runtime
  dependencies without changing tool/base pins. Final local suite: 1,043 passed /
  47 skipped. The resulting image has not been built, installed, promoted or
  published by this correction; a valid hash lock is not a working container.
- #379 has 95 hermetic checks. After quota reset, root used it to verify real
  project metadata and status transitions. It is bounded/fail-closed, not an
  atomic ownership lock. The root coordinator still serializes changes.
- #385 is a design-only contract, not schema/API/worker implementation. The
  pure module #389 is now merged after 130 controlled continuity tests, the
  combined configured suite (1,559 passed / 51 existing skips), normal hooks,
  all seven remote test checks and successful canonical APPROVE. Its production
  policy registry remains empty; no durable store/API workflow is enabled.
- #387 fixes both masked hook failures and declares yamllint 1.35.1. It has
  33 focused tests and a fresh declared full run of 1,180 passed / 48 skipped.
  The actual changed commit/push hooks passed; runtime image and full release
  acceptance remain separate.
- #369 adds 55 dedicated regression cases, including independent actual
  graph/slice classes, legacy-default ineligibility and time exhaustion as
  failed analysis. The combined local suite was 1,235 passed / 48 skipped.
  This validates the bounded existing-label canonical foundation, not richer
  R19 semantics, all R06 normalizations, universal canonicality or real G1/G2.
- #388 is documentation-only. Its historical cutoff at #387 is updated here;
  neither snapshot accepts a feature merely because a local branch has tests.

Narrow issues #365/#367/#363/#377/#381/#384/#364/#386/#376 and the earlier #370 are closed after
their reviewed corrections. #361/#362/#366/#374/#378 remain open for their
larger scope. GitHub auto-closed #378 when it parsed a closing keyword inside
a negated sentence in #385; root removed that wording, reopened #378 and
restored In Progress. This accidental closure is not acceptance evidence.

## Review-capacity checkpoint — not acceptance

Earlier read-only GitHub checks on September 25 found #382, #389 and #390
open at the exact historical heads below. All seven test checks succeeded; the separate
canonical actions failed because the reviewer reported a session limit.

| Candidate head | CI / supplemental checks | Failed canonical action |
|---|---|---|
| #382 `9035359e548ac210c3d101f24df76b7df2ebc32d` | [CI](https://github.com/scanipy/scanipy/actions/runs/36126040061), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36126040065) | [Review failure](https://github.com/scanipy/scanipy/actions/runs/36126625932) |
| #389 `2fd67cb58f2850dd0d0e8c0a4966ad1ee70fdbc0` | [CI](https://github.com/scanipy/scanipy/actions/runs/36126133600), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36126133376) | [Review failure](https://github.com/scanipy/scanipy/actions/runs/36126638167) |
| #390 `16252b21db172b967f13a815ca9bd8fe3078dd19` | [CI](https://github.com/scanipy/scanipy/actions/runs/36126058316), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36126058265) | [Review failure](https://github.com/scanipy/scanipy/actions/runs/36126622985) |

The earlier reported reset at 13:40 UTC was not itself recovery evidence.
The failed #390 comment's APPROVE word was not accepted. Later #390 action
36142432527 succeeded at 13:46:10 UTC with final APPROVE; merge followed at
13:48:29 UTC. #382 was combined with that reviewed main, retested (1,429 passed /
51 existing skips), pushed through normal gates, and independently reviewed in
successful action 36144557544 at 14:04:55 UTC; merge followed at 14:06:30 UTC.
Both squash trees were verified identical to their tested PR heads. Root read
the completed canonical verdicts and verified all seven checks before merging.
The #382 review's dependency table conflates #368 and #390; they are separate
merged PRs, both present. This factual note does not rewrite its verdict.
#389 then merged reviewed main without source conflicts. Its new head `4b5b514`
passed the configured full suite and all required checks; canonical action
36147217350 completed successfully at 14:28:11 UTC with final APPROVE, and merge
followed at 14:29:55 UTC. Root verified the squash tree equals the tested head.
#378 remains open/In Progress. The review's nonblocking acceptance-ID mapping,
future output-boundary validation and optional type-only assertion hygiene are
tracked in the handoff; they are not represented as implemented by this merge.
Continue remaining candidates serially with their own exact-head gates.
Local source/core/typed-CPG/Semgrep/store work is indexed in the current handoff,
not counted as merged evidence. No local test count fills a shared-gate PASS.

## Parser safety audit

Read-only audit of Joern `v4.0.554` source (tag resolves to
`cf59a329bf83063c096e1e803d608e5057d8bb95`), not an attestation that a release
archive's loaded classes match that source. No new target build or source
execution was launched to investigate these findings.

1. Java dependency fetching is disabled by default, but any nonempty
   `JAVASRC_FETCH_DEPENDENCIES` other than exact `no-fetch` enables it.
   `false` and `0` therefore enable fetching. The resolver can invoke Maven or
   Gradle project logic; network isolation alone cannot prohibit local builds.
   Sources: [AstCreationPass](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/passes/AstCreationPass.scala#L107),
   [MavenDependencies](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/x2cpg/src/main/scala/io/joern/x2cpg/utils/dependency/MavenDependencies.scala#L19),
   [GradleDependencies](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/x2cpg/src/main/scala/io/joern/x2cpg/utils/dependency/GradleDependencies.scala#L129).
2. The Java source parser checks for a `lombok` substring and may run trusted
   Delombok preprocessing by default. Child failures can leave incomplete
   transformed output while processing continues. This is not itself demonstrated
   execution of target Java methods/tests; no such result is claimed.
   Sources: [SourceParser](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/util/SourceParser.scala#L108),
   [Delombok](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/util/Delombok.scala#L40).
3. Exact static suffix: `--frontend-args --delombok-mode no-delombok`, not `--`.
   A broad arbitrary forwarding allowlist is unsafe. Sources:
   [frontend separator](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/x2cpg/src/main/scala/io/joern/x2cpg/frontendspecific/package.scala#L15),
   [Java options](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/Main.scala).
4. Default exclusions include `test/`; failed parses can be skipped. Process
   exit zero is not complete coverage. Disabling Delombok also does not supply
   generated members. Sources: [Java defaults](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/JavaSrc2Cpg.scala#L44),
   [AST omissions](https://github.com/joernio/joern/blob/v4.0.554/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/passes/AstCreationPass.scala#L66).

The now-merged #390 supplies #386's closed versioned Java profile and
value-aware invocation grammar for the shared worker/R05 route. Both parse and export must use
it. An explicit profile parameter is validation context, not authentication;
unprofiled direct scripts and other frontends remain outside that narrow proof.

Required follow-up: hermetic unsafe-override negatives; reviewed bounded real
scanner-only sentinel/process observations; descendant cancellation; file
coverage/error evidence; final Compose restrictions. Never execute an unsafe
target-build positive control. Missing generated/type/binding semantics remain
R19 fidelity work. Historical raw-v2 probes remain outside this new shared
profile guarantee and were not rerun or retroactively certified. R16 is not complete.

## Other active falsifiers and next actions

- Local-only checkpoint details are in the current handoff. #378's final
  dedicated PostgreSQL suite passed 89 checks with zero skips; #393/#394 and
  #391/#392 have scoped tested checkpoints. No count here certifies production
  source, accepted rule authority or a deployed scan. Optional skips remain
  explicit and suites from different branches are not summed into coverage.
- #395 contains legacy Git routes, but its first local checkpoint omitted the
  newly imported integrations package from the snapshot Docker COPY inventory.
  Read-only import-closure review caught this before publication. The corrected
  local checkpoint tests an assembled package without repository-path leakage;
  root independently reran its positive/missing-copy pair. The fresh suite
  passed 1,403 tests/51 existing skips; the older 1,401-test result is not
  substituted for it. Neither result is new-image evidence; no image was built.
- #396 local checkpoint passed 27 focused and 1,276 full-suite tests (51 optional
  skips), normal hooks and independent review. It makes new legacy scan requests
  explicitly unavailable while preserving historical schema/GETs. The user's
  app/database were not modified. Narrow isolated-mypy dependency and public
  default-password baseline corrections were reviewed; changed-password
  falsifiers still fail the actual secret hook. Containment is not cutover.
- #397/#398/#399 started as design work, not accepted producers: source-bound scalar
  value flow and per-rule isolation; bounded transport and verified no-checkout
  Git objects; immutable accepted bytes and durable current authority. Operational
  model adoption, independently installed trust and restore admission cannot be
  supplied by fixture keys or an agent's design approval. Fresh native evidence
  and final persistence/worker integration remain required.
- R11 native coverage follow-up: pinned Semgrep 1.175.0 source inspection shows
  core `scanned` includes targets that raise timeout/memory/parse errors. Its
  ordinary flag uses a nonempty applicable-rule list, not proof that every rule
  completed. Its core JSON writer omits skipped-path detail, and separate
  fixpoint-timeout evidence is inside optional profiling. Therefore a later
  adapter must validate actual intended rule/file accounting, all error and
  fixpoint-timeout channels, and exact supported profile behavior. Neither
  `scanned`, a progress counter, zero findings nor exit status alone certifies
  coverage. These are primary-source observations, not a native runtime test:
  [pinned scan handling](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/src/core_scan/Core_scan.ml#L713),
  [pinned JSON output](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/src/reporting/Core_json_output.ml#L749).
- R16 Git custody, newly confirmed by read-only code/guard inspection: the
  existing `tools/worker/secure_subprocess.py` Git allowlist checks only flag
  tokens, permitting arbitrary `-c` values and unlisted bare subcommands/URL
  forms. Its comment says the execution loop is not implemented, but
  `services/snapshot/worker.py` now calls real clone/checkout; its job parser
  validates field presence only and its environment leaves system Git config
  enabled. The separate default GitHub connector runner also inherits the
  environment, lacks a timeout/stream bound and selects `git` through PATH.
  No unsafe Git command was executed to verify this gap. Required correction:
  exact argument/value/protocol/environment controls and a reviewed source-only
  object extraction/capture producer, with no hooks, filters, builds, submodule
  execution or implicit helper commands. Do not enable the new workflow through
  these legacy paths or claim clone/checkout itself proves no execution.
- #378: an originally-open link could restore unchanged old suppression after
  resolved/reappeared/uncertain → open. The proposed correction binds link and
  per-dimension authorization to lifecycle generations. Required durable tests
  must include fresh links with old decisions, unrelated verdict/reference
  changes, repeated cycles, concurrency and immutable event-ID history.
- #384 (corrected by merged #387): pre-commit could mask a failed lint-staged result with a later success;
  pre-push could mask full-project mypy failure with a partial retry. Missing
  declared yamllint exposed the first path. Failed checks were rerun before
  earlier pushes; neither masking path is considered acceptable. The merged
  correction preserves all gates and verifies the fresh declared closure.
- #369 (merged): preserve actual four-class producers, explicit legacy-default
  rejection and deadline failures while adding richer graph semantics. New
  labels/roles require a separately versioned identity contract and evidence.
- #380: integrate reviewed current main and obtain canonical approval.
  #382 is now merged, but raw transport is not semantic mapping, call binding, matched returns or
  purity. R05 reports unavailable semantic observations honestly; it may not
  copy expected corpus labels into observed success fields.
- Before a corrected image or real campaign, recheck host resources and run
  bounded sequential startup/Java/Python probes. Source parser safety and
  packaging must be reviewed first; full 844-side evidence follows readiness.
- Preserve all remaining R01–R20 TODOs and exact submission scope. Stage-machine
  identity is confirmed; actual measured budgets/rehearsals, exact presentation
  date and separate release/image/video authority remain future inputs.

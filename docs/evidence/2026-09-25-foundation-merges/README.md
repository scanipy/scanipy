# September 25 — reviewed foundation corrections

Scope: repository correction evidence, not Black Hat feature acceptance.
Snapshot main: `6ae30df64678bf916062fa67dde98704d0c36153` on 2026-09-25 at 16:03:44 UTC.
Local verification cutoff: 16:07 UTC; later local work requires its own updated gates.
Owner: root engineering coordinator, umbrella #362.

Every merged row below had the required tests and canonical `claude-review`
APPROVE checked at the exact head before a normal PR merge. These are links to
observed repository records, not an offline archive of the workflow logs.
Release evidence retention and tests on the final combined artifact remain
R17 obligations. No full R-task, C01–C18 claim, or shared gate is accepted here.

## Merged correction records

| PR / bounded scope | Reviewed head | Merge commit | Required check records |
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
| [#401](https://github.com/scanipy/scanipy/pull/401), stage-machine/handoff reconciliation | `604d21cdecb80a7b113b701114ae8fda26f5e390` | `69f7f480e2bb04febec103b04d2b753924d3090a` | [CI](https://github.com/scanipy/scanipy/actions/runs/36148987761), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36148987748), [final verdict](https://github.com/scanipy/scanipy/pull/401#issuecomment-5834246883) |
| [#402](https://github.com/scanipy/scanipy/pull/402), fail-closed legacy Git acquisition | `b25c180008ea761a10bb032d9d2275ad7bd730c7` | `cfadaa238d22bfdfce64b3ff60e396bd18dda934` | [CI](https://github.com/scanipy/scanipy/actions/runs/36152183209), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36152182852), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36153520147), [final verdict](https://github.com/scanipy/scanipy/pull/402#issuecomment-5834860540) |
| [#403](https://github.com/scanipy/scanipy/pull/403), legacy application containment | `286d6b9d95c1a8110ac0774ad43f206b16cd8648` | `4cf10d015a4b9ce8c96a93601a2e30588265e1f1` | [CI](https://github.com/scanipy/scanipy/actions/runs/36154521403), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36154521435), [final verdict](https://github.com/scanipy/scanipy/pull/403#issuecomment-5834988173) |
| [#404](https://github.com/scanipy/scanipy/pull/404), bounded Semgrep observations | `ed55bfc833be031934be079dfa47916ff3e1f29b` | `6ae30df64678bf916062fa67dde98704d0c36153` | [CI](https://github.com/scanipy/scanipy/actions/runs/36156963079), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36156963061), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36156963009), [final verdict](https://github.com/scanipy/scanipy/pull/404#issuecomment-5835302857) |

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
- #401 reconciles the confirmed presentation-machine identity and prior
  foundation evidence. Its five CI jobs and successful review do not establish
  stage budgets, offline readiness or any C01–C18 claim.
- #402 refuses generic Git before argument traversal/resolution and default
  snapshot/provider acquisition before source/credential staging. Its missing
  integrations Docker COPY correction is included. #403 removes the separate
  legacy app's native scan path, refuses new scans and preserves historical
  reads/schema. These commits do not implement safe acquisition or the actual
  asynchronous scan workflow, build an image, or alter the user's running app/DB.

Narrow issues #365/#367/#363/#377/#381/#384/#364/#386/#376/#395/#396/#394 and the earlier #370 are closed after
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
Local source/core/typed-CPG/store work is indexed in the current handoff,
not counted as merged evidence. The later #404 parser merge is recorded
separately below. No local test count fills a shared-gate PASS.

The later #401 merge followed at 14:50:36 UTC. #402's first
[canonical action36152182986](https://github.com/scanipy/scanipy/actions/runs/36152182986)
failed with REQUEST-CHANGES solely for pending CI/checklist state. No product
change was requested or made between that failure and the same-head successful
action36153520147/final APPROVE. Merge followed at 15:24:42 UTC. This is a
separate failure/recovery record, not the earlier reviewer session-limit issue.
#403 merged at 15:44:10 UTC after all five exact-head CI jobs and its successful
canonical action. The review's pending-CI-link observation was resolved before
merge; the run above is the actual resolved evidence, not an assumed future pass.

Nonblocking #403 follow-ups remain root-owned: map containment tests to current
`TST-AC-*` IDs before full component acceptance, consider precise fixture tuple
annotations, and use `NoReturn` for unconditional compatibility refusals where
appropriate. They are not implemented by this evidence update. The existing
public development-default credential limitation remains explicit. No full
CMP-ORCH-03, R08/R16 or Black Hat claim was closed by narrow #396.

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

Task-local XML paths below identify diagnostic records, not a committed immutable
acceptance archive. Final evidence retention and combined-artifact gates remain required.

- Local-only checkpoint details are in the current handoff. #378's final
  dedicated PostgreSQL suite passed 89 checks with zero skips; #393 and
  #391/#392 have scoped tested checkpoints. No count here certifies production
  source, accepted rule authority or a deployed scan. Optional skips remain
  explicit and suites from different branches are not summed into coverage.
- #395, now merged through #402, contained legacy Git routes, but its first local checkpoint omitted the
  newly imported integrations package from the snapshot Docker COPY inventory.
  Read-only import-closure review caught this before publication. The corrected
  pre-merge checkpoint tests an assembled package without repository-path leakage;
  root independently reran its positive/missing-copy pair. The fresh suite
  passed 1,403 tests/51 existing skips; the older 1,401-test result is not
  substituted for it. Neither result is new-image evidence; no image was built.
- #396's earlier local checkpoint passed 27 focused and 1,276 full-suite tests (51 optional
  skips), normal hooks and independent review. It makes new legacy scan requests
  explicitly unavailable while preserving historical schema/GETs. The user's
  app/database were not modified. Narrow isolated-mypy dependency and public
  default-password baseline corrections were reviewed; changed-password
  falsifiers still fail the actual secret hook. The accepted-main combined suite
  later passed 1,646/51 before reviewed #403 merged. Containment is not cutover.
- #397/#398/#399 started as design work, not accepted producers: source-bound scalar
  value flow and per-rule isolation; bounded transport and verified no-checkout
  Git objects; immutable accepted bytes and durable current authority. Operational
  model adoption, independently installed trust and restore admission cannot be
  supplied by fixture keys or an agent's design approval. Fresh native evidence
  and final persistence/worker integration remain required.
- #397 projection review retained genuine failed rejection checks:
  `/tmp/scanipy-397-projection-review-red.xml` has 13 failures on the original
  source. The first correction passed 147 dedicated checks; the next review
  reproduced eight further failures in
  `/tmp/scanipy-397-projection-closure-wrapper-red.xml`. The owner reported 368
  marked checks passing after full FILE/AST/wrapper correction, but root then
  reproduced four scope-multiplicity/order failures in
  `/tmp/scanipy-projection-root-scope-red.xml` at source digest prefix `298de24`.
  The narrow correction then passed 387 selected checks; root independently
  reran the same four negatives successfully (1.55s,
  /tmp/scanipy-projection-root-scope-green.xml). Corpus independently reread
  the correction and reran 206 dedicated tests (zero skips/failures,46.01s,
  /tmp/scanipy-397-projection-corpus-final-review.xml); root and corpus approve
  source raw SHA prefix74ab0618. Root's configured full suite then passed2,469/51
  in263.41s with no failures (/tmp/scanipy-397-projection-full.xml). Normal commit,
  current-main and remote gates remain pending. Constructed
  native fixtures never establish a real Joern producer, fidelity or G1.
- #398 final shared-transport path correction `d3ce731` passed 130 focused
  checks on each of Python 3.11 and 3.12 and the configured full suite
  (1,774 passed/51 existing skips), with scoped review and normal gates.
  This follows the separate offline producer checkpoint; preserve its prior
  deadline-failing full run rather than replacing it with the later green run.
  No online Git/egress controller or native source command was enabled.
- #399's inventory integration at `58b552c` now has 309 combined focused
  passes. Its prior 2,297/140 full result remains tied to the earlier verifier
  tree. The public operational launcher still refuses; test keys, a supplied
  pin or the low-level loader do not establish current durable authority.
- #400's pin-relative loader `5b7dddf` has 235 focused checks including the
  independent external cause/context falsifier and 1,793/51 configured full
  verification, before later transport/renderer integration. The original
  `/tmp/scanipy-runtime-profiles-root-context-configured-before.xml` failure is
  retained; the scoped fix preserves primary exceptions and prior context.
  The pure renderer's author, corpus and root each passed the same 288 checks;
  these are not additive cases or actual Docker-parser/runtime observations.
  Combined accepted-main/transport/loader/renderer tests then passed 2,298 with
  51 existing skips in160.34s (/tmp/scanipy-400-renderer-combined-full.xml), and
  renderer commit af75910 passed normal hooks. Remote gates remain pending. Actual factory,
  current trust anchors, journal/outcome storage, kernel observers, supervised
  controller/recovery and operational admission remain required.
- #394's final combined candidate `ed55bfc` passed 1,840/51 with no failures;
  actual normal push passed and PR #404 had all seven remote test checks green
  ([CI](https://github.com/scanipy/scanipy/actions/runs/36156963079),
  [Gate3](https://github.com/scanipy/scanipy/actions/runs/36156963061)). Canonical
  action36156963009 completed successfully with APPROVE before the16:03:44 UTC
  merge at6ae30df; root verified the entire merged tree matches the reviewed head.
  Only narrow #394 is Done, not full R08/R11/R16 or native coverage/reproduction.
  The optional review suggestion to remove limit revalidation relied on an
  incorrect immutability premise: `object.__setattr__` changed the frozen policy
  and the existing guard correctly rejected it. Root retained the guard; any
  private-snapshot refactor needs separate review. CI checklist links were
  resolved before merge, not deferred as a failing requirement.
- #392's accepted-main integration `c5eaa472` preserves its three reviewed
  authored files byte-identically and passed1,710/51 with no failures in151.17s
  (/tmp/scanipy-392-containment-combined-full.xml). Current-main integration,
  normal push and exact-head remote review remain required; this is local-only
  filesystem custody, not SCM authenticity or durable source admission.
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
- R16 Git custody, historical defect confirmed by read-only code/guard inspection:
  the former `tools/worker/secure_subprocess.py` Git allowlist checked only flag
  tokens, permitting arbitrary `-c` values and unlisted bare subcommands/URL
  forms. Its stale comment described an unimplemented loop while the snapshot
  worker already used clone/checkout and inherited system Git configuration.
  Default connector runners also had ambient/unbounded execution. No unsafe Git
  command was executed to verify the gap. Merged #402 now refuses these default
  routes, and #403 contains the separate legacy app route. Preserve this history
  without claiming the old guard remains active. Required next work is actual
  reviewed source-only object extraction/capture, closed transport/runtime and
  online egress authority, with no hooks, filters, builds, submodules or implicit
  helpers. Disabled checkout is not safe acquisition or scan functionality.
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
- #380: local `652f1ee` now incorporates accepted main `4cf10d0`; nine
  non-process controls, targeted lint/type checks and normal commit gates passed.
  Producer/test bytes are unchanged from the earlier reviewed local source.
  The refreshed full suite passed1,700/51 in237.52s with no failures/errors
  (/tmp/scanipy-r05-containment-combined-full.xml). Normal push and remote
  canonical gates remain pending; the prior1,613/51 full result is not
  reassigned to this new tree.
  #382 is now merged, but raw transport is not semantic mapping, call binding, matched returns or
  purity. R05 reports unavailable semantic observations honestly; it may not
  copy expected corpus labels into observed success fields.
- Before a corrected image or real campaign, recheck host resources and run
  bounded sequential startup/Java/Python probes. Source parser safety and
  packaging must be reviewed first; full 844-side evidence follows readiness.
- Preserve all remaining R01–R20 TODOs and exact submission scope. Stage-machine
  identity is confirmed; actual measured budgets/rehearsals, exact presentation
  date and separate release/image/video authority remain future inputs.

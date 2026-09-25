# September 25 — reviewed foundation corrections

Scope: repository correction evidence, not Black Hat feature acceptance.
Historical snapshot main: `1b29100ad9c96ebab9a4ac1a439fc2a5b19ac2ee` on 2026-09-25 at 17:42:32 UTC.
Revision 11 retains the 17:29 UTC local snapshot and explicit 17:45 update below;
later local work requires its own updated gates.
Revision 12 appends the 2026-09-25 **19:00 UTC** cutoff below, based on accepted
Revision 11 main `d4ad0c0b692cef4539d5333c60066cdcedecfb4e`, with a separately
identified post-cutoff update. Earlier pending statements remain historical
observations, not instructions to repeat finished work.
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
| [#405](https://github.com/scanipy/scanipy/pull/405), Revision 10 handoff | `90a89c9500f5004d2028b0b4b6b586fd4ec466c0` | `2ee3fc026a5f77894355470922a5f399a330f4d6` | [CI](https://github.com/scanipy/scanipy/actions/runs/36159730381), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36159730401), [final verdict](https://github.com/scanipy/scanipy/pull/405#issuecomment-5835660379) |
| [#380](https://github.com/scanipy/scanipy/pull/380), evidence-backed R05 campaign producer | `9be0579cd745fff4c4115c1f241a93926113a9be` | `3e2773e2a1f6578c2a712a1b85b5a45d172503eb` | [CI](https://github.com/scanipy/scanipy/actions/runs/36161586241), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36162235882), [final verdict](https://github.com/scanipy/scanipy/pull/380#issuecomment-5835971061) |
| [#406](https://github.com/scanipy/scanipy/pull/406), bounded local source-custody prep | `b005eaa5e7081a3920a97b01be0281430f5ef74f` | `6f1ebc8720cac8f2bbba20a061c0cba7ca8ff792` | [CI](https://github.com/scanipy/scanipy/actions/runs/36164994819), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36164994869), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36165792723), [final verdict](https://github.com/scanipy/scanipy/pull/406#issuecomment-5836441907) |
| [#407](https://github.com/scanipy/scanipy/pull/407), lossless typed observed transport | `83b9ec6cc96e2d1283be87d12ea85de50ddef50b` | `1b29100ad9c96ebab9a4ac1a439fc2a5b19ac2ee` | [CI](https://github.com/scanipy/scanipy/actions/runs/36167975265), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36167975015), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36167975158), [final verdict](https://github.com/scanipy/scanipy/pull/407#issuecomment-5836718691) |

### Explicit later update — 17:45 UTC

- #407 merged at17:42:32 with tree `01ad138a6e67b1816b5db6b35c3d37ed38d10954`
  identical to reviewed83b9ec6. Full2,103/51 and normal push passed; all seven
  test checks completed before canonical SUCCESS/final APPROVE. The review's
  earlier pending-CI/checklist condition was resolved before that success.
  Narrow393Done only; source semantics and fullR19/G1 remain open. Public
  lookup indexing is an optional future measured optimization, not a defect
  correction required for this merge.
- Scalar c4f85c5 is now normally committed, with accepted-main integration
  f6903cf; its full run is still in progress. Git7dccd5e full passed2,265/51
  in275.96s; subsequent typed-main3abf021 needs fresh combined checks. Their
  older pending statuses below are the explicit17:29 checkpoint, not current
  instructions to redo already completed commits/tests.
- Later pure-journal API review found and corrected a generic raw/domain hash
  comparison that was wrong for execution authorization and undefined for
  admission. Four raw links and two explicit owner-dependent obligations are
  now separate. Final API checkpoint47731c42 also fixes inclusive total-byte
  accounting, repeated-reference charges and missing/unknown stream summaries.
  Root/peer approved only that pure design and allocated two pure code/test
  files. No filesystem capacity, durable store, DB/current authority, native
  controller or full runtime acceptance follows.

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

Additional accepted scopes:

- #405 merged at 16:21:50 UTC. Its full backlog and states are preserved;
  Revision 11 updates evidence/next actions, not acceptance or the milestone DAG.
- #380 merged at 16:49:57 UTC with reviewed tree
  `27b6a03d69671906cca9f6f97c4ec1148ab1a14b`. The exact `9be0579` full run
  passed 1,894 tests / 51 existing optional skips
  (`/tmp/scanipy-r05-revision10-combined-full.xml`). No fresh 844-side campaign,
  corrected G0, detection/purity/lifecycle or full environment acceptance is
  established by the five-file producer merge. #374 remains open.
- #406 merged at 17:20:34 UTC with tested tree
  `2a9d914d226f27d36a1111b2c1488068ceb9e4a1`, identical to `b005eaa`.
  Its full run passed 1,958 / 51 existing optional skips, reported elapsed
  271.58s (`/tmp/scanipy-392-r05-combined-full.xml`; XML suite time 271.463s).
  All three authored files remain identical to scoped-reviewed `e3d318b3`.
  This is bounded no-follow custody/readback, not actual Git acquisition,
  a database seal, current authority, an installed runtime or scan completion.
  Narrow #392 alone is Done.

Narrow issues #365/#367/#363/#377/#381/#384/#364/#386/#376/#395/#396/#394/#392/#393 and the earlier #370 are closed after
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
Local core/typed-CPG/occurrence-store work is indexed in the current handoff,
not counted as merged evidence. Source custody is now merged separately in
#406. The later #404 parser merge is recorded
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

#380's historical [REQUEST-CHANGES action36119641485](https://github.com/scanipy/scanipy/actions/runs/36119641485)
is retained. The final review confirmed its dependency/contract blockers were
resolved by accepted prerequisite merges, including the Java observer and
canonical budget contract. The final five-file producer delta was reviewed on
its own exact head; no old failed action became approval.

#406's [first action36164994933](https://github.com/scanipy/scanipy/actions/runs/36164994933)
failed with [REQUEST-CHANGES](https://github.com/scanipy/scanipy/pull/406#issuecomment-5836335604)
over prep/component scope and missing exact CI links. The same code, tests and
contract were resubmitted with a precise prep title/body, actual test mapping
and successful CI/Gate 3 links. The later action36165792723 and final APPROVE
5836441907 succeeded before merge. DECISION-BHMEA-01 and the existing prep
workflow explain the scope; no gate was bypassed, no historical AC-SNAP-05a/b
completion was claimed, and no historical WBS status was changed. The optional
traceability suggestion remains optional, not a new missing-authority claim.

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
  #391 have scoped tested checkpoints, while narrow #392 is now merged. No count here certifies production
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
  in263.41s with no failures (/tmp/scanipy-397-projection-full.xml). That result
  belongs to the earlier projection tree, not the later compiler/raw slice. Constructed
  native fixtures never establish a real Joern producer, fidelity or G1.
- #397's later base `e6c4a2e26de4b195ee541670d76ee56f20fe6dc0` has seven frozen
  uncommitted files at this cutoff. Compiler/declaration files have scoped
  approval: `bound_rules.py` SHA256
  `085a3bce52a33a951412025c002e84131866a29b24a9262d279df2c1f5aa3dc9`
  and projection SHA256
  `6cef9ac304db056f8815585f5e253a7b03aa46a22740cf7d80765c7e13c18667`.
  Root then preserved six genuine UUID-slot coercion failures at raw source
  `1c161ae7` in `/tmp/scanipy-397-root-binding-shape-red.xml`. The corrected
  raw source SHA256 is
  `2a1043b0ddde50b1cb64b3a6dd4baaa31d2a9e811852d1e60b62abfe3e319b2b`;
  it snapshots original exact owner-schema slots rather than repairing UUID
  strings. Root's 126 checks passed (34.380s XML suite time,
  `/tmp/scanipy-397-root-binding-final.xml`). Corpus independently read the full
  source/tests/contract and passed 128 checks (56.214s,
  `/tmp/scanipy-397-raw-corpus-corrected.xml`): 120 repository cases, the same
  six root regressions and two multi-entry/shared-helper controls. These are
  overlapping selections, not additive tests. The peer's earlier 127-pass /
  one-failure run (`/tmp/scanipy-397-raw-corpus-final.xml`) used an invalid
  helper-sink fixture, correctly rejected before solving; it is not a product
  defect and remains separate from the genuine six-failure record.
  Scoped compiler/raw approval is not current-tree whole-suite, normal commit,
  remote, native/model/authority or durable acceptance. Earlier 500-case and
  2,469/51 results stay with their earlier heads. Full Java/Python semantics,
  native fidelity and G1 remain unaccepted.
- #398 final shared-transport path correction `d3ce731` passed 130 focused
  checks on each of Python 3.11 and 3.12 and the configured full suite
  (1,774 passed/51 existing skips), with scoped review and normal gates.
  This follows the separate offline producer checkpoint; preserve its prior
  deadline-failing full run rather than replacing it with the later green run.
  No online Git/egress controller or native source command was enabled.
- #398's accepted-main refresh `7dccd5e8ecef5a5bd3d4cada49d4d9152a0c373d`
  has tree `7791ee03c49cbd5b480b722d1e9e8d7743680a6a`. All ten authored files
  remain unchanged after integrating accepted `6f1ebc8`. Its fresh full run
  is pending at this cutoff; the 2,211/51 result belongs only to prior
  `c2c2078c14b6e9aac58068d8360b2cb1786b495e`. Remote gates and actual runtime/
  acquisition authority remain required.
- #393's current `83b9ec6cc96e2d1283be87d12ea85de50ddef50b` has tree
  `01ad138a6e67b1816b5db6b35c3d37ed38d10954` after accepted `6f1ebc8` integration.
  Full verification passed 2,103 / 51 existing optional skips, reported
  elapsed 285.47s (`/tmp/scanipy-393-source-combined-full.xml`; XML suite time
  285.368s). The actual push was running with no PR at the cutoff. Prior
  `0929e47` full 2,039/51 and normal-push success are not this head's remote
  evidence. Observed graph transport is not source semantics or a live producer.
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
  renderer commit af75910 passed normal hooks. The later local
  `d51c5f33a0c929bd95be9107a1b46f73b5690652` includes the pure process-evidence
  codec and passed 2,971/51 combined full verification. Source SHA256
  `601fef04b641b28c6f7e3abe948490bd7507287c103194a42b2cc7f943ac0fe8`
  and test SHA256
  `14178e56d736b301715941bebe3da051d8482f5fbb3f0ff7d061b01be844628a`
  have scoped review: root and author passed the same 483-case selection;
  corpus passed the overlapping 480 selection. These are not additive.
  `/tmp/scanipy-process-evidence-root-path-red.xml`,
  `/tmp/scanipy-process-evidence-corpus-loss-red.xml` and
  `/tmp/scanipy-process-evidence-owner-loss-red.xml` preserve the path and fitting-loss-
  omission failures fixed before approval. Root final evidence is
  `/tmp/scanipy-process-evidence-root-final.xml` (483 passed, 3.79s).
  Pure PE serialization is not durable storage or runtime authority.
- The corrected 1,477-line runtime-store design SHA256
  `42d31451bade18ddfe8f488527e4f033cdc618baf25fa3d1ce5af10ca6d98b39`
  has scoped wire/state/replay review approval. It distinguishes verified
  visible readback from writer-acknowledged durability, immutable retries,
  registered spool ownership and sticky recovery/orphan state. The exact
  pure-journal API is still being specified; no store implementation exists.
  Required six-role authority linkage must use actual owning adapters and
  distinguish execution-authorization domain digests from raw artifact hashes;
  missing admission raw-digest fields cannot be invented. Physical capacity
  qualification, installer/work isolation, parent DB orphan barriers, current
  trust anchors/factory, kernel observers, supervised Docker lifecycle/recovery
  and actual operational authority remain unresolved. No guessed 64 MiB slot
  split, free-space sample, model constructor or design approval enables a run.
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
  (/tmp/scanipy-392-containment-combined-full.xml). That earlier local result
  remains historical; the later `b005eaa` 1,958/51 and accepted #406 merge are
  recorded above. Custody still does not prove SCM authenticity, DB admission
  or protection against a hostile process with the same OS identity.
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
- #380: earlier local `652f1ee` incorporated accepted main `4cf10d0`; nine
  non-process controls, targeted lint/type checks and normal commit gates passed.
  Producer/test bytes are unchanged from the earlier reviewed local source.
  The refreshed full suite passed1,700/51 in237.52s with no failures/errors
  (/tmp/scanipy-r05-containment-combined-full.xml). It is not the final accepted
  `9be0579` tree: the later 1,894/51, normal push and successful remote review
  are recorded above. Neither the prior 1,613/51 nor 1,700/51 is reassigned.
  #382 is now merged, but raw transport is not semantic mapping, call binding, matched returns or
  purity. R05 reports unavailable semantic observations honestly; it may not
  copy expected corpus labels into observed success fields.
- Before a corrected image or real campaign, recheck host resources and run
  bounded sequential startup/Java/Python probes. Source parser safety and
  packaging must be reviewed first; full 844-side evidence follows readiness.
- Preserve all remaining R01–R20 TODOs and exact submission scope. Stage-machine
  identity is confirmed; actual measured budgets/rehearsals, exact presentation
  date and separate release/image/video authority remain future inputs.

## Revision 12 — explicit 19:00 UTC cutoff, September 25

This is a bounded status/evidence update, not a new acceptance decision. The
accepted documentation base is `d4ad0c0b692cef4539d5333c60066cdcedecfb4e`
(Revision 11, PR #408). The candidates below are **not added to the merged
correction table**. A completed local check, normal push or green test workflow
does not replace exact-head canonical SUCCESS/final APPROVE. Running work has
no result at this cutoff; later completion requires a separately dated update.
Local XML and external-test paths identify reproducible diagnostic records,
not a public immutable archive of raw evidence. Counts from overlapping runs
or different trees are not summed into coverage.

### Publication and combined-tree checkpoints

| Scope / exact candidate | Observed checks at this cutoff | Still pending / scope boundary |
|---|---|---|
| Git source preparation, [PR #409](https://github.com/scanipy/scanipy/pull/409), `acbd9d6a517505efb2514dd922e5f6f03cf1a12a`, tree `bd07d391a05c5b70947074d213b3114d045cdb90` | Configured full **2,437 passed / 51 existing skips**, reported 306.01s; normal push passed. Corrected [CI 36176023679](https://github.com/scanipy/scanipy/actions/runs/36176023679) completed all five jobs SUCCESS, final completion 18:57:15 UTC. | [Canonical review 36176791343](https://github.com/scanipy/scanipy/actions/runs/36176791343) was RUNNING. No merge or online/native acquisition acceptance is inferred. |
| Occurrence-store preparation, [PR #411](https://github.com/scanipy/scanipy/pull/411), `e08ac41c0dd7b9d7e623a707661ddd1888abc938`, tree `27d12120b1410816abf24892d2a5a86e2c7caea7` | This correction is only 14 documentation lines over `2fec34db554361e97e67c92722172f7414ba5d24`; implementation bytes are unchanged. The earlier `2fec34d` full run passed **2,287 / 51 existing skips**, reported 379.83s, including **89 actual PostgreSQL checks with zero skips** (`/tmp/scanipy-378-revision11-full-with-postgres.xml`). Earlier [CI 36173529503](https://github.com/scanipy/scanipy/actions/runs/36173529503) and [Gate 3 36173529509](https://github.com/scanipy/scanipy/actions/runs/36173529509) completed all eight checks successfully. | Corrected normal push and current-head remote gates remain pending. The documentation records CLAR-BHMEA-02 and the still-missing finalization bridge; no workflow completion or retrospective current-head test result is claimed. |
| Qualified-rule codec, `6ae81ad246fc289f1d5e820ddc54f0884ba742a4`, tree `0cbc5d80c3dfb58dd2fe20b89090bb67335e09a4` | Focused **192 / 0 skips** (166 owned cases plus 26 ledger checks); configured full **2,269 / 51 existing skips**, reported 294.11s, `/tmp/scanipy-rule-codec-revision11-full.xml`. | No PR yet. This is bounded byte/identity/model decoding, not accepted publication, source analysis, tabulation or G1. |
| Shared runtime inventory, `980c5eff3501476e82f0303cc3eac365b500c94b`, tree `5eae2fef93c2e82936a3b42dd122896d0183c119` | Corrected module **99 / 0 skips**; independent **107 / 0 skips** (99 repository plus eight controlled external checks). Configured full **2,202 / 51 existing skips**, reported 287.66s, `/tmp/scanipy-runtime-inventory-corrected-full.xml`. | No PR yet. Final ancestor equality uses the reviewed identity/security projection; full measured-root, descendant and runtime-leaf stamps remain. Installed trust, immutable mounts, controller and native runtime admission are not established. |
| CodeQL observations, original own-file checkpoint `b907851e4e739492a6410974030d7fca759f0724`; combined `93ae0aaf5042c5739f2cd7b6425f00fb0950a8cd`, tree `2d44060ef50d7a1523cb43327ce48a1ac2d21e7d` | Original scope is exactly three files / 3,518 added lines. Independent corrected **440 / 0 skips** (427 repository plus 13 unchanged external checks); source SHA256 prefix `e2ace77d`. Combined head adds the exact reviewed `acbd9d6` dependency without changing those three files. | Its **first combined full suite was RUNNING**, with no result yet. No PR, native CodeQL invocation, query-pack acceptance, source custody or R13/G2 completion follows from the pure observation codec. |
| Pure runtime journal, `653d89d8d9bd5f5e501a8b03a8b0fc3db87a19fd` to combined `0dbee6ef97409b9dda7fcc38545595edefc82348`, tree `f87caca5de1a86fa23255db658b206ded74e40dc` | The five-file pure journal checkpoint has **331 / 0 skips** on both Python 3.11 and 3.12, with independent peer checks. Combined main plus the three-file inventory correction passed **434 focused / 0 skips**, reported 20.06s. | No new combined full or push. These are pure structural records and validation, not filesystem storage, durability acknowledgement, Docker/controller execution or current authority. |
| AL-02 command codec, source SHA256 prefix `bc361a8f`, two new files | Frozen implementation under independent review. The completed 291-case result is explicitly dated after this cutoff below, not reassigned to 19:00. | Normal commit was still pending. No SQL, permission, signature verification, live ledger, receipt or full AL-02 acceptance is implemented by this input-structure-only slice. |
| Source-bound scalar foundations, `c8fb75cff9a12868f0acf341cbc36475103c9547` | Configured full **3,365 / 140 explicit skips**, reported 467.67s. Its actual tree `d6f6bb8938944eb96bc03971e64012dbc937c26d` is identical to `f6903cfe7c3154001267b7a9bdec30c72a364675`; the test result is not reassigned to changed source. | Remote prerequisite integration and gates remain pending. Pure modeled Python evidence does not establish Java execution, real Joern/source association, installed/current authority, durable production delivery or G1. |

### Explicit later observations — after the 19:00 cutoff

- **19:05:08 UTC — #409 merged:** main
  `595484bd7bd81e3a1761c727edf5d38b5d736930` has the exact reviewed `acbd9d6`
  tree `bd07d391a05c5b70947074d213b3114d045cdb90` (verified by Git tree/diff).
  [Canonical action 36176791343](https://github.com/scanipy/scanipy/actions/runs/36176791343)
  completed SUCCESS with [final APPROVE](https://github.com/scanipy/scanipy/pull/409#issuecomment-5837964794),
  all five corrected-head test jobs were green, and the full checklist was
  checked before the exact-head guarded merge. Root read the complete final
  review and checked the action's parsed APPROVE. Prior failed reviews remain
  preserved. #398/#362 stay open; online acquisition, native runtime, DB sealing
  and delivered scan integration are not accepted by this offline/transport slice.
- CodeQL's first combined full run on `93ae0aa` subsequently completed:
  **2,864 passed / 51 existing skips**, zero failures/errors, reported 311.53s,
  `/tmp/scanipy-410-codeql-git-combined-full.xml`. This does not alter its RUNNING
  state at the strict cutoff or establish normal push, remote CI, canonical
  approval, native CodeQL execution or R13 acceptance.
- AL-02's independent 291-case result is timed below. After that review, normal
  commit `66607b9537242d7ca05c93b2da03722b841dd83c` passed all applicable source
  hooks: exactly two new files / 1,615 added lines. No full run or push had
  followed; the local commit remains an input-structure-only checkpoint.

### Contrary results and exact correction boundaries

- Git PR #409 retains its [initial failed canonical action
  36171909118](https://github.com/scanipy/scanipy/actions/runs/36171909118) and
  [review comment 5837245158](https://github.com/scanipy/scanipy/pull/409#issuecomment-5837245158).
  The corrected CI success and review running at the 19:00 cutoff do not relabel
  that failure. Its later successful review/merge is recorded separately above.
- Occurrence PR #411 retains [failed canonical action
  36173529725](https://github.com/scanipy/scanipy/actions/runs/36173529725) and
  [comment 5837461311](https://github.com/scanipy/scanipy/pull/411#issuecomment-5837461311).
  The CLAR/finalization documentation correction does not implement the missing
  bridge, resolve the larger issue or convert the old-head checks into a new
  canonical verdict.
- Runtime inventory first reported **72 passed / one `changed` failure** in
  `/tmp/scanipy-runtime-inventory-main-focused.xml`; the exact changing ancestor
  was not observed. An unchanged repeat passed all 73. Separately controlled
  sibling-file/directory changes reproduced **six pass / two fail** in
  `/tmp/scanipy-runtime-inventory-peer-ancestor-red.xml`, while measured roots
  and content stayed unchanged. This demonstrates that specific overstrict
  ancestor comparison, not the retrospective cause of the first unlocalized
  failure. The approved correction compares ancestor device/inode/full-mode/
  UID/GID only, retaining full nine-field observations and every full measured
  root/descendant/leaf check. No retry, swallowed change, new `/tmp` exception
  or hostile same-UID/root/ACL/mount protection is claimed. Independent final
  evidence is `/tmp/scanipy-runtime-inventory-peer-correction-final.xml`.
- CodeQL path review retained **12 failures / one positive** in
  `/tmp/scanipy-410-codeql-peer-path-red.xml`: unsupported bases could mask an
  invalid URI, and C1 controls were not consistently excluded from aliases,
  inventory paths and decoded URIs. The narrow correction preserves invalid/
  inconsistent precedence and rejects C0 plus DEL/C1 across those three inputs.
  Final unchanged external controls join the 427 owned cases in
  `/tmp/scanipy-410-codeql-peer-final-440.xml`. Raw report bytes stay intact;
  data-only path validation does not claim full source-custody parity.
- **AL-02 post-cutoff observation:** `/tmp/scanipy-al02-core-review-mJP0VJ/result.xml`
  records a suite start of **19:00:06.971 UTC on September 25**, after the main
  cutoff. That run completed **291 passed / zero skips/failures/errors** (286
  repository plus five external controls), reported 10.84s; XML suite time is
  10.831s. Independent scoped review then approved unchanged source `bc361a8f`
  and tests `27e1c230`. This later result does not establish that review or test
  completion had already occurred at 19:00. The five additional checks exercise
  two model artifacts,
  two detectors/four bilingual rules, late invalid-member rejection, detached
  carrier/UUID snapshots and missing UUID storage. Actual successful complex
  input used 69 SHA calls against 20,067 conservatively reserved calls. These
  are bounded-input/hash-work checks, not measured native performance or
  operational authorization. The external source is retained separately at
  `/tmp/scanipy-al02-core-review-mJP0VJ/test_ledger_peer.py`; it is not a fixture
  key, live publisher or accepted model event.

### Required next actions — no status promotion

1. Finish each pending current-tree full run, normal push and exact-head remote
   tests; read the actual canonical final verdict. Preserve failures and verify
   the prospective merged tree before any normal PR merge. Git #409's review
   and merge are complete as recorded above; integrate its accepted bytes.
   CodeQL's later full pass is not a remote gate.
   Retest changed combinations
   rather than borrowing another branch's counts.
2. Preserve the occurrence finalization bridge as open work under
   CLAR-BHMEA-02. Do not infer a complete scan workflow from the tested store,
   documentation correction or successful PostgreSQL foundation tests.
3. Complete the authority design's missing operational closure separately from
   the runtime evidence-store amendments. The **741-line authority design plus
   544-line amendment** retain scoped design approval. Two newly identified
   **runtime evidence-store DESIGN gaps** remain: publication-ID replay after
   intent retirement, and the full-reader **512 MiB versus 256 MiB hash-work
   allowance**. Those storage/API amendments are pending; neither authority
   design approval nor the pure AL-02 codec resolves them.
4. Integrate actual accepted-content/current-authority owners and the installed
   runtime/store/controller only through their reviewed interfaces. Missing
   fetched closure, authority metadata, durable finalization, source/runtime
   observations or cleanup must remain unavailable/unknown, not fabricated from
   supplied digests, frozen dataclasses, fixture keys or successful pure codecs.
5. Keep full Java **and** Python, all 422 corrected corpus cases, the 844 fresh
   case-side attempts and every remaining R01–R20/C01–C18 obligation unchanged.
   No shared G0/G1/G2/G3 or full R/C status changes in this snapshot. No release,
   image publication, user-service/database change, native engine run or operator identity/
   installation choice is authorized or claimed here.

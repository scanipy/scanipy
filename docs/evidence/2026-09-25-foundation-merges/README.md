# September 25 — reviewed foundation corrections

Scope: repository correction evidence, not Black Hat feature acceptance.
Historical snapshot main: `1b29100ad9c96ebab9a4ac1a439fc2a5b19ac2ee` on 2026-09-25 at 17:42:32 UTC.
Revision 11 retains the 17:29 UTC local snapshot and explicit 17:45 update below;
later local work requires its own updated gates.
Revision 12 appends the 2026-09-25 **19:00 UTC** cutoff below, based on accepted
Revision 11 main `d4ad0c0b692cef4539d5333c60066cdcedecfb4e`, with a separately
identified post-cutoff update. Earlier pending statements remain historical
observations, not instructions to repeat finished work.
Revision 13 below records the observed **20:51 UTC** cutoff on accepted main
`075f92fe9d6aa1afb0a16494769e9cc96ba0df16`. Its current instructions supersede
older pending statuses without rewriting any earlier observation.
Revision 14 appends the observed **22:25 UTC** cutoff on accepted main
`4911f6568a85206651adbf40428529eb090c389f`; earlier pending statuses stay
historical, not directions to repeat already completed work.
Owner: root engineering coordinator, umbrella #362.

Current pointer: [Revision17](#revision-17--0345-utc-cutoff-september-26),
2026-09-26 03:45 UTC with explicit03:48 update, accepted `ecc34161`; no feature acceptance.
Historical pointer: [Revision16](#revision-16--fixed-021458-utc-cutoff-september-26),
fixed 2026-09-26 02:14:58 UTC with an explicit later02:26 note, on accepted `c5c862e3`. Revision15 and all older
observations below remain historical; later results are not backdated.

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
| [#413](https://github.com/scanipy/scanipy/pull/413), pure CodeQL observations | `4be0c28c648baefce9c2070aaf0db09b7c8dec6a` | `5118c93a0e4dac4815faf56febe1e14eb98edfb3` | [CI](https://github.com/scanipy/scanipy/actions/runs/36181665721), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36181665520), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36182993701), [final verdict](https://github.com/scanipy/scanipy/pull/413#issuecomment-5838721370) |
| [#411](https://github.com/scanipy/scanipy/pull/411), bounded occurrence persistence | `1c2f3b7472b459a09700866ec0822a735dd66349` | `075f92fe9d6aa1afb0a16494769e9cc96ba0df16` | [CI](https://github.com/scanipy/scanipy/actions/runs/36185087471), [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36185087522), [successful APPROVE](https://github.com/scanipy/scanipy/actions/runs/36186007470), [final verdict](https://github.com/scanipy/scanipy/pull/411#issuecomment-5839122349) |

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
At that historical checkpoint, local core/typed-CPG/occurrence-store work was
indexed separately, not counted as merged evidence. Source custody merged in
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
The earlier statuses here are superseded only where the later dated updates
explicitly record completion or a new implementation checkpoint.

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

## Revision 13 — observed 20:51 UTC, September 25

Accepted main is `075f92fe9d6aa1afb0a16494769e9cc96ba0df16`, tree
`7bce9471a3d858d39871e20631eaa5655b02b202`. The current cutoff was confirmed
by an actual 20:51:15 UTC clock observation. Root's mistaken future 20:54
timestamp for the WORK02 approval was corrected to the actual 20:49 observation;
it is not used as an observed event. Earlier 17:29/17:45/19:00/19:05 evidence
retains its original head, scope and time. No R/C/gate/DAG status is promoted.

### New accepted component records

- **#413 merged at 20:08:11 UTC.** Its merge and reviewed `4be0c28` share tree
  `047536eda124eaae6d64e5237ff399da3c090bfb`. All seven CI/Gate 3 checks
  succeeded before final canonical action `36182993701` SUCCESS/APPROVE.
  The [initial review 36181665499](https://github.com/scanipy/scanipy/actions/runs/36181665499)
  raised pending-CI and Unicode concerns; it remains retained, not relabeled.
  Three actual NFD/NFC controls passed in
  `/tmp/scanipy-413-unicode-assertion-confirmation.xml`. The accepted parser
  preserves supplied raw results and explicit unknowns. No real CodeQL output
  acquisition/import/native invocation, query-pack/source authority, coverage,
  reproduction, incumbent comparison or full R13/G2 acceptance follows.
- **#411 merged at 20:33:41 UTC.** Reviewed `1c2f3b7` and merge `075f92fe`
  share the entire `7bce9471` tree. All eight remote test checks succeeded,
  including **89 actual isolated PostgreSQL cases with zero skips**; final
  action `36186007470` succeeded with APPROVE and the actual gate reported
  APPROVE/PASS. The initial failed review/CLAR history above remains retained.
  Earlier `3992e5c4363264cde23d8d3e78b8cddb77828de0` full verification was
  **2,621 passed /51 skipped**, 392.62s, on its own tree. The current focused
  **548** comprises 95 occurrence, 427 CodeQL and 26 ledger checks, not 548
  PostgreSQL cases. Persistence is implemented; current authority, live
  producers, final Finding/R09 bridge, durable decisions and API/UI are not.
  CLAR-BHMEA-02 and larger #378/#362 remain open.

### Local integrations — not additional accepted components

| Scope / artifact | Observed result | Remaining boundary |
|---|---|---|
| Packet `a9e80119f4b49bd1b3ae60a202a5d5615918f5c1` / controller `ccaf7e5ef8527b5903f48c2cc76d038dc1716617` | Identical tree `7976bbd438a6436fb019fca171579c31f2a58858`; `/tmp/scanipy-runtime-packet-ancestor-main-full.xml` reports **5,662 passed /51 skipped**, zero failures/errors, 483.365s. Its actual `tests.integration.test_occurrence_store` class has **89 executed cases, zero skips**. | Current-head remote gates, installed authority/kernel/runtime controls and actual controller/workflow remain required. Total XML cases 5,713 includes skips and is not the pass count. |
| Pure packet commit `639a6c96c881aa5ab950fc11fd921766dc113a5f` | Scoped source review/normal commit; **760 new +16 independent =776** checks on each Python 3.11.16/3.12.14. Reports `/tmp/scanipy-packet-root-review-py311.xml` (6.723s) and `/tmp/scanipy-packet-root-review-py312.xml` (9.353s). Later combined focused selection **1,946** passed. | Supplied-data lease/hash/owner checks do not manufacture current permission or runtime observations. Cross-version and overlapping counts are not added into coverage. |
| Metadata ancestor correction `5c57897bcb5b9635be05c5ab4994b345d0621c2b` | Independent **117** (1.623s), `/tmp/scanipy-profile-ancestor-canonical-peer.xml`; combined **664** (5.744s), `/tmp/scanipy-profile-ancestor-after.xml`. Full nine-field file/direct-parent checks remain; ancestor-only equality uses device/inode/full-mode/UID/GID. | The correction is not a swallowed change or retry. Hostile same-UID/root/mount protection and installed runtime custody are not established. |
| Inventory `d59c4275eee4c9537501143345aa4f94d53bbb8e` / rule `2f1b3f7b7562a035d95e2c4ada9bbed57453c794` | Current focused **647 /714**, respectively. Local/no PR at this cutoff; root's inventory normal push is running. Earlier full **2,536/51 /2,603/51** remain attributed to the older heads. | Complete normal/current-head remote gates before merge; no new full result is silently assigned to the refreshed trees. |
| AL-02 / AL-03 | AL-02 remains locally committed and independently reviewed. AL-03 `be3c00ddefa1921d7f3f9aebd909f8380ff5bf4c` has **56** draft shapes/facade controls; no AL-03 PostgreSQL acceptance. | At **20:49 UTC**, root/peer approved WORK02 SHA `85174198d5937e3755412d6cad53b60db9c9af5bcf6c8edb6a137d8c10b478fb` after replay `14A` and census `N-seen+1` corrections. Incorporate its logical raw/image/history/canonical accounting before affected helper code. Operator/current authority and actual owner bridges remain absent; these are not RSS/full-workload capacity guarantees. |
| RES non-event byte-custody core | Frozen source SHA `2fd1297a3b664689f2219693ac0ee8524cf419119977b83bf42037e0d18340f0`, tests `3a5093955dc8bab301cc652def4f10ff32f4a44399d810cf40b6a9869dbee16c`, contract `3dcb1d3d53d0077a09c7232522e5e182ccaf8fea06215de3b30e1e98b6d911f7`; **110 passed** each on 3.11.16/3.12.14, 12.934s/12.391s, `/tmp/scanipy-res-core-frozen-110-311.xml` and `/tmp/scanipy-res-core-frozen-110-312.xml`. | Independent review pending; private test-directory publication is not a qualified installation or operational constructor. Staged role plans and permanent intent mappings do not complete event/spool/full-history reader, physical capacity, six-role authority or DB orphan/pre-reservation barriers. |

The full-run XML was checked twice: root's first Python executable path was
missing, then corrected; an initial class-name filter matched zero, then the
actual class name matched 89. These are tooling/filter errors, not failed
product tests or evidence that the PostgreSQL cases were omitted. The final
counts above come from the actual suite/testcase attributes.

### Contrary evidence remains part of the record

- The original controller full at `6b763929` reported **3,772 passed /51
  skipped /one failure**, 345.76s, in
  `/tmp/scanipy-runtime-controller-git-main-full.xml`. It did not capture
  which held object changed; that cause remains unknown. Separately,
  `/tmp/scanipy-runtime-profile-stamp-controlled.xml` passed the unchanged
  short-read control and failed a controlled unmeasured sibling-directory
  change after measurement. This **one-pass/one-failure** demonstrates the
  ancestor overreach, not the retrospective cause of the full-run failure.
  Later corrected green results do not erase either record.
- RES cold-recovery draft source `0c595a37` produced **77 pass/one fail** in
  `/tmp/scanipy-res-core-recovery-first.xml`; an already verified two-link
  prerequisite pair could not be rebound. The exact recovery correction's
  unchanged controls pass in `/tmp/scanipy-res-core-pair-recovery-green.xml`.
  Python 3.12 draft `b531111d` produced **one failure** in
  `/tmp/scanipy-res-core-path-312-first.xml` on legitimate private path
  fragments; bounded primitive-fragment reconstruction corrected it, with
  the four-mode controls in `/tmp/scanipy-res-core-path-312-green.xml`.
  These genuine failures are separate from a test-only ExceptionGroup
  assertion correction and an executable-path setup failure before pytest.
- All earlier canonical, Unicode/path, journal chronology/spool/release,
  projection/UUID, inventory and budget contrary evidence remains retained.
  No failed review action is treated as approval; successful pure checks do
  not prove an actual native producer, signature/currentness or physical capacity.

### Dependency-ordered next actions

1. Root finishes exact-head foundation publication and combined runtime gates;
   specialists preserve accepted parser/store/source bytes during integration.
2. Incorporate approved AL logical accounting before SQL helpers. Use the
   actual RUNNING new-run state and atomic denial; do not invent pending runs,
   empty child results, fake authority IDs or retroactive lower-level adoption.
3. Finish RES independent review, then the separate qualified storage, full
   reader/event/spool, current-owner and DB barrier work. Permanent intent/role
   plans address the allocated non-event design gap; the deferred delegated
   full-reader hash-work boundary remains, not a widened allowance.
4. Bind actual source/accepted rules/native observations to retained detections
   before identity, final provenance/decisions/API/UI and real oracle rates.
   Preserve full Java/Python, all 422 cases/844 uncached sides and every claim.
5. Only after actual runtime readiness and explicit bounded-run approval,
   perform native probes/campaigns and G0/G1/G2, then separate G3 gates. The
   confirmed machine's 20:32 sample was about **8.3 GiB available RAM, full
   swap, 96 GiB free shared disk**—not reserved capacity. No installation,
   release/image publication, native campaign or user-app/DB mutation occurred.

### Explicit later update — 20:54 UTC

- Inventory `d59c427` completed normal push: Ruff, 249 formatted files,
  mypy 99 and configured unit selection passed. [PR #414](https://github.com/scanipy/scanipy/pull/414)
  is open against accepted `075f92fe`. [CI 36188497922](https://github.com/scanipy/scanipy/actions/runs/36188497922)
  and [canonical 36188497794](https://github.com/scanipy/scanipy/actions/runs/36188497794)
  are running; green lint is not completed CI/review. Rule `2f1b3f7` normal
  push is running after Ruff/format 250/mypy 100 passed; no result is inferred
  for its remaining unit stage or remote gates.
- Root independently reproduced a genuine RES double-begin thread race at
  frozen source `2fd1297a`: **one failure /zero skips**, 0.280s,
  `/tmp/scanipy-res-root-concurrency-configured-before.xml`. Root's narrow
  three-file lifetime correction has an interim **111 passed** (13.705s;
  original 110 plus the unchanged external race control) and a separate five
  new lifetime controls passing (0.642s). A redundant closed-state check
  initially failed mypy; the unsynchronized early check was removed and final
  static checks passed. Final independent/fault review, full and publication
  gates remain pending. Earlier 110-pass reports are not reassigned to the
  corrected source, nor do they erase this later real defect.

## Revision 14 — observed 22:25 UTC, September 25

The clock read at 22:25:56 UTC and remote records confirm accepted main
`4911f6568a85206651adbf40428529eb090c389f`, tree
`1b81b0fd1e4d52165695e957d90f7818aafe08cd`. All four PRs below merged only
after normal push, required CI, canonical SUCCESS/final APPROVE and truthful
completed checklist. Narrow scope only; no umbrella issue is auto-closed.

| PR | Reviewed head → merge | Observed gates |
|---|---|---|
| [#414 inventory](https://github.com/scanipy/scanipy/pull/414) | `d59c4275eee4c9537501143345aa4f94d53bbb8e` → `c7eb7b3e4cad8f66d2098213998b7931474295a5`, 21:14:06 UTC | [CI](https://github.com/scanipy/scanipy/actions/runs/36188497922) six successes, 89 actual PG cases; [final canonical](https://github.com/scanipy/scanipy/actions/runs/36189446059) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/414#issuecomment-5839597708). Initial [procedural failed review](https://github.com/scanipy/scanipy/actions/runs/36188497794) retained. |
| [#415 Revision 13](https://github.com/scanipy/scanipy/pull/415) | `e4085927026dd452e1c4f7cd6b1fffb670238dc3` → `fd35a61d49855af235535916b734593387d52ee8`, 21:32:28 UTC | [CI](https://github.com/scanipy/scanipy/actions/runs/36191054813) six successes, 89 actual PG cases; [final canonical](https://github.com/scanipy/scanipy/actions/runs/36191780566) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/415#issuecomment-5839898409). Initial [pending-CI failed review](https://github.com/scanipy/scanipy/actions/runs/36191054786) retained. |
| [#416 rule codec](https://github.com/scanipy/scanipy/pull/416) | `27ffcc843ec94af2f72c1514453d3d9ffbf5ca8e` → `2dcec908faa4fc160fed27a1d2ebbc02e2d4a4c2`, 21:56:20 UTC | [CI](https://github.com/scanipy/scanipy/actions/runs/36192191972) six and [Gate 3](https://github.com/scanipy/scanipy/actions/runs/36192193211) two successes, 89 actual PG cases; [final canonical](https://github.com/scanipy/scanipy/actions/runs/36193652089) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/416#issuecomment-5840152964). Initial [pending-CI/security-signoff review](https://github.com/scanipy/scanipy/actions/runs/36192191974) retained. |
| [#417 metadata loader](https://github.com/scanipy/scanipy/pull/417) | `de685797af77aa9a5303fb5bdeea1f372d428513` → `4911f6568a85206651adbf40428529eb090c389f`, 22:16:42 UTC | [CI](https://github.com/scanipy/scanipy/actions/runs/36195155422) six successes, 89 actual PG cases without skips; first [canonical](https://github.com/scanipy/scanipy/actions/runs/36195155430) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/417#issuecomment-5840329710). Actual gate printed APPROVE/PASS at 22:11:48 UTC. |

No Gate 3 run is inferred where changed paths did not trigger it. Rule #416
also had independent explicit Security Analyst APPROVED on its exact eight-path
scope: 228 passed /one existing DET-03 skip, not full component acceptance.
Its actual merge-tree affected selection passed 813 with zero skips;
`/tmp/scanipy-rule-416-merge-focused.xml`, SHA256
`8ce2c8dfdf767ac7aa5dfcdf5955b71304cedccf4e2185647b64855e7c344d05`,
6.315s. This is affected-selection evidence, not another full run.

Loader #417's actual fetched merge `bab501ff78a27d9a6eae389f0486faf9cd44453f`
has the same complete tree as reviewed head and final main. Root ran **1,090
affected cases, zero skips/failures/errors**, 9.594s, on that merge tree:
`/tmp/scanipy-loader-417-merge-focus.xml`, SHA256
`7a01920dade58b62ca5ade3d809147bb57c23667cc70e52f34aa196f664b9861`.
Earlier C617 full 3,424/51 stays at that earlier head, not the refreshed tree.
Its nonblocking review descriptions were corrected in the PR body: ancestor
identity/security retains five fields, not four, and exact PosixPath is required;
subclasses are rejected. No behavior change or contrary failure was erased.

### Local candidates — diagnostic evidence, not accepted implementation

| Candidate and exact scope | Current evidence | Pending gate / boundary |
|---|---|---|
| B resolver `b07174522a35a5ab9bb18add7379d92171a79f35`, tree `f5ddf9de824ca65ee8de51d0ef8dcc45c3f4e71e`; 13 reviewed additions, baseline 167 unchanged | 804 affected /0 skips, 53.025s, `/tmp/scanipy-resolver-b-c-main-focused.xml`, SHA256 `4cbc9536d44519d50f1b2f1f1e4b1ec73e4b4538ba1cb9461d1478e96dc46f14` | Actual normal push running; no PR at cutoff. No operational verifier/provider/authority. |
| B pre-C `c365e12977d7348d9cd19fc9a3c81bf4bb1fc76f` | Full **3,549 passed /51 optional skips**, zero failures/errors, 440.047s; `/tmp/scanipy-resolver-b-main-full.xml`, SHA256 `7b7766ab4f8b0fbe57f252fb8dcb1219895326cee7ee270665ec2a84afc406c8`; all 89 actual occurrence PG cases pass | Full belongs only to pre-C head; not relabeled after the accepted-C merge. |
| D renderer `6bf0651f1c07181762d6d941750a1e2cba049a9c`, tree `597444821204a2232db2964f88617d3da65379f3`; four paths | 856 affected /0 skips, 4.257s; `/tmp/scanipy-runtime-renderer-d-accepted-c-focus.xml`, SHA256 `91d6174af730eba4e00b8e7889f87492dc3f376877e1c9f6143e66bae6a1f3c2` | Fresh full, normal push and remote gates pending. Intended argv is not Docker/kernel observation. |
| E process evidence `257336c972ae095f0a7d1c11bab2b45a11696e1c`, tree `0d8d04279aadc9e3decf9e90c9fe2033e238b7e5`; four paths atop earlier D | Normal hooks and 479 owned /0 skips, 5.136s; `/tmp/scanipy-process-evidence-e-prep-focus.xml`, SHA256 `03a12c927cf0db78bd9d2bf77ef761163f2da0a8cf8106f6b378a785d8771297` | Accepted-parent refresh, full/push/remote, physical spool/journal/controller pending. F packaging begins from this exact E, not an enabled runtime. |
| Provenance `de17aa064e72feb960ecdb95fb564d308999e638`, tree `a6cedbe4a132139fc58792233ff1bd2cd5f141fc`; six paths, baseline 167+38 reviewed public entries | 702 affected /0 skips, 10.815s; `/tmp/scanipy-provenance-c-main-702-corrected.xml`, SHA256 `b081a66c5b8fcccf7c37a8cd4e02342175e84adc752b36b633d67ce92d1bb5b2` | Normal push/remote gates and actual producer integration pending. Synthetic records are not live signed scan provenance. |
| Provenance pre-C `1a349f22fe78f0370d3c7c97304b54800bd8a813` | Full **3,391 passed /51 optional skips**, zero failures/errors, 391.621s; `/tmp/scanipy-provenance-compat-rule-main-full.xml`, SHA256 `f1112b0381a72321be8bbd96af96d913c1ba8a63d02156df808d55774df24167`; all 89 actual occurrence PG cases pass | Later C refresh has the separate 702 affected checks, not another full. |
| RES combined `3194baa1e4a3002854f754c212006bc132adac20`, tree `41f5b633aab5976fad2594ef336cf683859b2256` | Full **4,720 passed /51 optional skips**, zero failures/errors, 563.717s; `/tmp/scanipy-res-ancestor-main-full-configured.xml`, SHA256 `2de82d22e4def5521177a9afe9d99120a1590e54e7ed32eadd5981e2725f8b13`; 89 actual occurrence PG cases pass | Narrow dependency publication, qualified installation/capacity, event/spool/full-reader, DB barriers and current authority still absent. |

The first provenance C-focused command named a nonexistent test filename and
exited 4 before tests. Its empty report remains `/tmp/scanipy-provenance-c-main-702.xml`,
SHA256 `270e1ce10fbec720f4a1fdd3725802175297bbaa55171ed08294953e210e9fc6`;
the corrected command selected actual `test_runtime_artifacts.py`. No product,
test or gate was changed for the green run. The earlier baseline commit's 38
public-value detections, root/peer exact review and baseline-only correction
remain in the new compatibility contract; no private fixture keys are retained.

### Accepted-ledger SQL: corrections, not real PostgreSQL acceptance

AL-03 is still an uncommitted 16-path allocation atop `be3c00d`. Root read the
complete SQL validation/mutation/read boundary and both actual integration
modules plus the 534-line separately opted-in fixture. Independent Security
Analyst approved the exact migration/table/ACL/history/fixed-bridge resources;
facade review and actual isolated PostgreSQL runs remain pending at this cutoff.
The approved five-resource review does not certify the entire SQL implementation.

Two actual source omissions were preserved as **five failing source-order
controls**, `/tmp/scanipy-al03-root-generated-clock-source-red.xml`: generated
denial JSON construction preceded its required K reservation, and positive
paths lacked required monotonic time comparisons. Corrected implementation
prepays two K(65536,64) plus K(4096,16), preserves lower reservations and all
limits, then validates generated bytes/tokens. Seal/initial/renewal/read/recheck
reject backwards observed time rather than manufacturing denial or restamping.
Stored-only wrappers distinguish malformed stored bytes from the unchanged
private work-limit marker, preserving unexpected SQL/driver failures.

The resulting unit/source selection passed **147**, zero skips; actual report
`/tmp/scanipy-al03-stored-generated-clock-unit.xml`, SHA256
`8dc689d200a45d0ce9a64c2042e379c68b43f28245bf0061b7ff2ee0763b2ae0`,
3.335s. Operations SHA256
`9308d2347cdf61b6e348aed3e5acb801e626980a9e78b1be6883a9a5e812d205`,
reads `c7cead1435acf3f2c35c7a24979f10bcf964809b890c17fdac2ed2ff09340e18`,
validation `3f61298ad1b142a4aae39e71b4dbbdcb0ba4a30bae431c63ff9e0e19fe5927d0`.
No PostgreSQL run, executor/RSS guarantee, live provider, cryptographic admission,
installed operator/restore identity or actual native permission is inferred.

Stored occurrence parsing remains bounded canonical/schema-name validation,
not a copied full semantic codec. Original lower helpers validate NEW inputs;
later reads depend on immutable ordinary history and the precise locked material
comparisons. The bridge does not expose a complete raw seal digest, so unused
seal fields are not claimed independently hash-rebound. Coherent privileged
corruption of both ownership domains is outside this guarantee.

### Immediate TODOs and unchanged acceptance

1. Finish B push/PR gates and D full; then E/F/G and provenance narrow dependency
   gates with checks on their actual final combined artifacts.
2. Complete AL facade review and first bounded separate-cluster SQL run; retain
   real failures and verify migration/roles/transactions/concurrency/limits.
3. Supply real source, model, authority, runtime and final provenance producers;
   wire persistence/decisions/API/UI. Finish operational store/controller and
   bounded native integration before the complete all-case campaign.
4. Execute G0/G1/G2 and independent offline stage rehearsal on this machine;
   collect immutable release evidence and seek separate publication authority.

The owner confirmed this machine, acceptance/RSVP and December 2 or 3; no
October lock or reduced scope. A fresh host observation around this cutoff
showed about 8,405 MiB available RAM, full 2 GiB swap and 93 GiB shared free
disk. That is not reserved capacity. The existing app/DB are healthy and were
not changed. No release, image publication, target execution or native campaign
occurred. Root's board reads retain #399/#378/#362 In Progress. All C/R/G states
and the entire original submitted scope remain unchanged.

### Explicit later update — observed 22:30 UTC

- B's actual normal push passed all four phases: Ruff, 267 formatted files,
  mypy 106 sources and the configured unit/invariant selector. Git exited 0;
  root independently read remote `b07174522a35a5ab9bb18add7379d92171a79f35`.
  [PR #418](https://github.com/scanipy/scanipy/pull/418) is open at that head;
  CI/canonical are pending, not approval. No new hook test count is invented.
- AL final scoped unit controls passed 185 on Python 3.11.16 and 3.12.14:
  149 AL +36 unchanged occurrence cases, zero skips/failures/errors. Reports
  `/tmp/scanipy-al03-unit-final-311.xml` (3.401s) and
  `/tmp/scanipy-al03-unit-final-312.xml` (7.835s), SHA256 respectively
  `69c50c84b170ccce9c143861a92447a30aa98b1c8b14c566ec9f3348681a6842`
  and `3f89f1164f5c45c3f92eb42b11ed447248cace644156f911912ac7b3253b7a08`.
  The 97 security +41 SQL cases
  were collected only, not run. All 15 changed path hashes remain frozen.
- Root created only task container `scanipy-al03-review-20260926`, ID
  `cd533fce165bbf316d67dd29a875c2a8461626cda2e5b79d691898103d0c052f`, from cached
  image `75f5a96988cdf694a215073c3e9c001b706b371e2f94df3967f2efdec2787f6b`
  (`linux/amd64`). It has network none, no ports, 1,536 MiB memory and equal
  memory+swap limit, 2 CPUs, 256 PIDs, 128 MiB shared memory, 1 GiB data tmpfs
  and only `/tmp/scanipy-al03-pg-jNKSa0zZ/socket` mounted. The outer directory
  remains owner-only mode 0700. `pg_isready` succeeded. Test-only trust auth
  is confined to this private socket/network-none cluster, not production.
- No AL PostgreSQL tests ran at this observation. Independent facade review
  and the separately granted three-case migration/publication/initial-run smoke
  precede expanded SQL checks. Root retains exact container ownership; the
  reviewed harness may remove only its own OID-matched child DB/roles, with no
  FORCE/CASCADE/session termination. User app/DB and occurrence cluster remain
  untouched. D full remains queued; no C/R/G acceptance state changes.

## Revision 15 — observed 23:31 UTC, September 25

The clock read at 23:31:21 UTC. Accepted main is
`0e1b2b9abe97c2be6c02023a9e3e72b4790106aa`, tree
`437a5dc2984c7337b2c703c327ea5ecf0319a3a2`. Earlier checkpoints above remain
byte-for-byte historical evidence. The records below distinguish accepted
repository changes from local diagnostics and incomplete operational work;
no C/R/milestone/DAG or shared-gate status changes. Local `/tmp` reports are
retained diagnostic records, not a public immutable acceptance archive.

### Newly accepted exact-head records

Times in the next table are local Git **merge-commit timestamps (CommitDate)**,
not GitHub's `mergedAt` API field. Root's retained actual API observation for
#421 is **23:25:39 UTC**, distinct from its commit timestamp 23:25:38 below.

| PR | Reviewed head → accepted merge; CommitDate UTC | Required checks and review |
|---|---|---|
| [#419 Revision 14](https://github.com/scanipy/scanipy/pull/419) | `2cfcadde6a305bba4bf604ca20d44bb09a66330b` → `ca73c7dd08ff659926e920537d204bce6e91051c`, 22:59:16 UTC | [CI 36198274236](https://github.com/scanipy/scanipy/actions/runs/36198274236), all six jobs successful; [final canonical 36198773649](https://github.com/scanipy/scanipy/actions/runs/36198773649) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/419#issuecomment-5840754580), actual gate 22:57:02 UTC. The [first checklist-only REQUEST-CHANGES](https://github.com/scanipy/scanipy/actions/runs/36198274179) and [comment](https://github.com/scanipy/scanipy/pull/419#issuecomment-5840697804) remain retained. |
| [#420 pure renderer](https://github.com/scanipy/scanipy/pull/420) | `6bf0651f1c07181762d6d941750a1e2cba049a9c` → `1b36e74c91df9b6c6eaf32a149abcf9b0429ab0f`, 23:08:27 UTC | [CI 36199215892](https://github.com/scanipy/scanipy/actions/runs/36199215892), all six jobs successful; first [canonical 36199215851](https://github.com/scanipy/scanipy/actions/runs/36199215851) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/420#issuecomment-5840812904), actual gate 23:04:05 UTC. |
| [#421 provenance compatibility](https://github.com/scanipy/scanipy/pull/421) | `de17aa064e72feb960ecdb95fb564d308999e638` → `0e1b2b9abe97c2be6c02023a9e3e72b4790106aa`, 23:25:38 UTC | [CI 36199933631](https://github.com/scanipy/scanipy/actions/runs/36199933631), all six jobs successful; final [canonical 36200550221](https://github.com/scanipy/scanipy/actions/runs/36200550221) SUCCESS/[APPROVE](https://github.com/scanipy/scanipy/pull/421#issuecomment-5840975647). The [first checklist-only failed review](https://github.com/scanipy/scanipy/actions/runs/36199933644) and [comment](https://github.com/scanipy/scanipy/pull/421#issuecomment-5840892973) remain retained. |

Each CI actually executed all 89 occurrence PostgreSQL cases without skips;
none executed the new AL suite. Root verified actual merge artifacts and
unchanged owned bytes, not merely prospective PR heads:

- #419 artifact `813f4fa665d2f51bc75bd4406ccecf4f15039472` has the same
  complete `47c4218b` tree as its reviewed head. Its 26 ledger checks passed;
  `/tmp/scanipy-revision14-419-merge-ledger.xml`, SHA256
  `e955793f41accb0df6b1292b3d7198128fc528cc36bc8a6eecb6d4cd697fb2da`.
  A missing positional CLI argument was an argparse invocation error, followed
  by the successful correctly configured structural check, not a product fix.
- #420 artifact `e888a4068a80e7b03148ebd0f439b2243b433b0b`, tree
  `63f28300aa444898f4ec9900408bcca8ea5f897b`, passed **856 /0 skips/errors/
  failures**, 7.680s; `/tmp/scanipy-renderer-420-merge-focused.xml`, SHA256
  `cd00a99bb5b86e0da96e34323e960f9b5efc497c9fdb3a0b69103a76989074a6`.
  This is the actual merge-focus XML hash; the supplied PR-body transcription
  omitted its initial `c`. Report bytes/counts are unchanged, not a test fix.
  The earlier exact `6bf0651` full passed **3,878 /51 optional skips**, zero
  failures/errors, 413.400s, including 89 actual PG cases;
  `/tmp/scanipy-runtime-renderer-d-main-full.xml`, SHA256
  `79ef69d50c2dcd013986d2e96b9e19f4a7ec1302eb9c0c17712cfdc792b4e458`.
  The merged-artifact focus does not reassign that full run to a different tree.
- #421 artifact `30a1256deb8d2e27c0093c5cb9be57318029875b` and accepted main
  share tree `437a5dc2`. **990 /0 skips/errors/failures** passed, 12.123s;
  `/tmp/scanipy-provenance-421-merge-focused.xml`, SHA256
  `efd61dce16a4894e1f5058ead44f60c9b41a025a240a896ca9dc9e5edea35b82`.
  All eight incoming Revision14/renderer paths and all six provenance paths
  remained exact, including the 205-entry baseline (167 accepted plus 38
  reviewed public values). Its pre-C full 3,391/51 remains attributed above.

The renderer produces intended `FrozenInvocation` data, not Docker/kernel
observations. Ten synthetic historical signatures preserve old bytes; they
are not live finding provenance, installed keys or a completed emitter/export.
Normal gates and narrow merges do not close #378/#399/#400/#362 or full claims.

### B, E and F local checkpoints

B [#418](https://github.com/scanipy/scanipy/pull/418) preserves two actual hosted
integration failures. Original [CI 36197035978](https://github.com/scanipy/scanipy/actions/runs/36197035978)
failed all 38 process cases at shared fixture setup, before a verifier launched;
the file/cap cause was not retained. Diagnostics-only `43e035ec` then failed
[CI 36199235817](https://github.com/scanipy/scanipy/actions/runs/36199235817)
the same way. At 23:06:58 UTC that second run identified
`config-3.11-x86_64-linux-gnu/libpython3.11.a`, **48,157,564 bytes**, exceeding
the unchanged **32 MiB per-file** copy cap; cumulative bytes 71,582,024 and
313 files did not exceed their caps. This is evidence for the second run's
cause, not retrospective knowledge of the first. Gate 3 passed on both heads;
the original [canonical APPROVE](https://github.com/scanipy/scanipy/pull/418#issuecomment-5840575210)
did not override failed CI or approve a later correction.

Reviewed `a69afcb8` uses exact validated interpreter metadata to omit only that
regular static development archive from the private diagnostic distribution.
Neighbor files and all other caps remain; no production/contract/baseline bytes
or original 38 process cases change. The controlled red
`/tmp/scanipy-418-static-archive-local-red.xml` has one failure, SHA256
`81542812fbe750f5d94a7be357c85ab5d805f9c06e468e8e58a840e259b715e9`.
Author and peer independently passed the same **63** controls, not 126 unique
cases: `/tmp/scanipy-418-static-archive-final.xml` (0.570s, SHA256
`4e4d329dda9161d6b718f3807b3e675675a36109c80f31eaf6538299e2e9aee5`)
and `/tmp/scanipy-418-static-archive-peer-final.xml` (0.578s, SHA256
`a07d2994a796dd3e29d0acac876f41f5390ef4ce49af81f66677b10b88fb09c7`).
No complete installed-runtime inventory or operational permission is inferred.

After accepted-D integration, B `3e1cfc5661c18593202f14e5649cef3a5a3f8015`,
tree `e7b5e294c335fdbf85302f038bb5c815a8347040`, passed **1,155**, zero skips/
errors/failures, 56.348s, including all **38 actual controlled process cases**;
`/tmp/scanipy-resolver-b-archive-main-focused.xml`, SHA256
`f57278c8f601ff485485913908a05f3c4dc720a07a0d397afcb55c5b144c1594`.
Its normal push was IN PROGRESS at 23:31. Corrected hosted CI/canonical review
remained required; the public operational runner still refuses unconditionally.

E `306a7d76fcf4c5398138ed42c4989e93ecf715db`, tree
`2a89f7945b7347b6cdf5649bce2e1a4943d07744`, passed a fresh configured full:
**4,357 passed /51 existing optional skips /zero failures/errors**, 423.449s,
including all **89 actual occurrence PG** cases, with only that separate fixture
enabled. `/tmp/scanipy-process-evidence-e-main-full.xml`, SHA256
`2bd35d4b0e8b8e1d4d57fb0662d4e4490f08e2f49ff2722ab7f108152dd64509`.
All four E files and baseline stayed frozen. No publication at the cutoff;
this is not a physical evidence store or observed controller/authority.

F `49fa9ecebc8bb188663f66a507e7424139f54467`, tree
`2813be3e25c98753b7c9a94c65ce4e1ecc88f8da`, passed **1,644 focused** cases,
zero skips/errors/failures, 30.316s; not a full run. Report
`/tmp/scanipy-runtime-journal-f-accepted-main-focused.xml`, SHA256
`c2ee40edabf259a6f9a1b2f8098057a82b28ebdce30baac07bb71c0297fdd1ed`.
The root preparation note is
`/tmp/scanipy-runtime-journal-provenance-8CwSSMSb/F-PREPARATION.md`.
E remains an unaccepted publication dependency. Pure structural replay does
not return durable/visible/current-authority receipts; no F full/push/PR or
physical store/controller acceptance is claimed at this cutoff.

### AL three-case smoke history and custody

All reports below are retained independently. A zero-skip run is not proof
that the unselected 144-case suite passed; `-x` stopped the failing invocations.

| Report | Actual result | Exact boundary / SHA256 |
|---|---|---|
| `/tmp/scanipy-al03-pg-first-smoke.xml` | One setup error, zero executed bodies/failures/skips; 15.207s | Alembic/SQLAlchemy parsed literal JSON colon tokens as binds. `7433aa88c59d06af80226695a9b3ad0947a6f53c13f09f4edfe1b99a32420315` |
| `/tmp/scanipy-al03-pg-literal-smoke.xml` | One passed body, one later setup error and one teardown error; zero assertion failures/skips; 22.852s | Immutable-row `FOR UPDATE` lacked UPDATE privilege; cleanup separately refused the truncated role-name ownership map. Two testcase elements/two error elements, not two failed bodies. `bf12972e6ac27cbb270d685bc14ec069130bcbbc97f35de9d21c7cfda1a0db2d` |
| `/tmp/scanipy-al03-pg-lock-login-smoke.xml` | Two passed /one failed /zero errors/skips; 36.918s | AL fixture combined revised accepted-content hashes with legacy raw content; actual `CaptureSeal` correctly rejected before the seal SQL call. `0ba5a43bbbe4845ef0f00449cd6386401c79fb4c13df57148671abaeeca5fe4b` |
| `/tmp/scanipy-al03-pg-seal-fixture-smoke.xml` | **Three passed /zero failures/errors/skips; 41.498s** | Migration/roundtrip, historical publication/request binding, initial actual RUNNING run and immutable same-command replay. `abbdd429133a99c255e3916b352a95a8345003e3ea3b3c3d4f698ec6e3910bdd` |

The corrections preserve contrary evidence and authority boundaries: literal
submission escaping leaves all SQL resource/old-owner bytes intact; removing
exactly 11 immutable-record locks retains the held namespace/execution locks
without granting UPDATE; accepted fixture logins use full UUIDs, pre-CREATE
server-bound checks and exact name/OID-before-GRANT, with ownership staged
through commit/close. The sealing fixture atomically replaces coupled fields
on a valid tenant template; production, SQL and all 12 shared helper callers
are unchanged. Earlier facade input/stored-error reds remain in the AL contract.

Scoped root/peer reviews approved these corrections. Independent sealing-fixture
**11 /0** passed in 2.641s at
`/tmp/scanipy-al03-seal-fixture-peer-final.xml`, SHA256
`b062e9a05915c04cdf4ba28f154ee50dfe81c7d1f7d6080b2fe66ea6af9cb73f`.
Author **324 offline /0** passed in 7.074s (229 AL +36 occurrence repository
+59 occurrence-envelope cases); `/tmp/scanipy-al03-seal-fixture-final.xml`,
SHA256 `d8bafebf7f00db2f6cfd78a6ce4c433fbf627d68c2b1cc0769e14b560171e4a5`.
Overlapping totals are not additive or actual PG assertions.

Root retained the failed cluster's catalog and zero-other-client observations
at `/tmp/scanipy-al03-reviewed-pg-6ERTSe5j/FAILED-CLUSTER-CHECKPOINT.md`, then
stopped/removed only exact old container `cd533fce165bbf316d67dd29a875c2a8461626cda2e5b79d691898103d0c052f`
at **23:00 UTC**. Its disposable tmpfs data/roles are gone; reports remain.
The old generated policy-admin name was **65 ASCII bytes**, not 64, against
server bound 63. The lost suffix was not reconstructed and no truncated role
or unknown OID was adopted. No application volume/resource was changed.

Replacement `scanipy-al03-reviewed-20260926`, exact ID
`4dbc2fc3e9f15ce2421963ada8792c9b363426b09a0e17782c7b8865d6d2f651`, uses
only `/tmp/scanipy-al03-reviewed-pg-6ERTSe5j/socket`, cached PostgreSQL image,
network none/no ports, 1,536 MiB memory/equal memory+swap, two CPUs, 256 PIDs,
128 MiB shm and 1 GiB data tmpfs, with owner-only outer directory. The successful
smoke's fixture teardown passed. A bounded read-only PG16.15 check found only
bootstrap/default databases, only `al03_admin` among task-role prefixes and
zero other client backends; its diagnostic connection closed. These observations
do not authorize further use without root's explicit grant.

AL remains uncommitted atop `be3c00d`, with source/integration/unit/contract
frozen (integration `11c71428`, unit `5fa9fd5e`, governing doc `66086d91`).
At 23:31, **144 cases were collection-ready, not suite-executed**. Full SQL,
restricted-role/concurrency/budget gates, real current providers/crypto/restore
administration and operational runtime acceptance remain open.

### Explicit later update — 23:36 UTC

Root subsequently observed B's actual normal push complete: all four own
pre-push phases passed and the remote head is exactly `3e1cfc56`. Corrected
[CI 36201470157](https://github.com/scanipy/scanipy/actions/runs/36201470157)
and [Gate 3 36201470146](https://github.com/scanipy/scanipy/actions/runs/36201470146)
are running; no hosted success or fresh canonical approval is inferred.
The actual merge artifact `0041f578e3f752971db5b9eb49116bc52b960576`, tree
`8d148e8bd22535221365ee8b7772cf69ab44a52c`, has exact parents accepted `0e1b2b9a`
and B `3e1cfc56`; all six provenance incoming paths and 14 B paths remain
exact, preserving the 205-entry merged baseline. Its **1,251 pure cases**
passed, zero skips/errors/failures, 27.709s;
`/tmp/scanipy-resolver-418-archive-merge-unit.xml`, SHA256
`1925723d4ad979864d7473f475d879400f134f4fd684aa59077664fe84db5eab`.
This did not rerun the 38 process cases and is not another full suite.

After that push released the broad slot, root started the frozen **AL144**
selection at **23:33:51 UTC** on the isolated replacement cluster. It was
RUNNING at this later observation, with no final result. It does not backfill
the three-case-only 23:31 checkpoint or permit source edits during the run.

Root's subsequent source-backed
[scope clarification](../../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md#tenant-local-authority-and-later-publication-extensions)
keeps tenant-local accepted builtin publication/current authority, complete
signed provenance, real Java/Python/CodeQL/Semgrep, measurements, lifecycle and
UI required. Cross-scope global adoption and statistical/LLM inferred-spec
publication are later extensions, not new Black Hat gates. Existing Gate 4,
INV-3, signed nullable global scope and all rejection/acceptance guards remain;
known inferred proposals cannot be relabeled builtin. The fixture's global
tenant-org issue and the deeper unsupported cross-scope owner protocol remain
recorded, without blocking the distinct required tenant-local path. No original
task/TODO/state is removed or new human authority claimed.

### Explicit later update — 23:38 UTC

The granted AL144 `-x` invocation stopped after **16 passed /one failed /zero
skips/errors**, 17 executed cases, 203.856s. Report
`/tmp/scanipy-al03-pg-expanded-144.xml`, SHA256
`fc09b759bc390c9f2f7b34feedf9028158d5b6ee209ac9bfa9189f15e926b862`.
Successful teardown and root's bounded catalog check found four default/
bootstrap databases, only `al03_admin` among task-role prefixes and zero other
clients. This is not 144 successful cases or a completed AL acceptance run.

The failing assertion directly compared a psycopg2 format-`c` bytea view to
expected format-`B`. A separate controlled SELECT confirmed equal bytes can
compare as unequal views; it did not establish the failed transaction's prior
row bytes. Root assigned a narrow test-only before/after exact-byte snapshot
correction, offline regression and AL contract note, with SQL/production
unchanged. No retry, changed expectation, publication or success is inferred.
Keep the earlier three-smoke pass and all three preceding failures distinct.

## Revision 16 — fixed 02:14:58 UTC cutoff, September 26

Snapshot is **2026-09-26 02:14:58 UTC**, accepted main
`c5c862e3035ac974af82be7f2b69680cf3ea4c70`, tree
`ea4d36f4e344a250d0ed1df7b9e8fc519c08deff`. Root supplied the observed remote
states/times below; this documentation task did not query or mutate GitHub.
Local accepted ancestry was independently read. Reports are retained diagnostic
files, not a public immutable archive. All previous cutoffs/failures and full
task/claim/gate/milestone/DAG states remain unchanged.

### Accepted foundations since Revision15

| PR / narrow scope | Accepted identity and root-observed UTC merge time | Observed gates / boundary |
|---|---|---|
| [#418 resolver B](https://github.com/scanipy/scanipy/pull/418) | `3b0221df12d080b774df34ddafde930703de30d9`, September25 23:48:07 | Reviewed head `3e1cfc5661c18593202f14e5649cef3a5a3f8015`; [CI36201470157](https://github.com/scanipy/scanipy/actions/runs/36201470157) six successes; final [canonical36202037242](https://github.com/scanipy/scanipy/actions/runs/36202037242) SUCCESS/[APPROVE5841154346](https://github.com/scanipy/scanipy/pull/418#issuecomment-5841154346). |
| [#423 Revision15](https://github.com/scanipy/scanipy/pull/423) | `b5a02b8c92b6a8bfa1d3a8c3b23ae0f96b1e84c2`, 00:21:50 | Reviewed head `5b6ba06fa66fccf9ffca8c442dddf06cc1df7c7d`; [CI36203888784](https://github.com/scanipy/scanipy/actions/runs/36203888784), final [canonical36203888755](https://github.com/scanipy/scanipy/actions/runs/36203888755) SUCCESS/[APPROVE5841366654](https://github.com/scanipy/scanipy/pull/423#issuecomment-5841366654). Documentation/history only; no technical state promotion. |
| [#424 typecheck repair](https://github.com/scanipy/scanipy/pull/424) | `0e53e188c37805f95fd1121067c3146149cf735a`, 00:32:20 | [CI36204659879](https://github.com/scanipy/scanipy/actions/runs/36204659879), [canonical36204659884](https://github.com/scanipy/scanipy/actions/runs/36204659884) SUCCESS/[APPROVE5841471771](https://github.com/scanipy/scanipy/pull/424#issuecomment-5841471771). Typecheck coverage is not runtime acceptance. |
| [#422 E process evidence](https://github.com/scanipy/scanipy/pull/422) | `577f52d7dd081926cb58f899f72894299bdbefcb`, 00:55:51 | [CI36205864132](https://github.com/scanipy/scanipy/actions/runs/36205864132), final [canonical36206373394](https://github.com/scanipy/scanipy/actions/runs/36206373394) SUCCESS/[APPROVE5841693693](https://github.com/scanipy/scanipy/pull/422#issuecomment-5841693693). Initial [36202468921 REQUEST-CHANGES](https://github.com/scanipy/scanipy/actions/runs/36202468921) retained. Actual artifact `ba2fa0428f2a71c00dcd2c57fd55ed4ef510faed`; pure process-evidence codec only. |
| [#425 F journal](https://github.com/scanipy/scanipy/pull/425) | `c5c862e3035ac974af82be7f2b69680cf3ea4c70`, 01:40:40 | [CI36208369666](https://github.com/scanipy/scanipy/actions/runs/36208369666), all six jobs successful; final [canonical36208944335](https://github.com/scanipy/scanipy/actions/runs/36208944335) SUCCESS/[APPROVE5842009483](https://github.com/scanipy/scanipy/pull/425#issuecomment-5842009483). Initial [36208369654 REQUEST-CHANGES](https://github.com/scanipy/scanipy/actions/runs/36208369654)/[5841929079](https://github.com/scanipy/scanipy/pull/425#issuecomment-5841929079) while CI pending remains retained. |

Resolver B's merge has parents previous accepted `0e1b2b9a` and reviewed
`3e1cfc56`; the current accepted status supersedes older pending instructions.
Both hosted fixture failures above remain. Its first
[canonical36197035863](https://github.com/scanipy/scanipy/actions/runs/36197035863)/
[conditional APPROVE5840575210](https://github.com/scanipy/scanipy/pull/418#issuecomment-5840575210)
did not override then-pending/failed CI. Final review retained a LOW oversized
result-output uncaught-exception observation; the parent contained the failure
and no fallback falsely claiming an unread request or source fix was claimed. Separate
[Gate3 36201470146](https://github.com/scanipy/scanipy/actions/runs/36201470146)
had two successful jobs, but the actual canary suite was skipped: no full canary
acceptance follows. Root supplied these exact historical readbacks separately
from this documentation task's local ancestry check.

F's actual artifact `aaba679fc495d69fb933f221698511b466e74dd9` and accepted
merge have the complete identical tree `ea4d36f4e344a250d0ed1df7b9e8fc519c08deff`.
Recorded full report `/tmp/scanipy-runtime-journal-f-main-full.xml`:
**5,049 passed /51 existing skips /0 failures/errors**, 472.775s, SHA256
`60aa959d407360f8870b9b01f4224d3347dd5e16e2d94f5113acb07de23dbe96`.
The separate accepted-artifact check
`/tmp/scanipy-runtime-journal-f-accepted-425.xml` passed **853 /0 skips**,
26.146s, SHA256
`88b18dba6097134171e22139310c7fab684e7509c7b1f6e089abfb208b9fc998`.
These selections overlap; they are not additive unique coverage. E/F accept
pure immutable process records and supplied-history structural replay, not a
physical durable writer, visible/durable acknowledgment, runtime controller,
current admission, source custody or native execution.

### Pending #426 pure administration verification

Exact head `ed4dd545f907e024adca2f2d845aded71f98fe43`, three paths. Corrected
full `/tmp/scanipy-admin-verification-f-main-full-corrected-url.xml` passed
**5,213 /51 skips /0 failures/errors**, 500.495s, SHA256
`9e9dbc7e2c3696bc3afd72745b810340dea0e03a8c59359b18da87bb2b0d64c8`.
Included selections are 164 new pure controls, 89 actual occurrence PostgreSQL
and 309 journal cases, not additional totals. The first malformed root-provided
URL run remains **62 passed /24 skipped /one setup error**; its cause/result
is not attributed to the corrected URL or relabeled passing.

The first actual push passed all hook phases but failed transport with SSH
exit141. A normal retry passed all phases and pushed at02:10:51 without bypass.
At cutoff [CI36210889992](https://github.com/scanipy/scanipy/actions/runs/36210889992)
is IN PROGRESS and [canonical36210889947](https://github.com/scanipy/scanipy/actions/runs/36210889947)
pending. [Gate3 36210889929](https://github.com/scanipy/scanipy/actions/runs/36210889929)
is SUCCESS with five selected passes/5,259 deselected, but the actual canary
suite was SKIPPED because its corpus was absent. This is neither full canary
coverage nor a substitute for required CI/canonical or #426 acceptance.

### Local AL, packet and A1 custody state at the cutoff

AL-03 current `7c992e1578cd2f7613ad85c93d9928c9902a5aed` has 18 paths;
CI workflow SHA prefix `714942c8`. Its accepted-F unit composition report
`/tmp/scanipy-al03-accepted-f-combined-unit.xml` has **1,570 passed /0 skips**,
SHA256 `a096766b1466102ffac618b44c076475b43f61e0a0df007d1b4fe24ef6ecf83c`.
The earlier real-PG **145-case success** and later stronger single-test result
are separate observations; 145 predates the base-descriptor correction and
does not establish current-source full acceptance. Original SQL, fixture,
bytea-view, capacity, TRUNCATE-preflight and typecheck contrary evidence remains
in the AL checkpoint, not erased by subsequent passing selections.

The first CI commit hook rejected a secret-pragma attachment. Only the pragma
annotation moved; YAML semantics and accepted205 baseline stayed unchanged.
Normal corrected commit passed; 31 offline CI guards are distinct from hosted
AL execution. Fresh full85864 started **02:11:52 UTC** at
`/tmp/scanipy-al03-full-wrapper-HZOnWQGE/full-regression-junit.xml` and is
**RUNNING, no final result at02:14:58**. Its wrapper requires bounded catalog
equality before and in finally-after cleanup. The prior small disposable
cluster failures are not permission to reuse their endpoints; only root's
separately designated current task fixtures may be used. No concurrent query,
rerun, provisioning or source edit is authorized by this evidence append.

G packet codecs remain clean `eba073bcce4ee035f745f71249a035769b2108dc`, tree
`7dbfd666fb94f57e7af63b9fafc9c69ee9158d6f`, six-path scope. Report
`/tmp/scanipy-g-packet-accepted-f-composition.xml` passed **1,853 distinct /0
skips/failures/errors**, 27.204s, SHA256
`3c510196848573f14c51364c4cfb0e3ddd7ca82f4315452736e5d2e37481d164`.
Thirteen actual unit modules preserve the previous1,788 selection plus hook39
and ledger26. Earlier760-host repeats are not additional unique cases. Full,
normal push and hosted gates remain pending; structure-only declared hashes,
leases and intended invocation fields are not independently verified authority.

A1's original230 diagnostic passes preceded three independent defects:
admin root.pk8 exact metadata missing before yield, current/predecessor public
leaf reread missing before return, and scandir acquisition-to-cleanup handoff.
The first two original mocked-OS reds are retained at
`/tmp/scanipy-a1-root-review-UWkC9U3T/root-key-layout-original.xml` (SHA256
`249896d271798272a71d99a5f52ffd1d8a9b50e8673bdb8a16bab75e6af17193`)
and `/tmp/scanipy-a1-public-reread-review-j5ntiYvg/public-reread-original.xml`
(SHA256 `29abe6729f72866d24c36e99f17480eac6df79f123d18731667bd1598c23737e`).
Their corrections passed283 repository +the same2 outside=**285**, not285 new
unique tests: `/tmp/scanipy-local-authority-a1-correction.xml`, SHA256
`387d4745c809274f596a48a2caa71c215f71a9e3139fd07efa47ee21285c2ace`.
At cutoff the third independent red has **one failure, actual iterator close
count0** and correction is underway. Later results are excluded from this
snapshot. No fixed-origin real-key/UID fixture, SQL, operator installation or
complete A1 approval has occurred. Peer design review is not hosted canonical
approval; the fixed-child cleanup comment no longer claims general descendants.

### Dependency-ordered next actions, without acceptance promotion

Finish actual #426 CI/canonical/merge gates; inspect AL full XML and exact
catalog equality before its publication queue; finish A1 third correction
review before any separately approved real-custody fixture staging; allocate
G full/push/hosted gates. Then implement genuine A2 ledger/provider/CLI and
current tenant-local builtin authority, qualified physical RES/journal and
event/spool/full-reader, capacity/work isolation, DB barriers and bounded
controller/bootstrap/native CPG/source integration. Complete occurrences,
independent identities, signed provenance, lifecycle/decisions and truthful UI.
Original Java/Python, Semgrep/CodeQL, comparator/reproduction, all422/844 campaign
and G0–G3 requirements remain. Global/inferred publication stays later extension
work under the current decision; it does not replace required tenant-local work.

The owner-confirmed machine/local Docker choice is unchanged. December2 or3,
exact day open; no October lock, new operator identities/restore authority,
release/image permission, user app/DB change, stage technical VERIFIED, umbrella
Done or task/claim/gate/DAG promotion is introduced by this documentation.

### Explicit later update — 02:26 UTC

Root's clock read02:26:09 UTC. These are later observations, not changes to the
02:14:58 snapshot. Accepted main is still `c5c862e3`; board399/362/400 all read
In Progress at02:22:57 and no board mutation was made.

PR426 exact `ed4dd545` now has all six CI36210889992 jobs SUCCESS. Root fetched
the actual checked-out synthetic merge `be8f96c257489175c2ecb44dac303ca6811868a0`,
verified parents c5c862e3/ed4dd545 and whole tree
`b152714d80d13acd380af35c38abe967ff874902`, identical to the tested candidate.
The actual occurrence guard at02:12:58.2524700 verified89 executed cases/no
skips; strict Mypy checked122 sources. Separate Gate3's five passes/canary
suite SKIPPED limitation is unchanged.

First canonical36210889947 completed FAILURE: actual gate02:15:32.3167017
parsed REQUEST-CHANGES. [Comment5842267656](https://github.com/scanipy/scanipy/pull/426#issuecomment-5842267656)
requires correcting component attribution and the then-pending CI evidence.
Root corrected only PR title/body to CMP-ORCH-03, the same accepted verifier
owner in #418/final comment5841154346, and checked actual CI items. Head/tree,
all three own files and baseline remained exact. No new component, historical
AC reassignment, CLAR resolution or automatic umbrella closure was introduced.
No fresh canonical approval or merge is yet claimed; both remain required.

A1's third finite cleanup correction is frozen at source
`c704d33698671069ea44c0b8c36c74bec8c46f8d8cd5a49c733f454197000837`.
Author293 repository +4 unchanged outside handoff controls +2 prior controls
passed299/0failures/errors/skips,2.177s:
`/tmp/scanipy-local-authority-a1-three-fixes.xml`, SHA256
`079ddca9daa98d2b7848950e6c9ee722e1f411d3be90f4a71a252edfbcec04c9`.
Independent repeat passed the same299/0,2.232s:
`/tmp/scanipy-a1-names-control-RcOZbMsY/names-correction-peer-299.xml`, SHA256
`ae959bb1e3bf96dcf77db203de486f6a897a4f8ebeb240ea0ed49f2f67d99379`.
Root read the corrections and independently parsed both XML reports. The
root review `/tmp/scanipy-a1-root-review-UWkC9U3T/REVIEW.md`, SHA256
`9a486c6b89d555042e6a76111c40e32487e596fe16d9fa69a955a5bbd99a5913`, retains
all three original reds and the230/285 checkpoints. These are overlapping
diagnostics, not598 unique cases or actual kernel/UID/private-key custody.
Original1927 resolver lines remain exact; no whole A1/hosted/operational
acceptance follows. Only an outside bounded context/build/ABI recipe is being
prepared; no snapshot copy, build, launch, key generation or SQL is granted.

AL full85864 is still running without a final XML/catalog outcome. Its tree
must stay frozen. The proposed AL contract/PR's misleading DET-02 attribution
also requires a reviewed correction to the worker-input boundary with explicit
coordinated schema/CI scope after this run, not a historical acceptance claim.
G and the full tenant-local runtime/source/provenance/UI acceptance queue remain
unchanged. None of these later observations promotes R/C/G or release/stage state.

## Revision 17 — 03:45 UTC cutoff, September 26

This is a new dated observation, not a rewrite of Revision16's pending statuses.
The draft clock read was03:46:01 UTC; only outcomes available by03:45 are used.
Accepted main is `ecc341613731254f84145bd8058b8cee4529385d`, tree
`bafba3fd014dbced7cf64664acfb0bbe8ed0db3a`. Root retains coordinated ownership;
no task/claim/milestone/DAG/shared-gate status or old checklist is promoted.
The submitted single-tenant target, all Java/Python/oracle/provenance/lifecycle/
UI requirements and separate release/stage obligations remain intact.

### Accepted administration, documentation and AL foundations

[Pure administrative verification #426](https://github.com/scanipy/scanipy/pull/426)
merged as `4504e741ab9068127d9c1ff5d266339e6ccf23ef` at02:45:14 UTC after
the existing six-job CI36210889992 and fresh
[canonical36212167151](https://github.com/scanipy/scanipy/actions/runs/36212167151),
final [APPROVE5842421256](https://github.com/scanipy/scanipy/pull/426#issuecomment-5842421256).
The original REQUEST-CHANGES5842267656 remains in Revision16: correction was
actual CMP-ORCH-03 scope/CI metadata, not new source, component reassignment or
CLAR resolution. [Revision16 #427](https://github.com/scanipy/scanipy/pull/427)
is accepted as `84d08691ace4f1383a2eb699d41ce1d49b67e864`; its historical
snapshots remain unchanged below this current pointer. Neither closes a full R/C.

[AL #428](https://github.com/scanipy/scanipy/pull/428) has all seven jobs in
[CI36213389189](https://github.com/scanipy/scanipy/actions/runs/36213389189)
SUCCESS by03:07:07. Its first canonical36213389169 REQUEST-CHANGES on
CI/checklist/board timing is retained in
[comment5842582209](https://github.com/scanipy/scanipy/pull/428#issuecomment-5842582209).
Only the body changed before successful
[canonical36214026407](https://github.com/scanipy/scanipy/actions/runs/36214026407),
final [APPROVE5842665586](https://github.com/scanipy/scanipy/pull/428#issuecomment-5842665586).
The actual gate parsed APPROVE at03:18:09.9140078 and recorded RULE-10 PASS
at03:18:09.9140947. No failed action is counted as approval.

AL merged at03:21:28 as `2aa401dad9c305418ddb98930a158761b80c4cd2`, tree
`3b1cbfb69e8d170cc35a49da3a018ed88e49b356`, parents84d08691/0e972f75.
The entire tree equals hosted checkout
`afa14212d5fd2e5449e0abbdc5a3f523a838d722`; all18 AL paths equal the reviewed
candidate, with the four Revision16 documents separately inherited unchanged.
Its primary worker-input owner is CMP-ORCH-03 with coordinated CMP-CP-03 schema
and ordinary CMP-CI-01 coverage, not historical detector-registry completion.
CLAR-BHMEA-01/02 stay OPEN; no umbrella closing keyword or Done promotion.

Actual AL artifact10896128892 has **145 unique passes /0 failures/errors/skips**,
384.935s:43 SQL +102 security. XML SHA256
`408f850522ed669b38840152facc01451a639b39d2127149333b76f31530d398`.
Its before/after catalogs are byte-equal1203 bytes, SHA256
`94dd8b9019afd5518e7c296e5b2b624d4341915ec852910a007f0c2fd046e2b4`:
four exact DB/OID/owner rows, unchanged roles with expected al03_admin/OID10,
and no other clients. Actual occurrence **89 passes /0 skips**,24.742s,
XML SHA256 `582430120cfb116cb7b174337743401eb8c51a9d3355ca761721c6452530be28`.
Attestor core5 passed but its actual canary corpus was absent/skipped; do not
infer full Gate3 or500-canary acceptance from that separate check.

The completed earlier root full85864 on exact7c992e15 contains **5,713 passes /
51 existing skips /0 failures/errors**,1370.956s, including actual145 AL,
89 occurrence and519 AL units. Report
`/tmp/scanipy-al03-full-wrapper-HZOnWQGE/full-regression-junit.xml`, SHA256
`64b2ee29cf5503f703cb303c28b85a4a88fb6986c890e67f5565a881976de9f6`;
both catalog observations equal94dd8b90 above. Earlier smoke/fixture/capacity/
descriptor and review failures remain in the owning contract and the retained
`/tmp/scanipy-al03-publication-handoff-O3HcNNqo/AL03-PUBLICATION-HANDOFF.md`.
Post-accepted run20918 separately passed **709 unique /0 failures/errors/skips**,
28.948s:286 AL-command +233 AL-repository +164 administrative +26
execution-state checker cases. Report
`/tmp/scanipy-al03-accepted-428.xml`, SHA256
`6a4d4a6d4f2b336d40bf770337f7b7c50683bb5d6060244fb3c6ca8eb83f1200`.
This is not another full or PostgreSQL run; counts across reports overlap.

### Accepted G packet codecs and actual hosted artifact readback

[G #429](https://github.com/scanipy/scanipy/pull/429) at exact
`b0d4107ba81c8697daf54c29e0d4e79f8cd97919` passed all seven jobs in
[CI36214691204](https://github.com/scanipy/scanipy/actions/runs/36214691204)
by03:34:09. [Canonical36214691089](https://github.com/scanipy/scanipy/actions/runs/36214691089)
completed SUCCESS at03:29:45 with full
[APPROVE5842747489](https://github.com/scanipy/scanipy/pull/429#issuecomment-5842747489).
Actual enforcement parsed APPROVE at03:29:40.9053188 and RULE-10 PASS at
03:29:40.9053902. The review's numerical wording760+346 is a typo: G has
414 packet +346 profile controls, **760 total**, not1,106 or new coverage.

Actual checkout logs for canonical, AL, occurrence, unit and integration name
`b3a76b9105c6e6a646dbac852d6fa6de52563fd4`, parents2aa401d/b0d4107,
tree`bafba3fd014dbced7cf64664acfb0bbe8ed0db3a`. The entire merge delta is the
six G paths, each Git blob byte-equal to headb0d4107; all other base paths,
including accepted AL, are preserved. G merged03:39:19 as
`ecc341613731254f84145bd8058b8cee4529385d` with this same tree and parents.
Pure packet/profile values are not installed or current execution authority.

Independent download/parse of actual hosted artifacts, not local inference:

- AL artifact10896509746: **145 unique passes /0 failures/errors/skips**,
  357.721s,43 SQL +102 security. XML SHA256
  `d55c3546dbed462a459d373e8a061437c0d0173224d2b658a3717bc4eac02ed2`.
  Before/after catalogs are byte-equal94dd8b90 above, preserving all four DB
  identities,15 role rows including pg builtins/al03_admin, and no other clients.
- Occurrence artifact10897285289: **89 unique passes /0 failures/errors/skips**,
  24.336s. XML SHA256
  `b8c616d87b2fc9d6cf829f9cc563faaf859d61889363c3eb9fa333b09d739af6`.
  No separate occurrence catalog artifact exists; AL catalog evidence is not
  attributed to that job. Both jobs' actual enforcement logs confirm execution.

Readback files are retained under `/tmp/scanipy-g429-hosted-review-T03V9b7y`:
complete canonical comment SHA256
`33be0832b876c295217bf02f52bc124284d932b77c07187c5cf48818b29517a3`,
actual enforce-step log
`9e08fa7c1f71e19c334cb5f9ccf4963264eac93b1bdd7d109e59b1a060d1b24d`
and six-file composition JSON
`a860d75d65295d60014dd674d667113fac91b3619bf1efa0992ad89a68043416`.

Root's distinct accepted-tree run85364 passed **2,536 unique /0 failures/errors/
skips**,62.192s, independently parsed from
`/tmp/scanipy-g-packet-accepted-429.xml`, SHA256
`6f2e17b5d01df2085a50cc88fd5d07808cbb5ddc3290438186c88267fad3a986`.
Its16 unit modules include G414+346, AL519 and administrative164, not extra
tests beyond2,536. Earlier full5973/51 atb0d4107 remains a separate prior-base
report, not a relabeled full/PG result on accepted AL/G composition. Quiet hosted
unit/application success is not assigned an inferred unique total.

### Local A1 native-test checkpoint and retained build refusal

Native-test candidate `fa2d209e465a1e099e2176d5acada82e5617ba32` was normally
committed with applicable hooks passing. Integration SHA256
`0a8f026affec37a23842d5aee502f7a6da365485fd16307a5436e1e14594f4b5`
and resolver SHA256
`414acc94b0bb59fc03307e713f55620fe89db51b8f13e4da990135d32ba63fe3`
retain all11 native test ASTs/38 cases; production owner66ac28e5 is unchanged.
Independent correction review and **48 synthetic passes /0 failures/errors/
skips**,0.610s, are recorded in
`/tmp/scanipy-native-custody-peer-PlLJeDVi/correction-peer-48.xml`, SHA256
`a3c8d0a46eb19329751b8d70ec7af622d7c84d6c281c07582977c784f50de49d`.
The author48 repeat overlaps. Original duplicate-cleanup and post-acquisition
interruption reds remain preserved; the sole cleanup owner now retains original
primary/cleanup evidence. **All38 native cases remain unexecuted.** No real
UID/key/lock/fsync success or installed/operator authority follows from fakes.

The actual bounded snapshot manifest `de5b602a` succeeded. Build-only68174
failed on the first read-only base-label projection; no build/name/create call
occurred. Its old `build-run/base.json` hash is
`e88bcd3765c00c198585ab6805bbe0f0aa7e0ddbc6bdcd94234648678d0db16b`.
After scoped formatter review, the bounded read-only projection probe passed;
`/tmp/scanipy-a1-watchdog-execution2-K2bI1AnV/base-probe/base.json` SHA256
`258471c6324f26bd379885f1e5793fb5b910ce137b744b8ee8eeac849ee0e4f4`.
Second actual invocation17413 retained Docker build exited/code0,
cleanup completed,24,212ms, stdout1,480/stderr209 bytes, EOF/untruncated.
Its `build-run/build.json` SHA256 is
`0520220db9c58d647030a9578f1e05a33cfedb94ada57648a5453c2f87165745`.
The driver nevertheless **exited1** when iid mode0664 failed exact custody;
`build-run/build-state-unknown.json` SHA256
`2fec45e78efd74ccad66dc5d4d406bf68aaf67c898467cf758532155e77e716c`
retains `BUILD-STATE-UNKNOWN`. There is no final-image inspection/result or
smoke/native acceptance. Keep the actual image/context and all old evidence;
Docker's successful return does not repair the watchdog's failure.

At this cutoff, exact-owned reconciliation and scoped umask/optional-Mounts
corrections are **preparation only**, not executed recovery, a new build or a
smoke grant. The reviewed ABI-only image plan is distinct from a new pinned
context needed for the38 real fixed-origin custody cases. A2 dependency
integration in the separate `RJLQcFmW` worktree is in progress; no A2 source
implementation or real builtin publication has occurred.

### Required continuation without status promotion

Root must review/authorize reconciliation, corrected driver and any separately
pinned smoke; then review a new38-case context and grant the actual isolated
custody fixture. In parallel after dependency checks and explicit source
allocation, implement/unit-test the reviewed seven-path A2 tenant-local builtin
administration/provider/CLI against real owners, preserving prior policy reads,
original signed bytes, replay/currentness and independent DB/head/ack recovery.
Real custody/PostgreSQL/operator gates precede enablement and acceptance, not
safe source/unit implementation. Identities, pins and restore policy remain
explicit owner choices.
Continue qualified RES/event/spool/full-reader, physical capacity/work isolation,
DB barriers and actual current factory/kernel/controller/source/database/native
integration. Finish occurrences, independent identities, provenance, decisions,
API/UI and every original submission gate/rehearsal. Do not insert later global
adoption or inferred publication as new acceptance prerequisites.

Root rechecked #400/#362 In Progress around03:36 before G acceptance; no board
change is performed here. Current host/owner facts, untracked user files, app/DB,
December2/3 window with exact day open and separate release/image permission
remain unchanged. This draft runs no native work and grants no installation,
execution, release, stage VERIFIED, task Done or shared-gate PASS.

### Explicit later update — 03:48 UTC

Root reports completed dependency preparation; direct readback confirms clean
`/tmp/scanipy-builtin-administration-a2-RJLQcFmW` at
`dc0c7f63dce9fbac0ba77a2d17250a8fb00d67b6`, tree
`e357b2303478d6f5f3c97766d77ef4e7f861b1f0`, parents
`fa2d209e465a1e099e2176d5acada82e5617ba32` and accepted
`ecc341613731254f84145bd8058b8cee4529385d`. The24 incoming accepted files
equal ecc34161; four A1 files equal the native-test checkpoint. No A2 source
implementation is added or allocated by this integration.

Distinct report `/tmp/scanipy-a2-dependency-check-DfC3ePYx/unit-976.xml`, SHA256
`8b5b6b2b7d3b914bc2281ea57d6c1faab8a3965f2c92d32a61c32e5d35963f34`,
independently parses as **976 unique passes /0 failures/errors/skips**,31.591s.
It is dependency-unit evidence, not another full/native/PG run or new installed
authority. It does not backdate completion into the03:45 snapshot or add to the
overlapping48/709/2,536 totals. Reconciliation/scoped driver correction, pinned
smoke, actual38-case custody, operator choices and the real A2 path remain gated.

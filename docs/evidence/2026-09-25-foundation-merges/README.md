# September 25 — reviewed foundation corrections

Scope: repository correction evidence, not Black Hat feature acceptance.
Snapshot main: `022365123d0a14127e2039dc005606a7401bc358` on 2026-09-25.
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
  are not real Java/Python semantic acceptance. #369 must make the combined
  actual-producer/deadline regressions permanent. Source-only snapshot/final
  persistence, full environment production and async occurrence retention remain.
- #383 fixes the stale lock-byte declaration and adds missing Python runtime
  dependencies without changing tool/base pins. Final local suite: 1,043 passed /
  47 skipped. The resulting image has not been built, installed, promoted or
  published by this correction; a valid hash lock is not a working container.
- #379 has 95 hermetic checks. After quota reset, root used it to verify real
  project metadata and status transitions. It is bounded/fail-closed, not an
  atomic ownership lock. The root coordinator still serializes changes.
- #385 is a design-only contract, not schema/API/worker implementation. A later
  pure matcher checkpoint `a2ffb71` has 130 controlled tests and a lifecycle
  generation repair; it is not merged or production-enabled in this snapshot.
  Its production policy registry remains empty.
- #387 fixes both masked hook failures and declares yamllint 1.35.1. It has
  33 focused tests and a fresh declared full run of 1,180 passed / 48 skipped.
  The actual changed commit/push hooks passed; runtime image and full release
  acceptance remain separate.

Narrow issues #365/#367/#363/#377/#381/#384 and the earlier #370 are closed after
their reviewed corrections. #361/#362/#366/#374/#376/#378 remain open for their
larger scope. GitHub auto-closed #378 when it parsed a closing keyword inside
a negated sentence in #385; root removed that wording, reopened #378 and
restored In Progress. This accidental closure is not acceptance evidence.

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

Current worker/R05 callers construct explicit environments, so dependency
fetching currently defaults off; the legacy arbitrary environment input and
implicit Delombok behavior still need correction. #386 owns a closed versioned
Java profile and value-aware invocation grammar. Both parse and export must use
it. An explicit profile parameter is validation context, not authentication;
unprofiled direct scripts and other frontends remain outside that narrow proof.

Required follow-up: hermetic unsafe-override negatives; reviewed bounded real
scanner-only sentinel/process observations; descendant cancellation; file
coverage/error evidence; final Compose restrictions. Never execute an unsafe
target-build positive control. Missing generated/type/binding semantics remain
R19 fidelity work. R16 is not complete.

## Other active falsifiers and next actions

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
- #369: integrate actual four-class producers and explicit legacy-default
  rejection; time exhaustion must remain a failed analysis, not a weak success.
- #380/#382: integrate reviewed current main and obtain canonical approval.
  Raw transport is not semantic mapping, call binding, matched returns or
  purity. R05 reports unavailable semantic observations honestly; it may not
  copy expected corpus labels into observed success fields.
- Before a corrected image or real campaign, recheck host resources and run
  bounded sequential startup/Java/Python probes. Source parser safety and
  packaging must be reviewed first; full 844-side evidence follows readiness.
- Preserve all remaining R01–R20 TODOs and exact submission scope. Actual stage
  hardware/date and separate release/image/video authority remain future inputs.

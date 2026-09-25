# R13-CQ-OBS-01 — CodeQL SARIF observation and adapter roadmap

Date: 2026-09-25. Status: **PROPOSED — design only; root review required**.
Author: core/canonical agent, under the root's read-only R13 allocation.
This file is outside the repository. It authorizes no implementation, engine
execution, installation, key publication, database migration, or release.

## 1. Outcome and non-negotiable scope

The first proposed component retains and interprets bounded externally supplied
CodeQL-style SARIF bytes. It does not scan source, run CodeQL, authenticate the
report's producer, or emit production findings. Its success means that the
specified observation projection was constructed, not that analysis completed.

The full submitted CodeQL adapter remains required. The submission promises
established detection engines including CodeQL, CWE/origin labels, analysis
without executing scanned code, identity/provenance integration, and measured
oracle reproduction. An import-only entrypoint must be explicitly labelled as
such; it cannot be advertised as built-in repository scanning.

Keep these four milestones separate:

1. **Pure observation component:** this proposed codec and controlled tests.
2. **Real import adapter:** actual CodeQL-produced output at a documented import
   entrypoint, with source association, accepted rule/CWE/class mapping, failures,
   and authentic evidence boundaries. This can establish the declared import
   component milestone; it does not establish native scanning.
3. **Native source adapter:** reviewed extraction/query/runtime profiles and
   actual positive executions, without target execution or unapproved build
   hooks. No supported mode is selected by this document.
4. **Shared G2 integration:** durable raw retention, R09 identities, R11 measured
   fresh reproduction, R12 signed provenance, R14 comparisons and final UI.

Neither 1 nor a fake/synthetic report can satisfy 2–4. The first import component
does not wait for final R11/R12 consumers before supplying real output to them.
It also does not silently remove native source support from the full objective.

## 2. Inspected implementation and precise gaps

The production-code audit is pinned to accepted commit
`1b29100ad9c96ebab9a4ac1a439fc2a5b19ac2ee`. During the audit the root advanced
main to `d4ad0c0b692cef4539d5333c60066cdcedecfb4e`; its delta consists only of
four progress/review/ledger documents. All production files listed below and
the submission are byte-unchanged across those two commits.

| Evidence at the audited commit | Consequence for the implementation plan |
|---|---|
| `workers/pins.json:21` names CLI 2.20.0 and archive SHA256 `669f70ead993acbc04a719be342d761544e4240209a283c9d1e1916402930460` | A declared archive pin is not installed-runtime verification or a runnable adapter; this audit downloaded no archive. |
| `detectors/registry.py:111–156`; all three shipped manifests use IFDS; no shipped CodeQL query/pack | No actual CodeQL rule set, metadata mapping, or supported-language execution is established. |
| `services/scan/worker.py:290–334` | Oracle port exists; production default raises. A protocol does not implement CodeQL. |
| `worker.py:399–414` | `as_detector_like` omits the registry's CWE, languages and oracle-query fields. A later adapter cannot recover them by guessing. |
| `services/scan/detector_worker.py:514–669` | Job path requires a CPG, lacks an injected oracle adapter and signs with `sarif_hash=None`; source-only/import admission needs a separate reviewed integration. |
| `services/scan/semgrep_observations.py` | Useful bounded raw-span/parser precedent, but Semgrep schema and private helpers are not a CodeQL public codec. |
| `services/scan/oracle_attestor.py` | Existing actual runner is Semgrep-specific, not a CodeQL runner. |
| `services/scan/attestor.py:253–280` | Existing rate compares unique canonical result projections against run 1; empty baseline yields 1.0000. Do not silently change that metric or claim nonempty acceptance from it. |
| `db/migrations/versions/20260524_0001_initial_tenancy_tables.py:347` | `UNIQUE(scan_id, partition)` cannot represent independent per-engine measurements in the same partition. |
| `services/scan/oracle_fingerprint.py:116–167` | File/line lookup prefers CALL, then column, then node ID. That deterministic tie-break is not proof of semantic association for CodeQL. |
| `analysis/artifact_identity.py`; R09 serializers | Graph and slice class/namespace/status are independent. Vendor fingerprints cannot fill either structural artifact. |
| `analysis/sarif/canonical_emit.py` | Output normalizer is not a lossless native SARIF import path. |
| `services/scan/source_capture.py:19–23,322–331,477` | Real custody and exact source-inventory bytes exist; an in-memory inventory join is not a custody/lease/SCM proof. |

The active R13 checklist at the audited review's lines 926–959 requires the
real adapter, precise supported entrypoint, query/runtime/failure contracts,
real positive, permitted distribution, and downstream integration. Preserve
all C01–C18/R01–R20 requirements; this proposal checks none of them complete.

## 3. Primary-source evidence and its limits

All retrievals were read-only on 2026-09-25 UTC. The web tool returned a backend
404; bounded HTTPS GETs of documentation/schema/release metadata were used.
No CodeQL executable, query pack, database, source archive, or installer was
downloaded. Digests below identify retrieved document bytes, not loaded code.

| Source | Exact reference and raw SHA256 |
|---|---|
| GitHub SARIF documentation | [Pinned documentation](https://github.com/github/docs/blob/2494c728029507123c2b4e5bde28e5524e3bd27c/content/code-security/reference/code-scanning/codeql/codeql-cli/sarif-output.md), SHA256 `0af3f160cb4a3ab9c3d431032f13086b9753c3c219601f1786e37a8023865503` |
| GitHub compiled-language build documentation | [Pinned documentation](https://github.com/github/docs/blob/2494c728029507123c2b4e5bde28e5524e3bd27c/content/code-security/reference/code-scanning/codeql/build-options-for-compiled-languages.md), SHA256 `4405522fcbcf2a6110f0535cee101d4c5f8d79ded3e9b6484c9145b543c4219c` |
| OASIS SARIF 2.1.0 errata 01 schema | [Official schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json), SHA256 `c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e` |
| CLI release | [Official 2.20.0 release](https://github.com/github/codeql-cli-binaries/releases/tag/v2.20.0), published 2024-12-09T17:28:53Z; release API ID 189494195 |
| Compatible query source reference | [Annotated tag object](https://api.github.com/repos/github/codeql/git/tags/36ecffd1d91df21316e272429587f05f3d2552e7), `codeql-cli/v2.20.0` targets commit `3b2e55bc2ac942ac2cf2646f5c69acd081ce8ea2`; this is not a built pack digest or installed-pack attestation |
| CLI terms | [Official pinned terms](https://github.com/github/codeql-cli-binaries/blob/778dd2254be47d7d9e039a8c412032ad18126941/LICENSE.md), SHA256 `f4637e78a23b768634fad409599e72c81e288286fb0de0a086abe709583beb26` |

Relevant observations from the GitHub SARIF documentation: rules can be listed
without being executed; default result grouping can combine query outputs;
native partial fingerprints and code flows are optional/engine-owned evidence;
format details may change. These are current documentation statements, not
empirical CLI 2.20.0 output guarantees. The proposed codec preserves what is
present rather than reconstructing unreported results.

Two documentation/schema differences require caution: the GitHub table spells
`newLineSequences`, while the normative field is `newlineSequences`; the table
mentions artifact `index`, whereas the normative index is on artifactLocation.
Preserve unexpected keys as raw observations, never silently rename them or
use these descriptions to fabricate a pinned native fixture.

The current Java no-build documentation describes dependency discovery through
Maven/Gradle. Consequently a build-mode name alone is not a C16 safety argument.
Pinned extractor/launcher behavior, actual closed invocation, dependencies and
runtime isolation need a separate review before any native experiment.

The CLI terms are separate from Scanipy's Apache-2.0 source license and contain
use/distribution/hosted-use restrictions. This note makes no legal conclusion
that the planned use or redistribution is permitted. Obtain the applicable
terms/entitlement and owner decision before installation, bundling or release.

## 4. Proposed first implementation ownership

Exactly three new repository files, after root approval and issue allocation:

- `services/scan/codeql_observations.py`: pure codec, raw-span observations,
  bounded source-inventory path joins; no native/process/FS/network behavior.
- `tests/unit/test_codeql_observations.py`: hermetic adversarial tests with
  module-level `pytestmark = pytest.mark.unit`.
- `docs/bhmea/CODEQL-OBSERVATIONS-CONTRACT.md`: reviewed version of this contract
  and honest checkpoint evidence.

No first-slice edits to registry, worker, oracle fingerprinting, SARIF emitter,
Semgrep, dependency pins, Dockerfiles, SQL, accepted-input authority, source
capture, UI or submission. No real native fixture is invented. Controlled
JSON is labelled synthetic; later retained real fixtures require separate scope.

Do not import Semgrep's private parser. A small separately tested bounded JSON
span reader may live privately in this new module; sharing/refactoring parsers
is a later explicit change, not an opportunity to expand this three-file slice.
Use stdlib only. Never dynamically load a schema, codec, query, plugin or module
from report fields. The schema URLs are metadata, not fetch instructions.

Proposed identifiers:

```text
observation profile = scanipy-codeql-sarif-observations/1
archive schema      = scanipy-codeql-observation-archive/1
raw-result key      = scanipy-codeql-sarif-result/1:<raw-result-sha256>
expected CLI pin    = 2.20.0 (comparison target, not producer authentication)
```

These are new, pre-deployment formats. They do not reinterpret existing
Semgrep, SARIF emitter, graph-v2/slice-v2, or signed historical formats.

## 5. Exact public boundary and absence semantics

Proposed functions, with their names fixed for review:

```python
parse_codeql_observations(
    report: bytes | None,
    *,
    stdout: bytes | None = None,
    stderr: bytes | None = None,
    returncode: int | None = None,
    source_inventory: bytes | None = None,
    source_root_aliases: tuple[str, ...] = (),
    limits: CodeQLObservationLimits | None = None,
) -> CodeQLObservations

encode_codeql_observations(
    observations: CodeQLObservations,
    *, limits: CodeQLObservationLimits | None = None,
) -> bytes

decode_codeql_observations(
    archive: bytes,
    *, limits: CodeQLObservationLimits | None = None,
) -> CodeQLObservations
```

`report` is a report-file payload; it is not automatically process stdout.
Optional channels distinguish unprovided (`None`) from observed empty (`b''`).
External import normally has no process observations. A supplied return code
is retained as input-channel evidence, not authenticated execution; use exact
signed 32-bit int, excluding bool, or None. Never synthesize zero on import.

No tenant, commit, `S_version`, environment or ExecutionBinding is guessed.
The later owning adapter supplies and verifies that execution association
outside this pure artifact. Importing a valid UUID or a digest would not prove
it. No result of this API is an authority-bearing permission or DB receipt.

Exact built-in bytes, tuple, str and int are required at public inputs. Limits
and output carriers are exact frozen/slotted, non-content-repr dataclasses.
Freeze nested primitive values before use; frozen dataclasses can be mutated
with low-level Python operations and are not constructor-history evidence.
Missing/poisoned slots or subtypes cause stable typed errors without invoking
instance validators, properties, conversion callbacks, equality or repr.

Suggested error classes are `CodeQLInputError`, `CodeQLLimitError` and
`CodeQLArchiveError`, with closed reason codes and numeric bounds only.
Raw report/log text never enters normal exception strings. Private original
causes may be retained for diagnostics; normal UI/logging must not stringify
those raw cause chains. No callback or custom JSON object hook is accepted.

## 6. Resource and parser contract

These are conservative implementation ceilings, not measured stage budgets.
All limits may be lowered by trusted configuration, never raised above /1.
Check limits' primitive snapshots independently before touching payloads.

| Limit field | Hard /1 ceiling |
|---|---:|
| `max_report_bytes` | 16 MiB |
| `max_stdout_bytes`, `max_stderr_bytes` | 1 MiB each |
| `max_inventory_bytes` | 1 MiB |
| `max_archive_bytes` | 20 MiB, including manifest, framing and all payloads |
| `max_manifest_bytes` | 64 KiB |
| `max_result_bytes` | 1 MiB per emitted result element, including malformed elements |
| `max_runs` | 8 retained runs; supported projection is exactly one run |
| `max_results` | 10,000 across all runs, including malformed/duplicate elements |
| `max_rules` | 10,000 across all driver/extension rule arrays |
| `max_artifacts` | 20,000 across all runs |
| `max_depth` | 32; root depth zero, every array/object descent adds one |
| `max_values` | 250,000 across report plus inventory, counting object keys too |
| `max_string_bytes` | 1 MiB per decoded UTF-8 string |
| `max_number_bytes` | 128 per numeric lexeme |
| `max_inventory_files` | 10,000 |
| `max_source_path_bytes` | 1,024 UTF-8 bytes |
| `max_source_root_aliases` | 8, each nonempty and at most 128 UTF-8 bytes |

All positive integer fields exclude bool. Admit len before copying/decoding;
bound raw and escaped/decoded string size before materialization. Check queue
and aggregate value counts before adding parser nodes, not after building an
unbounded document. Keep linear storage in payload size plus parsed node count;
do not materialize every ancestor path for every node.

The archive manifest has an additional fixed 256-value/8-depth parser ceiling;
its values are not charged again to the report/inventory counter. This keeps
parse and archived replay on the same data budget. Each complete reparse is
separately bounded by the same ceilings; do not accumulate all intermediate
forests from validation/replay. Resource-limit refusal takes precedence over
ordinary malformed-data handling once any cap is exceeded.

Strict UTF-8 JSON accepts one root value followed only by JSON whitespace and
EOF. Reject duplicate object keys at every depth, nonfinite numeric extensions,
bad escapes/UTF-8/unpaired surrogate escapes and concatenated documents. Unknown
valid JSON number lexemes remain raw spans, not float conversions. Known index,
length and coordinate fields require an exact integer lexeme in their declared
range; `true`, `1.0`, `1e0` and oversized integers are not accepted as indices.
No YAML, compressed data, zip/tar extraction, external references or encodings
selected by input are supported.

Malformed JSON inside a within-budget report produces a retained
`parse_status=invalid-json` observation, with no fabricated result prefix.
Valid JSON with an unsupported envelope is retained with that distinct status.
A resource violation raises `CodeQLLimitError` and produces no completed
observation or accepted prefix. The actual future ingestion owner must retain
the bounded raw input/failure before this call; the pure parser does not claim
to provide durable storage. Above-cap input requires bounded quarantine/refusal
evidence at its transport, not an unlimited allocation to preserve it.

## 7. Lossless observation schema

The archive retains original raw payloads. Public views reference spans into
those payloads; they must never replace them with canonicalized vendor JSON.
Use exact half-open byte offsets `0 <= start <= end <= len(report)`.
Each span must delimit the exact parsed JSON value it claims to represent.
Issue spans always refer to report bytes; inventory/channel-only issues use
None and never mislabel an inventory offset as a report location.

The following are the closed public carrier fields for the first slice:

```text
ByteSpan(start:int, end:int)
FieldSpan(name:str, key:ByteSpan, value:ByteSpan)
Issue(code:str, span:ByteSpan|None)
RuleJoin(status:str, rule_ordinal:int|None)
PathJoin(status:str, source_path:str|None, inventory_ordinal:int|None)
LocationObservation(ordinal:int, raw:ByteSpan, fields:tuple[FieldSpan,...],
                    path_join:PathJoin, region:ByteSpan|None,
                    issues:tuple[Issue,...])
ResultObservation(run_ordinal:int, result_ordinal:int, duplicate_ordinal:int,
                  raw:ByteSpan, raw_sha256:str, fields:tuple[FieldSpan,...],
                  rule_join:RuleJoin, locations:tuple[LocationObservation,...],
                  issues:tuple[Issue,...])
RunObservation(ordinal:int, raw:ByteSpan, fields:tuple[FieldSpan,...],
               results_status:str, results:tuple[ResultObservation,...],
               issues:tuple[Issue,...])
CodeQLObservations(profile:str, report:bytes|None, stdout:bytes|None,
                   stderr:bytes|None, returncode:int|None,
                   source_inventory:bytes|None,
                   source_root_aliases:tuple[str,...],
                   limits:CodeQLObservationLimits, parse_status:str,
                   format_status:str, inventory_status:str,
                   runs:tuple[RunObservation,...], issues:tuple[Issue,...])
```

All digest strings in this component are lowercase 64-hex raw SHA256, never
environment/domain hashes. `fields` includes EVERY direct object field in its
original order, not merely recognized keys. Non-object result/location elements
retain their raw span, have `fields=()`, and carry an invalid-shape issue.
Nested unknown fields remain lossless through their enclosing value spans and
the complete raw report. First-slice consumers must not treat an untyped opaque
subtree as decoded semantic evidence.

Closed statuses:

```text
parse_status     = missing | parsed | invalid-json
format_status    = not-evaluated | supported-projection | unsupported | invalid
inventory_status = not-supplied | valid-data | invalid-data
results_status  = missing | present | null | invalid
RuleJoin.status = matched-driver-rule | unindexed-id | missing | invalid |
                  ambiguous | inconsistent | unsupported-component
PathJoin.status = inventory-match | not-supplied | invalid | missing |
                  outside-inventory | inconsistent | unsupported-uri |
                  unsupported-base | ambiguous
```

`RuleJoin.rule_ordinal` is nonnull only for matched-driver-rule. Path and
inventory ordinal are both nonnull only for inventory-match. Every other join
keeps these fields null, not a guessed candidate. All row ordinals are zero-based
actual array positions; spans stay inside the owning row and exact parse tree.
Parent/run/result ordinals must agree. These cross-field rules are enforced on
replay and on encoder input, not trusted from dataclass construction.

`supported-projection` means only the structural profile in §8. It NEVER means
full OASIS schema validation, authenticated CodeQL, completed scanning, query
coverage, source-byte association, valid finding, or lifecycle absence.
No overall `success`, `coverage_complete`, `is_finding` or `strong` boolean is
provided. Keep error issues ordered by deterministic document traversal, not a
set. Cap issues by `max_values`; exhausting that cap fails rather than dropping
diagnostics and reporting completion.

Reserve finite issue codes, rather than formatting attacker strings:
`invalid-json`, `root-shape`, `version-missing`, `version-invalid`, `version-unsupported`,
`schema-field-invalid`, `runs-missing`, `runs-shape`, `run-count-unsupported`,
`run-shape`, `tool-shape`, `driver-shape`, `driver-name-invalid`,
`driver-version-missing`, `driver-version-invalid`, `driver-version-conflict`,
`driver-version-mismatch`,
`results-shape`, `result-shape`, `message-shape`, `known-field-shape`,
`rule-reference`, `rule-ambiguity`, `rule-contradiction`, `component-unsupported`,
`location-shape`, `location-count-unsupported`, `artifact-reference`,
`artifact-contradiction`, `uri-unsupported`, `base-unsupported`,
`inventory-missing`, `inventory-invalid`, `path-outside-inventory`,
`region-shape`, `region-range`, `coordinates-unverified`,
`external-properties-unresolved`, `threadflow-reference-unresolved`,
`native-execution-failure`, `native-execution-claim-invalid`, `unknown-field`.
Every issue with an available offending value has that value's span. Unknown
fields are informational observations, not permission to ignore a contradictory
known field. Code review must close any additional reason code before use.

## 8. Supported structural projection and native metadata

The /1 interpreted envelope is an object with `version="2.1.0"`, exactly one
run object, a tool/driver object with a nonempty string name, and a present
results array. Missing results are not an empty scan. Other envelopes up to the
retention caps remain inspectable but not supported. Do not fetch `$schema`;
if present its string is retained and type checked, not accepted as authority.

Retain all runs/results even when their count makes the profile unsupported.
Do not use only run zero, sort results, or merge two runs. Tool component
`version`/`semanticVersion` are observed claims: compare present strings with
the fixed 2.20.0 target, record mismatch/conflict, and retain every original
field. A matching string is not loaded-engine evidence. Do not invent or strip
version suffixes to make a match. No undocumented pinned 2.20 name/field pattern
is asserted from current documentation or controlled JSON.

The direct result fields with known types are checked when present: message
object; string IDs/GUIDs/baseline-state/kind/level; integer ruleIndex and
occurrenceCount; object string maps for partialFingerprints/fingerprints;
arrays for locations, relatedLocations, codeFlows, suppressions and taxa.
The recognized SARIF enum domains are checked against the pinned normative
schema. An unfamiliar enum value is retained with an issue, never relabelled.
The type checker does not recursively claim schema validity of every optional
opaque SARIF subtree. Store their exact field spans and classify them opaque.

The initial literal domains/ranges are closed, not dynamically loaded:

```text
result.kind = notApplicable | pass | fail | review | open | informational
result.level = none | note | warning | error
result.baselineState = new | unchanged | updated | absent
suppression.kind = inSource | external
suppression.status = accepted | underReview | rejected
run.columnKind = utf16CodeUnits | unicodeCodePoints
indices = -1 .. 2**63-1; occurrenceCount = 1 .. 2**63-1
lines/columns = 1 .. 2**63-1
charOffset/byteOffset = -1 .. 2**63-1
charLength/byteLength = 0 .. 2**63-1
```

The result message must have string text or string id; markdown alone does not
repair a missing message. Optional markdown is string, arguments is an array of
strings. Check each suppression object's required kind and optional status;
keep other suppression fields opaque. Check the direct `invocations` array:
each object must have exact boolean executionSuccessful, and a present exitCode
must be an exact signed 32-bit integer. False executionSuccessful, nonzero
exitCode, or an error-level toolExecutionNotification adds a failure issue;
none establishes actual process execution. Referenced/opaque notification data
cannot be treated as evidence of no errors. Missing values stay missing.

Known malformed shapes/ranges produce format_status=invalid; supported-shape
but out-of-profile version/run count/component/external-data reference produces
unsupported. Invalid takes precedence over unsupported. Missing report or
invalid JSON has not-evaluated format. Otherwise the status is
supported-projection, even though producer/coverage/source remain unverified.
Unknown uninterpreted fields alone do not invalidate this restricted projection.
Unmapped inventory/coordinates are separate join issues, not fabricated schema
failures. Mismatched CLI version or missing both version fields is unsupported;
conflicting present version fields is invalid. This is a fixed comparison
policy, not a claim about the full vendor version-string grammar.

Important interpretation rules:

- `run.language` is not evidence of the analyzed programming language.
  Preserve locale, artifact sourceLanguage, query metadata and future actual
  extraction-language evidence separately.
- Preserve driver rules/extensions/taxonomies/artifacts and their order. Rules
  listed as available are not an executed-query inventory.
- Preserve `guid`, `correlationGuid`, `occurrenceCount`, complete named native
  fingerprint maps, all suppression metadata and baselineState. No identifier
  or hash is silently selected as the universal finding key.
- Result ordinal is `(run_ordinal, result_ordinal)`, snapshot-local only.
  `duplicate_ordinal` is the number of earlier byte-identical result spans in
  THAT run. Preserve repeats and never collapse them into a set.
- The content key identifies exact raw result JSON bytes, not source semantics.
  Equal keys can legitimately occur at different ordinals. Different whitespace
  can change the key. Native `occurrenceCount` does not authorize manufacturing
  additional records or reconstructing grouped BQRS tuples.
- Keep native suppressions and baselineState as vendor observations. They do
  not create a Scanipy human decision, resolve an occurrence, suppress a future
  finding, establish absence, or change oracle origin.
- Code flows/related locations are native ordered observations, not Scanipy
  IFDS witnesses or an independently verified taint path. Preserve all of them,
  including multiple threads, location IDs and cached threadFlow references.
  Unsupported cached/external references remain explicit unresolved issues;
  nothing is downloaded, inferred or silently replaced by an empty trace.
- Keep message text/markdown/arguments/IDs verbatim as raw data. Do not render
  HTML, execute links, substitute message templates, or turn query help into
  trusted instructions in this component.
- Reported invocation success, errors, exit code and notifications remain
  report claims. Failed invocation claims cannot become successful-empty
  evidence. Preserve contradictory report/channel values together.

## 9. Exact rule and location joins

### 9.1 Driver rule joins

For first-slice interpretation, only `tool.driver.rules` is a supported indexed
rule table. Retain extension rules, but a reference to another component is
`unsupported-component`, not remapped to driver by name/index coincidence.
Conservatively, ANY explicit result.rule.toolComponent is unsupported in /1,
including apparently matching name/GUID; only implicit-driver references are
joined. A later extension can support explicit components with its own tests.

An explicit nonnegative ruleIndex must be in range and name an object with a
valid nonempty ID. If result ruleId or the result's descriptor reference also
provides identity, EVERY supplied identity must agree with that actual table
row. A missing/default index of -1 is not index zero. Invalid bool/float indices,
contradictory IDs/components or duplicate conflicting references never resolve.
Descriptor `rule.id`/`rule.index`, if present, must agree with top-level ruleId/
ruleIndex and the selected row. A supplied descriptor GUID is only a consistency
check against an actually present selected-row GUID; it is never an alternate
search key. GUID-only references without id/index remain unjoined. A missing
selected-row GUID cannot silently confirm a supplied GUID.

Without an index, exact ruleId can select a driver row only when unique. Zero
matches leaves `unindexed-id`; duplicate matching rows are `ambiguous`, even
if their content happens to be identical. An explicit valid index disambiguates
duplicate rows but does not prove execution or query acceptance. Never choose
the first row, last row, lowest ID, fuzzy suffix or a guessed query filename.

Preserve all supplied IDs and original clause/result positions. CWE tags and
taxonomies are observations. The later finding adapter needs an accepted exact
query-artifact-to-rule/CWE/class mapping; no ad-hoc string or help-URL heuristic
may supply mandatory findings metadata or change an oracle into a core result.

### 9.2 Optional source-inventory join — explicitly not custody

`source_inventory` is the original data artifact from the existing schema
`scanipy-execution/source-inventory/1`, not a new source receipt. Interpret its
closed keys as `{schema, files}`, with each row exactly `{path,size,sha256}`.
Paths are unique, sorted by UTF-8 bytes, relative POSIX paths; size is an exact
nonnegative int bounded by the existing 64 MiB/file and 512 MiB/total custody
ceilings; SHA256 is 64 lowercase hex. Require the owner's canonical JSON
spelling (UTF-8, sorted keys, no extra whitespace, no ASCII escaping of ordinary
Unicode), while retaining the exact supplied bytes. Invalid inventory is
retained and disables all inventory matches; it is never an empty inventory.

The future implementation must import the real existing schema constant and
cross-test this tiny data projection against an actual custody-generated
inventory. It does not duplicate CaptureReceipt, ExecutionBinding, source-tree
framing or an authority codec. This first archive records only the raw SHA256
of inventory bytes. The owner's domain inventory digest and source-tree digest
are different values; neither is verified from a path join or substituted for
the other.

No source file is opened. Matching a report URI to an inventory row establishes
only `inventory-match` with that row ordinal. It cannot establish actual source
bytes, region contents, source-tree completeness, commit ancestry, tenant
ownership, safe custody, current lease, or report/source correspondence. Those
require the owning verified capture adapter and immutable execution association.

The importer may supply a sorted unique tuple of root alias strings. Each
explicitly means "treat this uriBaseId as the root of THIS supplied inventory"
for a data-only join. It does not authenticate a report's originalUriBaseIds or
grant access to a filesystem root. Missing alias gives `unsupported-base`.
No alias may contain NUL/control characters (C0 and DEL/C1: codepoints 0–31
and 127–159); no custom mapping is accepted. The same exclusion applies to
inventory paths and percent-decoded URI paths. Other Unicode scalar values
are retained exactly, without normalization or a claim of full custody policy.

### 9.3 URI and artifact rules

Only a relative URI path is mapped in /1. Parse percent escapes once, require
strict UTF-8, and compare exact decoded Unicode without casefolding or Unicode
normalization. Reject absolute/network/file/scheme/drive forms, query/fragment,
backslash, encoded slash/backslash, NUL/control characters, empty or `.`/`..`
components. A literal `#` in a filename must arrive percent-escaped; double
decoding is forbidden. Unsupported raw forms are retained, not sanitized into
an apparently safe path. No FS resolution, symlink following or path opening.

An inline artifact index resolves only within its actual run artifact table;
-1/missing means unindexed. If both URI/base and index are present, the indexed
artifact location must exist and agree with the inline location's decoded path
and alias identity. Otherwise mark inconsistent/unresolved; never select an
arbitrary same-name artifact. Preserve duplicate artifact rows and explicit
indices. A direct URI can join inventory without borrowing an arbitrary
artifact row's hashes/metadata. Embedded artifact contents never replace source
bytes or execute; their raw fields remain opaque.

Original URI bases and chained bases are retained. No base chain is resolved in
/1. Report-side absolute base URIs are not filesystem permissions or verified
capture roots; an asserted alias does not erase a contradiction or unsupported
chain. All base choices remain explicit in the archive. An invalid/inconsistent
URI or artifact reference keeps that status even when its base is also
unsupported; base interpretation cannot hide a malformed known field. A valid
URI with an unknown base remains unsupported-base, not a fabricated schema
failure or inventory match.

Every supplied primary location is retained and interpreted independently.
Only exactly one well-shaped physical primary location has first-profile
location cardinality support. Zero or multiple locations are not truncated to
the first. Logical-only locations remain observed but unmapped. Related/path
locations are not promoted into primary locations to repair missing evidence.

### 9.4 Coordinates and future native association

Retain region field presence, raw integers and the run's columnKind. Missing
columns are not written back as measured column 1. Reject contradictory or
out-of-range present coordinates; retain absent fields rather than filling
them. Line/column, character-offset and byte-offset forms are distinct. Never
treat UTF-16 units, Unicode codepoints, UTF-8 bytes and native CPG columns as
interchangeable; end-column exclusivity and newline interpretation must survive.

The first slice does not convert coordinates or verify snippets against source;
it records `coordinates-unverified`. Later conversion requires exact source
bytes and a reviewed versioned coordinate policy, with non-BMP, CRLF, tabs,
multibyte prefixes, absent/contradictory forms and invalid-boundary tests.

Later graph association must enumerate all candidates using source bytes,
coordinates and actual semantic roles; unique verified association or explicit
ambiguous/unsupported is required. The existing CALL/column/node-ID tie-break
must not be used as semantic proof. Never fabricate a witness or placeholder
hash to avoid a missing association.

## 10. Exact archive and replay boundary

The proposed binary frame is:

```text
ASCII "SCANIPY-CODEQL-OBSERVATION/1\n"
u32be manifest_length
manifest_length bytes of canonical UTF-8 JSON
present payloads in order: report, stdout, stderr, source_inventory
EOF
```

Manifest closed keys: `schema`, `profile`, `limits`, `returncode`,
`source_root_aliases`, `parts`. `parts` is an object with exactly the four
payload names above; each value is null (absent) or exactly
`{"length": N, "sha256": Hex64}`. Empty present payload has length zero and
SHA256 of empty bytes. No paths, URLs, code objects, compression or external
blob fetches are allowed. Limits are exactly the §6 field table.

Canonical manifest spelling is `json.dumps(sort_keys=True, ensure_ascii=False,
allow_nan=False, separators=(",", ":"))` UTF-8 with no newline. Before encoding,
bound aggregate escaped output bytes and snapshot every field; canonical JSON
means a unique control-envelope spelling, NOT semantic/cross-refactor identity.
Input report/stdout/stderr/inventory bytes are never reserialized.

Decode checks total length, bounded manifest length BEFORE parse, duplicate
keys, exact shape/version/limits, all raw payload hashes and exact EOF. Stored
limits must be no greater than the caller's independently validated allowed
limits; then parse using the stored limits, rather than silently relabelling
the original record with relaxed limits. Reject concatenation, trailing bytes,
bad present/absent distinctions, digest mismatch and unsupported versions.

Derived observations are not serialized as authoritative extra data. Decode
reconstructs them from original payloads. Encode of an observations object must
independently snapshot all fields and reparse the original inputs; compare its
COMPLETE derived view to the supplied view using private primitive projections.
Reject forged spans, changed issue/status/ordinal/join, omitted or duplicated
result, conflicting limits or raw bytes. Do not ignore conflicting mutable
carrier fields because the raw payload alone looked plausible.

Exact reparse equality proves consistency of this codec with the stored input,
not authenticity, freshness, complete native execution, source correspondence,
query acceptance, a reproduction experiment or a signature. Replaying imported
JSON twice is never two CodeQL runs.

## 11. Later real adapter contract and integration obligations

### 11.1 Real import entrypoint

After the pure component, specify an actual entrypoint receiving a retained
report artifact plus genuine capture/execution association and accepted query
metadata. It must retain raw report/process evidence durably before identity
or mapping, then expose every native result and explicit per-result status.
Malformed/unmapped/ambiguous rows remain evidence; they are not removed from
denominators or converted to empty-success.

Actual import needs a trusted adapter that obtains exact inventory bytes from
`LocalSourceCaptureStore.verify` under the real capture lease/read-only custody
and checks them against the archive. Bind the real source-tree/manifest/SCM
proofs, report raw digest, capture/tenant scope, accepted S/query artifacts and
environment observations through their existing owning codecs. A source tree
digest supplied beside arbitrary bytes is not verification.

No `Finding` is emitted until rule, supported language, class, CWE, source,
origin and provenance requirements are satisfied. Origin remains
`oracle-passthrough`, including after a real structural slice succeeds. R09
missing/requested-failed/not-applicable graph and slice status stays explicit;
vendor fingerprints, raw JSON hashes and same-source IDs never fill a structural
strong slot. The native record and its multiplicity survive identity failure.

An explicit registry engine identifier `codeql` is recommended for a later
versioned extension, with oracle partition derivation. Do not silently label it
Semgrep or conceal the engine inside legacy `external`. If compatibility needs
`external`, retain an independent exact engine identity and versioned dispatch
contract; root must approve that choice. This first slice edits neither path.

### 11.2 Native extraction/query execution

Do not write speculative CLI flags into a runtime implementation. Before a real
run, require all of the following actionable artifacts:

- Exact supported language(s), source-entry selection and whole-capture coverage;
  neither locale nor query filename proves extraction language.
- Installed executable/launcher/JDK/runtime/query-pack content inventory, actual
  versions, dependency closures and pinned invocation support. The release tag
  and archive pin alone do not establish this.
- Accepted ordered query set, its actual pack/query bytes and raw digests;
  requested, available and actually executed query inventories kept separate.
- Reviewed source-extraction profile proving no target hooks/imports/builds or
  dependency managers run; network/env/loader/working-dir controls and actual
  kernel limits through #400, not a timeout wrapper alone.
- Explicit grouping/emission configuration. Verify pinned support before using
  a future `--ungroup-results` mode; do not claim recovered BQRS multiplicity
  from already grouped SARIF.
- Exact staged process/evidence order for database creation, query execution
  and export, with independent failures, aggregate deadlines/storage/output
  quotas and no success after incomplete cleanup or missing output.
- Permitted installation/distribution decision and actual required entitlement;
  no image/release publishing is authorized by source-code approval.

Python and Java are the initial project languages, not verified CodeQL support
in this implementation. Java no-build dependency resolution is a concrete C16
risk to resolve, not a reason to quietly substitute trivial fixtures or drop
the promised language. Other promised oracle/language work remains open.

### 11.3 R11/R12/R14 and durability

Use separate native result occurrence counts and metric projections. Preserve
the existing reproduction formula unless a versioned policy explicitly changes
it; add per-engine record identity/storage without reusing the old unique
partition row for both Semgrep and CodeQL. Record baseline/reproduced/additions/
losses/failures, engine and query versions, grouping, source association and
identity basis. Nonempty fresh real runs are required for meaningful acceptance;
the empty-baseline convention is not evidence of stability.

R14 compares the actual named native fingerprint strategy, when present, against
Scanipy's actual identities on the same inputs. Report missing vendor identities
explicitly. No globally unique or refactor-stable guarantee is inferred from
`primaryLocationLineHash`, result GUID, message/location grouping or code flow.

R12 must sign/store actual report/SARIF hashes and complete required provenance,
with persistent installed keys and independent verification. Do not retain the
legacy `sarif_hash=None` shortcut for the accepted adapter path. Raw/domain
digests stay distinct and signatures cannot certify a falsely described run.

R08/#378 lifecycle failure rules remain: cancelled/expired/closed runs cannot
be overwritten into success. Late raw bytes need the installed recovery journal
linked to the original run/barrier; current ordinary terminal replay functions
are not a generic late-evidence sink. Do not widen ordinary live authorization
or claim the proposed recovery store is already implemented.

## 12. Required falsifiers and acceptance evidence

All first-slice tests below are controlled parser/codec tests, not native scans.
Every new test must be collected by the actual unit/pre-push selector. Freeze
source/test hashes for independent review before broad tests or a commit.

| Test group | Required negative/positive controls |
|---|---|
| Input snapshots | Exact types; bool-as-int; missing/poisoned slots; mutated limits/output carriers; malicious conversion/equality/repr/property callbacks not invoked; snapshot before encoding. |
| JSON | Duplicate keys at every depth; BOM/invalid UTF-8/surrogates; escaped duplicate keys; huge exponent/integer/string; N/N+1 depth/value/byte caps; two documents; trailing garbage; escaped-output expansion. |
| Envelope | Missing/null/wrong version/runs/results; zero/two runs retained unsupported; metadata-only run never empty completed scan; `$schema` URL never fetched. |
| Losslessness | Byte-identical raw parts; whitespace/key order/numeric lexemes/unknown nested fields retained; invalid result elements retained; repeated identical results keep all ordinals; duplicate ordinal resets per run. |
| Rule binding | ruleId/index agreement and mismatch; -1/missing vs zero; bool/float index; duplicate IDs with/without explicit index; extension/driver collision; available-but-not-run rules never coverage proof. |
| Native metadata | All fingerprint names, GUIDs, occurrenceCount, suppressions, baselineState, taxa/CWE tags, traces and message placeholders preserved; no local decision or structural identity created. |
| Locations | Missing/multiple/logical-only locations retained; no first-location shortcut; artifact URI/index/base contradictions; duplicate artifacts; unknown index; external/cached references never fetched. |
| Paths | Absolute/file/network/drive/UNC forms; traversal and percent-encoded separators; double encoding; `%20`, `%23`, Unicode exact match; invalid UTF-8; alias missing/unknown/chain; source file absent; case/normalization collision not silently merged. |
| Inventory | Real custody-generated canonical inventory cross-test; hash/path/order/size/schema mutations; supplied-invalid distinct missing and valid empty; same-looking unverified inventory never custody permission. |
| Coordinates | Non-BMP/CRLF/tab/multibyte region forms retained without guessed byte conversion; present invalid/reversed values rejected; missing fields not written back as observed defaults. |
| Failures | Nonzero channel code; missing/empty channel; native invocation failure plus positive rows; malformed/truncated report; resource refusal no accepted prefix; raw evidence still available to owning caller. |
| Archive | Exact framing/EOF; missing vs empty; hash/length mismatch; concatenation; future schema; lower-limit rejection; poisoned/omitted derived view; full parse/encode/decode equality. |
| No side effects | Poison subprocess/FS/network/dynamic import/codecs callbacks; no native execution, external reference loading, canonicalization, fingerprints, DB or authority calls. |

Later component acceptance additionally requires a retained genuinely emitted
CodeQL report and an actual import-entrypoint positive with exact rule/CWE/class/
location/origin mappings and defined unavailable/failure behavior. Record the
producer command/profile/version, source and rule artifacts, raw bytes and
conditional coverage. Synthetic JSON can never substitute for that report.

Native acceptance adds a real nonempty source execution under the reviewed safe
profile; then two genuinely fresh engine runs for R11 and the full G2 shared
consumers. Report original red failures, skips and unsupported cases instead of
only successful reruns. Do not infer algorithmic or coverage guarantees from
finite fixture success.

## 13. Action list and dependency order for the implementing LLM

All items are TODO; none is marked implemented or accepted by this note.

1. **Root design approval:** decide §4 ownership, §5–10 exact pure API/schema,
   fixed limits and inventory-join-only boundary. Allocate a narrow issue.
2. **Pure component:** implement the three files, controlled tests, static
   checks, independent review and normal repository gates. Preserve all raw
   channels and unsupported states; do not wire it into production findings.
3. **Real evidence intake design:** define the accepted external-import user
   path and actual capture/execution/query associations; use owning authority
   codecs and real durable retention. No UUID/key fixture grants.
4. **Real CodeQL output:** after permitted acquisition/runtime scope is agreed,
   retain actual supported output and metadata. Confirm pinned SARIF differences
   empirically; amend/version the projection if necessary, never edit evidence
   to match constructed tests.
5. **Runnable import adapter:** add exact query/CWE/class mapping and registry/
   worker dispatch without mandatory CPG. Verify nonempty real import and
   unavailable/malformed/unmapped failure handling at the declared entrypoint.
6. **Native source mode:** separately select/verify safe supported extraction
   and query profiles with #400, installed artifacts, no target execution,
   actual coverage and legal prerequisites. Keep full submission scope open.
7. **Identity/durability:** integrate R09 and R08/#378 using verified source/native
   association; no placeholder hashes, guessing, set-collapse or result loss.
8. **Provenance and reproduction:** supply real adapter output to R11/R12/R14;
   add per-engine durable measurements, persistent-key verification, actual
   vendor-identity comparison and joint G2/UI acceptance.
9. **Release/readiness:** document the lawful installation path and verified
   offline prerequisites on the confirmed presentation machine; obtain separate
   publication authority. No performance/readiness budget is established here.

## 14. Root decisions requested before source allocation

- Approve or amend the three-file pure observation slice, explicitly not the
  runnable/full R13 adapter or native acceptance.
- Approve optional exact source-inventory data joins without inventing a new
  CaptureReceipt/authority codec; require actual custody/lease binding later.
- Approve the independently tested bounded span grammar and exact archive
  schema/limits, with no change to Semgrep's private parser or current emitters.
- Confirm that real import and native source milestones stay separately named;
  no first-slice success may erase the native-safety/query/language obligations.
- Allocate later actual engine identity/registry/query mapping and installed
  runtime/licensing decisions to their owners; no such owner choice is assumed.

## 15. Evidence and change record

This draft used local reads and bounded primary-source documentation/metadata
GETs only. No tests, hooks, builds, scans, source execution, database calls,
engine/pack downloads, remote writes or repository edits were performed for
this task. The four pre-existing user untracked paths remain untouched.

Root-owned scalar/compiler/runtime/authority work remains separately frozen or
in its allocated workflow. The new note neither edits nor accepts those trees.
Its first implementation scope remains proposed until root review.

## 16. Root allocation and local implementation checkpoint

On 2026-09-25 the root reviewed and approved the frozen 765-line proposal
(SHA256 `8202a1320f329ddb80099fd73d5ea2aa4a3141ed4f790ff22d6093ccdcb8e1e7`)
for exactly the three-file pure slice in §4 under issue #410. The original
PROPOSED status above records the proposal chronology; this additive entry
records engineering scope approval, not human model acceptance or full R13.
The isolated branch starts at accepted `d4ad0c0b692cef4539d5333c60066cdcedecfb4e`.
Root verified/claimed board ownership and delegated this implementation.

The first local implementation is frozen for independent review. It changes
only the three allocated files. The source uses the accepted custody schema
constant and does not reuse Semgrep's private parser. Original payload bytes
remain lossless; source-inventory matches are data-only joins. A fixed private
carrier snapshot checks every slot and type-tagged derived field before replay;
no caller equality, repr, constructor-history or validation callback is trusted.
Derived-view snapshot counts are bounded from the admitted JSON-value ceiling,
with stricter per-run/result/alias counts before tuple traversal. Each reparse
has a fresh bounded report-plus-inventory counter; manifest parsing has its
separate fixed ceiling. No source/authority state is created by these checks.

Local controlled evidence on Python 3.11.16, using the root's declared test
environment and explicit worktree PYTHONPATH:

- Initial red: `/tmp/scanipy-410-codeql-initial-red.xml`, one collection error
  before the new module existed (not a native or runtime product failure).
- Development red: `/tmp/scanipy-410-codeql-development-red.xml`, 145 pass /
  six fail. Five malformed artifact-reference cases were misclassified as
  unmapped, and an explicit component hid a malformed rule index. Both were
  corrected to respect invalid-known-field precedence; the unchanged 151-case
  set then passed in `scanipy-410-codeql-classification-corrected.xml`.
- Expanded red: `/tmp/scanipy-410-codeql-expanded.xml`, 349 pass / one fail.
  A payload length above the stored resource cap raised the generic archive
  error; it now raises CodeQLLimitError before copying the payload.
- Final index-domain red: `/tmp/scanipy-410-codeql-threadflow-red.xml`, 378 pass /
  four fail. Malformed interpreted cached-threadflow indices were incorrectly
  classified unsupported; exact integer/range failures are now invalid.
- Final selected run: `/tmp/scanipy-410-codeql-final.xml`, **382 passed,
  zero failures/errors/skips**, 1.396 seconds. The command explicitly selects
  `tests/unit/test_codeql_observations.py -m unit`; the module has the unit marker.
  This covers strict JSON/span retention, native order/multiplicity, rule/path
  ambiguity, failure claims, all resource-limit fields, malformed and mutated
  carriers, complete archive replay and external-access refusal controls.
- The custody cross-test uses the actual LocalSourceCaptureStore to generate
  an inventory from test-owned inert bytes. It establishes codec agreement,
  not SCM authenticity or a real report/source association. No scanned source
  is executed. All SARIF inputs are explicitly constructed diagnostic data.
- Scoped Ruff lint/format checks pass for both Python files; strict mypy passes
  for the new production module. No dependency installation was needed.

Independent source review, repository-wide testing and normal hooks/commit/PR
gates remain pending. No engine execution, installed authority, real CodeQL
report, runnable import adapter, component_verified or G2 acceptance is
established. Full R13 and every later TODO/evidence limitation remain open.

### Independent path review and narrow correction

The corpus peer read the frozen source/tests and found two additional path
interpretation defects at source SHA256
`52dc87cdb168816a4d72397c1206f5fb5221846f5f5bf9aa50f56f48e1efd49d`.
Its unchanged external controls retained 12 failures / one valid unknown-base
positive in `/tmp/scanipy-410-codeql-peer-path-red.xml`. The implementation agent
independently reproduced those same 12 failures / one pass in
`/tmp/scanipy-410-codeql-core-peer-path-red.xml`, without changing that external
test. These results do not erase the earlier 382-test checkpoint.

Root reviewed the full source and external controls and authorized only these
two corrections: invalid/inconsistent URI/reference status cannot be hidden by
an unsupported base, and aliases/inventory paths/decoded URIs consistently
exclude C0 plus DEL/C1. The latter matches the explicitly reviewed character
range in the owning source-custody path helper; it does not import other custody
policy, add `.git` exclusion, authenticate source bytes or promise full custody
parity. Existing valid unknown/chained bases remain unsupported, not invalid.
Raw reports and invalid inventories remain retained; invalid public aliases
fail before parsing, as before.

Final corrected selected unit run:
`/tmp/scanipy-410-codeql-path-corrected.xml`, **427 passed, zero
failures/errors/skips**. The 45 additional controls cover direct/chained/indexed
precedence and C0/DEL/C1 boundary positives/negatives across all three input
domains (including literal and percent-escaped URI forms). The unchanged
external test passes all **13** cases in
`/tmp/scanipy-410-codeql-core-peer-path-green.xml`. Scoped Ruff lint/format and
strict module mypy pass. All three files are frozen again for independent
correction review; no broad tests, hooks, commit, remote/native execution or
production/authority activation occurred.

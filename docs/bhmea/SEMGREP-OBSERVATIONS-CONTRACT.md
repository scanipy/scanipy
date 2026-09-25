# R08/R11/R16 — Lossless Semgrep observations

Status: local parser implemented and independently reviewed; repository acceptance pending.
Owner: root coordinator. Narrow issue: #394. Full submission: #362 remains open.
Date: 2026-09-25. Base: `2709177afff1c78f06532e0298dd5ee4d608237f`.

Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
This supplements the worker/attestor contracts for the current Black Hat goal;
it does not rewrite historical PLAN/SDD/WBS or completed signed records.

## 1. Objective and first-slice boundary

Preserve every result returned by one Semgrep invocation, in returned order,
before any set conversion or identity computation. Parse the retained output as
data, keeping original bytes and explicit malformed/unsupported observations.
This is not a native runner, accepted-rule resolver, coverage verifier,
occurrence database adapter, SARIF projector, attestor or lifecycle engine.

Exclusive first-slice files:

- This contract.
- `services/scan/semgrep_observations.py`.
- `tests/unit/test_semgrep_observations.py`.

Do not modify the existing `oracle_attestor.py`, its tests, the deployed app,
rules, Dockerfiles, source captures or database migration in this slice. Existing
production defaults remain incomplete; adding an unused parser does not repair
the integrated production path or satisfy G1.

## 2. Verified producer facts and current defects

The application Dockerfile currently selects Semgrep 1.175.0. On 2026-09-25 the
upstream annotated tag `v1.175.0` resolved to source commit
`7963c5a2d7e784ab24d0c14e29c63c6d53751336`. This source revision is not proof of
the bytes installed in any existing image or of a locked dependency closure.

The current Scanipy invoker uses `capture_output=True`, inherits its environment,
accepts exit codes 0 and 1, and returns parsed JSON without raw execution custody.
The current projection defaults missing `results` to an empty list, converts
matches to a `frozenset`, and does not verify file/rule completion. Its path
mapping also consults the host filesystem. These are observed code defects or
limitations, not behavior to reproduce in the new observation boundary.

Pinned primary-source checks:

- `error_on_findings` defaults false; findings cause exit code 1 only in the
  relevant configured mode. Output handling can choose the findings code ahead
  of structured errors. Therefore even a findings-mode exit 1 does not by
  itself establish complete analysis.
  [Pinned output implementation](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/cli/src/semgrep/output.py#L467).
- The CLI scanned-path list is constructed from selected targets, with an
  explicit upstream limitation concerning skipped rules. Skipped-path detail
  depends on verbose output, and the Python output layer supplies an empty
  skipped-rule list itself. Neither list is a standalone coverage certificate.
  [Pinned output construction](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/cli/src/semgrep/output.py#L635).
- `--error`, strictness, nosem handling, rule-ID rewriting, Git-ignore handling,
  and Semgrep-ignore handling are distinct controls. A reviewed native profile
  must specify each intentionally; `--no-git-ignore` alone is not all-source
  coverage. Source-level option declarations do not prove current launcher
  routing or a safe runtime.
  [Pinned scan command](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/cli/src/semgrep/commands/scan.py).
- Native matches contain a rule ID, physical location and extra data; the
  report has explicit results, errors and path telemetry. Version and several
  telemetry fields are optional in the upstream schema. Preserve absence
  distinctly from an observed empty list.
  [Pinned output schema](https://github.com/semgrep/semgrep/blob/7963c5a2d7e784ab24d0c14e29c63c6d53751336/cli/src/semgrep/semgrep_interfaces/semgrep_output_v1.atd).

This contract uses profile `scanipy-semgrep-observations/1`, scoped to the
reviewed Semgrep 1.175.0 output family. It never claims general compatibility
with an arbitrary newer Semgrep schema.

Retrieved-source SHA-256 values (2026-09-25; source, not installed-tool identity):

| Pinned file above | SHA-256 |
|---|---|
| `commands/scan.py` | `2d9d6ea23c68b01191a92ba72e38531c8f5d50b348e5a21df3010466f3f9ab0d` |
| `output.py` | `f63a1e51d78087253c513fe13db88fcbfed9708a22ce1efb3b0aade06f71deaf` |
| `semgrep_output_v1.atd` | `e029dafd39ea177040ae4ce9220acbac6d18cadf15aeba0a0fd858b2649273cd` |

## 3. Inputs, immutable output and trust boundary

Inputs are exact `bytes` stdout/stderr and an observed integer process return
code. A negative POSIX signal return code is preserved as such. `bool` is not an
integer. The producer remains responsible for truthful process observations,
complete stream capture and bounds during execution; hashing supplied bytes is
not proof that a subprocess ran or that the stream was not truncated upstream.

No shell/subprocess, network, filesystem read, source lookup, registry call,
database mutation, graph/solver import or LLM call is permitted in this module.
No source coordinate is used to open a file. No native result field can select
the finding's engine/origin, accepted spec, source commit, image or policy.

Return an immutable observation report containing:

- Profile identifier, original stdout/stderr bytes and their SHA-256 digests,
  observed return code, and independently computed stream lengths.
- Structural parse status: `parsed` or `invalid-report`; neither means a
  successful scan or a complete inventory.
- Observed version and a separate `matched`, `missing`, `mismatched`, or `invalid`
  version status. Only exact string `1.175.0` matches this profile. Missing is
  not assumed compatible; another/malformed version is unsupported.
- Ordered result observations with original zero-based tool ordinals. Every
  array entry is either a supported native match or a rejected-result record
  with an explicit reason; never silently filter one out.
- Original raw spans for each result and recognized report-level telemetry,
  plus structured issues for absent, malformed or unsupported observations.
- Coverage status fixed to `unverified` in this first slice. No constructor or
  convenience argument can set it to complete.

`parsed` means only that the whole bounded UTF-8 JSON object was parsed. It is
independent of version status, results-array status and match projection status.
Version mismatch/missing does not erase parsable raw observations or certify
their native semantics. `results_status` is `present`, `missing`, or `invalid`;
`result_count` is the observed array length only when present, otherwise null.
Missing/nonarray results must never be returned as count zero. A malformed
whole report has no inferred result count. No output state certifies a complete
native schema, accepted engine run or all-source result inventory.

Native match descriptors retain the observed rule ID, raw reported path,
start/end coordinates, message and severity without inventing defaults. Engine
and origin, where exposed as adapter descriptors, are fixed to `semgrep` and
`oracle-passthrough`. These are not final Findings: actual accepted spec/tool/
source/environment provenance must be bound by a trusted later producer before
durable occurrence or final-record emission.

Raw bytes and frozen primitive/tuple fields must not alias caller-mutable maps.
Do not return mutable dictionaries hidden inside a frozen dataclass.
The parser is the validation boundary. Its returned value objects are not
authenticated receipts, and their public dataclass constructors are not separate
input-validation APIs. A downstream producer must not accept a caller-constructed
report as proof of parsed bytes, execution, capture binding or provenance. It
must parse the actual retained streams at its trusted observation boundary.

## 4. Byte custody, parsing and multiplicity

The retained stdout is authoritative raw evidence. For each top-level `results`
array entry, retain its exact half-open UTF-8 byte span into stdout and the exact
bytes of that JSON value, excluding only surrounding array separators/spacing.
Validate that slicing the parent stream at that span reproduces the result.
Escapes and internal whitespace remain unchanged. JSON reserialization must
never be labeled original tool bytes.

Native result order is evidence, not a claim of stable tool ordering across
independent executions. Preserve identical duplicate entries separately. If a
result key is provided, use a named raw-byte identity namespace and an ordinal
among identical raw-byte keys; neither is a structural/suppression identity.
Do not conflate differently encoded but semantically similar JSON values, or
deduplicate by rule/location/message. Later reproduction comparison has its own
explicit projection and denominator.

Use strict UTF-8 and JSON grammar. Reject duplicate object keys at every depth,
including equivalent escaped spellings; reject nonstandard NaN/Infinity tokens,
trailing input and top-level nonobjects. Finite native numeric telemetry may be
retained as raw JSON observations, not rounded into a new canonical value.
Do not promote raw JSON to the portable SQL envelope format by implicit coercion.

Check nesting/token/stream bounds before materializing an unbounded JSON tree.
Byte-span discovery must handle quoted braces/brackets, escaped quotes and
backslashes, Unicode escapes and multibyte literal UTF-8. It must not search
for a textual `"results"` substring that might occur in a message or nested
object. Structural parsing and span accounting must agree exactly.

If the entire report is syntactically malformed, retain its bounded streams and
an `invalid-report` diagnostic; do not recover a convenient prefix and claim a
complete array. For valid JSON with a malformed individual result, retain and
account for that entry plus every other returned entry. If an envelope-wide
bound prevents individual materialization, report that explicit failure with
the preserved raw stream; never return a misleading completed prefix.

## 5. Supported fields and explicit uncertainty

Require `results` to be an observed array; missing/null/object is not zero
findings. `errors` and `paths` are independently observed telemetry, not inferred
from `results`. Preserve missing versus empty versus malformed for each.

A `projected` match means only conformance of this document's observed-field
projection, not full conformance of every optional Semgrep native field or
acceptance as a final finding. Each other result is explicitly `rejected` and
retains its raw span/bytes and reason. A projected match requires correctly
typed native rule/path/start/end/extra fields. Positive lines/columns must be
actual integers, not bools; end must not
precede start. Native offset, when supplied, is retained independently and is
not invented from line/column. The pinned schema documents a native `-1` dummy
offset: preserve that observed sentinel distinctly from missing and from a
known nonnegative offset; never turn it into offset zero. Smaller values are
unsupported. In this projection, missing offset is accepted as unknown and is
not a reason to invent the upstream parser's default; explicitly null or a
noninteger offset is rejected. Preserve a separate presence state from the
nullable descriptor value. Blank or wrongly typed severity/rule/path and a wrongly typed
message are rejected explicitly rather than replaced with invented values.
An observed empty message is retained unchanged, not fabricated or discarded.
Do not strip or rewrite an observed message. An unknown native severity stays an
explicit unsupported observation until a reviewed mapping is defined.

Keep raw paths as observations; this layer neither calls `Path.resolve()` nor
claims path containment. A subsequent source-bound adapter must validate and map
them against the exact immutable capture. Absolute, traversal-like or malformed
paths cannot be used to read source or manufacture a known safe location.

Recognized telemetry includes native errors, reported scanned/skipped paths,
skipped rules, rules-by-engine and requested engine. Preserve exact raw values
even when their shape is unsupported. Unknown top-level fields must be retained
and flagged, not silently discarded as irrelevant; they may change the meaning
of a producer report. Missing/different native version is explicit. Supported
JSON extension data inside a result remains part of its original raw bytes,
but is not interpreted as trusted source/spec/policy/provenance metadata.

The exact recognized native match severities are `ERROR`, `WARNING`, `EXPERIMENT`,
`INVENTORY`, `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, and `INFO`. Preserve them without
converting to the old UI bands. Native diagnostic levels `error`, `warn`, `info`
are a different vocabulary. Later severity policy must account for the pinned
schema's `ERROR`/`HIGH` correspondence rather than silently reuse the current
UI's `ERROR` to `critical` mapping.

Recognized report keys are `version`, `results`, `errors`, `paths`, `time`,
`explanations`, `rules_by_engine`, `engine_requested`,
`interfile_languages_used`, `skipped_rules`, `subprojects`, `mcp_scan_results`,
and `profiling_results`. Recognition means retained native telemetry, not
semantic acceptance of optional Pro, supply-chain, explanation or profiling
data. Native `rules_by_engine` entries are rule/engine pairs, not an invented
rule-to-boolean map; requested engine values are `OSS` or `PRO`. Preserve these
observations but do not infer per-file execution from them.

## 6. Bounds and failure behavior

Reviewed hard profile ceilings (also defaults; callers may only lower them):

| Resource | Bound |
|---|---:|
| Stdout | 16 MiB |
| Stderr | 1 MiB |
| Individual raw result | 1 MiB |
| Returned results | 10,000 |
| JSON container nesting, root object at depth 1 | 32 |
| JSON values plus object member keys | 250,000 |
| Observed coordinate/offset integer | signed 64-bit; positive coordinates, offset at least -1 |

These are conservative parser limits, not measured native RAM or stage latency
budgets. Each object, array, scalar value and object member key counts once;
punctuation does not. Scalars do not add a container nesting level. The observed
return code is a signed 32-bit integer, preserving negative signal observations.
Large native streams must already be bounded by the future runner; rejecting a
supplied 17 MiB byte object does not undo its allocation or retain unseen bytes.

For an oversized input rejected before parsing, raise a typed input-limit error
with observed lengths and no fabricated complete digest or result prefix. The
caller still owns the supplied raw stream and its bounded failure-retention
policy. Do not truncate and return `parsed` as if nothing were omitted.

Avoid per-result whole-prefix rescans or repeated encoding of the entire
report. Span accounting and bounds should be linear in retained input plus
decoded values, apart from explicit bounded validation operations.

## 7. Required tests for the first slice

- [x] Exact spans/bytes for whitespace variants, escapes, multibyte literals,
  nested `results` keys, quoted delimiters, empty arrays and repeated results.
- [x] Original ordinal/multiplicity survives; source list/dictionary mutation
  cannot mutate returned descriptors; no structural identity is created.
- [x] Duplicate keys at every nesting level, nonfinite tokens, trailing input,
  invalid UTF-8, malformed envelope and missing `results` fail honestly.
- [x] Bad one-result shape does not silently discard that result or neighboring
  valid observations. Every retained array entry is accounted for.
- [x] Missing/null/empty errors and path telemetry remain distinguishable.
  Unexpected version/fields/severity are explicit unsupported observations.
- [x] Exact boundary and boundary-plus-one cases for every hard ceiling, with
  lower-limit tests and refusal to raise a limit above the profile maximum.
- [x] Return codes 0, 1, error and signal never certify coverage; every output
  remains `unverified`, even with no errors and a complete-looking path list.
- [x] No filesystem/network/subprocess/solver path is used. Paths are not
  resolved against the host or used to open files; no provenance is fabricated.
- [ ] Existing configured tests, Ruff, strict mypy, normal hooks, exact-head CI
  and successful canonical APPROVE pass before merge.

Synthetic reports test the parser contract only. This slice does not claim any
real Semgrep invocation, measured reproduction rate or full source coverage.

## 8. Mandatory follow-up action items

- [ ] Lock and verify Semgrep/tool/dependency/image bytes; a version string or
  upstream Git tag is not an observed runtime image digest.
- [ ] Review a closed native invocation/environment profile: explicit rules,
  working directory, ignore/nosem/ID-rewrite behavior, strictness, exit mode,
  offline enforcement, stream/time/memory/process limits and private workspace.
  Never run target code, source hooks, build steps or source-selected commands.
- [ ] Bind actual accepted spec/rule contents and observed tool/code/image
  artifacts separately from policy-document digests.
- [ ] Produce and verify actual intended/processed file and rule coverage under
  a reviewed supported rule/engine profile. Do not derive completeness from the
  CLI target list, empty skipped-rule list, exit code or zero matches alone.
- [ ] Map raw locations against the verified source capture without traversal,
  guessed basename fallback, invented line numbers or source changes.
- [ ] Persist every valid observed occurrence atomically with its identity work
  while retaining rejected/partial-run diagnostics. Never use the legacy set
  projection before occurrence custody.
- [ ] Preserve detected observations through later graph/slice/identity failure;
  successful absence/fix decisions require separate complete-coverage evidence.
- [ ] Run actual fresh engine reruns on the same accepted inputs. Use the
  existing baseline-projection reproduction metric; retain run count, baseline
  size, reproduced count, additions/losses/failures and empty-baseline behavior.
- [ ] Persist and expose the measured rate and scope through API/UI/export with
  `rate-only` semantics, including at 100%; no core theorem or suppression claim.
- [ ] Complete real signed provenance/fresh-process verification, Docker
  restart/retry and offline-stage evidence on the final accepted artifact.

Neither this contract nor completion of its first parser slice marks R08, R11,
R16, G1 or any submitted Black Hat claim accepted.

## 9. Independent review and local evidence

The independent corpus/tooling reviewer read this contract and the existing
oracle projection on 2026-09-25. After requiring explicit selected-field versus
full-schema conformance, offset presence/sentinel behavior, independent version/
results statuses and an unknown rather than zero unobserved result count, the
reviewer approved this narrow three-file design. Root adopted those corrections
before implementation. That initial verdict was design approval only.

The same independent reviewer subsequently read the three implementation files
and ran the dedicated tests. Review found that whitespace-only rule/path fields
were accepted despite the blank-field prohibition. The corrected predicate
tests nonblank text without stripping the returned value; tests retain rejected
raw entries and preserve nonblank surrounding whitespace and whitespace-only
messages. The reviewer rechecked the correction and issued scoped code approval.
An additional independent controlled audit used seed 3940925 and reported zero
grammar/span disagreements in 6,000 generated/mutated JSON cases. This is a
finite parser diagnostic, not native-engine evidence or a general proof.

Final corrected-code local checks on Python 3.11.16:

- Dedicated unit-marked suite: **194 passed, 0 skipped**. All new tests use the
  unit marker selected by actual CI and pre-push expressions.
- Full configured `pytest tests/` suite, preserving corpus-data exclusions and
  removing live DB/AWS opt-ins: **1,443 passed, 51 skipped**. Skips are not passes
  or real deployment coverage. The earlier pre-correction run was 1,435/51 and
  is not substituted for this corrected-code result.
- Actual hard stdout/stderr/result/count/depth/value boundaries are exercised,
  including 16 MiB stdout, 1 MiB stderr/result, 250,000 values/keys and signed
  64-bit line/column/offset maxima. The last coordinate-ceiling test was added
  after scoped code approval without changing production code. These
  are parser limits, not measured native or presentation budgets.

No Semgrep subprocess, scanned source, database write or production default was
used by these parser tests. Normal hooks, exact-head CI and a successful
canonical review remain mandatory before repository merge. The separate
native/coverage/provenance and integration actions in section 8 remain open.

# Typed refactor report and acceptance gate, version 2

Status: IMPLEMENTATION CONTRACT for R04 / #367. This document does not record a
G0 run, accept a claim, or authenticate a producer. Reports, retained evidence,
and reviewed gate policy are different inputs. The checker never executes or
imports code from a corpus or evidence directory.

## Producer integration seam

The report is JSON with exactly these root fields (optional untrusted `summary`
is permitted):

```text
schema_version: 2
gate_policy_id: "bhmea-refactor-gate/2"
gate_policy_digest: sha256:HEX
report_id: nonempty producer-assigned identifier
corpus: {corpus_id, corpus_version, corpus_digest, case_manifest_sha256}
run: {
  code_revision, started_at, completed_at,
  execution_kind: real_joern | controlled_fixture | historical,
  freshness: fresh | reused, cache_mode: disabled | enabled,
  command: [actual argv strings],
  environment_digest: sha256:HEX | null,
  environment_manifest: evidence_reference | null
}
cases: [case_observation, ...]  # exactly the policy/manifest inventory
```

Timestamps are UTC ISO-8601 strings ending in `Z`. Revisions are full 40-hex Git
commit IDs. Every digest is `sha256:` plus 64 lowercase hex characters; no empty,
default, inferred or fabricated digest is an observation. Every evidence
reference is `{path: relative_POSIX_path, sha256: digest}`. Paths are relative to
the report's evidence root; absolute paths, parent traversal, symlinks and
non-regular files are forbidden. The checker hashes the actual retained bytes.

A case observation has exactly:

```text
case_id, language, evidence_type,
before: side_observation,
after: side_observation,
correspondence: {status: established | ambiguous | not_run, evidence: [reference]},
observed_preconditions: {
  fixture_syntax: {status, producer, evidence: [reference]},
  transformation_validation: {status, producer, evidence: [reference]},
  purity_certificate: {status, producer, evidence: [reference]}  # iff demanded
},
lifecycle: lifecycle_observation | null
```

For each manifest precondition the observation's status is the observed value,
`failed`, or `not_run`. `producer` is null only for `not_run`; an observed value
requires a named actual producer and retained evidence. Expected manifest
preconditions are demands, **never observations to copy into the report**.
Unknown/missing purity analysis remains `not_run` even when the fixture expects
`proven`. Parser/schema validation is not a purity certificate.

Each side has exactly:

```text
source_tree_digest,
processing_status: completed | failed | not_run,
reason: nonempty string | null,
fingerprint: {hash, class: strong | weak, namespace} | null,
locator: {status: matched | not_found | ambiguous | not_run, value: locator | null},
finding: {status: present | absent | not_run, id, rule_id, origin},
scan: {
  status: completed | failed | not_run, scan_id: string | null,
  source_tree_digest, covered_files: [relative paths], covered_rules: [rule IDs],
  skipped_files: [relative paths], failed_files: [relative paths]
},
error: {stage: parse | locate | fingerprint | detect | timeout, visible: bool} | null,
evidence: [reference]
```

`locator.value` is the full observed `{file,line,column,callee,call_text}` from
unique real graph matching, not the first matching call or an unchecked copied
locator. A present finding requires an actual finding ID, rule ID and unchanged
origin (`deterministic-core` or `oracle-passthrough`). Absent/not-run findings
have null ID; absent may retain the searched rule ID. Presence or absence can
only be reported from completed processing and completed detection. A fingerprint does not
invent a detector finding: structural observations may have finding/scan
`not_run`. A failed/not-run processing side has no fingerprint. Non-completed
processing requires a reason. A completed side may have no identity and remains
unevaluated for a structural comparison.

Lifecycle observations come from R07, not the fingerprinter:

```text
{
  before_finding_id, after_scan_id,
  state: resolved | open,
  reason: fixed | analysis_failed,
  decision_inherited: bool,
  evidence: [reference]
}
```

Null lifecycle is valid incomplete evidence for G0; it cannot pass removal or
failure-control acceptance. No after-hash is required for removal. Acceptance
requires an actual prior finding located at the intended sink with that file
and rule covered by its prior completed scan, completed after detection over every source
file and the same rule, no skipped/failed files, observed absence, and a linked
R07 `resolved/fixed` transition. An intentional parse failure must instead be
visible, leave its prior finding `open/analysis_failed`, and inherit no decision.
It earns error-handling credit only, never a structural flip or successful fix.

## Environment identity, not an image alias

`run.environment_manifest` points at actual JSON with this versioned shape:

```text
namespace: "scanipy-refactor-analysis-environment/1"
code_revision: same actual revision as run
components: [{role, name, version, digest}, ...]
configuration: {key: JSON value, ...}
```

The policy pins required component roles: snapshot image, detector image,
analysis code, Joern, export script, mapper, graph model, fingerprint,
canonicalization, budget policy, rules and accepted specifications. Multiple
different roles may refer to the same actual content. Image digests are their
own component identities, never substituted for the full manifest digest.
Components contain actual content identities/version observations; configuration
must include actual canonicalization B/T and relevant engine/rule/model options.
The checker requires a nonempty configuration; semantic completeness of that
configuration remains the producer/reviewer obligation.

Canonical manifest bytes are UTF-8 JSON with sorted keys, ASCII escaping,
separators `(',', ':')`, and no newline. `environment_digest` is SHA-256 of
`SCANIPY-REFACTOR-ANALYSIS-ENV/1\n` followed by those bytes. The evidence reference
separately hashes the exact file bytes. The namespace is deliberately distinct
from the existing image-valued `env_digest`; it is a report-boundary manifest,
not a silent schema migration of worker provenance. R09/R05 must produce it from
actual runtime inputs. Missing manifests/digests may be null in an honest
baseline but block semantic acceptance.

## Modes and trust boundary

The reviewed policy pins exact corpus/manifest digests, all required case IDs,
language/evidence/outcome cells, accepted strong namespaces, execution kinds,
freshness/cache rules, maximum age, environment roles and protected history.
Default baseline mode is the G0 gate: it requires real Joern, fresh uncached
execution within the policy's 168-hour age limit and before/after processing
attempts for every required case. Each attempt must be completed or failed
with retained evidence (and an actual failure reason). A limited or all-not-run
record can have valid diagnostic structure but cannot pass default G0. An
explicit alternate controlled-test policy may permit such diagnostic records;
it is never the default policy. Missing detection/lifecycle, purity and full
environment manifests may remain honestly incomplete in G0; no evidence or
findings are fabricated to fill them. Failing hashes and weak identities are
valid red feature observations. Feature acceptance needs
every required case to pass. Nonregression requires every case passing in G0 or
any accepted improvement still to pass; per-language/type/outcome counts are
also recomputed, so aggregate improvement cannot hide a regression.

Reported summaries, outcomes and `matches_expectation` are never authoritative.
Only optional root `summary` is accepted as ignored display data; semantic
fields in case records cannot be replaced by a claimed pass flag. Structural
equality is recomputed from compatible strong hashes, actual processing and
correspondence, and observed required preconditions. Unknown namespaces are
honest unevaluated baseline evidence, not accepted strong identity.

Every report also binds `gate_policy_digest`: SHA-256 of
`SCANIPY-REFACTOR-GATE-POLICY/2\n` plus canonical JSON of the entire policy
excluding **only** `history`. Canonical JSON uses the environment section's
exact rules. The version ID alone is insufficient: changing accepted
namespaces, strength rules, inventories or freshness must not reinterpret
protected successes as failures and erase their regression protection. Old
reports with another semantic policy digest are rejected; any necessary policy
migration requires explicit reviewed preservation of prior acceptance, not
restamping old reports. History-only updates do not change this semantic digest.

Policy history starts with no G0 digest: no baseline has been manufactured.
After the real G0 is reviewed, pin its exact report SHA-256 in policy; append
accepted improvement report hashes after review. Acceptance and nonregression
must receive exactly those reports. Old reference reports need not satisfy
today's age limit, but must retain the same corpus/semantic-policy digest and
otherwise satisfy G0 eligibility and valid bindings.

This gate establishes report consistency and enforces stated evidence rules.
It cannot establish that an untrusted producer actually ran Joern, prove a
purity claim from a status string, authenticate raw logs, or certify an
arbitrary environment manifest complete. Signed provenance, actual producer
integration and real G0/G2 runs remain separate obligations. Unit-test reports
are explicitly controlled fixtures, not corpus measurements.

## Expected code artifact and commands

Acceptance and nonregression require `--expected-revision`: the exact lowercase
40-hex **analysis-code artifact** commit supplied by the trusted release/run
controller. It is not the scanned repository's commit, and must not be copied
from the candidate report. Only the candidate must match; protected historical
reports legitimately describe older analysis revisions. Baseline accepts the
option when explicit G0 artifact binding is required. This rejects a still-fresh
old green report submitted for a new buggy implementation. A Git SHA alone does
not identify dirty or mounted code: the environment manifest must also capture
actual mounted analysis-code content and the controller must verify that binding.
Neither this option nor hashes authenticate producer assertions.

Set `ANALYSIS_CODE_REVISION` from that trusted controller before the commands
below; do not derive it from candidate JSON.

```bash
python3 scripts/check_refactor_report.py --mode baseline --report /evidence/g0/report.json --corpus-root tests/corpora/refactor
python3 scripts/check_refactor_report.py --mode nonregression --expected-revision "$ANALYSIS_CODE_REVISION" --report /evidence/current/report.json --corpus-root tests/corpora/refactor --baseline /evidence/g0/report.json --accepted-improvement /evidence/improved/report.json
python3 scripts/check_refactor_report.py --mode acceptance --expected-revision "$ANALYSIS_CODE_REVISION" --report /evidence/g2/report.json --corpus-root tests/corpora/refactor --baseline /evidence/g0/report.json --accepted-improvement /evidence/improved/report.json
```

Use supported Python 3.11+ and PyYAML. The default policy is
`docs/bhmea/refactor-gate-policy-v2.json`; `--policy` selects another explicitly
reviewed policy. `--evidence-root` overrides the candidate report's directory;
protected reference evidence remains relative to each reference report.
Exit 0 means the selected gate passed, 1 means a structurally valid report failed
G0 eligibility, semantic acceptance or nonregression, and 2 means invalid/incomplete gate inputs. The JSON
result preserves separate structural/removal/failure denominators and detailed
case failures. Full task/L0 integration must invoke acceptance, not baseline.

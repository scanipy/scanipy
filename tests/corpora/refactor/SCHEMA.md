# Machine integration contract — schema 2

`case-manifest.schema.json` is the strict JSON Schema. `case-manifest.json`
contains all required cases sorted by unique `case_id`. `case_count` must equal
the actual array length; JSON Schema alone cannot enforce this cross-field
invariant or unique case IDs, so consumers must check both explicitly.

## Identity and paths

- Root fields: `schema_version=2`, `corpus_id=CMP-CORP-REFAC-01`,
  `corpus_version=0.2.0`, `path_base=corpus_root`, `tree_digest_algorithm`,
  `case_count`, `cases`.
- `before_dir` and `after_dir` are relative to this corpus directory, not CWD
  or the repository root. Locators' `file` paths are relative to the corresponding
  side's source-tree root. Reject absolute paths, `..`, escaping resolution and
  symlinks. Line/column numbers are one-based positive integers, not booleans.
- A locator is `{file,line,column,callee,call_text}`. It identifies source
  intent; the runtime producer must independently establish one matching sink
  in its graph. Never fall back to the first sink/call when matching fails.
- `seed_id` is null for supplemental controls. Primary IDs are
  `seed-NNN/REFRACTOR`; retained-sink fixes add `/structural`; controls use
  `control/NAME`. Select by exact IDs, not guessed file basenames.

## Outcome semantics

`structural_comparison` requires `expected_outcome=stay|flip`, non-null
before/after locators and `required_strength=strong_strong`. Compare actual
computed hashes only after validating both slice classes, compatible identity
namespace, processing status, correspondence and expected preconditions.

`finding_removal` requires `expected_outcome=absent`, `after_locator=null`,
`required_strength=null`, and `observation_subject=finding_lifecycle`. Absence
is established by successful covered detection/lifecycle evidence, never by
null fingerprints, missed locators or failed parsing.

`analysis_failure` requires `expected_outcome=failure`, null after-locator and
strength, and `expected_failure={stage:parse,visible:true,must_not_resolve:true}`.
It is not an ordinary mismatch or a removed finding.

`expected_preconditions` records required `fixture_syntax`,
`transformation_validation`, and optionally `purity_certificate=proven|not_proven`.
These are demands on later evidence, not actual observations. The legacy
`ground_truth_label` is binary for primary cases and may be null for controls;
it must never override typed semantics.

## Digest algorithm and acyclic lock binding

For each tree, reject symlinks and enumerate regular files recursively. Ignore
empty directories. Sort by the POSIX relative filename. Feed SHA-256 the
following concatenation for each file, with lengths measured in bytes:

```text
uint64-big-endian(len(relative_path_utf8)) || relative_path_utf8 ||
uint64-big-endian(len(raw_file_bytes))     || raw_file_bytes
```

Prefix the lowercase 64-character hex result with `sha256:`. The algorithm is
named `sha256-length-prefixed-path-and-content-v1` and implemented in
`pipeline/manifest_contract.py`. Paths and contents both affect identity; the
length framing avoids concatenation ambiguity. Do not normalize source bytes.

The manifest includes `before_tree_digest` and `after_tree_digest` for every
case, but does not contain the corpus digest or its own hash. `corpus.lock`
binds `case_manifest_sha256` to SHA-256 of the exact manifest file bytes; it also
binds each seed's source-tree and metadata hashes and the complete inventory.
`corpus_digest` is SHA-256 over UTF-8 canonical JSON of the lock object after
excluding **only** `corpus_digest`, `built_at`, and `built_by`. Canonical JSON
uses sorted keys, ASCII escaping, separators `(',', ':')`, and no final newline.
The `sha256:` prefix applies here too. This graph of hashes is acyclic.

The generated manifest's file serialization is sorted-key ASCII JSON with a
two-space-indented root and one compact JSON object per case line (four leading
spaces, no internal separator whitespace), plus one trailing newline. This
preserves all case data while fitting the repository's 500 KiB artifact gate.
Consumers hash the actual file bytes,
not a reserialized object. `--check` reconstructs current source-derived cases
and compares exact manifest bytes as well as the fresh canonical lock digest.

## Report producer / gate obligations

A schema-2 campaign report must bind `corpus_id`, `corpus_version`,
`corpus_digest`, and `case_manifest_sha256`, plus revision/toolchain/commands/
source/cache/coverage metadata. Include exactly one observation for each
required case ID; reject omissions, duplicates, extras and mixed bindings.
Carry actual per-side hash, slice class, identity namespace, processing state,
and correspondence, not just an outcome flag. A gate independently computes
equality and validates the category-specific evidence. Recomputed totals are
derived output; reported totals and `matches_expectation` are untrusted.

Missing removal/failure producers must emit honest `not_run`/incomplete cases,
not invented success. G0 diagnostics may report partial structural evidence;
full acceptance requires all required evidence categories. Schema-1 historical
reports cannot be silently upgraded by adding a version number.

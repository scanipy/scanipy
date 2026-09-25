# Refactor corpus — CMP-CORP-REFAC-01, version 0.2.0

This is the corrected source-fixture input for Black Hat refactor-stability
testing. It defines expected results **before** running an engine. It does not
contain a successful runtime invariance campaign or prove that G0/R03/R04/R17
is complete. The active requirements are the Black Hat submission and its
execution review; older architecture documents provide historical context.

The original 50 seeds × seven transforms remain as 350 primary cases. The 50
seeds still repeat eight base topologies (four finding classes × Java/Python).
This is **not** a 50-independent-topology or v1.0.0 diversity claim. Additional
controls test distinct interactions but are reported separately, not counted
as new independent primary seeds. All source is synthesized; none is sourced
from a public repository.

## What changed

The old superficial transformations are replaced with actual source operations:

- Two existing independent assignments that both feed the sink are swapped.
- Pure extraction moves a multi-operand expression into a called helper whose
  return reconnects to the sink. No unused or identity-only helper substitutes
  for extraction.
- Package/module relocation physically moves source and updates a separate
  importing consumer. Java classes contain their helper methods inside the
  class body and compile against ordinary JDK APIs.
- Aliasing negatives call a helper that mutates an aliased value subsequently
  used by the original sink.
- Security fixes have explicit removal expectations. Retained sink API calls
  also have separate structural-comparison cases where a meaningful pair exists.

Python pure fixtures contain an actual exact-built-in type guard, not a type
annotation masquerading as proof. Java helpers use resolved String/primitive
operations. These source preconditions are requirements for the analyzer's
certificate; metadata does **not** issue a purity certificate.

## Required inventory

| Evidence category | Cases | Required observation |
|---|---:|---|
| Structural equality | 270 | Both slices strong; hashes equal; unambiguous corresponding sinks |
| Structural inequality | 100 | Both slices strong; hashes differ; corresponding sinks |
| Finding removal | 50 | Completed, adequate-coverage after-scan establishes absence and correct lifecycle handling |
| Intentional parse failure | 2 | Visible failure; prior finding must not be resolved or suppressed |
| Total | 422 | Exact manifest inventory; no omitted or duplicated cases |

There are 370 structural cases, including 38 retained-sink fix comparisons.
The 34 named controls cover inline-method (eight), combined extraction/rename/
relocation (eight), sink-relevant literal changes (eight), argument-order changes
(two), helper-return changes (two), two-call/multi-assignment extraction (four
exact sink occurrences), and intentional parse failure (two).

The historical binary label split for the 350 primary cases is still 250
`should-stay` / 100 `should-flip`. It is a taxonomy compatibility field, **not**
the acceptance algorithm: a `genuine-fix` removal must not invent an after-hash
to satisfy that old binary label. `evidence_type` and `expected_outcome` govern
schema-2 evaluation.

## Layout and integration

`case-manifest.json` is the complete machine-readable inventory;
`case-manifest.schema.json` defines its types. See [SCHEMA.md](SCHEMA.md) for
digest framing, path and report-binding rules. Seed `meta.yaml` files and
`controls/meta.json` hold source-derived requirements. `corpus.lock` binds the
exact manifest bytes, seed metadata, and every before/after source tree.

The pipeline regenerates source from `bases/__init__.py`,
`pipeline/refactor_transforms.py`, and `pipeline/supplemental_cases.py`.
`pipeline/validate_fixtures.py` independently checks important transformation
shapes. `--check` compares current trees and metadata with the versioned
methodology and recomputes the lock; it does not merely re-hash an old lock.

The unchanged old lock is archived at `history/0.1.0/corpus.lock`. Its matching
source remains in Git revision `940d440cb99e23131d28ee5bbb1655ea29d46a58`.
Old schema-1 reports apply only to that historical corpus, never this revision.

## Reproduce from repository root

Use a supported Python >=3.11 interpreter. Install declared corpus validation
dependencies into an isolated environment if they are not already available:

```sh
python3.11 -m venv .venv-corpus
.venv-corpus/bin/python -m pip install -r tests/corpora/refactor/pipeline/requirements-test.txt
.venv-corpus/bin/python -B tests/corpora/refactor/pipeline/build_corpus.py --check --syntax
.venv-corpus/bin/python -m pytest tests/corpora/refactor/pipeline/test_pipeline.py -o addopts='' -q
```

For complete source syntax validation, put JDK 17+ `javac` on PATH and run:

```sh
.venv-corpus/bin/python -B tests/corpora/refactor/pipeline/build_corpus.py --check --java --syntax-report /tmp/refactor-syntax-report.json
```

The Java check compiles each complete fixture source tree with `--release 17`,
`-proc:none`, a 256 MiB compiler heap and a per-tree timeout. It does not execute
the generated programs or annotation processors. The Python check uses `ast.parse`,
not imports or program execution. Exactly two deliberately malformed after-trees
are expected to fail their language syntax check. A syntax report is explicitly
not a Joern parse/export/map or fingerprint acceptance report.

To deliberately regenerate owned fixture data, use `--write`. This replaces
generated trees and metadata; review the diff, update the version/methodology
when source meaning changes, and then run `--check`. Generation/checking uses
no network or randomness. Only `built_at`/`built_by` and the self-digest are
excluded from the canonical corpus digest.

## Outstanding runtime and diversity work

The report producer must run real production frontend, mapping, slice,
purity/summary, canonicalization and fingerprint collaborators, independently
verify per-side strength and correspondence, and retain honest incomplete rows.
The detector/lifecycle producer must establish removals and parse-failure
retention with coverage evidence. Neither source validity nor equal weak hashes
satisfies those requirements. Expand independently sourced/curated topology
diversity separately; do not drop meaningful Java/Python cases to improve scores.

See [annotation-methodology.md](annotation-methodology.md) and
[CHANGELOG.md](CHANGELOG.md) for the source rationale and regression impact.

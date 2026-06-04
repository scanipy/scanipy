# Detector class: `path-traversal`

**Stage:** A (Python core; Java deferred) · **Engine:** `ifds` → `deterministic-core`
**CWEs:** CWE-22 (path traversal)

## Specs

| File | Languages | Source-of-truth |
|---|---|---|
| `specs/python-os-path-traversal.dsl.yaml` | python | DOC-DSL §8.2 (migrated `tarslip.yaml` semantics) |

## Java is deferred (not invented)

The docs describe Java path-traversal only as "any Java sibling required by
CVE-2025-61765" (DOC-CMP-DET-03 §4.2, `AC-DET-03b`), which is the deferred
CVE-reproduction work tracked by **CLAR-MIGRATION-02**. No curated Java
source/sink inventory exists in DOC-CMP-DET-03 / DOC-DSL / DOC-CMP-DET-01, so the
manifest declares `languages: ["python"]` only — authoring a Java spec from
memory would violate RULE-4 and INV-6 (dishonest per-language labeling).

`AC-DET-03b` (the migrated path-traversal CVE-2025-61765 regression) stays
deferred; it needs `migrate_tarslip` + a Stage-A scan harness (ORCH), out of
this component's scope.

No `(class, language)` pair enters Algorithm-2 benchmarking before `CMP-CP-06`
is green for that language (RULE-7).

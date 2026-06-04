# Detector class: `deserialization`

**Stage:** A (Java core; Python deferred) · **Engine:** `ifds` → `deterministic-core`
**CWEs:** CWE-502 (deserialization of untrusted data)

## Specs

| File | Languages | Source-of-truth |
|---|---|---|
| `specs/java-jackson-untrusted-deser.dsl.yaml` | java | DOC-DSL §8.3 (Java Jackson untrusted deserialization) |

## Python is deferred (not invented)

No Python deserialization source/sink inventory is specified in
DOC-CMP-DET-03 / DOC-DSL / DOC-CMP-DET-01. The manifest declares
`languages: ["java"]` only; a Python spec would be invented from memory
(RULE-4 / INV-6 violation). A CLAR naming the missing inventory is returned to
the orchestrator.

No `(class, language)` pair enters Algorithm-2 benchmarking before `CMP-CP-06`
is green for that language (RULE-7).

# Detector class: `injection`

**Stage:** A (Java + Python core) · **Engine:** `ifds` → `deterministic-core`
**CWEs:** CWE-89 (SQL injection), CWE-78 (OS command injection)

## Specs

| File | Languages | Source-of-truth |
|---|---|---|
| `specs/java-py-injection.dsl.yaml` | java, python | DOC-DSL §8.1 (Java JDBC SQLi), DOC-CMP-DET-01 §7.4 (Python command injection) |

The DSL spec is parsed by `CMP-DET-01 parse_spec()` and registered by `CMP-DET-02`
(`engine: ifds` ⇒ `determinism_partition = deterministic-core`, derived downstream,
never authored on the manifest — DOC-CMP-DET-03 §4.4).

## Provenance / staging notes

`CMP-DET-03` content is pass-through with respect to provenance: `origin`, `S_version`,
`env_digest`, and `cpg_order_hash` are threaded by downstream consumers
(`CMP-ORCH-03` / `CMP-ORCH-01` / `CMP-SNAP-01` / `CMP-CORE-03`), not by this spec.

No `(class, language)` pair enters Algorithm-2 benchmarking before `CMP-CP-06` is
green for that language (RULE-7). These specs make Stage-A benchmarking *possible*;
they do not assert any recall claim.

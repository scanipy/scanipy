# Vuln corpus — ground-truth labelling methodology (CMP-CORP-VULN-01, DOC §3.4)

This corpus is the **held-out evaluation set** for Algorithm 2's per-(class, language)
recall claim (`AC-CORE-01b`). It is **not DONE without this methodology document**
(corpus-agent rule: no manually generated labels without documented, reproducible
methodology). Ground truth here is **never** hand-invented; it is one of three kinds:

## 1. OWASP Benchmark — CSV-verbatim ground truth (SOURCED)

- The label for each OWASP item is taken **verbatim** from the upstream
  `expectedresults-<version>.csv`: `(test name, category, real-vulnerability flag, CWE)`.
- We do **not** re-derive or override the upstream verdict. `positive: true` iff the CSV
  `real vulnerability` column is `true`; `cwe_ids` is the CSV `cwe` column.
- `category -> class` map used: `sqli|cmdi|ldapi -> injection`, `pathtraver -> path-traversal`.
  Only the four Stage-A core classes are populated at v0.1.0.
- Each item records the pinned upstream commit, path, and `upstream_sha256` so a
  fetch-on-demand pull is integrity-verifiable. OWASP content is **not vendored**
  (license: GPL-2.0, off the vendor allow-list — see LICENSES.md, CLAR-CORP-07).

## 2. Juliet — NSA/SARD CWE tag preserved (SYNTHESIZED seed at v0.1.0)

- Juliet's ground truth is the CWE tag carried by each SARD test case. Real Juliet
  cases preserve that tag verbatim into `cwe_ids`; the BadSource→sink structure makes
  the vulnerable site unambiguous.
- v0.1.0 ships **synthetic Juliet-shaped** seeds (clearly labelled `synthetic: true`)
  authored in the canonical BadSource→sink idiom; ground truth is **by construction**
  (the tainted source provably reaches the recorded sink line). Bulk download of the
  real Juliet 1.3 suite from NIST SARD is deferred to `CLAR-CORP-08`.

## 3. BigVul held-out — upstream vuln rows + deterministic split (SYNTHESIZED seed)

- BigVul rows are vulnerability-introducing function changes; `positive: true` marks a
  known-vulnerable function. The held-out split is a **deterministic, training-disjoint**
  function of each row id (see `bigvul_heldout/training_exclusion_proof.md`).
- v0.1.0 ships a small synthetic BigVul-shaped CSV (`bigvul_heldout/data/bigvul_sample.csv`,
  labelled SYNTHESIZED) so the split machinery is exercised and reproducible. The
  held-out item's source is a synthetic stand-in with ground truth by construction.

## Slice schema (DOC §3.1)

Each `<source>/slices/<class>/<language>/<item>/manifest.yaml` carries: `slice_id`,
`source`, `class`, `language`, `cwe_ids`, `positive`, `fix_pair_id`, `license`,
`vendored`, `ground_truth_sites`, `provenance`. Positives carry non-empty
`ground_truth_sites` (the exact file+line+kind a detector must flag); clean variants
carry none. `pipeline/build_lock.py` refuses to emit the lock on any violation.

## Per-(class, language) slicing + INV-6 (DOC §3.3)

A slice is **populated only when its `(class, language)` pair has cleared `CMP-CP-06`**.
A pair with no slice is **`front-end-blocked`** (INV-6), never a recall failure. At GA
only Stage-A languages (Java, Python) carry slices for the four core classes.

## Relabelling discipline

A slice's `cwe_ids` may not change without an amendment to this document and a corpus
semver bump (DOC §7 annotation-drift contract). The forbidden-source / no-overlap rule
is in LICENSES.md.

## No-overlap with model/training data (CRITICAL)

This is an EVAL/held-out split. No item may be identical to, or templated from, any
sample used as training data for Algorithm 2 spec inference (`CMP-TRI-02`) or detector
DSL curation. For BigVul this is enforced structurally by the held-out/training-eligible
disjointness proof; for OWASP/Juliet, additions must be screened before inclusion.

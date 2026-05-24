# Vuln corpus — CMP-CORP-VULN-01 (held-out evaluation set)

This corpus is the **held-out evaluation set** for Algorithm 2's per-(class, language)
recall claim (`AC-CORE-01b`, consumed by `CMP-CORE-01` via `TST-AC-CORE-01b`). It
integrates three sources — **OWASP Benchmark**, **Juliet (NSA/SARD)**, and a
**BigVul held-out split** — sliced along `(class, language)`. Its integrity (especially
BigVul held-out / training disjointness) is INV-6's load-bearing precondition: a
contaminated held-out set makes any recall number uninterpretable (the model has seen
the test). See `DOC-CMP-CORP-VULN-01` for the full contract.

## Status — v0.1.0 (NOT the v1.0.0 release bar)

This is an honest **scaffolding** build delivering: the **deterministic BigVul split +
training-exclusion proof machinery**, a **reproducible `corpus.lock`**, a **genuinely
referenced OWASP seed** (real pinned commit + CSV-verbatim ground truth), small
**synthetic Juliet/BigVul seeds**, and a passing **integrity test suite**. It does
**not** yet meet `AC-CORP-VULN-01a`'s "integrated at scale" bar (full OWASP/Juliet
vendoring + full BigVul split) — that is the `CLAR-CORP-18/08` sourcing campaign.

| Source | This build (v0.1.0) | v1.0.0 release bar |
|---|---|---|
| OWASP Benchmark | 5 items (real CSV-verbatim ground truth, fetch-on-demand) | full Stage-A class coverage, vendored after CLAR-CORP-18 |
| Juliet | 2 synthetic Juliet-shaped seeds | real NIST/SARD suite, vendored (Public Domain) |
| BigVul held-out | 1 held-out item over a 20-row synthetic-shaped sample | full BigVul split, held-out lock preserved across releases |

## SOURCED vs SYNTHESIZED

- **SOURCED** (real upstream, real pinned provenance, CSV-verbatim ground truth):
  - `owasp_benchmark/slices/{injection,path-traversal}/java/*` — OWASP BenchmarkJava
    `1.2beta`, commit `2734ae486356765ea4e45393a28e20bcb5047f8c`. Ground truth is the
    upstream `expectedresults-1.2beta.csv` verdict, verbatim. Content is **fetch-on-demand**
    (GPL-2.0 is off the vendor allow-list — DOC §7); each manifest pins `upstream_sha256`.
- **SYNTHESIZED** (authored for this corpus; ground truth by construction):
  - `juliet/slices/.../*` — Juliet-shaped BadSource→sink seeds (`synthetic: true`).
  - `bigvul_heldout/data/bigvul_sample.csv` + the one held-out item — BigVul-shaped seed
    exercising the deterministic split machinery.

## Provenance summary

| Dataset | Upstream | Pin | License | Vendored? |
|---|---|---|---|---|
| OWASP Benchmark | OWASP-Benchmark/BenchmarkJava | tag `1.2beta` / `2734ae4…` | GPL-2.0 | no (fetch-on-demand) |
| Juliet | NIST SARD Juliet 1.3 (imitated) | — | Public Domain (NIST) | yes (synthetic seed) |
| BigVul | Fan et al., MSR 2020 (imitated) | — | MIT | yes (synthetic seed) |

## Held-out guarantee (the hard rule)

BigVul is partitioned into a **held-out evaluation** slice and a **training-eligible**
complement by a deterministic, order-independent rule (`sha256(row_id) % 10 == 9`).
Held-out ∩ training-eligible is provably empty and re-asserted at every build (a
non-empty intersection **refuses the build** and is a hard release blocker). The
held-out digest is pinned in `bigvul_heldout/heldout_split.lock` and `corpus.lock`, and
is **preserved across releases** (`AC-CORP-VULN-01a`). Full proof:
`bigvul_heldout/training_exclusion_proof.md`. BigVul training data is **never** used as
the held-out evaluation split.

## Layout

```
corpus.lock                          version manifest; sha256 over all slice manifests
owasp_benchmark/slices/<class>/<lang>/<item>/manifest.yaml
juliet/slices/<class>/<lang>/<item>/{manifest.yaml, source/}
bigvul_heldout/
  heldout_split.lock                 sha256 over the held-out row_id set (cross-release)
  training_exclusion_proof.md        MANDATORY disjointness proof (DOC §3.2)
  data/bigvul_sample.csv             split input (SYNTHESIZED seed at v0.1.0)
  slices/<class>/<lang>/<item>/{manifest.yaml, source/}
annotation-methodology.md            ground-truth labelling methodology (DOC §3.4)
pipeline/                            build_lock.py, bigvul_split.py, test_corpus_integrity.py
```

## Rebuild / verify

```
python3 pipeline/build_lock.py --write     # re-derive split + write corpus.lock
python3 pipeline/build_lock.py --check      # CI: fail on digest drift / leakage
python3 -m pytest pipeline/test_corpus_integrity.py
```

## Open CLARs (block v1.0.0, not v0.1.0)

- `CLAR-CORP-18` — CTO approval to **vendor GPL-2.0 OWASP BenchmarkJava** content (GPL
  is off the corpus vendor allow-list). Until resolved, OWASP ships fetch-on-demand.
- `CLAR-CORP-19` — sandbox/sourcing budget to **vendor the full OWASP suite + the real
  NIST/SARD Juliet 1.3 suite + the upstream BigVul CSV** and re-derive the held-out
  split at scale (bulk sourcing exceeds one agent-run).

# Vuln corpus — license attribution + forbidden-source note (CMP-CORP-VULN-01, DOC §7)

**Vendor allow-list** (for content vendored verbatim into the repo): MIT, Apache-2.0,
BSD-2-Clause, BSD-3-Clause, MPL-2.0, Public Domain (NIST), CC0-1.0. **GPL/AGPL require
explicit CTO approval** and are NOT vendored without it. Each item records its license
in `manifest.yaml` and it is validated by `pipeline/build_lock.py`.

## Sourced datasets

| Dataset | Upstream | License | Disposition |
|---|---|---|---|
| OWASP BenchmarkJava | OWASP-Benchmark/BenchmarkJava @ `1.2beta` (`2734ae4…`) | **GPL-2.0** | **NOT vendored** — off the allow-list. Ships fetch-on-demand: manifests pin `upstream_sha256` + path + commit; ground truth taken from `expectedresults-1.2beta.csv`. See CLAR-CORP-18. |
| Juliet Test Suite 1.3 | NIST SARD | Public Domain (NIST) | On allow-list. v0.1.0 ships synthetic Juliet-shaped seeds; real suite vendoring deferred to CLAR-CORP-19. |
| BigVul | Fan et al., MSR 2020 (ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset) | MIT | On allow-list. v0.1.0 ships a synthetic BigVul-shaped split input; real CSV sourcing deferred to CLAR-CORP-19. |

## Synthesized items (authored for this corpus)

- `juliet/slices/.../source/*` and `bigvul_heldout/slices/.../source/*` — original
  synthetic test cases authored for CMP-CORP-VULN-01, released CC0 / Public Domain as
  part of the Scanipy v3.2 repository. They imitate the upstream idiom; they are **not**
  copies of upstream files.
- `bigvul_heldout/data/bigvul_sample.csv` — synthetic BigVul-shaped split input.

## Licensing note (why OWASP is fetch-on-demand)

OWASP BenchmarkJava is licensed **GPL-2.0** across all released versions (verified on
tag `1.2beta` and `master`). GPL-2.0 is a strong copyleft license off this corpus's
vendor allow-list; vendoring it verbatim into a multi-tenant SaaS repo would raise
copyleft-propagation questions. Per DOC §7 ("If license forbids redistribution: the
slice ships as a fetch-on-demand reference, not as vendored content"), OWASP items are
referenced by pinned commit + path + content sha256, not vendored. CTO approval to
vendor (or a decision to keep fetch-on-demand) is tracked as **CLAR-CORP-18**.

## Forbidden-source / no-overlap rule (CRITICAL — eval/held-out integrity)

This corpus is a **held-out evaluation set**. No item may be identical to, or templated
from, any sample used as training data for Algorithm 2 spec inference (`CMP-TRI-02`) or
detector-DSL curation. For BigVul this is enforced structurally by the held-out /
training-eligible disjointness proof (`bigvul_heldout/training_exclusion_proof.md`).
**BigVul training data is never used as the held-out evaluation split.** New OWASP/Juliet
items must be screened for training-set overlap before addition.

## Refusals

| Candidate | Reason refused |
|---|---|
| Vendoring OWASP BenchmarkJava `.java` files | GPL-2.0 off vendor allow-list; shipped fetch-on-demand pending CLAR-CORP-18. |

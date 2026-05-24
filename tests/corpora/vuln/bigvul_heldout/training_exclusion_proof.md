# BigVul training-exclusion proof — CMP-CORP-VULN-01 (DOC §3.2, HARD RULE)

This document is **mandatory** (DOC-CMP-CORP-VULN-01 §3.2). It is the load-bearing
witness that the BigVul held-out evaluation split is **disjoint** from any BigVul row
that could reach a spec-inference run (`CMP-TRI-02`), a spec-curator review, or a
detector-DSL design loop. A held-out / training-eligible intersection is a **HARD
RELEASE BLOCKER** (DOC §7) and invalidates every recall number reported under
`AC-CORE-01b` since the contamination date.

> **v0.1.0 scope.** This build operates over a small, clearly-labelled BigVul-*shaped*
> sample (`data/bigvul_sample.csv`, SYNTHESIZED — see README.md and `LICENSES.md`),
> not the full upstream BigVul CSV. The **procedure, locks, digests, and disjointness
> assertion are real and reproducible**; only the row population is a seed. Sourcing the
> full upstream BigVul dataset and re-deriving this split at scale is `CLAR-CORP-19`.
> The procedure below is the one that will run unchanged on the full dataset.

## 1. Deterministic split procedure (DOC §3.2 item 1)

Implemented in `pipeline/bigvul_split.py`. For every BigVul row:

1. **Stable row id.** If the dataset row has an explicit `row_id`, it is used verbatim.
   Otherwise it is derived deterministically and order-independently as
   `row_id = "bigvul:" + sha256(commit_sha + "\0" + file_path + "\0" + func_name)[:32]`.
2. **Reproducible enumeration.** Rows are sorted by `(commit_sha, file_path, func_name,
   row_id)` — a total order — so re-runs enumerate identically. The partition itself
   does not depend on this order (it is a pure function of each `row_id`).
3. **Partition rule.** A row is **HELD-OUT** iff `int(sha256(row_id), 16) % 10 == 9`
   (a fixed ~10% slice). Every other row is **TRAINING-ELIGIBLE**. The partition is
   total and disjoint by construction — each row lands in exactly one side.

Re-running `pipeline/build_lock.py --write` reproduces byte-identical locks; CI guards
drift with `pipeline/build_lock.py --check`.

## 2. Persisted digests (DOC §3.2 items 2-3)

Source input: `data/bigvul_sample.csv`
`input_csv_sha256 = sha256:7ac71b8f3d5f5bf9b34166f8e18341b0b39d2f60ed9a6b7bb135e1dc270d3091`

| Set | Count | Digest (sha256 over the sorted row_id set) |
|---|---|---|
| HELD-OUT (evaluation) | 1 | `sha256:8ca711ce12bd131a43008556370ac2c0917e53761b35d1135d777c90f871d58d` |
| TRAINING-ELIGIBLE (complement) | 19 | `sha256:cc7d86d6ee5a30a0bbfe21b5fdedcde2969e38ae6a1e9862b5aba49f1fb97de8` |
| Total rows | 20 | — |

Held-out row ids (full enumeration at this version):

- `bigvul:100d0b9ffa07ebda3a9e0ed2894e1823` — `src/net/proxy.py::forward` (CWE-918, ssrf)

The held-out digest is also recorded in `corpus.lock::bigvul_heldout_digest` and in
`heldout_split.lock`. **It is PRESERVED ACROSS RELEASES** (`AC-CORP-VULN-01a`); any
change requires a new corpus semver and a regenerated proof + release-ledger entry.

## 3. Disjointness assertion (HARD)

`SplitResult.assert_disjoint()` is called inside `split_rows()` at every build and is
re-verified by `pipeline/test_corpus_integrity.py`:

```
heldout ∩ training_eligible == ∅
```

If this set is ever non-empty the build **refuses to emit the lock** (exit 2) and the
release is blocked.

## 4. Signed assertion (DOC §3.2 item 4)

> The held-out row_id set digested above has **never** been fed to any spec-inference
> run (`CMP-TRI-02`), any spec-curator review, or any detector-DSL design loop. At
> v3.2 GA none of those consumers have run against BigVul at all; when they do, they
> MUST consume only the **training-eligible** complement (digest in row 2 above) and
> MUST assert, at ingest, that no row they read is a member of the held-out set.
>
> Asserted by: `corpus-agent` (Corpus Curator role), CMP-CORP-VULN-01, v0.1.0,
> 2026-05-24. Ownership formalization tracked under `CLAR-OWNER-01`.

## 5. Re-derivation

```
python3 pipeline/build_lock.py --write     # re-derive split + write both locks
python3 pipeline/build_lock.py --check      # CI: refuse on digest drift / leakage
python3 -m pytest pipeline/test_corpus_integrity.py
```

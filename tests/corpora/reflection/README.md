# Reflection corpus — CMP-CORP-REFL-01 (ground-truth methodology)

This corpus is the **INV-4 falsifier evaluation set** for `CMP-SNAP-03` (`CW-DETECT`).
It drives **Gate 2 (Falsifier CW)** via `tests/falsifier/cw/test_snap03_falsifier.py`
(`TST-AC-SNAP-03a`). A single false negative — `CW-DETECT` returning `closed-world`
on an item labelled `not-closed-world` — is a **release blocker**. This document is
the ground-truth-labelling methodology mandated by `DOC-CMP-CORP-REFL-01 §3.4`; the
corpus is **not DONE without it**.

## Status — v0.1.0 (NOT the v1.0.0 release bar)

This is a **provisional, scaffolding** build that delivers the load-bearing
**mutation-injection pipeline** and a **reproducible `corpus.lock`**, plus a small
**genuinely-sourced hand-curated seed**. It deliberately does **not** yet meet
`AC-CORP-REFL-01a`'s `N ≥ 50` *hand-curated* examples per category, nor the
`review_status: second-pass` dual-review bar for hand items (`DOC §3.4`, `§7`).

| Track | This build (v0.1.0) | v1.0.0 release bar |
|---|---|---|
| Mutation-injected / language | 20 (meets CLAR-CORP-01) | ≥ 20 |
| Hand-curated / category, second-pass | 0 (two single-pass seed items only) | ≥ 50 |

Gate 2 (`TST-AC-SNAP-03a`) is still a `pytest.mark.xfail` stub (`CMP-SNAP-03` not
implemented). The corpus is wired so the gate arms when `CW-DETECT` lands; the gate
**must not be declared passing on the v0.1.0 hand-curated coverage** — see CLARs below.

## What is SOURCED vs SYNTHESIZED

- **SOURCED (real public repos, real `source_url` + `commit_sha`, on the license
  allow-list):**
  - `categories/java-class-forname/0001-spring-classutils-forname` — spring-framework
    `ClassUtils.java` @ `b932df6…` (Apache-2.0); `Class.forName` at lines 304 & 313.
  - `categories/python-getattr/0001-requests-models-getattr` — psf/requests
    `models.py` @ `147c8511…` (Apache-2.0); runtime `getattr` at line 718.
  Both are `review_status: single-pass` and therefore do **not** count toward the
  `N ≥ 50` hand-curated bar.
- **SYNTHESIZED (pipeline-generated from in-repo pinned clean bases):**
  - `categories/mutation-injected/<lang>/` — 20 items per language, produced by
    `pipeline/inject_reflection.py` from `clean_bases/<lang>/`. These are
    `labelled_by: pipeline` (ground-truth by construction) — no second-pass needed.
  - `clean_bases/<lang>/` — synthetic closed-world calculators authored for this
    corpus (Apache-2.0). They are the pinned injection inputs, recorded by content
    sha (`commit_sha: sha256:…`, `synthetic: true`).

## Per-category labelling protocol

1. **Who labels.** A Corpus Curator reads each candidate source tree end-to-end.
2. **What counts as reflection / dynamic dispatch (→ `not-closed-world`).** Any
   *reachable* construct whose call/type target is not statically fixed: Java
   `Class.forName` / `Method.invoke` / `Proxy.newProxyInstance` / Spring dynamic
   proxies; Python `__import__` / `getattr` / `eval` / `exec`; Ruby `send` /
   `method_missing` / `define_method`; PHP variable functions / `call_user_func`;
   JS dynamic `require` / `new Function` / `eval`; Go `reflect.Value.Call`.
3. **Safe-direction rule (INV-4, zero tolerance).** When in doubt, label
   `not-closed-world`. A `closed-world` label is a *positive* claim that the item is
   visibly free of reachable reflection/dynamic dispatch — it must be defensible.
   A wrong `closed-world` label seeds a silent false negative and **defeats Gate 2**.
   Every `not-closed-world` item carries non-empty `expected_sites` (the exact
   file+line+kind a sub-detector must flag); every `closed-world` item carries none.
4. **Dispute resolution.** Disagreement between the two reviewers resolves toward
   `not-closed-world` (the safe direction). A retained `closed-world` label requires
   both reviewers to agree the construct is absent or unreachable.

## Dual-review requirement

Hand-labelled items require `review_status: second-pass` (two independent reviewers)
to count toward `AC-CORP-REFL-01a`. `pipeline`-labelled mutation-injected items are
ground-truth **by construction** and are exempt. `pipeline/build_lock.py` emits a
`hand_curated_second_pass` tally per category and warns on single-pass hand items.

## Mutation-injection pipeline (deterministic seed contract)

`pipeline/inject_reflection.py::inject(clean_source, language, seed, recipe)` is a
**pure function of `(sha256(clean_source), seed, recipe)`** (`DOC §3.5`,
`AC-CORP-REFL-01b`): no global RNG, no wall-clock, no dict/FS-order dependence. It
inserts one reachable reflection construct after a stable anchor inside the entry
method and labels the result `not-closed-world` with `expected_sites` = the exact
injection line. Re-running the build reproduces a byte-identical tree and the same
`corpus_digest`. Verified by `pipeline/test_pipeline.py`.

## Versioning + digest (release ledger — AC-CORP-REFL-01c)

`corpus.lock` carries `corpus_version` (semver) and `corpus_digest` (sha256 of the
canonical serialization, excluding the volatile `built_at`/`built_by` and the digest
field itself). Any add/remove/relabel bumps `corpus_version` and re-pins the digest;
`pipeline/build_lock.py --check` is the CI drift guard. The active version is part of
the release ledger.

## Forbidden-source list

No item may be identical to, or templated from, any sample used to train an
LLM-based reflection classifier consumed downstream (`DOC §3.4`, `§7`). Refusals are
recorded in `LICENSES.md`. License allow-list: MIT, Apache-2.0, BSD-2-Clause,
BSD-3-Clause, MPL-2.0 (never GPL/AGPL without explicit CTO approval).

## Rebuild

    python3 pipeline/build_lock.py --write    # regenerate mutation items + lock
    python3 pipeline/build_lock.py --check     # CI: fail on digest drift
    python3 -m pytest pipeline/test_pipeline.py

## Open CLARs (block v1.0.0, not v0.1.0)

- `CLAR-CORP-03` — assignment of the second reviewer for the `second-pass` dual-review
  protocol (blocks scaling hand-curated categories to `N ≥ 50`).
- `CLAR-CORP-04` — whether `mutation-injected` counts may substitute for hand-curated
  counts toward `AC-CORP-REFL-01a`'s per-category `N ≥ 50`, or whether the two tracks
  are scored separately.
- `CLAR-CORP-05` — sandbox network/sourcing budget for bulk-sourcing real OSS
  reflection samples at `N ≥ 50` per category (this build could reach github.com but
  bulk hand-curation + dual review is out of one agent-run scope).
- `CLAR-CORP-06` — the v0.1.0 mutation pipeline's per-item `seed` does not produce
  structurally-distinct source trees (20 items/language collapse to ~1–3 trees). The
  v1.0.0 generator must vary structure / identifiers / call-context per seed for genuine
  per-item coverage. Until then Gate 2 is NOT declared passing on this corpus.

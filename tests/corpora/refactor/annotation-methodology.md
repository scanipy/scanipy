# Refactor corpus — ground-truth labelling methodology (CMP-CORP-REFAC-01)

This document is the labelling methodology mandated by
`DOC-CMP-CORP-REFAC-01 §4.1` and `.claude/commands/corpus-agent.md`
("No manually generated labels without methodology documentation"). The corpus
is **not DONE without it**, and `corpus.lock.annotation_methodology_ref` points
here.

The headline property: **no label in this corpus is hand-assigned.** Each
`(seed, refactor)` ground-truth label is *derived by construction* from the
refactor transform that produced the `after/` tree, under the slice-preservation
rule below. The transform and the label come from the same deterministic
function (`pipeline/refactor_transforms.py`), so a curator cannot label a pair
inconsistently with how it was generated.

## 1. What is labelled

For each seed (a closed-world program with exactly one seeded finding of a
Stage-A core class) and each of the 7 named refactors, the pair carries a binary
ground-truth label:

| Label | Meaning for Algorithm 3 |
|---|---|
| `should-stay` | Re-running Algorithm 3 on `after/` MUST yield a `slice_fingerprint` byte-identical to `before/`. |
| `should-flip` | Re-running Algorithm 3 on `after/` MUST yield a `slice_fingerprint` different from `before/`. |

The label set is exactly `{should-stay, should-flip}` — no third value.

## 2. The derivation rule (why a label is what it is)

The label is a function of the refactor, fixed by the refactor taxonomy
(`PLAN.md §"Algorithm 3"` + `AC-CORE-02b`). It is not a per-seed judgement.

| Refactor | Algorithm 3 normalization pass | Label | Derivation |
|---|---|---|---|
| `alpha-rename-local` | α-renaming of locals | `should-stay` | The transform is a consistent alpha-rename of bound seeded identifiers. It is a bijection on names; the backward interprocedural slice (source→sink dataflow) is identical up to alpha-equivalence, which Algorithm 3 normalizes away. |
| `pdg-only-formatting` | PDG-only formatting | `should-stay` | The transform inserts only whitespace + comments. No statement is added/removed/reordered relative to a PDG edge, so the sliced PDG is unchanged. |
| `independent-reordering` | canonical topological sort | `should-stay` | The transform inserts a statement that is PDG-independent of the slice (`unrelated = 7 + 35`). Canonical topological sort places independent statements deterministically; the slice's relative order is unchanged. |
| `pure-extract` | summary-inlining normalization | `should-stay` | The transform extracts a **pure, side-effect-free, alias-stable** helper. Algorithm 3 inlines pure summaries before fingerprinting, so the extract is invisible to the slice. |
| `fqn-move-package-rename` | FQN normalization | `should-stay` | The transform changes only the package / module path. FQN normalization canonicalises fully-qualified names, so the slice is unchanged. |
| `genuine-fix` | n/a — sink removed / made safe | `should-flip` | The transform replaces the dangerous sink with a safe / parameterized equivalent (e.g. `PreparedStatement`, `os.path.basename`, host allow-list, `json.loads`). The tainted source no longer reaches a dangerous sink; the backward slice genuinely changes. |
| `aliasing-changing-extract` | NOT covered by summary-inlining | `should-flip` | The transform routes the tainted value through a freshly-aliased mutable holder before the sink. This changes the points-to / aliasing relation feeding the sink. Algorithm 3's summary-inlining covers *pure* extracts only (contrast `pure-extract`), so the fingerprint must flip. A fingerprint that stays here would be **over-normalizing** — a `CMP-CORE-02` bug. |

This table is the entire labelling decision procedure. Because the label is a
deterministic property of the refactor name, the corpus is reproducible and
audit-checkable: `pipeline/build_corpus.py` refuses to emit `corpus.lock` if any
pair's recorded label disagrees with `refactor_transforms.GROUND_TRUTH`, and if
any `should-flip` pair's `after/` tree is byte-identical to `before/`.

## 3. Seed construction (where the seeded findings come from)

Seeds are SYNTHESIZED. Each seed is rendered from one of 8 base templates
(4 Stage-A classes × 2 Stage-A languages) in `bases/__init__.py`. The template
is a pure function of a seed integer: the seed perturbs **identifier names and
constant values only**, never the source→sink topology, so every instantiation
of a template carries the same seeded finding. This keeps the ground-truth label
well-defined across seeds.

Stage-A scope (`.claude/rules/04-staging.md`): classes are
`injection | path-traversal | ssrf | deserialization`; languages are
`java | python`. No other class or language is seeded — Algorithm 3 invariance is
only benchmarked on gate-passing Stage-A pairs (INV-6).

## 4. Adding a new refactor (AC-CORP-REFAC-01b — documented procedure)

A new refactor column is added **only** by the following procedure, which carries
a mandatory regression-impact assessment:

1. **Justify the pass.** A new `should-stay` refactor must correspond to a named
   normalization pass in `PLAN.md §"Algorithm 3"`. If it does not, the addition
   is invented scope — file a `CLAR-CORP-*` instead (RULE-4). A new `should-flip`
   refactor must correspond to a genuine slice change documented in `SDD.md §6`.
2. **Add the transform.** Implement a pure, deterministic transform in
   `pipeline/refactor_transforms.py`, append its name to `REFACTORS`, and add it
   to `SHOULD_STAY` or `SHOULD_FLIP` (this auto-populates `GROUND_TRUTH`).
3. **Add a derivation row** to §2 of this file stating the label and why.
4. **Regression-impact assessment (mandatory).** In the release ledger entry for
   the version bump, record: (a) the new `pair_count` (`seed_count × refactor_count`),
   (b) whether the change is additive (new column) or alters existing pairs,
   (c) the new `corpus_digest`, and (d) the diff in `label_distribution`. Any
   change that alters an existing pair's bytes invalidates downstream
   `CMP-CORE-02` benchmark numbers and must say so explicitly.
5. **Semver bump.** Bump `CORPUS_VERSION` (minor for additive, major if existing
   pairs change), regenerate, and commit the new `corpus.lock`. The digest pins
   the new contents.

## 5. Dispute / failure handling

If `TST-AC-CORE-02a/b` reports a label disagreement (curator label vs.
implementation fingerprint), follow `DOC-CMP-CORP-REFAC-01 §7` and
`DOC-RUNBOOK §8`: if the implementation is right and the label is wrong, the
corpus is wrong — amend §2 here, bump `corpus_version`, and record the
correction in the release ledger. If the label is right and the implementation
is wrong, it is a `CMP-CORE-02` bug, not a corpus change.

## 6. Reproducing the corpus

```
cd tests/corpora/refactor
python3 pipeline/build_corpus.py --write    # regenerate seeds + corpus.lock
python3 pipeline/build_corpus.py --check     # CI: fail on digest drift
python3 -m pytest pipeline/test_pipeline.py  # inventory + determinism self-tests
```

The build is hermetic (no network, no clock in the digest, no RNG); two builds
on any machine produce the same `corpus_digest`.

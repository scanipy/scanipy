# Historical refactor evidence recovered on 2026-09-25

This bundle preserves local artifacts labeled as a 2026-08-31 run. Recovery
performed byte comparison, hashing, static content inspection, and report-count
checks only. It did **not** execute Joern, repair the corpus, establish G0, or
rerun acceptance tests.

## Preserved artifacts

| File | Kind | Bytes | SHA-256 |
|---|---|---:|---|
| [refactor-invariance-topo8-2026-08-31.json](refactor-invariance-topo8-2026-08-31.json) | Raw machine report | 50303 | `fc851c78ec356d22e329129a9be8544f359e0ff40164b268a850c39ce40374b4` |
| [refactor-invariance-topo8-2026-08-31.txt](refactor-invariance-topo8-2026-08-31.txt) | Original emitted summary | 2416 | `c5fb00d230db2d324b39bd608d39378c14b83bff484a27682433f54ce313ed53` |
| [original-writeup.md](original-writeup.md) | Original authored interpretation; not current claim guidance | 4442 | `fc60f0abfe9792d11f46534b3e18de0be0a039c31b197618b587f23f86a3ba8f` |

[recovery.yaml](recovery.yaml) records the source paths, byte-transfer checks,
review scope, and missing execution metadata. The current, qualified account is
[the recovery evidence note](../../../EVIDENCE-refactor-invariance-2026-08-31.md).

The original write-up contains historical assertions such as which claims were
defensible and whether a `strong` label establishes canonicality. Those
assertions are preserved for traceability, **not endorsed**. The later review
identified invalid/vacuous transformations, uncertain fix semantics, and a
strong-canonicality counterexample; use the current note and remediation
backlog when evaluating claims.

## Provenance and limitations

The files were recovered from a local scratchpad copy of `t2run/docs/`, not
downloaded anew from a release or rerun from a known image. The filenames and
original write-up supply the historical date. The report itself has no exact
execution timestamp, executed commit/tree digest, resolved image digest,
`S_version`, or cache/parse-count record. Recovery must not fill those gaps with
the current worktree revision or an image currently bearing the same tag.

The report declares `RealFingerprinter(joern+algorithm-3)`, corpus v0.1.0, and
`--limit 8`. That declaration is retained; this archive alone does not
independently authenticate the original invocation. Raw Joern exports and
execution logs are not part of this recovered bundle. Original instructions
used the mutable `scanipy-t2run:latest` image and an unpinned PyYAML addition;
they are not a verified current reproduction recipe.

Static inspection found synthetic fixture metadata, fingerprint hashes, the
in-container path `/app/tests/corpora/refactor`, and the authored reproduction
command. No apparent credentials or unrelated private source were found in the
three selected files. This is not a full repository/history secret audit.

## Verify the preserved bytes

From the repository root:

```bash
sha256sum docs/evidence/historical/2026-08-31/refactor-invariance-topo8-2026-08-31.json \
  docs/evidence/historical/2026-08-31/refactor-invariance-topo8-2026-08-31.txt \
  docs/evidence/historical/2026-08-31/original-writeup.md
```

Compare against the table and `recovery.yaml`. Preserve this bundle unchanged
when new results arrive; create a separately identified run instead.

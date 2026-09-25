# Recovered historical refactor report — labeled 2026-08-31

Recovery note authored 2026-09-25. This is **historical evidence**, not a new
Joern execution, corrected-corpus G0, or passing acceptance gate. The recovered
raw outputs are preserved byte-for-byte in
[the historical bundle](evidence/historical/2026-08-31/README.md).

Main's historical PR #358 (`ac1575e`) independently contains those same original
JSON, text summary, and authored write-up bytes. Reconciliation retains its
original `docs/evidence/` report paths and this annotated interpretation; the
unchanged original write-up remains in the historical bundle. This confirms
another repository copy, not the missing runtime metadata or claim validity.

## What the artifacts actually report

The [machine report](evidence/historical/2026-08-31/refactor-invariance-topo8-2026-08-31.json)
declares `RealFingerprinter(joern+algorithm-3)` against `CMP-CORP-REFAC-01`
v0.1.0, digest
`sha256:0750651a2d915dbdb672993b2a41d644f893f5e7407d260e5e28054b3f4e50f6`.
It considers the first eight seeds, **56 pairs**, not all 350 pairs on record.
The corpus declares eight base topologies repeated across 50 seeds.

The following table recounts per-pair fields from that original JSON. It agrees
with the historical write-up's numeric table, but replaces its public-claim
verdicts with observations only. Expected labels are historical corpus labels,
not newly validated ground truth.

| Historical refactor label | Expected | Java observations (4 pairs) | Python observations (4 pairs) |
|---|---|---|---|
| `alpha-rename-local` | stay | 4 stayed | 4 stayed |
| `pdg-only-formatting` | stay | 4 stayed | 4 stayed |
| `fqn-move-package-rename` | stay | 4 flipped | 4 stayed |
| `independent-reordering` | stay | 4 stayed | 4 flipped |
| `pure-extract` | stay | 4 stayed | 1 stayed, 3 flipped |
| `genuine-fix` | flip | 3 flipped, 1 stayed (`seed-007`) | 4 flipped |
| `aliasing-changing-extract` | flip | 4 unevaluated | 4 flipped |

Recomputed totals: **40 as expected, 12 contrary, 4 unevaluated**; 30 stayed
and 22 flipped among 52 evaluated pairs. All 52 evaluated comparisons are
*labeled* strong/strong in the report. Four Java aliasing-change cases have
`no-fingerprint-after`; those are neither computed flips nor proof of removal.
The original emitted text summary agrees with these counts.

## What recovery verifies, and what it does not

Recovery checked source/destination SHA-256 and byte equality, unique case
inventory, hash-comparison consistency, totals, and the language/refactor table.
[recovery.yaml](evidence/historical/2026-08-31/recovery.yaml) records the transfer
and unknown metadata. These checks establish that the preserved report is
internally consistent and unchanged from the recovered files. They do not
authenticate its original execution or validate its ground truth.

The report does not bind an exact execution timestamp, executed code revision,
resolved image digest, `S_version`, or cache/parse-count record. The historical
date comes from artifact names and the original write-up. Current workspace
revision or currently tagged image contents must not be substituted for the
missing original values. Raw Joern exports and execution logs are not included
in this bundle.

## Current limitations superseding the old interpretation

The [original authored write-up](evidence/historical/2026-08-31/original-writeup.md)
is archived unchanged, including its old claim guidance. Its prose is not a
current acceptance decision. In particular:

- R03 in the [review backlog](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md)
  identifies invalid Java insertion, an inserted statement mislabeled as
  reordering, unused helpers mislabeled as extraction, a Python comment
  mislabeled as a module move, and alias modifications not feeding the sink.
  Equal or different hashes on those fixtures do not establish the named
  transformations' behavior.
- R18 records an isomorphic-graph counterexample whose results are all labeled
  `strong` but not invariant. A `strong` label alone cannot validate the
  historical write-up's assertion that every evaluated result is canonical
  invariance evidence.
- The `seed-007` genuine-fix result is a historical unchanged fingerprint.
  Establishing a security-correct fix and its expected result still requires
  the R03 fixture audit; the old prose's unconditional false-negative diagnosis
  is not re-certified here.
- Eight repeated base topologies do not establish behavior on unseen programs
  or satisfy the unresolved sourced-diversity bar in `CLAR-CORP-17`.

Local-rename and formatting equality counts remain recorded observations, not
newly approved public guarantees. All submitted claims need the corrected
fixtures, canonicality work, and appropriate current acceptance evidence.

## Follow-up and reproduction status

Use the [evidence conventions](evidence/README.md) for all new runs. R03 must
produce validated versioned fixtures, R04 must enforce report contents, R05
must verify pinned reproduction commands, and the shared G0 gate must record
the corrected baseline. R18/R20 and relevant integration gates remain required
before full-submission conclusions.

The archived command uses mutable image tags and an unpinned PyYAML addition;
it is an historical command record, not a verified recipe for the current
workspace. No Joern command was executed to create this recovery note. No
remediation task, submission claim, or release gate is marked complete here.

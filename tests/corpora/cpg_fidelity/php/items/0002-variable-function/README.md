# Item 0002-variable-function

- **Source:** vendored (synthesized for this corpus; authored by the Corpus Curator).
- **source_url:** `vendored`
- **source_commit:** content-addressed (sha256 of the `source/` tree; see `corpus.lock`).
- **License:** Apache-2.0
- **Category:** `variable_functions`
- **dynamic:** `true`
- **Primary file:** `source/variable_function.php`

## What this exercises

Variable function $fn($name) where $fn holds a function-name string chosen at runtime.

## Ground truth

`ground_truth/{ast,cfg,callgraph,pdg}.json` — hand-derived per the procedure in
`../../methodology.md` (v0.1.0; nikic/PHP-Parser + the CFG/PDG extractor are pinned
there but not executed at build time, since PHP is not on the corpus-build host —
the JSON is the persisted output the `CMP-CP-06` harness compares against).

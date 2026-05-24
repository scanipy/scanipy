# 0006-syn-blocks-procs-lambdas

- **Source:** SYNTHESIZED for this corpus (`pipeline.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `blocks_procs_lambdas`, `dynamic`
- **What it exercises:** higher-order control/data flow through `&block`,
  `block.call`, `yield`, and a stored lambda (`DOUBLE`). Indirect call sites
  (`call`, `yield`, `reduce`/`each` with blocks) are higher-order; the item is
  tagged `dynamic` because the concrete callee behind `step.call` is not
  statically fixed (lower-bound recall).

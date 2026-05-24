# 0003-syn-method-missing

- **Source:** SYNTHESIZED for this corpus (`ghost_methods.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `method_missing`, `dynamic`
- **What it exercises:** ghost methods via `method_missing` / `respond_to_missing?`.
  Calls to undefined names (`find_by_*`) have no static target. The
  `method_missing` def itself is a real node with resolvable internal edges
  (`decode`, `super`); the ghost-call sites are unrepresentable statically and
  the item is tagged `dynamic` so recall is read as a lower bound.

# 0001-syn-plain-calls

- **Source:** SYNTHESIZED for this corpus (`order_total.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `plain_calls`, `closed_world`
- **What it exercises:** statically-resolvable intra-file call edges
  (`subtotal -> add`, `with_tax -> subtotal/tax`), a simple `if/else` branch CFG,
  and def-use PDG edges over local variables. No dynamic dispatch — a baseline
  "closed-world" call graph the front-end should resolve completely.

# 0002-syn-send-dispatch

- **Source:** SYNTHESIZED for this corpus (`dispatcher.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `send`, `dynamic`
- **What it exercises:** runtime dispatch via `send` / `public_send`. The
  call target is a computed symbol, not statically fixed. Ground-truth records
  these as `dynamic_sites` (lower-bound recall convention, INV-6); the static
  helper call `normalize` is a resolvable edge.

# 0004-syn-define-method

- **Source:** SYNTHESIZED for this corpus (`dynamic_accessors.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `define_method`, `dynamic`
- **What it exercises:** methods synthesized at class-load time via
  `define_method` over a data-driven loop. The generated accessor methods have
  no static `def` site; ground-truth records `define_method` as top-level
  `dynamic_sites`. The bodies still call `fetch` / `store` (resolvable).

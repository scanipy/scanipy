# 0009-src-sinatra-indifferent-hash

- **Source:** SOURCED from a real OSS repository.
- **source_url:** https://github.com/sinatra/sinatra
- **source_commit:** 7b50a1bbb5324838908dfaa00ec53ad322673a29 (tag v4.1.1)
- **path_in_source:** lib/sinatra/indifferent_hash.rb
- **license:** MIT (on the corpus license allow-list)
- **categories:** `sourced`, `blocks_procs_lambdas`, `dynamic`
- **What it exercises:** a real, method-rich class (`IndifferentHash < Hash`)
  with extensive intra-file call edges (`convert_key`, `convert_value`), heavy
  use of `super`, and `&method(:...)` references. Exercises call-edge precision
  and PDG recall on genuine production Ruby. `super` calls are recorded as
  `super:<method>` edges (lower-bound: the dispatch target is the parent class).
  `merge!` contains a `yield` (higher-order call site) at line 132, so the item
  carries the `dynamic` tag per the methodology HARD rule (INV-6 lower bound).

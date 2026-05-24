# 0007-syn-active-record-style

- **Source:** SYNTHESIZED for this corpus (`user_repository.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `rails_active_record`, `send`, `dynamic`
- **What it exercises:** a Rails-style repository (no Rails dependency) that
  chains `where`/`order`/`first` and applies a named scope via `scope.send(name)`.
  Models the dynamic-finder idiom the Joern Ruby front-end struggles with.
  Static chain edges are resolvable; the `send`-based scope application is a
  `dynamic_site`.

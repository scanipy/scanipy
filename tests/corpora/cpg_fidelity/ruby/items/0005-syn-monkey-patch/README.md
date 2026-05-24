# 0005-syn-monkey-patch

- **Source:** SYNTHESIZED for this corpus (`string_ext.rb`).
- **source_url:** `vendored`
- **license:** Apache-2.0 (authored for this corpus)
- **categories:** `monkey_patch`
- **What it exercises:** reopening core class `String` to add `shout` /
  `upcase_words`, then calling `text.shout` from `Megaphone#announce`. The
  reopened defs are real call targets, but resolving `text.shout` requires
  whole-program open-class awareness; the `monkey_patch` tag signals the
  front-end may under-resolve this edge (lower-bound).

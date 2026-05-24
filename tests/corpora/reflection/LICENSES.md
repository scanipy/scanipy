# Reflection corpus — license attribution (CMP-CORP-REFL-01, DOC §7)

License allow-list: **MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, MPL-2.0**.
GPL/AGPL require explicit CTO approval and none are present. Each item's license is
recorded in its `provenance.yaml` and validated by `pipeline/build_lock.py`.

## Sourced items (real public repos)

| Item | Upstream | Commit | License |
|---|---|---|---|
| `categories/java-class-forname/0001-spring-classutils-forname` | spring-projects/spring-framework `spring-core/.../util/ClassUtils.java` | `b932df6ad25ee570909c3c2c1ed1a60bd49bbb48` (tag v6.1.6) | Apache-2.0 |
| `categories/python-getattr/0001-requests-models-getattr` | psf/requests `requests/models.py` | `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4` (tag v2.31.0) | Apache-2.0 |

- **spring-framework** — Copyright the original authors; Apache License 2.0.
- **requests** — Copyright Kenneth Reitz and contributors; Apache License 2.0.

Both files are vendored verbatim into the item's `source/` tree to satisfy the
reproducibility contract (DOC §7); their `sha256` is recorded in `corpus.lock`.

## Synthesized items (authored for this corpus)

- `clean_bases/<lang>/*` — original synthetic closed-world calculators authored for
  CMP-CORP-REFL-01. Licensed **Apache-2.0** as part of the Scanipy v3.2 repository.
- `categories/mutation-injected/<lang>/*` — pipeline-generated from the above clean
  bases; inherit the Apache-2.0 license of their synthetic input.

## Refusals (forbidden-source / license)

| Candidate | Reason refused |
|---|---|
| CPython `Lib/runpy.py` (`__import__` site) | PSF License Agreement is not on the corpus allow-list; replaced with the Apache-2.0 psf/requests `getattr` example to keep license provenance clean. |

No corpus item is known to overlap any LLM reflection-classifier training set
(DOC §3.4 forbidden-source rule). New items must be screened before addition.

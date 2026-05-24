# LICENSES — Python CPG-fidelity corpus (CMP-CORP-CPG-python)

License allow-list (DOC §7): MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, MPL-2.0, PSF.
Any program outside this list is rejected at build time.

## SOURCED programs

| Program | Upstream | Commit | License |
|---|---|---|---|
| `0011-requests-hooks-sourced` | [psf/requests](https://github.com/psf/requests) `src/requests/hooks.py` | `cd90742ed94d901759e26766197d0ce7c7bd9c8e` | Apache-2.0 |

`psf/requests` is distributed under the Apache License 2.0
(<https://github.com/psf/requests/blob/main/LICENSE>). The single sourced file is
reproduced verbatim for fidelity-evaluation purposes; the upstream copyright and
license notice apply.

## SYNTHESIZED programs

`programs/0001`..`0010` were authored for this corpus and are released under
Apache-2.0 as part of Scanipy v3.2. They are content-addressed in `corpus.lock`
(`commit_sha: sha256:...`, `synthetic: true`).

## Refusals

- Programs derived from Joern's own `pythonsrc` test fixtures are forbidden
  (would bias the `CMP-CP-06` gate). None are present.
- Python-2 programs are rejected at build time (DOC §7).

# LICENSES — CMP-CORP-CPG-js

License allow-list (DOC §7): **MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause,
MPL-2.0, ISC**. GPL/AGPL require explicit CTO approval (none used here).

## SOURCED programs (real OSS)

| Program | Upstream | Commit | License |
|---|---|---|---|
| `programs/0201-escape-string-regexp` | sindresorhus/escape-string-regexp | `cbc42403142c96923b482604e1f3d627b1956aff` | MIT |
| `programs/0202-is-number` | jonschlinkert/is-number | `98e8ff1da1a89f93d1397a24d7413ed15421c139` | MIT |

Upstream `LICENSE` text is copied into each program's `source/` directory.

## SYNTHESIZED programs

`programs/0001`–`0005`, `0101`, `0102` are authored for this corpus and released
under **Apache-2.0** (consistent with the repo). They are content-addressed
(`commit_sha: sha256:…`, `synthetic: true` in `provenance.yaml`).

## Refusals (sources screened out)

| Candidate | Reason |
|---|---|
| isaacs/once @ `0fbb41e` | License is **BlueOak-1.0.0**, not on the allow-list. Rejected. |
| Joern `jssrc` test fixtures | Forbidden by DOC §7 (would bias the CPG-fidelity gate). Not sourced. |

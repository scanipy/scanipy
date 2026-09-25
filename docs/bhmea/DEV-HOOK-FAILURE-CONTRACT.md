# Development hook failure contract

Scope: corrective issue #384 under #366, CMP-CI-01 developer tooling. This
preserves the existing named Gate 1–4 workflows; it does not add a new named
gate or establish Black Hat feature acceptance.

## Exit-status contract

| Hook | Required behavior |
|---|---|
| `pre-commit` | Run lint-staged, then Python/security pre-commit checks. Any nonzero or missing-command result is fatal; a later success cannot mask it. |
| `pre-push` | Run Ruff lint, format, one full mypy invocation, then the existing unit/invariant selection. Stop on the first failure. |
| `commit-msg` | Preserve the single conventional-commit validator's result and quoted filename argument; missing validator remains fatal. |

Mypy receives every populated directory from `analysis`, `detectors`,
`integrations`, `services`, `workers`, in that order. Empty/missing directories
retain the existing scaffold exemption; an error from discovery is **not** an
empty scaffold. A failed full invocation is never retried against a smaller
source set. Protected-branch update/deletion checks and existing explicit user
bypass semantics are unchanged; this correction adds no bypass.

## Why both corrections are needed

During #381 integration, lint-staged failed because `yamllint` was absent from
the fresh development PATH. The old pre-commit wrapper lacked `set -e`, so the
following successful Python hook masked the failure. All affected checks were
rerun explicitly before PR #383 was published. The separate hook audit then
found that pre-push could mask a type error outside the first source directory
by retrying mypy against only that directory.

New tests were run against the unchanged hooks before implementation: all
three injected first-stage error codes and the missing `npx` case incorrectly
returned 0 (four expected regression failures); the full-mypy error case also
incorrectly returned 0 (one expected regression failure). The corrected hooks
preserve those nonzero results. The tests execute the actual hook scripts with
isolated, trusted command stubs and real filesystem discovery; they do not
execute scanned source or target build hooks.

## Fresh developer setup

`package.json` invokes the `yamllint` CLI from lint-staged, outside the Python
pre-commit framework's isolated environment. Therefore `dev` now explicitly
declares `yamllint==1.35.1`, matching `.pre-commit-config.yaml`'s existing pin.
The isolated hook package alone does not satisfy lint-staged's PATH requirement.

Install the declared `.[dev,http]` extra in an activated Python 3.11 development
environment and the declared Node tooling. When using worktrees, install Node
dependencies with `npm install --ignore-scripts --no-package-lock --no-audit
--no-fund`; do not let Husky's prepare script change shared `core.hooksPath`.
Select the intended worktree's `.husky` directory per Git command when testing
changed hooks, without changing another worktree's configuration.

Observed fresh verification environment on 2026-09-25:

- Python 3.11.16; uv 0.12.19 used to create a private venv and install
  `-e '.[dev,http]'` with third-party wheel-only resolution. Only the trusted
  Scanipy development package was built for editable installation.
- 67 installed distributions; `uv pip check` reported all compatible.
- yamllint 1.35.1, PyYAML 6.0.3, pathspec 1.1.1, pytest 9.1.1, mypy 2.3.1,
  Ruff 0.15.22 and pre-commit 4.6.2 were observed, not assumed latest.
- Actual `yamllint --version` matched 1.35.1; a valid YAML fixture passed and
  malformed YAML failed under the repository configuration. The test also
  binds the declared version to the existing isolated hook pin and CLI on PATH.

Reference paths (not deployment prerequisites): worktree
`/tmp/scanipy-precommit-366-FhbTjxWK`; private test venv
`/tmp/scanipy-hook-devtools-iT7nt4o1/venv`. No shared test environment was mutated.
The fresh install is development-tooling evidence, not a snapshot image or
full analysis environment proof. Native image startup, Java safe mode,
canonical identity and full campaign acceptance remain separate work.

## Audit boundaries

All three `.husky` Git hooks were inspected; only the two masking defects
needed source changes. Commit-message validation remains one status-propagating
command and has positive, failure and missing-command regression coverage.
The `.claude` post-edit/status hooks explicitly describe advisory behavior;
they are not substituted for Git/CI enforcement and are unchanged. No changes
to the agent's source-of-truth guard, named CI gates, runtime finding behavior,
worker tool/base pins, registry mappings or container processes are included.

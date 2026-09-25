# Execution-ledger checks — 2026-09-25

Evidence type: local tooling/component diagnostic, not a scan or feature gate.
Scope: R01's ledger checker and R17's retained evidence integrity. The worktree
is based on `940d440cb99e23131d28ee5bbb1655ea29d46a58`; these new files are
pending PR review/merge. No G0/G1/G2/G3 or full R-task is accepted by this note.

## Observed checks

| Check | Observed result |
|---|---|
| `python scripts/check_bhmea_execution_state.py docs/bhmea/execution-state.json` | Exit 0; 20 tasks, 18 claims, 85 acyclic milestones/gates |
| `python -m pytest tests/unit/test_check_bhmea_execution_state.py -p no:cacheprovider` | Exit 0; 26 passed on supported Python 3.11 |
| `ruff check scripts/check_bhmea_execution_state.py tests/unit/test_check_bhmea_execution_state.py` | Exit 0 |
| `python -m mypy scripts/check_bhmea_execution_state.py` | Exit 0; one source file checked |
| SHA-256 and byte length of retained historical/readiness artifacts | Nine artifacts match their manifests; retained JSON parses |
| `cmp` of the three historical artifacts against their recovered temporary originals | All exit 0 |

The mutation tests reject missing/duplicate IDs, cycles, missing edges, optional
cache work blocking G0, delayed G1, reduced G2 prerequisites/language scope,
unsupported DONE/claim/readiness assertions, missing evidence, path escapes,
and duplicate JSON keys. They do not authenticate execution evidence or prove
the implementation behind a claim.

## Runtime and reproduction

The tests/lint/typecheck used isolated Python 3.11 tooling in Docker, with the
worktree mounted at `/workspace` and `PYTHONPATH=/workspace` for tests. The image
was the existing `python:3.11-slim`, observed registry digest
`python@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6`.
Dependencies were installed separately from the project's `dev,http` extras
in `/tmp/scanipy-bhmea-venv-xuG814`, mounted read-only at `/bhmea-venv`.
No scanned source or application database was used. This is not a shipped
worker-image or clean-install check. Dependency freezing/CI reruns remain
separate from this scoped result.

On a development environment with Python >=3.11 and the project dev extras,
run the commands in the table from the repository root. The ledger command is
stdlib-only. Evidence artifact hashes are specified in the historical
`recovery.yaml` and readiness `manifest.yaml`; recompute them over exact bytes.

The whitespace/EOF mutating pre-commit hooks exclude only retained historical
and `raw/` evidence paths to preserve bytes. Schema, secret, merge-conflict and
size checks remain enabled; an evidence exclusion is not a license to commit
unreviewed sensitive content. Authored evidence notes are still formatted.
`git diff --cached --check` reports the original extra EOF blank line in
`2026-09-25-r05-readiness/raw/container.log`; it is deliberately retained to
preserve the recorded digest, not repaired and called an original artifact.

The secret hook flagged 66 high-entropy values in six evidence files. They were
reviewed as artifact/code/source SHA-256 values, historical slice fingerprints,
the inspected Docker container/network IDs, and Docker metadata paths containing
that container ID. Their exact file/value hashes are added to `.secrets.baseline`
as reviewed non-secrets; no broad path/plugin exclusion was added. Existing
baseline entries are preserved. Raw evidence is unchanged. This is a scoped
review of the new artifacts, not a full repository/history secret audit.

### Independent baseline-entry recount

Compared with reviewed main `89ed803`, `.secrets.baseline` has **69 entries
versus 3**, a net **66 added finding entries and zero removed entries**. All
66 additions explicitly have `is_secret: false`. The Git diff reports **541
inserted lines**, not 541 entries; each JSON entry spans multiple lines.

| Added evidence path | Added finding entries | Reviewed value category |
|---|---:|---|
| `2026-09-25-r05-readiness/manifest.yaml` | 16 | Artifact/code/source and container identity digests |
| `2026-09-25-r05-readiness/raw/container-inspect.json` | 4 | Docker container identity and metadata paths |
| `2026-09-25-r05-readiness/raw/container.log` | 6 | Recorded artifact/container identity values |
| `2026-09-25-r05-readiness/raw/diagnostic.json` | 6 | Actual code/source/tool/artifact identities |
| `historical/2026-08-31/recovery.yaml` | 4 | Historical artifact/corpus digests |
| `historical/2026-08-31/refactor-invariance-topo8-2026-08-31.json` | 30 | Historical corpus and reported slice hashes |

Paths in this table are relative to `docs/evidence/`. Reproduce the entry
counts independently (read-only):

```bash
jq '[.results[] | .[]] | length' .secrets.baseline
git show 89ed803:.secrets.baseline | jq '[.results[] | .[]] | length'
git diff --numstat 89ed803 -- .secrets.baseline
```

Entry identity was compared by `(filename, type, hashed_secret)`, not line
count. Classification still requires reviewing the actual referenced content;
this recount verifies scope, not an automatic proof that arbitrary high-entropy
values can never be sensitive. No raw artifact was changed for this recount.

## Remaining work

- Required PR review and CI, with no premature completion of umbrella #362.
- R04's independent typed semantic report checker; this ledger tool is not it.
- Actual source-to-finding, identity, attestation, lifecycle, installation and
  stage acceptance under the full review backlog.

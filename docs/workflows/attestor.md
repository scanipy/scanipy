# attestor.yml — Gate 3 — Attestor core

**Workflow `name:`** `Gate 3 — Attestor core (every detector/engine/Env change)`
**File:** `.github/workflows/attestor.yml`

---

## Purpose

`attestor.yml` runs **Gate 3 — the Attestor core pipeline** (`CMP-CP-05`, anchor ACs
`AC-CP-05a` + `AC-CP-05c`). It verifies that the `origin=deterministic-core` partition
produces **byte-identical SARIF** across independent runs under fixed
`(S_version, env_digest, LLM_TRIAGE=off)` — the operational discharge of reproducibility
property (a) (`CLAUDE.md §2`) and INV-1. A byte-difference is a determinism regression
and a **hard release blocker**. It runs whenever a change touches the detection/analysis
surface (detectors, analysis core, workers, scan/snapshot services).

---

## Triggers

```yaml
on:
  push:
    branches: [main]
    paths: [detectors/**, analysis/**, workers/**, services/scan/**, services/snapshot/**]
  pull_request:
    paths: [detectors/**, analysis/**, workers/**, services/scan/**, services/snapshot/**]
  workflow_dispatch:
```

- **`push` to `main`** restricted to the five watched paths.
- **`pull_request`** restricted to the same five paths — **but with no `branches:`
  filter**, so it fires on a path-touching PR to *any* target branch, not only PRs into
  `main` (see Notes).
- **`workflow_dispatch`** — manual re-attestation (used by `DOC-RUNBOOK §4.3`).

**Concurrency:** `group: ${{ github.workflow }}-${{ github.ref }}`,
`cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` — superseded PR runs are
cancelled; `main` runs are release blockers and run to completion (cancelling one
mid-determinism-canary would record a partial partition).

**Permissions:** `contents: read`, `checks: write`. **Env:** `PYTHON_VERSION: "3.11"`.

---

## Jobs & steps

### `attestor-core` — "Gate 3 — Attestor core pipeline (AC-CP-05a/c)"  *(Gate 3)*

`runs-on: ubuntu-latest`. Steps:

1. `actions/checkout@v4`; `actions/setup-python@v5` (3.11, pip cache); deps via
   `pip install -e ".[dev]"`.
2. **"Check canary corpus exists"** — if `tests/corpora/canary` is missing, prints a
   WARNING that `TST-AC-CORE-01a` will be skipped and that `CMP-CORP-CANARY-01` must be
   DONE for the full 100-repo suite. (Warning only — does not fail the job.)
3. **"Run Attestor core tests"** —
   `pytest tests/ -m "invariant or empirical" -k "attestor or determinism or core_partition" -q --tb=long -v --junit-xml=attestor-results.xml`,
   with env `SCANIPY_ENV=test` and **`LLM_TRIAGE: "off"`** (INV-3: triage must not
   influence the core partition).
4. **"Upload results"** — `actions/upload-artifact@v4` (`attestor-results`),
   `if: always()`.

### `determinism-canary` — "Determinism — 100 canary repos × 5 re-runs (TST-AC-CORE-01a)"

`needs: attestor-core`. Steps:

1. `actions/checkout@v4`.
2. **"Detect canary corpus presence"** (`id: corpus_check`) — emits
   `has_corpus=true` iff `tests/corpora/canary/corpus.lock` exists, else
   `has_corpus=false` with a skip message.
3. Python setup, deps, and **"Run determinism canary suite"**
   (`pytest tests/ -m "empirical" -k "determinism_canary" …`) — **each gated on**
   `steps.corpus_check.outputs.has_corpus == 'true'`.

The corpus-presence check is a **step output**, not a job-level `if:`, on purpose: the
inline comment records that `hashFiles()` is not allowed in a job-level `if:` and that
the original scaffold used `if: hashFiles(...)` there, which **failed the workflow at
parse time on every push since commit 00c5bfe**. Moving the check into a first step that
emits `has_corpus` is the fix.

---

## How it works

When a PR (path-touching) or a `main` push changes the detection surface, `attestor-core`
re-runs the core determinism tests with the LLM triage explicitly off and uploads JUnit
results. If the canary corpus exists, the follow-on `determinism-canary` job replays 100
canary repos × 5 re-runs and asserts byte-identical SARIF; if the corpus is absent it
skips cleanly. A byte-difference fails the gate and blocks the release.

---

## Gate / rule mapping

- **Gate 3 — Attestor (`AC-CP-05a/c`)** → job `attestor-core`. Enforces **INV-1**
  (determinism partition) operationally. Required status check on `main`
  (check name `Gate 3 — Attestor core pipeline (AC-CP-05a/c)`).

---

## Failure response

A red `attestor-core` is an **attestation incident** — a byte-difference in the core
partition. Reproduce locally, compare `cpg_order_hash` and `fingerprint_class`
distribution, hunt pseudo-sources (clock, env, random seed, hashmap/glob order,
parallelism), and **block deploy** (`deploy.yml`'s `pre-deploy-checks` refuses any SHA
whose Gate 3 is not green). File a `CLAR-*` if a new pseudo-source class is unspecified.
Full procedure: `DOC-RUNBOOK §8.3` → `DOC-RUNBOOK §7`. Re-attestation:
`DOC-RUNBOOK §4.3` (trigger this workflow via `workflow_dispatch`).

---

## Notes / gotchas

- **PR trigger has no `branches:` filter.** The `pull_request:` block filters by `paths:`
  only, so it fires on path-touching PRs to any branch. `DOC-CMP-CI-01 §3.1` describes
  this as "push to `main` paths-touched … ; same for PR", which reads as main-targeted;
  the YAML is broader. Documented here as a known doc-vs-YAML wording mismatch
  (not fixed — workflow files are not edited by documentation work).
- **Expected-red on `main` until the corpus lands.** The `determinism-canary` job skips
  cleanly without `tests/corpora/canary/corpus.lock`, but `attestor-core`'s test
  selection (`-k "attestor or determinism or core_partition"`) depends on detectors /
  analysis code that do not exist yet (Phase 2/4 work). Until those inputs land, the
  Attestor cannot produce a meaningful pass; treat reds as expected-pending-inputs, not
  determinism regressions, and confirm against the test selection before declaring an
  incident.
- The job-level-`if` + `hashFiles()` parse-failure history (commit 00c5bfe) is the reason
  for the step-output corpus-check pattern — do not reintroduce a `hashFiles()` job-level `if:`.

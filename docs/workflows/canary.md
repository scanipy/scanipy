# canary.yml — Canary — SCM parity + nightly regression

**Workflow `name:`** `Canary — SCM parity + nightly regression`
**File:** `.github/workflows/canary.yml`

---

## Purpose

`canary.yml` is a **supporting (non-gate) nightly workflow** with two independent jobs:

1. **SCM parity** (`TST-AC-SCM-03c`) — the 100 canary repos must resolve to **identical
   commits** across GitHub / GitLab / Bitbucket / Azure DevOps, exercising the SCM
   integration layer (`CMP-SCM-*`).
2. **Nightly regression** — the full unit + integration + nightly test suite, with
   coverage, as a broad catch-all regression net.

Neither job is one of the four named gates (`DOC-CMP-CI-01 §3.2`); they are
informational regression coverage.

---

## Triggers

```yaml
on:
  schedule:
    - cron: "30 3 * * *"      # nightly at 03:30 UTC
  workflow_dispatch:
```

- **`schedule`** — `30 3 * * *` decodes to **03:30 UTC every day**. The inline comment
  states this is intentionally **after `falsifier-cw` completes** (which runs 02:00 UTC).
- **`workflow_dispatch`** — manual run.

**Permissions:** `contents: read`, `checks: write`. **Env:** `PYTHON_VERSION: "3.11"`.
**No `concurrency` block** (see Notes).

---

## Jobs & steps

### `scm-parity` — "SCM parity — 100 canary repos (TST-AC-SCM-03c)"

`runs-on: ubuntu-latest`. Steps:

1. `actions/checkout@v4`.
2. **"Detect canary corpus presence"** (`id: corpus_check`) — emits `has_corpus=true`
   iff `tests/corpora/canary/corpus.lock` exists, else `has_corpus=false` with a skip
   message (`CMP-CORP-CANARY-01` not DONE).
3. Python setup, deps, **"Run SCM parity tests"**
   (`pytest tests/integration/ -m "integration" -k "scm_parity or canary" … --junit-xml=canary-scm-results.xml`),
   and **"Upload results"** — **all gated on** `steps.corpus_check.outputs.has_corpus == 'true'`.

As in `attestor.yml`, the corpus check is a **step output** (not a job-level `if:`)
because `hashFiles()` is disallowed in a job-level `if:` — the inline comment records the
same parse-time-failure history (commit 00c5bfe) and fix.

### `nightly-regression` — "Nightly regression suite"

`runs-on: ubuntu-latest`, **no corpus gate** — always runs. Steps:

1. `actions/checkout@v4`; `actions/setup-python@v5` (3.11, pip cache).
2. **"Install dependencies"** — `pip install -e ".[dev]" pytest-cov`.
3. **"Run nightly tests"** —
   `pytest tests/ -m "unit or integration or nightly" -q --tb=short --cov=. --cov-report=xml --junit-xml=nightly-results.xml`
   with `SCANIPY_ENV=test`.
4. **"Upload coverage"** — `actions/upload-artifact@v4` (`nightly-coverage`), `if: always()`.

---

## How it works

Every night at 03:30 UTC (and on manual dispatch), `scm-parity` checks for the canary
corpus and — if present — asserts cross-provider commit-resolution parity over 100 repos;
in parallel, `nightly-regression` runs the full marked test suite with coverage. The two
jobs are independent (no `needs`).

---

## Gate / rule mapping

**Not a gate — supporting workflow.** Provides nightly SCM-parity and full-suite
regression coverage. It does not appear in the four-gate table and is not a
branch-protection required check.

---

## Failure response

No dedicated runbook gate procedure (not Gate-class). A red `scm-parity` indicates a
cross-provider commit-resolution divergence in the SCM layer (`CMP-SCM-*`); a red
`nightly-regression` is a general regression — triage the failing tests. There is no
deploy-block tied to this workflow.

---

## Notes / gotchas

- **No `concurrency:` block** — unlike `ci.yml` and `attestor.yml`. Because the workflow
  is scheduled / manually dispatched (not rapid PR pushes), overlapping runs are unlikely;
  but two near-simultaneous `workflow_dispatch` runs would not auto-cancel each other.
- **`scm-parity` is expected-skip / `nightly-regression` expected-thin on `main` today.**
  The canary corpus (`CMP-CORP-CANARY-01`) does not exist yet, so `scm-parity` skips
  cleanly. `nightly-regression` runs but currently exercises only the scaffold test set
  (most application source is Phase 2/4 work). Treat thin/skipped runs as
  expected-pending-inputs.
- `scm-parity` depends on the same `tests/corpora/canary/corpus.lock` file as
  `attestor.yml`'s `determinism-canary` job — both consume `CMP-CORP-CANARY-01`.

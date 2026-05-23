# ci.yml — CI — Scanipy v3.2

**Workflow `name:`** `CI — Scanipy v3.2`
**File:** `.github/workflows/ci.yml`

---

## Purpose

`ci.yml` is the main per-PR / per-push pipeline. It runs the developer-experience
quality bars (lint, type-check, unit tests, integration tests) **and** carries two of
the four named CI gates from `CMP-CI-01` (`docs/components/DOC-CMP-CI-01.md`):

- **Gate 1 — DSL distributivity proofs** (`AC-DET-01a`, INV-4 owner for the DSL closure).
- **Gate 4 — e-process martingale** (`AC-TRI-02b`, INV-3 support — keeps the LLM off the
  detection path).

The lint/unit/integration jobs are pre-existing quality bars, **not** Gate-class checks
(`DOC-CMP-CI-01 §3.2`). Only `dsl-proofs` and `eprocess-unit` are named gates.

---

## Triggers

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

- `push` to `main` and `pull_request` targeting `main`. No path filter — every change
  runs the full job graph.

**Concurrency:**

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

Superseded PR / feature-branch runs are cancelled when a developer pushes again.
`main` runs are **never** cancelled (`cancel-in-progress` is `false` on `refs/heads/main`)
so a `main` run is not killed mid-flight — the inline comment notes this matters once
deploy/attestor work lands.

**Top-level `permissions`:** `contents: read`, `checks: write`, `pull-requests: write`.
**Env:** `PYTHON_VERSION: "3.11"`, `NODE_VERSION: "20"`.

---

## Jobs & steps

### `lint` — "Lint & typecheck"

`runs-on: ubuntu-latest`, no `needs`. Steps:

1. `actions/checkout@v4`.
2. `actions/setup-python@v5` (3.11, pip cache).
3. **"Install Python dev dependencies"** — `pip install -e ".[dev]"`.
4. **"Ruff lint"** — `ruff check .`.
5. **"Ruff format check"** — `ruff format --check .`.
6. **"Mypy strict"** — runs `mypy` over `analysis/ detectors/ integrations/ services/`
   **only if** any `*.py` source exists under those dirs; otherwise prints a
   scaffold-phase skip message. (Scaffold-phase guard.)
7. `actions/setup-node@v4`, **"Install Node dependencies"**, **"ESLint"**,
   **"Prettier check"** — each gated on `hashFiles('web/**/*.{ts,tsx,js,jsx}') != ''`,
   i.e. they run only once `web/` has TS/JS source. `cache: npm` is intentionally
   omitted (setup-node errors without a lockfile); `npm install` is used (not `npm ci`)
   until a lockfile is committed.
8. **"Node toolchain — skipped (scaffold phase…)"** — the inverse guard
   (`hashFiles(...) == ''`) prints a visible skip message.

### `unit-tests` — "Unit tests"

`needs: lint`. Checkout + Python setup + deps, then:

- **"Run unit tests"** — if Python source exists under
  `analysis/ detectors/ integrations/ services/ workers/`, runs
  `pytest tests/unit/ -m unit -q --tb=short --cov=. --cov-report=xml` (the
  `coverage.fail_under = 80` production contract from `pyproject.toml` applies).
  Otherwise it passes `--cov-fail-under=0` so the scaffold phase (zero source → zero
  coverage) does not tank the job. The override drops the moment the first `.py` source
  lands.
- **"Upload coverage"** — `actions/upload-artifact@v4` (`coverage-unit`), only if
  `coverage.xml` exists.

### `dsl-proofs` — "Gate 1 — DSL proofs (AC-DET-01a)"  *(Gate 1)*

`needs: lint`. Checkout + Python setup + deps, then:

- **"Run DSL proof tests"** — `pytest tests/unit/test_dsl_proofs.py -m unit -q --tb=short -v`.

This is the operational discharge of the DSL distributivity precondition (INV-4 safe
direction): every combinator must carry a machine-checked distributivity proof
obligation. No scaffold guard — the test file is owned by `CMP-DET-01`.

### `eprocess-unit` — "Gate 4 — e-process martingale (AC-TRI-02b)"  *(Gate 4)*

`needs: lint`. Checkout + Python setup + deps, then:

- **"Run e-process martingale tests"** — if any `test_*.py` exists under
  `tests/falsifier/eprocess/`, runs `pytest tests/falsifier/eprocess/ -q --tb=short -v`;
  otherwise prints a scaffold-phase skip message. The directory currently holds only
  `__init__.py`; pytest would exit code 5 ("no tests collected") which CI counts as
  failure, so the guard skips cleanly. **The guard auto-flips and Gate 4 becomes
  enforced the moment the first `TST-AC-TRI-02b` test lands** (owned by `CMP-TRI-02`).

### `integration-tests` — "Integration tests"  *(non-gating, informational)*

`needs: [unit-tests, dsl-proofs]`, with `if: github.event_name == 'push' || github.base_ref == 'main'`.
Runs a `postgres:16` service container (DB `scanipy_test`, health-checked via
`pg_isready`); sets `SCANIPY_DATABASE_URL` and `SCANIPY_ENV=test`. Step:

- **"Run integration tests"** — if any `test_*.py` exists under `tests/integration/`,
  runs `pytest tests/integration/ -m integration -q --tb=short`; otherwise prints a
  scaffold-phase skip message (same exit-5 guard).

---

## How it works

On every PR to `main` (and on push to `main`): `lint` runs first; `unit-tests`,
`dsl-proofs`, and `eprocess-unit` fan out from `lint`; `integration-tests` runs after
both `unit-tests` and `dsl-proofs` succeed (and only on push or main-targeted PRs). The
two gate jobs (`dsl-proofs`, `eprocess-unit`) carry the `Gate N — …` check names that
become the branch-protection required-status-check contexts once the org upgrades
(`DOC-CMP-CI-01 §3.3`).

---

## Gate / rule mapping

- **Gate 1 — DSL proofs (`AC-DET-01a`)** → job `dsl-proofs`. INV-4 (DSL closure).
- **Gate 4 — e-process martingale (`AC-TRI-02b`)** → job `eprocess-unit`. INV-3 support.
- `lint`, `unit-tests`, `integration-tests` are **not** gates (`DOC-CMP-CI-01 §3.2`).

---

## Failure response

- **Gate 1 red:** a combinator lacks (or regressed) a discharged distributivity proof.
  Author the proof in `analysis/ifds/dsl/`; do not relax the gate. → `DOC-RUNBOOK §8.1`.
- **Gate 4 red:** the e-process implementation no longer satisfies the martingale
  property `E[E_τ|H0] ≤ 1`. Blocks **customer-enablement** deploy only, not baseline
  release. → `DOC-RUNBOOK §8.4`.
- **`lint` / `unit-tests` / `integration-tests` red:** standard quality-bar failures;
  fix the offending lint / test. No runbook gate procedure (not Gate-class).

---

## Notes / gotchas

- **Scaffold-phase guards** appear in `lint` (mypy + Node steps), `unit-tests`
  (`--cov-fail-under=0` override), `eprocess-unit`, and `integration-tests`. Each skips
  cleanly with a visible message until its source/tests land, then auto-enforces. This
  is the project pattern (no `|| true` masks — `DOC-CMP-CI-01 §7.2`).
- **`main` runs are never cancelled** (concurrency `cancel-in-progress: false` on `main`).
- Gate 4 is currently **effectively non-enforcing** because `tests/falsifier/eprocess/`
  has no tests yet (`CMP-TRI-02` not implemented). This is expected and self-documenting,
  not a misconfiguration.

# falsifier-cw.yml — Gate 2 — Falsifier CW

**Workflow `name:`** `Gate 2 — Falsifier CW (nightly + pre-release)`
**File:** `.github/workflows/falsifier-cw.yml`

---

## Purpose

`falsifier-cw.yml` runs **Gate 2 — the Falsifier CW** (`CMP-SNAP-03`, anchor AC
`AC-SNAP-03a`). It asserts that `CW-DETECT` — the closed-world precondition detector and
INV-4 owner for Algorithm 1 — has **zero false negatives** on the curated reflection
corpus (Spring dynamic proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`,
PHP variable functions, Java `Class.forName`, plus mutation-injected reflection). A
single false negative — a reachable-reflection snippet wrongly passed as `closed-world` —
is an INV-4 violation and a **hard release blocker**.

---

## Triggers

```yaml
on:
  schedule:
    - cron: "0 2 * * *"        # nightly at 02:00 UTC
  push:
    tags: ["v[0-9]+.[0-9]+.[0-9]+-rc*", "v[0-9]+.[0-9]+.[0-9]+"]
  workflow_dispatch:
    inputs:
      env_digest:
        description: "Worker env_digest to test against (leave blank for latest)"
        required: false
```

- **`schedule`** — `0 2 * * *` decodes to **02:00 UTC every day**.
- **`push` tags** — release-candidate tags (`v*.*.*-rc*`) and final release tags
  (`v*.*.*`). This is the pre-release gate.
- **`workflow_dispatch`** — manual run with one optional input, `env_digest` (the worker
  `env_digest` to test against; blank = latest).

**Permissions:** `contents: read`, `checks: write`. **Env:** `PYTHON_VERSION: "3.11"`.
No `concurrency` block (scheduled/tag-driven; not subject to rapid supersession).

---

## Jobs & steps

### `falsifier-cw` — "Gate 2 — Falsifier CW — zero false negatives (AC-SNAP-03a)"  *(Gate 2)*

`runs-on: ubuntu-latest`. Steps:

1. `actions/checkout@v4`; `actions/setup-python@v5` (3.11, pip cache); deps via
   `pip install -e ".[dev]"`.
2. **"Check reflection corpus exists"** — **fails the job (`exit 1`)** if
   `tests/corpora/reflection/` is missing, and again if
   `tests/corpora/reflection/corpus.lock` is missing. Unlike the Attestor/canary
   corpus checks (which warn or skip), this gate **hard-requires** the corpus —
   `CMP-CORP-REFL-01` must be DONE first.
3. **"Run Falsifier CW — zero false negatives"** —
   `pytest tests/falsifier/cw/ -m falsifier -q --tb=long -v --junit-xml=falsifier-cw-results.xml`
   with `SCANIPY_ENV=test`.
4. **"Upload results"** — `actions/upload-artifact@v4` (`falsifier-cw-results`), `if: always()`.
5. **"Publish test results"** — `dorny/test-reporter@v1` (`reporter: java-junit`),
   `if: always()` — surfaces FN cases on the PR/check page.

---

## How it works

Nightly at 02:00 UTC and on every release(-candidate) tag, the job installs deps,
hard-asserts the versioned reflection corpus is present, then runs the falsifier suite.
Any false negative fails the gate; the test reporter publishes the failing cases. A
maintainer can also dispatch the workflow manually, optionally pinning a specific
`env_digest`.

---

## Gate / rule mapping

- **Gate 2 — Falsifier CW (`AC-SNAP-03a`)** → job `falsifier-cw`. Enforces **INV-4**
  (`CW-DETECT` safe direction: zero FN). Required status check
  (`Gate 2 — Falsifier CW — zero false negatives (AC-SNAP-03a)`); re-verified at
  release by `deploy.yml`'s `pre-deploy-checks`.

---

## Failure response

A red run means `CW-DETECT` produced a false negative — an INV-4 violation. Add the
missing reflection pattern to `CW-DETECT` (`CMP-SNAP-03`), with **Security Analyst
sign-off per RULE-9**; expand the corpus only after the fix lands; **do not relax the
gate**. A `CW-DETECT` version bump should re-trigger Gate 3 (`attestor.yml`) on the next
paths-touched event. Full procedure: `DOC-RUNBOOK §8.2`.

---

## Notes / gotchas

- **Hard-fails (not skips) when the corpus is absent.** This is deliberate and differs
  from `attestor.yml`/`canary.yml`, which skip cleanly. Until `CMP-CORP-REFL-01` is DONE
  and `tests/corpora/reflection/corpus.lock` is committed, **this gate is expected-red**
  (Phase 2 corpus work). Treat reds as "corpus not yet built", not as a CW-DETECT
  regression, until the corpus lands.
- Scheduled at **02:00 UTC**, intentionally one hour before `canary.yml` (03:30 UTC),
  whose comment notes it runs "after falsifier-cw completes".
- The `env_digest` dispatch input is currently informational to the suite (it is exposed
  as a `workflow_dispatch` input; the test harness consuming it is part of `CMP-SNAP-03`
  implementation, not yet present).

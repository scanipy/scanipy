# stage-gate.yml — Stage Gate — CPG-fidelity evaluation

**Workflow `name:`** `Stage Gate — CPG-fidelity evaluation`
**File:** `.github/workflows/stage-gate.yml`

---

## Purpose

`stage-gate.yml` is the harness for the **CPG-fidelity gate (`CMP-CP-06`)**. It evaluates
whether a given `(language, stage)` pair clears the per-language CPG-fidelity thresholds
on its curated fidelity corpus (`CMP-CORP-CPG-{lang}`). This is the gate that RULE-7
references: **no `(class, language)` pair may enter Algorithm 2 benchmarking until
`CMP-CP-06` is green for that language** (`.claude/rules/04-staging.md`,
`CLAUDE.md §7`, INV-6). A failing language is reported as `front-end-blocked`, never as a
recall failure (INV-6).

---

## Triggers

```yaml
on:
  workflow_dispatch:
    inputs:
      language:  { description: "...(java|python|js|go|ruby|php)", required: true, type: choice, options: [...] }
      stage:     { description: "...(A|B|C|D)",                     required: true, type: choice, options: [A, B, C, D] }
      corpus_version: { description: "Corpus version hash (from corpus.lock)", required: true }
```

- **`workflow_dispatch` only** — this is the **only dispatch-only workflow** and the
  **only one with required inputs**. There is no push / PR / schedule trigger.
- Three **required** inputs: `language` (choice of `java|python|js|go|ruby|php`),
  `stage` (choice `A|B|C|D`), and `corpus_version` (the corpus.lock hash, free text).

**Permissions:** `contents: write`, `checks: write` (note: `contents: write`, broader
than the read-only gate workflows). **Env:** `PYTHON_VERSION: "3.11"`. No `concurrency`.

---

## Jobs & steps

### `cpg-fidelity` — "CPG-fidelity gate — ${{ inputs.language }} (Stage ${{ inputs.stage }})"

`runs-on: ubuntu-latest`. Steps:

1. `actions/checkout@v4`; `actions/setup-python@v5` (3.11, pip cache); deps via
   `pip install -e ".[dev]"`.
2. **"Verify corpus readiness"** — **fails (`exit 1`)** if
   `tests/corpora/cpg_fidelity/<language>/` does not exist (`CMP-CORP-CPG-<language>`
   must be DONE) or if its `corpus.lock` is missing.
3. **"Run CPG-fidelity benchmark"** —
   `pytest tests/ -m "empirical" -k "cpg_fidelity and <language>" … --junit-xml=stage-gate-<language>-results.xml`,
   with env `SCANIPY_ENV=test`, `STAGE_GATE_LANGUAGE`, `STAGE_GATE_CORPUS_VERSION`.
4. **"Evaluate thresholds and write verdict"** — an inline Python heredoc reads
   `tests/results/cpg_fidelity/<language>/latest.json` and checks four thresholds:

   | Metric | Threshold |
   |---|---|
   | `parse_success_rate` | ≥ 0.995 |
   | `call_edge_precision` | ≥ 0.90 |
   | `call_edge_recall` | ≥ 0.85 |
   | `pdg_recall` | ≥ 0.80 |

   It prints `PASS`/`FAIL` per metric and exits `1` with `GATE-FAIL: …` if any metric is
   below threshold, else prints `GATE-PASS: all thresholds met for <lang>`. (A missing
   results file also `exit 1`s.)
5. **"Upload verdict"** — `actions/upload-artifact@v4`
   (`stage-gate-<language>-verdict`), `if: always()`.

---

## How it works

A stage-gate operator dispatches the workflow for a specific `(language, stage,
corpus_version)`. The job hard-requires the language's fidelity corpus, runs the fidelity
benchmark, then a Python step compares the recorded metrics against the four thresholds
and emits a `GATE-PASS` / `GATE-FAIL` verdict (also uploaded as an artifact). A pass is
the prerequisite for promoting that language into Algorithm 2 benchmarking for its stage.

The thresholds in this workflow (precision ≥ 0.90, recall ≥ 0.85, PDG ≥ 0.80) are the
concrete numbers; `.claude/rules/04-staging.md` lists parse ≥ 99.5% and defers the
edge/PDG thresholds to `CLAR-CORP-02 per language` (see Notes).

---

## Gate / rule mapping

- Enforces **RULE-7** (staging gate) and **INV-6** (per-language honesty) via
  **`CMP-CP-06`**. It is **not** one of the four named CI gates (Gate 1–4); it is the
  staging gate harness. A `STAGE-GATED` component is waiting on this gate, not on a
  dependency (`.claude/rules/04-staging.md §"What STAGE-GATED means"`).

---

## Failure response

A `GATE-FAIL` verdict means the language's CPG front-end did not clear fidelity
thresholds; the language is reported **`front-end-blocked`** (INV-6), and its
`(class, language)` pairs may **not** enter Algorithm 2 benchmarking. The fix is
front-end investment (e.g. `T-STAGE-C-FE-01` for Go points-to, `T-STAGE-D-FE-01` for
Ruby/PHP front-end maturity — filed as `CLAR-FE-02` / `CLAR-FE-01`), not relaxing the
gate. There is no dedicated `DOC-RUNBOOK §8` entry (that section covers the four named CI
gates); staging procedure lives in `.claude/rules/04-staging.md` and the `/stage-gate`
agent briefing.

---

## Notes / gotchas

- **Dispatch-only with required inputs.** It cannot fire automatically; an operator must
  supply `language`, `stage`, and `corpus_version`. There is no scheduled or PR run.
- **Threshold source-of-truth nuance.** The workflow hard-codes call-edge precision 0.90 /
  recall 0.85 / PDG 0.80. `.claude/rules/04-staging.md` states parse ≥ 99.5% but defers
  the other three to `CLAR-CORP-02 per language`. If `CLAR-CORP-02` resolves to
  per-language values different from these constants, the workflow constants would need a
  follow-up (this is a potential future divergence, flagged — not fixed here).
- **Expected to fail today** for any language: the per-language fidelity corpora
  (`CMP-CORP-CPG-*`) and the results JSON are Phase 2+ work and do not exist yet, so
  step 2 (corpus readiness) or step 4 (missing `latest.json`) will `exit 1`. This is
  expected-pending-inputs.
- `contents: write` is broader than the read-only gate workflows; the YAML does not
  show a step that writes to the repo, so the elevated permission is currently unused by
  the visible steps (documented as-is, not inferred away).

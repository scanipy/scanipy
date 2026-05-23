# DOC-CMP-CI-01 — Continuous-integration gate pipeline

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CI-01` — Purpose, T-CMP-CI-01-01..05 verbatim
- `WBS.md §2.4 CMP-DEPLOY-04` — `AC-DEPLOY-04b` ("The CI gates in `CMP-CI-01` are enforced as hard pipeline failures, not advisory checks")
- `SDD.md §12` — "AC-DET-01a, AC-SNAP-03a, AC-CP-05c, and AC-TRI-02b are continuous gates"
- `SDD.md §3 CMP-DET-01` — `AC-DET-01a` verbatim
- `SDD.md §4 CMP-SNAP-03` — `AC-SNAP-03a` verbatim
- `SDD.md §9 CMP-TRI-02` — `AC-TRI-02b` verbatim
- `SDD.md §10 CMP-CP-05` — `AC-CP-05c` verbatim
- `CLAUDE.md §15` — the four named gates table
- `docs/cross-cutting/DOC-RUNBOOK.md §8` — gate failure response procedures
- `docs/cross-cutting/DOC-INV.md §INV-1, §INV-3, §INV-4` — invariants enforced by the gates
- `.github/workflows/ci.yml`, `attestor.yml`, `falsifier-cw.yml` — concrete workflow files
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md`

This document is the **implementation contract** for `CMP-CI-01`. It catalogues the four named gates and binds them to the existing workflow files. It introduces **no fifth gate**; the gate set is exactly the four enumerated in `CLAUDE.md §15` and `SDD.md §12`.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CI-01` |
| Subsystem | Cross-cutting CI pipeline (`WBS.md §16`) |
| Staging | cross-cutting — lit up in Stage A; extended per stage (`WBS.md §16`) |
| Depends-On | `CMP-DEPLOY-04` (CI/CD pipeline scaffolding) (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`. SRE owns infrastructure; per-gate owners listed in `DOC-RUNBOOK §8`. |
| INV-* enforced | **INV-1** (Gate 3 — Attestor), **INV-3** (Gate 4 — e-process martingale; e-process keeps LLM off the detection path), **INV-4** (Gate 1 — DSL distributivity; Gate 2 — Falsifier CW). |
| Failure semantics | Gates 1, 2, 3 — **hard release blockers**. Gate 4 — **blocks customer-enablement deploy only**, not baseline release (`DOC-RUNBOOK §8.4`). |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CI-01`):**

> Enforce the four named gates as continuous, hard-failing CI gates rather than periodic checks. Wire them so a failure of any one fails the pipeline.

**Operational role.** `CMP-CI-01` is the pipeline that wires the four gates named in `SDD.md §12` to GitHub Actions and to branch protection on `main`. The component does NOT define new acceptance criteria; it inherits the AC of each underlying gate (`AC-DET-01a`, `AC-SNAP-03a`, `AC-CP-05c`, `AC-TRI-02b`). Its job is mechanism: that each gate runs at the right trigger, with the right failure semantics, and is enforced as a required status check on `main`. `AC-DEPLOY-04b` is the meta-AC ("enforced as hard pipeline failures, not advisory checks") that this component discharges operationally.

This component does **not** invent additional gates. The lint/typecheck/secret-detection jobs in `ci.yml` are pre-existing developer-experience checks, not Gate-class checks. The four named gates and only the four are tracked here.

---

## 3. Interface contract

`CMP-CI-01` is realized as a set of GitHub Actions workflows. The contract is the wiring of gates to triggers, owners, and branch-protection rules.

### 3.1 The four named gates (from `CLAUDE.md §15`)

| Gate | Anchor AC | Workflow file | Job name | Trigger | Failure semantics |
|---|---|---|---|---|---|
| **Gate 1 — DSL proofs** | `AC-DET-01a` | `.github/workflows/ci.yml` | `dsl-proofs` | every PR + every push to `main` | **Hard release blocker** — branch-protection required check |
| **Gate 2 — Falsifier CW** | `AC-SNAP-03a` | `.github/workflows/falsifier-cw.yml` | `falsifier-cw` | nightly cron (`0 2 * * *`) + pre-release tags `v*.*.*-rc*` and `v*.*.*` + `workflow_dispatch` | **Hard release blocker** — a single FN fails the release |
| **Gate 3 — Attestor** | `AC-CP-05c` (anchor: `AC-CP-05a`, `AC-CP-05c`) | `.github/workflows/attestor.yml` | `attestor-core` | push to `main` paths-touched in `detectors/**`, `analysis/**`, `workers/**`, `services/scan/**`, `services/snapshot/**`; same for PR | **Hard release blocker** on every detector / engine / `Env` change |
| **Gate 4 — e-process martingale** | `AC-TRI-02b` | `.github/workflows/ci.yml` | `eprocess-unit` | every PR + every push to `main` | **Blocks customer-enablement deploy only**, not baseline release (`DOC-RUNBOOK §8.4`) |

### 3.2 Pre-gate developer-experience checks (NOT Gate-class)

`ci.yml` also runs `lint`, `unit-tests`, and (when source exists) `integration-tests`. These are not Gate 1–4 and do not appear in the named-gates table; they are first-pass quality bars. Secret detection runs in the `pre-commit` framework (`.pre-commit-config.yaml`) — that is a separate pre-commit hook, not a CI gate of `CMP-CI-01`.

### 3.3 Branch protection on `main`

The four Gate jobs are configured as **required status checks** on `main`. The exact required-check names map verbatim to the job `name:` fields above (so the `Gate N — ...` prefix is preserved in the GitHub Checks API). This wiring is part of `CMP-DEPLOY-04`'s deployment job; `CMP-CI-01` is responsible for ensuring the job names remain stable so the branch protection does not drift.

> **Subject to `CLAR-DEPLOY-17` (WBS §17).** Server-side required-status-checks are **not currently available** on this repository (GitHub Free/private; `gh api .../branches/main/protection` returns 403). Until `CLAR-DEPLOY-17` resolves (upgrade plan / make public vs keep shims), gate enforcement is **process-level**: the `enforce-pr-only-merges.yml` shim + the RULE-10 doctrine stand in for native required checks. The required-check wiring described here is the target state once protection is available.

### 3.4 Verbatim ACs anchored by each gate

| Gate | Verbatim anchor (from SDD.md) |
|---|---|
| Gate 1 | > **AC-DET-01a:** Each combinator carries a machine-checked distributivity proof obligation (`f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the bounded domain); CI fails if a combinator lacks a discharged obligation. |
| Gate 2 | > **AC-SNAP-03a:** **[Falsifier CW]** Zero false negatives on the curated reflection corpus (Spring dynamic proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection). A single false negative is a release blocker. |
| Gate 3 | > **AC-CP-05c:** CI runs both pipelines on the canary corpus on every detector / engine / `Env` change. |
| Gate 4 | > **AC-TRI-02b:** The e-process implementation passes a martingale-property unit test (empirical `E[E_τ|H0] ≤ 1` across simulated stopping times) before production enablement. |

Paraphrasing these is a contract break (RULE-4); they are quoted verbatim above.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Source tree at HEAD | PR or push | Standard `actions/checkout@v4`. |
| Pinned worker image digest | `CMP-DEPLOY-02` (Gate 3 path) | Gate 3 must run under the pinned image; `LLM_TRIAGE=off` is set explicitly in `attestor.yml`. |
| Reflection corpus (Gate 2) | `CMP-CORP-REFL-01` | `tests/corpora/reflection/corpus.lock` MUST exist; `falsifier-cw.yml` exits early if missing. |
| Canary corpus (Gate 3 determinism sub-job) | `CMP-CORP-CANARY-01` | `tests/corpora/canary/corpus.lock` presence checked at runtime; sub-job skipped if missing (scaffold-phase guard). |
| DSL test file | `tests/unit/test_dsl_proofs.py` (Gate 1) | Owned by `CMP-DET-01`. |
| e-process tests | `tests/falsifier/eprocess/` (Gate 4) | Owned by `CMP-TRI-02`. |

### 4.2 Outputs

| Output | Consumer | Contract |
|---|---|---|
| GitHub Checks status per gate | branch protection on `main` | Required check; failure blocks merge. |
| JUnit XML (`falsifier-cw-results.xml`, `attestor-results.xml`) | `actions/upload-artifact@v4` | Retained as workflow artifacts for incident audit. |
| Test reporter publication | `dorny/test-reporter@v1` (Gate 2) | Surface FN cases on the PR check page. |

No provenance fields are written by `CMP-CI-01` itself. The gates verify provenance-bearing artifacts produced upstream; the gates themselves do not emit findings.

---

## 5. Invariants touched

| Invariant | How `CMP-CI-01` enforces it | Test |
|---|---|---|
| **INV-1** | Gate 3 (Attestor) asserts byte-identical SARIF over `origin=deterministic-core` findings. A finding emitted without correct `origin` would fail INV-1 schema NOT NULL upstream; Gate 3 verifies the partition is honoured operationally. | `TST-AC-CP-05c [FORTHCOMING]`, `TST-INV-1-*` (per emitter) |
| **INV-3** | Gate 4 (e-process martingale) is the load-bearing test that the spec gate doesn't drift to accept overbroad specs under repeated optional stopping. Without Gate 4, an e-process used in production invalidates INV-3's "version-pinned spec" guarantee (R-3 mitigation per `SDD.md §13`). Gate 3 additionally runs under `LLM_TRIAGE=off`. | `TST-AC-TRI-02b [FORTHCOMING]`, `TST-INV-3-CP-05 [FORTHCOMING]` |
| **INV-4 (DSL closure)** | Gate 1 (DSL proofs) is the operational discharge of the DSL distributivity precondition (the "safe direction" of Algorithm 2's owner DSL). A combinator without a discharged proof fails the gate. | `TST-AC-DET-01a [FORTHCOMING]`, `TST-INV-4-DET-01 [FORTHCOMING]` |
| **INV-4 (CW-DETECT)** | Gate 2 (Falsifier CW) is the load-bearing test that `CW-DETECT` has zero false negatives — the required safe direction for INV-4's owner of Algorithm 1's precondition. | `TST-AC-SNAP-03a [FORTHCOMING]`, `TST-INV-4-SNAP-03 [FORTHCOMING]` |

---

## 6. Dependency contract

`Depends-On: CMP-DEPLOY-04` (`WBS.md §20`) — the CI/CD pipeline must exist before the gates can be wired into it. `CMP-DEPLOY-04` owns:

- The GitHub Actions runner pool and OIDC-to-AWS trust.
- The branch-protection automation that translates "required status check" into a merge block.
- The release-tag workflows (used as Gate 2 triggers).

Per-gate corpus dependencies are *content* dependencies, not WBS-DAG dependencies — the gates are wired by `CMP-CI-01` *before* the corpora ship, with scaffold-phase guards that skip with a visible message until the corpus lock files land. This pattern is already in `falsifier-cw.yml` (reflection corpus check) and `attestor.yml` (canary corpus check).

---

## 7. Failure modes and error contracts

Failure response per gate is owned by `DOC-RUNBOOK §8`. Summary:

| Gate failure | Severity | Action (DOC-RUNBOOK §8.N) | Re-attestation required? |
|---|---|---|---|
| Gate 1 (DSL proofs) | Hard PR block | §8.1 — author the missing proof in `analysis/ifds/dsl/`; do not relax the gate. | No (gate is local to the DSL) |
| Gate 2 (Falsifier CW) | Hard release block | §8.2 — Add the missing reflection pattern to `CW-DETECT` (per `RULE-9` Security Analyst review); expand the corpus only after the fix lands; do not relax the gate. | No, but a CW-DETECT version bump → re-run Gate 3 on next paths-touched event |
| Gate 3 (Attestor core) | Hard release block + deploy block | §8.3 — Follow §7 (Attestation incident). Block deploy. Architect owns root-cause investigation. | Yes — full re-attestation per `DOC-RUNBOOK §4.3` |
| Gate 4 (e-process martingale) | Blocks customer-enablement deploy only | §8.4 — Triage the e-process implementation (per `RULE-9` Security Analyst review); do not enable triage / spec inference in production until the gate is green again. The baseline release path is unaffected. | No — this gate guards a separate deploy track |

### 7.1 What `CMP-CI-01` MUST NOT do

- Introduce a fifth Gate-class check without an SDD-level AC. (`SDD.md §12` names exactly four.)
- Promote a developer-experience job (lint, mypy, ruff, secret detection) to Gate-class status — those are not in `SDD.md §12`.
- Relax a gate (skip on flake, downgrade to advisory, etc.). `AC-DEPLOY-04b` forbids advisory enforcement.
- Bypass branch protection for any user, including admins, for the four Gate-class checks.

### 7.2 Pipeline anti-patterns rejected

- `if: always()` on a Gate-class step (would let a failed gate report success).
- `|| true` masking of a Gate-class command. No silent fallbacks in CI; `AC-DEPLOY-04b` forbids advisory enforcement, which a `|| true` mask would simulate.
- Cancelling a Gate-class run on `main` mid-stream (`ci.yml` and `attestor.yml` both keep `cancel-in-progress: false` on `main` for exactly this reason — see the inline comments).

---

## 8. Provenance threading

`CMP-CI-01` does **not** write to the `findings` table or emit SARIF. It is the *enforcer* of provenance-bearing tests run upstream. It writes:

| Field | Where | Threading rule |
|---|---|---|
| GitHub Checks status per Gate | GitHub Checks API | Failure surfaced as a required-status-check block on `main`. |
| JUnit XML artifact | workflow `actions/upload-artifact@v4` | Retained per artifact-retention policy; used for incident audit. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, finding-level rows. The gate verifies them; it does not produce them.

---

## 9. Acceptance criteria cross-reference

`CMP-CI-01` does not own its own AC family. The component's AC-equivalent is `AC-DEPLOY-04b` from `WBS.md §2.4` plus the four gate ACs inherited verbatim from upstream components.

| AC | Verbatim source | Test artifact |
|---|---|---|
| **AC-DEPLOY-04b** | `WBS.md §2.4`: > The CI gates in `CMP-CI-01` are enforced as hard pipeline failures, not advisory checks. | `TST-AC-DEPLOY-04b [FORTHCOMING]` — branch-protection audit test: assert each of the four Gate job names is a required check on `main`; assert no `|| true` / `if: always()` masks on Gate-class steps. |
| **AC-DET-01a** (Gate 1) | `SDD.md §3 CMP-DET-01` (verbatim §3.4) | `TST-AC-DET-01a [FORTHCOMING]` — wired in `ci.yml` job `dsl-proofs`. |
| **AC-SNAP-03a** (Gate 2) | `SDD.md §4 CMP-SNAP-03` (verbatim §3.4) | `TST-AC-SNAP-03a [FORTHCOMING]` — wired in `falsifier-cw.yml`. |
| **AC-CP-05c** (Gate 3) | `SDD.md §10 CMP-CP-05` (verbatim §3.4) | `TST-AC-CP-05c [FORTHCOMING]` — wired in `attestor.yml`. |
| **AC-TRI-02b** (Gate 4) | `SDD.md §9 CMP-TRI-02` (verbatim §3.4) | `TST-AC-TRI-02b [FORTHCOMING]` — wired in `ci.yml` job `eprocess-unit`. |

Per-task tests for `T-CMP-CI-01-01..05`:

| Task | Verification |
|---|---|
| `T-CMP-CI-01-01` | Gate 1 is a required check; `ci.yml/dsl-proofs` runs on every PR. |
| `T-CMP-CI-01-02` | Gate 2 is a required check on release tags; `falsifier-cw.yml` runs on `v*.*.*-rc*` and `v*.*.*`. |
| `T-CMP-CI-01-03` | Gate 3 is a required check on every detector / engine / `Env` change (paths-touched filter in `attestor.yml`). |
| `T-CMP-CI-01-04` | Gate 4 is wired in `ci.yml/eprocess-unit`; deploy stage `customer-enablement` checks Gate 4 status before promoting. |
| `T-CMP-CI-01-05` | `DOC-RUNBOOK §8` exists and covers each gate (DONE — see `docs/cross-cutting/DOC-RUNBOOK.md §8.1–8.4`). |

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CI-01 |
|---|---|---|---|
| `CLAR-SARIF-01` | Public hosting URL for the Scanipy SARIF extension JSON Schema | **DEFERRED** | Lists CMP-CI-01 as blocked for the "SARIF schema-validation gate", but that validation gate is NOT one of the four named gates today. The schema-validation check would be a *new* gate addition under a future SDD AC; until that AC exists, this CLAR is upstream of a future SDD change, not of `CMP-CI-01`'s current scope. **No action in this doc.** |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED; per-gate owners in `DOC-RUNBOOK §8`. |

No new CLAR-CI-* are filed by this document. The four-gate scope is fixed by `CLAUDE.md §15` + `SDD.md §12` and is not extensible without an SDD-level AC.

---

## 11. References

- `WBS.md §16 CMP-CI-01` — verbatim Purpose + tasks.
- `WBS.md §2.4 CMP-DEPLOY-04` — `AC-DEPLOY-04b`.
- `SDD.md §12` — "AC-DET-01a, AC-SNAP-03a, AC-CP-05c, and AC-TRI-02b are continuous gates".
- `SDD.md §3 CMP-DET-01` — `AC-DET-01a` verbatim.
- `SDD.md §4 CMP-SNAP-03` — `AC-SNAP-03a` verbatim.
- `SDD.md §9 CMP-TRI-02` — `AC-TRI-02b` verbatim.
- `SDD.md §10 CMP-CP-05` — `AC-CP-05c` verbatim.
- `CLAUDE.md §15` — the canonical four-gate table.
- `docs/cross-cutting/DOC-RUNBOOK.md §8` — per-gate failure response procedures.
- `docs/cross-cutting/DOC-INV.md §INV-1, §INV-3, §INV-4` — invariants enforced.
- `.github/workflows/ci.yml` — Gates 1 + 4.
- `.github/workflows/attestor.yml` — Gate 3.
- `.github/workflows/falsifier-cw.yml` — Gate 2.
- `.claude/rules/00-global.md §RULE-10` — code review approval required before merge.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an Implementation Agent (SRE role) to maintain `CMP-CI-01`. The four named gates are exhaustive; no fifth gate is added without an upstream SDD AC.*

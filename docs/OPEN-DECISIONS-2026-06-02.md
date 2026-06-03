# Scanipy v3.2 — Open Decisions Requiring Team Input

**Prepared:** 2026-06-02 · **Source of truth:** `WBS.md §17` (CLARIFICATION-NEEDED register)
**Status of the register:** 72 total decisions — **30 resolved**, **42 still open** (31 `OPEN` + 11 `DEFERRED`).

This document lists every decision that is still **waiting on a human** before the dependent
engineering work can proceed. Nothing here can be decided by an automated agent: each one needs an
empirical baseline, money/legal sign-off, a specialist's judgement, or information that lives outside
this repository.

---

## How to read this

- **"Blocks"** = the work that cannot finish until this is decided.
- **"Provisional"** = a sensible default already written into the spec. For these, the team only has
  to **ratify** (accept) or **override**. Items with no provisional are genuinely open.
- **"Owner"** = the role best placed to decide. Many will collapse onto one or two people.
- **Priority** is about *leverage* — how much downstream work each decision unblocks — not urgency.

> **The single most important decision is `κ` (Part 1).** It is the cork in the bottle: until it is
> picked, the entire core analysis engine cannot be built or benchmarked. Everything else can wait;
> this one is on the critical path.

---

## Part 1 — THE critical-path blocker: pick `κ` first

| | |
|---|---|
| **Decision ID** | `CLAR-PARAM-01` (κ portion) + `CLAR-PARAM-02` (the related π₀) |
| **Plain-English ask** | What numeric **regression threshold `κ`** does each detector use in the incremental snapshot algorithm? The spec confirmed every *other* tuning constant (θ_cone=0.25, θ_files=0.4, budget B=2¹⁶ nodes / T=200 ms) but left **κ as "TBD by the detector at registration."** |
| **Why it matters** | κ is the gate on **Algorithm 1** (incremental re-analysis, `CMP-SNAP-02`). With κ unset, `CMP-SNAP-02` cannot be finalised — and SNAP-02 sits at the head of the core chain. |
| **Blocks (the whole core engine)** | `CMP-SNAP-02 → CMP-CORE-01 (IFDS/IDE solver) → CMP-CORE-02 (fingerprint) → CMP-FND-01 (normalizer) → CMP-ORCH-03 (worker)`, and through them `CMP-CP-05` (attestor), `CMP-CI-01`, `CMP-RES-01`. This is roughly **half of the remaining buildable system.** |
| **Why an agent can't decide it** | κ is meant to be calibrated **per detector class** against a real performance/precision baseline that does not exist yet (planned for "Phase 5"). Guessing a number would violate RULE-4 (no invented scope) and could silently weaken a soundness threshold. |
| **What the team must produce** | Either (a) a per-detector-class κ value with the data/justification behind it, **or** (b) an explicit decision that κ is calibrated empirically during a named phase, with an interim value for development. The same applies to **π₀** (the per-class precision floor for the spec-acceptance gate, `CLAR-PARAM-02`) — α=0.05 is already fixed; only π₀ needs a baseline. |
| **Recommendation** | Treat κ and π₀ as one short "Algorithm-parameter calibration" work item: schedule the baseline measurement, set interim development values now so the core chain can be *built and tested* (even if not yet *certified*), and pin the real numbers at Stage-A go-live. |

---

## Part 2 — Decisions grouped by who should make them

### A. Architect / CTO — algorithm shape & scope (decidable now, no external data needed)

These need a design ruling, not money or measurement. Most already have a provisional to ratify.

| ID | The decision | Blocks | Provisional / recommendation |
|---|---|---|---|
| `CLAR-DET-01` | Add a first-class `detectors` SQL table, or keep detectors as on-disk YAML + in-memory registry? | CMP-DET-02, CMP-CP-03 | **Provisional:** on-disk YAML + in-memory registry; persist accepted specs via `spec_versions`. Ratify or upgrade to a table. |
| `CLAR-DET-02` | Must the registry re-run the *full* distributivity-closure check, or is the narrower shape check enough (relying on registration-time check)? | CMP-DET-02, CMP-CORE-01 | **Provisional:** narrower shape check accepted as defense-in-depth. Ratify. |
| `CLAR-CP-01-01` | Is the API guard `CMP-CP-01` an "INV-2 emitter" needing its own test, or is that obligation discharged downstream? | CMP-CP-01 test scope | **Provisional:** CP-01 is a non-emitting routing guard (INV-2 N/A here). Ratify. |
| `CLAR-SNAP-02` | Two specs disagree on the `snapshots` table shape (an async state-machine in one doc vs the simpler shipped schema). Which is canonical? | CMP-SNAP-01 status surface; **CMP-SNAP-05** | **Provisional:** ship to the simpler shipped schema; defer the state-machine to SNAP-05. Needs an architect ruling before SNAP-05 — tied to unbuilt SNAP-05, so not yet urgent. |
| `CLAR-CP-06-01` | Persist CPG-fidelity verdicts to a DB table (for dashboards/trends), or keep JSON-only? | CMP-CP-06; dashboard view | No provisional — product/architect call. JSON satisfies the test literally. |
| `CLAR-API-01` | Align two API URLs under a single `/api/v1/` prefix? | None (cosmetic; SDD paths are normative until changed) | **Provisional:** SDD paths stand; revisit pre-GA. Low priority. |

### B. CTO / Business — money, licensing, vendor (cannot be decided by engineering)

| ID | The decision | Blocks | Note |
|---|---|---|---|
| `CLAR-FE-01` | Ruby/PHP front-end (Stage D): **build, buy, or delay** the proprietary parser work? | Stage D (Ruby+PHP move from oracle to core) | Pure business/budget call. Until decided, Ruby/PHP stay oracle-passthrough (already the honest default). |
| `CLAR-FE-02` | Go front-end (Stage C): scope of the points-to / interface-dispatch investment? | Stage C (Go core) | **Provisional:** Andersen-style baseline if approved. Needs scoping + budget. |
| `CLAR-CORP-18` | OWASP BenchmarkJava is **GPL-2.0**, off the corpus license allow-list. Grant CTO approval to vendor it, or keep fetch-on-demand? | CMP-CORP-VULN-01; downstream recall benchmark | Legal/license sign-off. **Provisional:** fetch-on-demand (no GPL vendored) until ruled. |
| `CLAR-DEPLOY-17` | Server-side branch protection is unavailable on this repo (GitHub Free). **Upgrade the plan / make repo public**, or keep the process-level "loud red check" shims? | CI gate enforcement | **Provisional:** keep the process shims (current state). CTO ratify before Stage-A. |
| `CLAR-DEPLOY-18` | Deliver the production infrastructure-as-code (`infra/` Terraform) as part of CMP-DEPLOY-01, or as the first task of CMP-DEPLOY-02? | CMP-DEPLOY-02..05; SNAP-05 | CTO already approved deferring it from DEPLOY-01; needs ratification before Phase 4 build-out. |

### C. SRE / DevOps — operational thresholds & infra ops

| ID | The decision | Blocks | Note |
|---|---|---|---|
| `CLAR-SLA-02` | Numeric per-tenant rate-limit budgets (API requests/min, LLM requests/day) | CMP-CP-01 enforcement defaults | Needs capacity-planning input. Proposed defaults exist in `DOC-API §7`. |
| `CLAR-CP-04-01` | On an Auth0 outage, allow degraded read-only mode, or stay fully fail-closed (503)? | CMP-CP-04 dashboard | **Provisional:** fail-closed. Read-only mode would need careful token-revocation design + Security sign-off. |
| `CLAR-CP-05-01` | What numeric reproduction-rate triggers an alarm vs a release-notes flag for oracle findings? | CMP-CP-05 tuning | **Working assumption:** alarm < 99% (7-day), investigate < 95%. Confirm. |
| `CLAR-CP-05-02` | Does the attestor run on every push to `main`, or only on a path filter (risking missed base-image changes)? | CMP-CP-05 CI; CI-01 Gate 3 | SRE/CI ruling. |
| `CLAR-CP-06-02` | Hard-enforce that the fidelity-gate run uses the production worker image, or only record it? | CMP-CP-06 CI | **Provisional:** hard-enforce (fail-closed). Confirm. |
| `CLAR-DB-02` | Pin the PostgreSQL row-level-security session-variable scheme (`app.org_id` etc.) | CMP-CP-01, CMP-CP-03 | Needs **SRE + Security** sign-off. Scheme proposed in `DOC-DB §3.2`. |
| `CLAR-SARIF-01` | Public hosting URL for the SARIF extension JSON-Schema | CMP-CI-01 SARIF gate | Can be vendored locally until a URL is pinned. Pre-GA. |

### D. Security Analyst — required sign-offs (RULE-9)

| ID | The decision | Blocks | Note |
|---|---|---|---|
| `CLAR-CP-02-01` | KMS decrypt-failure handling: add fine-grained AWS error introspection + retry/backoff to match the documented 3-way taxonomy, or formally narrow the contract to the current fail-closed catch-all? | CMP-CP-02 | Current behaviour is fail-closed (Security-confirmed safe) but deviates from the doc. Needs a Security ruling: tighten code or narrow doc. |
| *(also: `CLAR-DB-02`, `CLAR-CP-04-01` above need Security as co-signer)* | | | |

### E. Corpus / Data — test-corpus sourcing campaigns (need budget + people, not a quick call)

These are the largest bucket. The pattern is the same across languages: the v0.1.0 corpora are honest
*scaffolds* that exercise the machinery but are **explicitly not** gate-strength. Reaching the real bar
needs **real open-source code sourced, license-screened, and dual-reviewed at scale** — a multi-PR
effort beyond any single automated run. Each needs a **sample-size target `N`** pinned and a
**sourcing budget** approved.

| ID | What's needed | Corpus |
|---|---|---|
| `CLAR-CORP-03` | A named **second reviewer** for the dual-review protocol | Reflection |
| `CLAR-CORP-04` | Scoring rule: do mutation-injected items count toward the hand-curated quota? | Reflection |
| `CLAR-CORP-05` | Budget for bulk-sourcing ~800 real OSS reflection samples | Reflection |
| `CLAR-CORP-06` | v1.0.0 generator must produce structurally-distinct items per seed | Reflection |
| `CLAR-CORP-17` | Distinct-topology target + real-repo sourcing | Refactor |
| `CLAR-CORP-19` | Budget to integrate full OWASP / Juliet / BigVul vuln corpora | Vuln |
| `CLAR-CORP-11` | Python ground-truth toolchain: provision pinned tools, or ratify the in-repo extractor? | CPG-Python |
| `CLAR-CORP-12` | JS/TS ground-truth: adopt Jelly 1.4 + tsc (pinned toolchain) | CPG-JS/TS |
| `CLAR-CORP-13` | Minimum program count `N` for a gate-strength JS/TS set | CPG-JS/TS |
| `CLAR-CORP-14` | Go corpus `N` + real-world sourced quota | CPG-Go |
| `CLAR-CORP-15` | Ruby corpus per-category `N` | CPG-Ruby |
| `CLAR-CORP-16` | PHP corpus `N` + framework distribution + PHP worker image digest | CPG-PHP |
| `CLAR-CORP-07` | Java ground-truth needs Soot/WALA toolchain provisioned | CPG-Java |
| `CLAR-CORP-08` | Confirm pinned JDK (17 vs available 21) for Java extraction | CPG-Java |
| `CLAR-CORP-09` | Java per-language `N` + real-repo sourcing campaign | CPG-Java |
| `CLAR-CORP-10` | Confirm the "≥10% generated-code" balance threshold | CPG-Java |

> **Practical note:** items E are what gate the **per-language go/no-go** (`CMP-CP-06`). Today every
> language is honestly reported as `front-end-blocked` (no false recall claims — INV-6). They unblock
> *language coverage*, not the core engine, so they rank **below κ** but are the long pole for shipping
> beyond Java+Python.

### F. Information that lives outside this repository (someone must locate it)

| ID | What's missing | Blocks |
|---|---|---|
| `CLAR-SCM-01` | Where is the **legacy v2 GitHub connector** that the regression test must match byte-for-byte? It is not in this repo. | CMP-SCM-02 |
| `CLAR-SCM-02` | Which HTTP **header carries the Azure DevOps webhook signature**? (An interim default is implemented and marked TODO.) | CMP-SCM-03 (ADO only) |
| `CLAR-MIGRATION-01` *(see defect note below)* | Where are the **legacy taint definitions (`tarslip.yaml`) and C/C++ CodeQL queries** that `CMP-DET-03` must migrate, and what defines the historical CVE-2025-61765 baseline? | CMP-DET-03 (also blocked on the unbuilt core chain) |
| `CLAR-MIGRATION-01` *(the other one)* | Is **v2→v3.2 data migration** (findings, memberships, credentials) in scope, or is this a new-environment-only launch? | CMP-CP-03 |

---

## Part 3 — Ownership (one decision unblocks tracking for everything)

| ID | The decision | Note |
|---|---|---|
| `CLAR-OWNER-01` | Assign a **named owner** to every component (`CMP-*`) and every risk mitigation (`R-*`). | Currently deferred. This is a team-seating exercise; once done it populates `docs/cross-cutting/DOC-OWNERS.md` and removes the "unassigned" ambiguity from many items above (e.g. the corpus second-reviewer). Recommend doing this early — it is cheap and clarifies who decides the rest. |

---

## Part 4 — Two register defects to fix (housekeeping, not decisions)

While compiling this I found two bookkeeping problems in `WBS.md §17` worth a quick cleanup pass
(I did **not** change them — flagging for your call):

1. **Duplicate ID `CLAR-MIGRATION-01`.** Two *different* questions carry the same ID (row ~931: v2
   data migration; row ~973: legacy detector-artifact location). One should be renumbered
   (e.g. the detector-artifact one → `CLAR-MIGRATION-02`) so they can be tracked separately. This is
   the same class of bug as the `CLAR-DB-02` collision already fixed this cycle.
2. **Stale status token on `CLAR-TRI-01`.** Its notes say *"resolved-with-PR-255"* (merged) but the
   status column still reads `OPEN`. It should flip to `RESOLVED`. Its decision (keep the float
   primitive; adjudication→outcome projection is the caller's job) is already in effect in the code.

Both are one-line edits a `/sync-wbs` or `/cto` pass can make; neither needs a team discussion.

---

## Part 5 — The one-page summary (for the meeting)

**Decide in this order:**

1. **κ (and π₀)** — `CLAR-PARAM-01/02`. Unblocks ~half the remaining system (the whole core engine).
   *Owner: Architect + whoever runs the Phase-5 baseline.* **← do this first.**
2. **The "ratify-the-provisional" batch** — the Part 2A architect items + the SRE fail-closed defaults
   (CP-04-01, CP-05-01/02, CP-06-02) + Security's CP-02-01. These are mostly "yes, accept the default"
   and can be cleared in one sitting. *Owner: Architect / SRE / Security in one review.*
3. **Money/legal** — `CLAR-FE-01/02` (Go/Ruby/PHP front-end build-vs-buy), `CLAR-CORP-18` (GPL
   license), `CLAR-DEPLOY-17/18` (GitHub plan + IaC). *Owner: CTO.*
4. **Corpus sourcing program** — the 16 `CLAR-CORP-*` items. Treat as one funded, multi-PR data
   campaign with a single owner. Gates language coverage beyond Java+Python. *Owner: Corpus lead + budget.*
5. **Find the legacy artifacts** — `CLAR-SCM-01/02`, the two `MIGRATION` items. *Owner: whoever has v2 access.*
6. **Assign owners** — `CLAR-OWNER-01`. Cheap; do it early so 1–5 have clear decision-makers.

**What is already safe and honest right now (no decision needed):**
- All deployment substrate choices are resolved (AWS stack pinned).
- Java+Python are the only languages claimed for the core path; every other language is honestly
  labelled `front-end-blocked` with no inflated recall numbers.
- The 5 schema/registry decisions just ratified this cycle (DB-01/03/04/05, DET-03).

---

*Generated for team discussion. Tell me which way each decision goes and I can record the rulings back
into `WBS.md §17` (and fix the two Part-4 defects) in one pass.*

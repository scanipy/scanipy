# STATUS — Management / CTO

**Owner:** CTO (+ Architect for the marked items) · **Updated by:** management, via PR · **Engineering contact:** orchestrating agent
**Baseline:** WBS §21 v3.2 DoD. **Audited 2026-06-04: 3 of 12 lines MET.** Target: 12/12.

---

## 1. THE FORK — one decision gates four §21 lines

§21-L10 ("every CLAR resolved **or explicitly deferred**") is internally satisfiable by deferral —
but the work deferred on 2026-06-03 (CLAR-CORP-05 bulk reflection sourcing, CLAR-CORP-19 vuln-corpus
scale) **plus** the unfunded CLAR-FE-03 scanner is exactly what lines **L3** (Stage-A ACs green),
**L4** (CP-05 byte-identical SARIF over canary), **L5** (SNAP-04 seeded-FN), and **L7** (Gates 2/3
real) require to certify. As currently decided, those lines are **uncertifiable as written**.

**Choose one (or a hybrid with explicit per-line scoping):**

- **Option A — Re-baseline:** amend the Stage-A empirical lines to what the seed corpora + built
  machinery support; document "full-scale recall/zero-FN measured post-MVP" as an explicit deferral
  with reasoning (keeps §21-L10 honest). Requires an Architect-signed amendment record (the §21 text
  itself lives in WBS.md — flag the orchestrator to draft it after the decision).
- **Option B — Fund:** un-defer CLAR-CORP-05 + CLAR-CORP-19, fund CLAR-FE-03 (independent
  reflection-oracle scanner), staff the corpus campaigns (`STATUS-CORPUS-TEAM.md`).

> **DECISION:** _____ (A / B / hybrid — if hybrid, list per-line scoping)
> **Owner:** _____ · **Date:** _____ · **Record:** _____ (link the decision memo / WBS §17 PR)

---

## 2. §21 scorecard tracker (12 lines)

Verdicts are the 2026-06-04 audit; engineering re-scores after every relevant merge.

| # | §21 line | Verdict 2026-06-04 | What flips it | Owner track | Status (fill) |
|---|---|---|---|---|---|
| L1 | Phase 0 — every CMP has DOC-CMP-* | **MET** | — | — | MET |
| L2 | Phase 1 — every AC has TST-AC-*, every INV has TST-INV-* | MET-as-artifacts | Stays met; stubs go green under L3 | Engineering | _____ |
| L3 | Stage A — every Stage-A CMP all ACs green (Java+Py) | UNMET | Waves 3–7 code (CORE-02, FND-01, ORCH-01/03, CP-05, CP-06) **+** corpora at gate-strength **+** Fork §1 | Engineering + Corpus + CTO | _____ |
| L4 | CP-05 — byte-identical core SARIF | UNMET (Gate 3 passes **vacuously** today) | FND-01 (Wave 3, in flight) → CP-05 build (Waves 4–5) + CANARY-01 corpus | Engineering + Corpus | _____ |
| L5 | SNAP-04 — re-partition on seeded CW-DETECT FN; SLA published | UNMET (mechanism merged; **detection scanner unbuilt**) | CLAR-FE-03 decision → scanner build + adversarial corpus + falsifier-cw PR trigger | CTO (fund) + Engineering | _____ |
| L6 | TRI-02 — adversarial + martingale tests | **MET** | — | — | MET |
| L7 | CI-01 — four gates as hard pipeline failures | PARTIAL (Gates 1+4 real; Gate 2 never runs on PR; Gate 3 vacuous) | Gate 2: REFL corpus + PR-trigger decision (§3-D). Gate 3: CP-05 + CANARY-01 | Engineering + Corpus + CTO | _____ |
| L8 | DEPLOY-01..05 — substrate, signed image, observability, isolation | PARTIAL (decisions recorded; **execution not started**) | `STATUS-AWS-TEAM.md` runbook, items 1–9 | AWS/SRE | _____ |
| L9 | Staging table AC-driven (not prose) | UNMET | CP-06 harness (Wave 6) + corpora verdicts + table publisher | Engineering + Corpus | _____ |
| L10 | CLAR register — all RESOLVED or explicitly deferred | UNMET (19 OPEN) | §3 decisions below | CTO/Architect | _____ |
| L11 | OOS register — no drift | **MET** | — | — | MET |
| L12 | Risks R-1..R-5 — DONE or LIVE-AS-POLICY | UNMET (R-3 done, R-5 policy; R-1/R-4 need SNAP-04+CP-05; R-2 needs CP-06) | Same dependencies as L4/L5 + CP-06 | All three tracks | _____ |

---

## 3. Decision register — OPEN items needing a management/architect signature

Engineering cannot proceed past these without a recorded decision (RULE-4/RULE-8). Options ordered
by the existing decision-doc analysis where one exists.

### A. CLAR-FE-03 — independent reflection-oracle scanner (blocks L5, L7-Gate-2-full, L12-R1/R4)
Separate-codebase scanner (higher-fidelity points-to, whole dependency closure) that *detects* CW-DETECT
false negatives. The merged `diff_oracle.py` is the re-partition mechanism only. A toy oracle is
INV-4-unsafe and already rejected.
Options: **(i)** fund the build now (M–L engineering after design); **(ii)** defer + re-baseline L5
(pairs with Fork Option A); **(iii)** interim third-party tool as oracle (needs Architect review for
the independence requirement, DOC-CMP-SNAP-04 §6.2).
> **DECISION:** _____ · **Owner:** _____ · **Date:** _____

### B. CLAR-PARAM-04 — κ well-posedness (blocks SNAP-02a economics gate; Stage-A go-live item)
Options per `docs/DECISION-PARAM-01-kappa-2026-06-03.md`: affine bound `+C₀` / delta-only
persistence fix / ratified corpus floor. *(Architect)*
> **DECISION:** _____ · **Owner:** _____ · **Date:** _____

### C. CLAR-CORE-01 — DOC-CMP-CORE-01 §3.1/§8 reconcile with shipped interfaces *(Architect)*
Code is authoritative in practice since PR #266/#268; the DOC text must be reconciled (or the
deviation ratified) so the register can close.
> **DECISION:** _____ · **Owner:** _____ · **Date:** _____

### D. Gate-2 on PRs — policy
`falsifier-cw.yml` runs nightly/tags only. §21-L7 says "continuously enforced as hard pipeline
failures." Decide: add a `pull_request` trigger once the REFL corpus is gate-strength (runtime cost
on every PR), or ratify nightly+release as satisfying "continuously enforced" (an L7 re-baseline).
> **DECISION:** _____ · **Owner:** _____ · **Date:** _____

### E. Corpus decisions (block `STATUS-CORPUS-TEAM.md` campaigns; itemized there)
| CLAR | Question | Decision | Owner | Date |
|---|---|---|---|---|
| CORP-03 | Second corpus reviewer — who? | _____ | _____ | _____ |
| CORP-04 | Mutation-vs-hand-curated scoring rule | _____ | _____ | _____ |
| CORP-05 | Bulk OSS reflection sourcing (currently DEFERRED — see Fork) | _____ | _____ | _____ |
| CORP-08 | Java ground-truth JDK pin (DOC says 17, sandbox is 21) | _____ | _____ | _____ |
| CORP-09 | Per-language corpus N + real-OSS SOURCED quota | _____ | _____ | _____ |
| CORP-10 | Generated-code balance ≥10% — confirm | _____ | _____ | _____ |
| CORP-11 | Python ground-truth toolchain (pin scalpel/Pyan3/Pyre **or** ratify in-repo extractor + amend DOC) | _____ | _____ | _____ |
| CORP-17 | REFAC corpus topology-diversity bar for v1.0.0 | _____ | _____ | _____ |
| CORP-19 | Vuln-corpus scale-up (currently DEFERRED — see Fork) | _____ | _____ | _____ |

### F. New since 2026-06-04 (Wave-3 filings)

| CLAR | Question | Decision | Owner | Date |
|---|---|---|---|---|
| DET-04 | Source/sink inventories for ssrf (java+py) + deserialization/python are absent from every DOC — supply the curated inventories, or descope those (class,language) pairs from Stage A | _____ | _____ | _____ |
| DEPLOY-19 | Pin `fastapi` (version) + schedule the CP-01 request-lifecycle adapter follow-up (the framework-agnostic seam is merged, #286) — RULE-8: CTO approval needed before the dependent ORCH-01 integration | _____ | _____ | _____ |
| PROC-01 | *(RESOLVED 2026-06-04 — recorded for visibility)* Build-ahead regime ratified by the project owner: hermetic-subset prep PRs sanctioned project-wide; component DONE stays RULE-2+RULE-3 gated | RESOLVED | Project owner | 2026-06-04 |

*(CLAR-PARAM-02 π₀ is Phase-8 customer-enablement, not an MVP blocker — listed for completeness only.)*

---

## 4. Engineering wave plan (for context — agent-executed, no action needed here)

Build-ahead regime: mechanisms built against typed interfaces with honest prep framing; final AC
certification waits on the corpus/AWS tracks above.

| Wave | Contents | State |
|---|---|---|
| 1–2 (2026-06-03) | CORE-01 PR1+PR2, CP-02/CP-03/DET-02/SCM fixes, SCM conformance, CLAR ratifications | **Merged** (#262–#271) |
| 3 (in flight) | FND-01 normalizer/SARIF · SNAP-05 worker · CP-01 session seam · CORE-01 PR3 (inter-proc witness + incremental fix) · DET-03 real Stage-A specs | Running |
| 4 | CORE-02 (Algorithm 3 slice fingerprint) · ORCH-03 worker | Planned |
| 5 | ORCH-01 scan API · CP-05 attestor mechanism | Planned |
| 6 | CP-06 harness · CI gate re-wiring · AC-driven staging table (L9) | Planned |
| 7 | Integration hardening, falsifier teeth, residuals | Planned |

**Not in the §21 MVP** (flag if the *sellable* MVP needs them): CP-04 dashboard/SSO (needs QA-authored
AC + CI JS/TS runner + `web/` scaffold), ORCH-02 scheduler, RES-01.

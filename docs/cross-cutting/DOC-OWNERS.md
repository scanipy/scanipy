# DOC-OWNERS — Scanipy v3.2 ownership map

> **Status:** RATIFIED 2026-06-03 — **role/agent-doctrine ownership** (`CLAR-OWNER-01` RESOLVED, role-based).
> **Decision record:** `docs/DECISION-PART3-ownership-2026-06-03.md` (Part 3).
> **Revisit when human teams are seated.** Named-individual assignment is out of agent scope
> (RULE-4 — no human-name source in the repo); supply names later by editing this one file.

This file is the canonical owner map referenced by `WBS.md §17 CLAR-OWNER-01`. It assigns ownership
by **agent-role** (the nine roles of `CLAUDE.md §10` + the `claude-review` CI check), not by named
person. Ownership is **multi-dimensional**: each component carries a *primary build-owner role* plus
standing cross-cutting owners plus a RULE-9 Security co-sign where it applies.

`Risk owned:` tags in `WBS.md` are **component→risk** mitigation attributions, **not** person
assignments — see `DECISION-PART3 §4`.

---

## 1. Standing cross-cutting owners (apply to every component)

- **Documentation Manager** — owns the `DOC-CMP-*` contract for every component (RULE-1).
- **QA** — owns every `TST-AC-*` / `TST-INV-*` (RULE-3).
- **`claude-review` CI check** — sole code-review owner gating every PR (RULE-10).
- **CTO** — owns every `CLAR-*` resolution and staging-gate decision (RULE-8).
- **Architect** — owns INV-1..6 design review on every component touching an invariant.

## 2. RULE-9 Security co-sign — the seven INV-3/INV-4 components (non-negotiable owner)

`CMP-CP-02`, `CMP-SNAP-03`, `CMP-SNAP-04`, `CMP-DET-01`, `CMP-TRI-01`, `CMP-TRI-02`, `CMP-TRI-03`.
These carry the Security Analyst in their owner set regardless of which role builds them.

---

## 3. Subsystem → owning role map (all 12 subsystems, `CLAUDE.md §5`)

| Subsystem | Components | Primary build-owner role | Mandatory co-owners (beyond the standing five) |
|---|---|---|---|
| SCM Integration | CMP-SCM-01/02/03/05 | Implementation | **+SEC** on SCM-03 webhook (CLAR-SCM-02) |
| Snapshotter | CMP-SNAP-01..05 | Implementation (SNAP-05: SRE+Impl) | **+SEC (RULE-9)** on SNAP-03, SNAP-04; Architect on SNAP-02 (κ well-posedness) |
| Detector Catalog | CMP-DET-01/02/03 | Implementation | **+SEC (RULE-9)** on DET-01; SEC co-sign on DET-02 binding condition |
| Analysis Core | CMP-CORE-01/02/03 | Implementation | **Architect** (Alg 2/3/5, INV-5/INV-6) |
| Orchestration | CMP-ORCH-01/02/03 | Implementation | — (ORCH-03 is the INV-1/INV-2 origin+provenance emitter) |
| Findings & Provenance | CMP-FND-01/02/03 | Implementation | SRE (FND-02 migration); SEC co-sign (FND-03 signing) |
| Triage & Spec Inference | CMP-TRI-01/02/03 | Implementation | **+SEC (RULE-9) on all three**; QA on TRI-02 martingale falsifier |
| Control Plane & Attestation | CMP-CP-01..06 | Implementation (CP-05: SRE+Impl) | **+SEC (RULE-9)** on CP-02; SEC co-sign CP-03/04; Architect on CP-06 (INV-6) |
| Deployment | CMP-DEPLOY-01..05 | **SRE/DevOps** | SEC co-sign on DEPLOY-05 (tenant isolation) |
| Corpora | CMP-CORP-REFL / CPG-{java,python,js,go,ruby,php} / CANARY / REFAC / VULN | **Corpus Curator** | QA (dual-review); CTO/legal on VULN GPL (CLAR-CORP-18) |
| CI gates | CMP-CI-01 | **SRE/DevOps** | — (the four named gates) |
| Research mode | CMP-RES-01 | Implementation | — |

## 4. Risk → mitigation-owner role map (`WBS.md §19`)

| R-* | Statement (abridged) | Mitigation-owner role(s) | Status |
|---|---|---|---|
| R-1 | CW-DETECT FN leaks a wrong `deterministic-core` label | Security Analyst ⊕ Implementation (SNAP-03/04) | mitigation in-flight (CMP-SNAP-04) |
| R-2 | Front-end fidelity dominates schedule | Architect ⊕ CTO (FE spend) | LIVE (CMP-CP-06; FE delayed — DECISION-PART2 Q1) |
| R-3 | Spec gate misused without martingale test | Security Analyst ⊕ QA | LIVE (TST-AC-TRI-02b hard gate, Gate-4) |
| R-4 | Determinism regression invisible to same-path re-run | SRE/DevOps ⊕ Implementation ⊕ Security | mitigation in-flight (CMP-SNAP-04 + CMP-CP-05) |
| R-5 | Detector-catalog chicken-and-egg | **CTO** (staging policy) | LIVE AS POLICY (`WBS.md` R-5) |

## 5. CLAR-CORP-03 — reflection second reviewer (DEFERRED)

Stays **DEFERRED** with the corpus sourcing campaign (DECISION-PART2 Q4). The second reviewer must be
**distinct from the corpus builder** (independence). Under this role map it is a **QA ⊕ Corpus-Curator**
pairing *pending a named person* — a single agent cannot honestly self-certify both sides, so it remains
DEFERRED until a name or a second independent reviewer is assigned.

---

*Role-based ownership; to be revisited when human teams are seated. To assign named individuals, add a
"Named owner" column / per-row names here and flip the relevant entries — no other file needs to change.*

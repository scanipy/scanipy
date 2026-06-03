# Decision Record — Part 3: Ownership (`CLAR-OWNER-01`)

**ID:** `DECISION-PART3` · **Prepared:** 2026-06-03 · **Author:** CTO analysis pass (governance/ownership), advisor-reviewed
**Resolves (the engineering/governance analysis behind):** `CLAR-OWNER-01` (`WBS.md:930`, status **DEFERRED**) — "assign a named owner to every component (`CMP-*`) and every risk mitigation (`R-*`)."
**Realizes:** `docs/OPEN-DECISIONS-2026-06-02.md` **Part 3** ("Ownership — one decision unblocks tracking for everything") and folds in **Part 2 §E / §8 Q4** (`CLAR-CORP-03`, routed here and DEFERRED with the corpus campaign).
**Companion to:** `docs/DECISION-PARAM-01-kappa-2026-06-03.md` (Part 1 — κ/π₀) and `docs/DECISION-PART2-2026-06-03.md` (Part 2 — groups A–F). Same governance posture.
**Status:** **RATIFIED 2026-06-03 — role-based ownership accepted (§6 Q1 → option 1, "Use built-in roles").** The §3–§5 role/agent-doctrine map is the v3.2 working owner assignment, to be revisited when human teams are seated. _Per the Part-2 §8 precedent, this answer is recorded here but **not** auto-written into source-of-truth:_ creating `docs/cross-cutting/DOC-OWNERS.md` from §5 and flipping `CLAR-OWNER-01` (DEFERRED → RESOLVED-role-based) in `WBS.md §17` are offered as a one-step follow-up you trigger. As authored, this memo edits **no** source-of-truth file, does **not** create `DOC-OWNERS.md`, and writes **no** production code. (Named-individual assignment remains a "team-seating exercise … once teams are seated", `WBS.md:930` — available the moment you supply names.)

> **One-paragraph summary.** Scanipy v3.2 is a **solo / agent-driven** project: there are no human teams to seat, so a *named-individual* resolution of `CLAR-OWNER-01` is **impossible without input this repo does not contain** (RULE-4 — an agent may not invent names). What *is* both decidable and honest is a **role/agent-doctrine ownership map**: the project already defines nine agent-roles (`CLAUDE.md §10`) and already distributes ownership of *every* component across them by doctrine — Doc Manager owns each `DOC-CMP-*`, QA owns each `TST-AC-*`, the `claude-review` CI check gates every PR (RULE-10), Security co-signs the seven INV-3/INV-4 components (RULE-9), CTO owns every CLAR/staging decision. Ownership is therefore **multi-dimensional**, not one-role-per-row. This memo (a) enumerates all **47** `CMP-*` and all **five** `R-*` with their *honest current owner-state* — which for every component is **UNASSIGNED to a person** (the `Risk owned:` tags are *component→risk* attributions, **not** role→component assignments, and `WBS.md:930` confirms OWNER-01 is unpopulated); (b) proposes a role-based map as the **RECOMMENDED DEFAULT working assignment for v3.2, to be revisited when human teams are seated**; (c) asks **exactly one** human question (ratify role-based, or supply names now); and (d) folds in `CLAR-CORP-03` (the reflection second reviewer), which **stays DEFERRED** with the corpus campaign — noting only that the reviewer must be *distinct from the corpus builder* and maps to a QA/Corpus role pairing pending a named person.

---

## 0. The ruling (what we are deciding)

| # | Decision | Owner to ratify |
|---|---|---|
| **D-1** | A *named-individual* resolution of `CLAR-OWNER-01` is **out of agent scope** (RULE-4): no human-name source exists in the repo. The repo-decidable deliverable is a **role/agent-doctrine ownership map** keyed to the nine roles in `CLAUDE.md §10`. `CLAR-OWNER-01` therefore stays **DEFERRED** pending ratification (option to keep role-based as the working assignment). | CTO (classification) |
| **D-2** | **Honest current owner-state: every `CMP-*` is UNASSIGNED to a person.** The five `Risk owned:` tags (`WBS.md:535,570,700,725,737`) attribute *risk mitigation* to *components* (component→risk), they are **not** role→component owner assignments; the §19 matrix (`WBS.md:1000-1006`) does the same. No row in `WBS.md` names a human owner of any component. | CTO |
| **D-3** | **Ownership is multi-dimensional, not one-role-per-component.** Each component carries a **primary build-owner role** *plus* standing **cross-cutting owners** (Doc Manager, QA, `claude-review`, CTO) *plus* **RULE-9 Security co-sign** where it applies. A single-owner-per-row table would *understate* the doctrine the project already mandates. | Architect/CTO |
| **D-4** | **RECOMMENDED DEFAULT — role/agent-doctrine ownership for v3.2.** Adopt the §3 subsystem→role map + the §4 `R-*`→role map as the **working assignment**, explicitly labelled "role-based; to be revisited when human teams are seated." This unblocks *tracking* (RULE-11 board ownership) without inventing names. | **CTO (this is the human question, §6 Q1)** |
| **D-5** | **RULE-9 Security co-sign is a non-negotiable owner on exactly seven components:** `CMP-CP-02, CMP-SNAP-03, CMP-SNAP-04, CMP-DET-01, CMP-TRI-01, CMP-TRI-02, CMP-TRI-03` (`.claude/rules/00-global.md` RULE-9). These carry Security in their owner set regardless of which role builds them. | Security + CTO |
| **D-6** | **`CLAR-CORP-03` stays DEFERRED** (it was routed here from Part 2 §E and already deferred with the whole corpus campaign — `DECISION-PART2 §8 Q4`). The second reviewer must be **distinct from the corpus builder** (independence requirement); under role-based ownership it maps to a **QA ⊕ Corpus-Curator** pairing *pending a named person*. It is folded into this record but is **not** a second human question. | CTO (rolls with the campaign) |
| **D-7** | **`docs/cross-cutting/DOC-OWNERS.md` is NOT created by this memo.** Its proposed content is offered as a table *inside* this record (§5). Standing up the file is a **human-triggered follow-up** once names land or the role-based map is ratified — at which point a `/doc-agent` pass writes it and `/sync-wbs` reconciles the board. | CTO (post-ratification) |

---

## 1. Why a named-owner resolution is impossible here — and what *is* decidable

`CLAR-OWNER-01` asks for a **named owner** per `CMP-*` and per `R-*` (`WBS.md:930`). Its own note frames it as a "**team-assignment exercise … once teams are seated**," and `OPEN-DECISIONS` Part 3 calls it a "**team-seating exercise**" (`OPEN-DECISIONS-2026-06-02.md:128-132`). Two facts make the *named* form unresolvable by an agent:

1. **There are no human teams in this repo to seat.** The only owners the project defines are the **nine agent-roles** of `CLAUDE.md §10` (CTO, Architect, Doc Manager, QA, Security Analyst, SRE/DevOps, Corpus Curator, Implementation) plus the **`claude-review` CI check** (RULE-10, which "replaced the retired `/code-review-cmp` Skill"). The git author of record is "Implementation Agent."
2. **RULE-4 forbids inventing the missing input.** A human name is exactly the kind of "required input … missing from `PLAN.md`/`SDD.md`" that must be surfaced as a question, not designed inline (`.claude/rules/00-global.md` RULE-4; `.claude/rules/03-scope.md`).

What *is* both decidable and honest is the **role/agent-doctrine layer**: the doctrine already assigns ownership of every artifact class to a role (Doc → `DOC-CMP-*`; QA → `TST-AC-*`; `claude-review` → every PR; CTO → every CLAR). The agent-decidable resolution is therefore to **make that implicit role-ownership explicit and complete**, and offer it as the working default. This mirrors how Part 2 handled its HUMAN items: surface the genuine human call, but pin a safe default in force in the meantime.

---

## 2. Owner-state legend (every enumerated row carries exactly one)

| State | Meaning |
|---|---|
| **UNASSIGNED** | No named human owner today (the honest state of **every** `CMP-*` per `WBS.md:930`). |
| **TAGGED→R** | Carries a `Risk owned:` tag in `WBS.md` — a *component→risk* mitigation attribution, **not** a role→component owner. (`CMP-SNAP-03, CMP-SNAP-04, CMP-TRI-02, CMP-CP-05, CMP-CP-06`.) Still UNASSIGNED to a person. |
| **IMPLIED-by-subsystem** | Owning *role* is implied by the `CLAUDE.md §5` subsystem map (and confirmed by the §3 proposal); still no named person. |
| **+SEC (RULE-9)** | Additionally requires Security co-sign per RULE-9 (the seven INV-3/INV-4 components). |

Every `CMP-*` is simultaneously **UNASSIGNED** (to a person) **and IMPLIED-by-subsystem** (to a role); the TAGGED→R and +SEC flags are additive markers where they apply.

---

## 3. (a) Complete enumeration — all 47 `CMP-*` with current owner-state + proposed primary role

Component list verified against `WBS.md` (37 non-CORP + 10 CORP = 47; CORP-CPG expands to six languages: java/python/js/go/ruby/php). **Standing cross-cutting owners apply to every row** and are stated once below the table, not repeated per row.

### SCM Integration — primary role: **Implementation** (subsystem `integrations/scm/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-SCM-01 (ABC) | UNASSIGNED · IMPLIED | Implementation |
| CMP-SCM-02 (GitHub) | UNASSIGNED · IMPLIED | Implementation |
| CMP-SCM-03 (GL/BB/ADO) | UNASSIGNED · IMPLIED | Implementation **+SEC** (webhook-signature path — see DECISION-PART2 §7 SCM-02) |
| CMP-SCM-05 (HTTP retry) | UNASSIGNED · IMPLIED | Implementation |

### Snapshotter — primary role: **Implementation** (`services/snapshot/`, `analysis/cpg_delta.py`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-SNAP-01 (API) | UNASSIGNED · IMPLIED | Implementation |
| CMP-SNAP-02 (Alg 1) | UNASSIGNED · IMPLIED | Implementation (+ Architect for the κ well-posedness ruling, DECISION-PARAM-01) |
| CMP-SNAP-03 (CW-DETECT) | UNASSIGNED · **TAGGED→R-1** (`WBS.md:535,570`) | Implementation **+SEC (RULE-9)** — INV-4 owner |
| CMP-SNAP-04 (diff oracle) | UNASSIGNED · **TAGGED→R-1, R-4** (`WBS.md:570,725`) | Implementation **+SEC (RULE-9)** |
| CMP-SNAP-05 (worker+env) | UNASSIGNED · IMPLIED | **SRE/DevOps** (worker image / `env_digest` source) + Implementation |

### Detector Catalog — primary role: **Implementation** (`analysis/ifds/dsl/`, `detectors/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-DET-01 (DSL) | UNASSIGNED · IMPLIED | Implementation **+SEC (RULE-9)** — INV-4 distributivity gate |
| CMP-DET-02 (registry) | UNASSIGNED · IMPLIED | Implementation (+SEC co-sign on the DET-02 binding condition, DECISION-PART2 §2) |
| CMP-DET-03 (scaffold+migration) | UNASSIGNED · IMPLIED | Implementation |

### Analysis Core — primary role: **Implementation** (`analysis/ifds/solver.py`, `analysis/ordering.py`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-CORE-01 (IFDS/IDE, Alg 2) | UNASSIGNED · IMPLIED | Implementation (+ Architect for Alg-2 / INV-6 design) |
| CMP-CORE-02 (fingerprint, Alg 3) | UNASSIGNED · IMPLIED | Implementation (+ Architect — INV-5 `fingerprint_class`) |
| CMP-CORE-03 (canonical order, Alg 5) | UNASSIGNED · IMPLIED | Implementation (+ Architect — INV-5 `cpg_order_hash`) |

### Orchestration — primary role: **Implementation** (`services/scan/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-ORCH-01 (scan API) | UNASSIGNED · IMPLIED | Implementation |
| CMP-ORCH-02 (scheduler, Alg 4) | UNASSIGNED · IMPLIED | Implementation |
| CMP-ORCH-03 (worker) | UNASSIGNED · IMPLIED | Implementation (INV-1/INV-2 origin+provenance emitter) |

### Findings & Provenance — primary role: **Implementation** (`services/scan/`, `db/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-FND-01 (normalizer) | UNASSIGNED · IMPLIED | Implementation |
| CMP-FND-02 (store schema) | UNASSIGNED · IMPLIED | Implementation (+ SRE for the Alembic migration) |
| CMP-FND-03 (signed provenance) | UNASSIGNED · IMPLIED | Implementation (+SEC co-sign on signing/audit chain) |

### Triage & Spec Inference — primary role: **Implementation** (`services/triage/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-TRI-01 (LLM triage) | UNASSIGNED · IMPLIED | Implementation **+SEC (RULE-9)** — INV-3 |
| CMP-TRI-02 (e-process gate, Alg 6) | UNASSIGNED · **TAGGED→R-3** (`WBS.md:700`) | Implementation **+SEC (RULE-9)** + **QA** (martingale falsifier — see *falsifier-gates-need-math-review*) |
| CMP-TRI-03 (drift monitor) | UNASSIGNED · IMPLIED | Implementation **+SEC (RULE-9)** |

### Control Plane & Attestation — primary role: **Implementation** (`services/control_plane/`); dashboard `web/`

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-CP-01 (API guard) | UNASSIGNED · IMPLIED | Implementation |
| CMP-CP-02 (cred encryption) | UNASSIGNED · IMPLIED | Implementation **+SEC (RULE-9)** — KMS taxonomy (DECISION-PART2 §5) |
| CMP-CP-03 (tenancy schema) | UNASSIGNED · IMPLIED | Implementation (+SEC co-sign RLS, DB-02) + SRE (migration) |
| CMP-CP-04 (auth + dashboard) | UNASSIGNED · IMPLIED | Implementation (TS dashboard) + SRE (Auth0) + SEC (CP-04-01) |
| CMP-CP-05 (attestor) | UNASSIGNED · **TAGGED→R-4** (`WBS.md:725`) | **SRE/DevOps** (CI pipeline) + Implementation + SEC (INV-3 self-test) |
| CMP-CP-06 (CPG fidelity gate) | UNASSIGNED · **TAGGED→R-2** (`WBS.md:737`) | Implementation + **Architect** (INV-6 honesty) + Corpus (fidelity corpora) |

### Deployment — primary role: **SRE/DevOps** (`infra/`, `.github/workflows/`, `workers/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-DEPLOY-01 | UNASSIGNED · IMPLIED | SRE/DevOps |
| CMP-DEPLOY-02 | UNASSIGNED · IMPLIED | SRE/DevOps |
| CMP-DEPLOY-03 | UNASSIGNED · IMPLIED | SRE/DevOps |
| CMP-DEPLOY-04 | UNASSIGNED · IMPLIED | SRE/DevOps |
| CMP-DEPLOY-05 | UNASSIGNED · IMPLIED | SRE/DevOps (+SEC co-sign — tenant isolation verification) |

### Corpora — primary role: **Corpus Curator** (`tests/corpora/`)

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-CORP-REFL-01 | UNASSIGNED · IMPLIED | Corpus Curator (+ QA second-pass review — see `CLAR-CORP-03`, §4/§5) |
| CMP-CORP-CPG-java | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CPG-python | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CPG-js | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CPG-go | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CPG-ruby | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CPG-php | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-CANARY-01 | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-REFAC-01 | UNASSIGNED · IMPLIED | Corpus Curator |
| CMP-CORP-VULN-01 | UNASSIGNED · IMPLIED | Corpus Curator (+ CTO/legal for the GPL OWASP call, CORP-18) |

### CI gates / Research — primary roles below

| CMP-* | Current owner-state | Proposed primary role |
|---|---|---|
| CMP-CI-01 | UNASSIGNED · IMPLIED | **SRE/DevOps** (the four named gates) |
| CMP-RES-01 | UNASSIGNED · IMPLIED | Implementation (research mode `services/research/`) |

**Standing cross-cutting owners — apply to ALL 47 rows above (stated once):**
- **Documentation Manager** owns the `DOC-CMP-*` contract for every component (`CLAUDE.md §10`, RULE-1).
- **QA** owns every `TST-AC-*` / `TST-INV-*` for every component (`CLAUDE.md §10`, RULE-3).
- **`claude-review` CI check** is the sole code-review owner gating every PR (RULE-10).
- **CTO** owns every `CLAR-*` resolution and staging-gate decision touching the component (`CLAUDE.md §10`, RULE-8).
- **Architect** owns INV-1..6 design review on every component touching an invariant.

---

## 4. (a continued) — the five `R-*` risks with current owner-state + proposed mitigation-owner role

Risk register: `WBS.md §19` (`WBS.md:1000-1006`); inline `Risk owned:` tags at `WBS.md:535,570,700,725,737`. The matrix lists **mitigation-owner components**; the column header is literally "Mitigation owner(s)" (`WBS.md:1000`) and names **components, not people** — so the current owner-state for every R-* is **UNASSIGNED to a person**.

| R-* | Statement (abridged, `WBS.md:1002-1006`) | Mitigation owner **components** (matrix) | Inline tag(s) | Proposed mitigation-owner **role(s)** |
|---|---|---|---|---|
| **R-1** | CW-DETECT FN leaks a wrong `deterministic-core` label | CMP-SNAP-04 (differential oracle) | `SNAP-03:535`, `SNAP-04:570` | **Security Analyst** (INV-4 safe-direction) ⊕ Implementation (SNAP-03/04) |
| **R-2** | Front-end fidelity dominates schedule; weak front-ends depress AC-CORE-01b | CMP-CP-06 (gate) + T-STAGE-{C,D}-FE-01 | `CP-06:737` | **Architect** (INV-6 honesty) ⊕ **CTO** (FE build/buy spend — FE-01/02, DECISION-PART2 §3) |
| **R-3** | Spec gate misused — e-process without martingale unit test | TST-AC-TRI-02b as hard production-enablement gate (wired by CMP-CI-01) | `TRI-02:700` | **Security Analyst** ⊕ **QA** (martingale + positive-power + negative-control — *falsifier-gates-need-math-review*) |
| **R-4** | Determinism regression invisible to same-path re-run | CMP-SNAP-04 + CMP-CP-05 partition split | `CP-05:725` ("alongside CMP-SNAP-04") | **SRE/DevOps** (attestor CI, CMP-CP-05) ⊕ Implementation (SNAP-04) ⊕ Security (co-sign) |
| **R-5** | Detector-catalog chicken-and-egg — stubbed classes block adoption | Stage A front-loads `{injection, path-traversal, ssrf, deserialization}`; other six post-Stage-A | *(none — no single component)* | **CTO** — owned as a **staging policy** ("LIVE AS POLICY", `WBS.md:1107`), not a single-component build owner |

**Note on R-5:** it has **no inline `Risk owned:` tag** because its mitigation is a *staging decision* ("Stage A is the minimum shippable set", `WBS.md:1006`), not a component. The DoD tracks it as **"LIVE AS POLICY"** (`WBS.md:1107`), so its natural owner is the **CTO** (staging-gate authority, `CLAUDE.md §10`), not Implementation.

---

## 5. (b) Proposed `docs/cross-cutting/DOC-OWNERS.md` content — RECOMMENDED DEFAULT

> **This is the proposed *content* of the future file, presented here for ratification. This memo does NOT create `docs/cross-cutting/DOC-OWNERS.md`** (D-7) — that is a human-triggered `/doc-agent` follow-up once this map is ratified or names are supplied. The map is **role/agent-doctrine ownership for v3.2, to be revisited when human teams are seated.**

### 5.1 Subsystem → owning role map (all 12 subsystems from `CLAUDE.md §5`)

| Subsystem | Components | Primary build-owner role | Mandatory co-owners |
|---|---|---|---|
| SCM Integration | CMP-SCM-01/02/03/05 | Implementation | Doc · QA · claude-review · CTO; **+SEC** on SCM-03 webhook |
| Snapshotter | CMP-SNAP-01..05 | Implementation (SNAP-05: SRE+Impl) | Doc · QA · claude-review · CTO; **+SEC (RULE-9)** on SNAP-03, SNAP-04 |
| Detector Catalog | CMP-DET-01/02/03 | Implementation | Doc · QA · claude-review · CTO; **+SEC (RULE-9)** on DET-01 |
| Analysis Core | CMP-CORE-01/02/03 | Implementation | **Architect** (Alg 2/3/5, INV-5/INV-6) · Doc · QA · claude-review · CTO |
| Orchestration | CMP-ORCH-01/02/03 | Implementation | Doc · QA · claude-review · CTO |
| Findings & Provenance | CMP-FND-01/02/03 | Implementation | Doc · QA · claude-review · CTO; SRE (FND-02 migration); SEC (FND-03 signing) |
| Triage & Spec Inference | CMP-TRI-01/02/03 | Implementation | Doc · QA · claude-review · CTO; **+SEC (RULE-9) on all three** |
| Control Plane & Attestation | CMP-CP-01..06 | Implementation (CP-05: SRE+Impl) | Doc · QA · claude-review · CTO; **+SEC (RULE-9)** on CP-02; SEC co-sign CP-03/04; Architect on CP-06 (INV-6) |
| Deployment | CMP-DEPLOY-01..05 | **SRE/DevOps** | Doc · QA · claude-review · CTO; SEC co-sign DEPLOY-05 |
| Corpora | CMP-CORP-REFL/CPG-{6}/CANARY/REFAC/VULN | **Corpus Curator** | Doc · QA (incl. dual-review) · claude-review · CTO; CTO/legal on VULN GPL |
| CI gates | CMP-CI-01 | **SRE/DevOps** | Doc · QA · claude-review · CTO |
| Research mode | CMP-RES-01 | Implementation | Doc · QA · claude-review · CTO |

### 5.2 Risk → mitigation-owner role map

| R-* | Mitigation-owner role(s) | Status |
|---|---|---|
| R-1 | Security Analyst ⊕ Implementation (SNAP-03/04) | mitigation in-flight (CMP-SNAP-04) |
| R-2 | Architect ⊕ CTO (FE spend) | LIVE (CMP-CP-06 gate; FE delayed per DECISION-PART2 §8 Q1) |
| R-3 | Security Analyst ⊕ QA | LIVE (TST-AC-TRI-02b hard gate, Gate-4) |
| R-4 | SRE/DevOps ⊕ Implementation ⊕ Security | mitigation in-flight (CMP-SNAP-04 + CMP-CP-05) |
| R-5 | CTO (staging policy) | LIVE AS POLICY (`WBS.md:1107`) |

### 5.3 `CLAR-CORP-03` — reflection second reviewer (folded in, **stays DEFERRED**)

`CLAR-CORP-03` (`WBS.md:952`) needs a **named second reviewer** for the reflection dual-review (`review_status: second-pass`, AC-CORP-REFL-01a). It was routed to Part 3 and **deferred with the whole corpus campaign** (`DECISION-PART2 §8 Q4`, line 231: "CORP-03 rolls into CLAR-OWNER-01 … the campaign … waits"). Disposition here:

- **It stays DEFERRED.** It does not become a second human question; it travels with the funded-or-deferred corpus campaign (already deferred to the safe default).
- **Independence requirement (binding when it lands):** the second reviewer must be **distinct from the corpus builder** — `reflection/corpus.lock:4` shows `hand_curated_second_pass: 0` everywhere, so today there is *no* second pass at all.
- **Role-based placeholder:** under this map it maps to a **QA ⊕ Corpus-Curator pairing** (QA owns review independence; Corpus owns the artifact) — *pending a named person*. The pairing satisfies the distinctness requirement structurally (the reviewer role ≠ the builder role) but a single agent cannot honestly self-certify both sides, so it remains DEFERRED until a name or a second independent reviewer is assigned.

---

## 6. (c) The single human question

> Per RULE-4, an agent may not invent human names. Exactly **one** decision needs you. It carries a recommended default; everything stays safe and tracked while it waits (the role-based map is the in-force working assignment under either answer's interim).

| # | Question (plain) | Options (recommended first) | Recommended default |
|---|---|---|---|
| **Q1** | Who owns each part of the project — should we **use the built-in agent-role assignments** as the working owner map for now (each subsystem owned by its natural role — e.g. Implementation builds the analysis code, SRE owns deployment and CI, Corpus Curator owns the test corpora — with Documentation, QA, automated Code-Review and the CTO as standing cross-cutting owners, and the Security reviewer mandatory on the seven security-sensitive components), **or** do you want to **supply named individual people** for each component and risk right now? | **(1) Ratify the role-based map** as the v3.2 working assignment (revisit when human teams are seated) · (2) Supply named individuals now | **(1) Ratify the role-based map.** It is cheap, unblocks tracking (the board / RULE-11) immediately, invents no names (RULE-4-safe), and is trivially upgraded to named people later by editing one file. Naming individuals is only needed if you already have people to seat. |

**YOUR DECISION (2026-06-03): (1) Ratify the role-based map** as the v3.2 working assignment (revisit when human teams are seated). The §3–§5 map is now the in-force working ownership; named individuals can be supplied later by editing one file. Ready follow-up (you trigger): `/doc-agent` creates `docs/cross-cutting/DOC-OWNERS.md` from §5; `/sync-wbs` flips `CLAR-OWNER-01` → RESOLVED-role-based and reconciles board ownership (RULE-11).

*(`CLAR-CORP-03` is intentionally **not** a second question — it stays DEFERRED with the corpus campaign per D-6.)*

---

## 7. Proposed `WBS §17` register text (for a human to paste — *not* applied here)

> **Proposed** edits for the CTO to make after ratification. This memo does **not** write them and does **not** flip `CLAR-OWNER-01` from DEFERRED.

**Refine `CLAR-OWNER-01` notes** — append:
> Named-individual assignment is out of agent scope (RULE-4 — no human-name source in repo); the repo-decidable layer is a **role/agent-doctrine ownership map** (`docs/DECISION-PART3-ownership-2026-06-03.md`). RECOMMENDED DEFAULT: ratify the role-based map (subsystem→role + R-*→role, §3–§5 of the record) as the v3.2 working assignment, revisited when human teams are seated. `Risk owned:` tags are component→risk attributions, not person assignments. Stays **DEFERRED** pending the one human question (ratify role-based vs supply names). On ratification, a `/doc-agent` pass creates `docs/cross-cutting/DOC-OWNERS.md` from §5 and `/sync-wbs` reconciles board ownership (RULE-11).

**`CLAR-CORP-03`** — keep **DEFERRED** (travels with the corpus campaign, already deferred per `DECISION-PART2 §8 Q4`); record: second reviewer must be **distinct from the corpus builder**; role-based placeholder = QA ⊕ Corpus-Curator pairing pending a named person.

*(Register housekeeping, noted not fixed: do not collide with the existing `CLAR-MIGRATION-01` duplicate-ID / stale `CLAR-TRI-01` status defects flagged in `OPEN-DECISIONS` Part 4 and `DECISION-PART2 §10`.)*

---

## 8. Governance boundary — what this memo does and does not do

- **Does:** produce the Part-3 ownership decision record; enumerate all 47 `CMP-*` + 5 `R-*` with honest current owner-state grounded in `file:line`; propose a role/agent-doctrine ownership map as the recommended default; present the future `DOC-OWNERS.md` content as a table *inside* the record; surface exactly one human question with a recommended default; fold in `CLAR-CORP-03` as DEFERRED.
- **Does NOT:** edit `PLAN.md`/`SDD.md`/`WBS.md`; flip any `CLAR-*` status (`CLAR-OWNER-01` and `CLAR-CORP-03` both stay as-is); **create `docs/cross-cutting/DOC-OWNERS.md`**; invent any human name (RULE-4); write production code.
- **Ratification path:** **CTO** is the approver (RULE-8; `OWNER` domain → CTO per `clar-resolve.md`). The CTO answers §6 Q1 (ratify role-based vs supply names). On ratification: `/doc-agent` creates `DOC-OWNERS.md` from §5; `/sync-wbs` reconciles the board (RULE-11); `CLAR-OWNER-01` may then flip to RESOLVED (role-based) or stay DEFERRED awaiting names. `CLAR-CORP-03` stays DEFERRED with the corpus campaign regardless.

---

## 9. Risks & backstops

| Risk | Backstop |
|---|---|
| Role-based map mistaken for a *named* resolution | Header + D-1 + §6 state explicitly it is role-based, "revisited when human teams are seated"; `CLAR-OWNER-01` stays DEFERRED until ratified |
| `Risk owned:` tags misread as person assignments | D-2 + §2 legend + §4 note: tags are component→risk; column header is literally "Mitigation owner(s)" naming components |
| Single-owner-per-row understates the doctrine | D-3 + standing-cross-cutting-owners block: Doc/QA/claude-review/CTO own every row; RULE-9 Security on seven |
| RULE-9 Security co-sign dropped on a sensitive component | D-5 names the exact seven (`CMP-CP-02, SNAP-03, SNAP-04, DET-01, TRI-01, TRI-02, TRI-03`) and flags them **+SEC** in §3/§5 |
| `CLAR-CORP-03` accidentally "resolved" without a name | D-6 keeps it DEFERRED; independence (reviewer ≠ builder) recorded as a binding condition for when it lands |
| `DOC-OWNERS.md` created prematurely / under wrong names | D-7: file NOT created here; content lives in §5; human-triggered `/doc-agent` follow-up post-ratification |

---

## 10. References

- `WBS.md:930` (`CLAR-OWNER-01`, DEFERRED, "populate `DOC-OWNERS.md` once teams are seated") · `WBS.md:952` (`CLAR-CORP-03`) · `WBS.md:900` (per-component ownership tracked under OWNER-01)
- `WBS.md:535,570,700,725,737` (the five `Risk owned:` tags) · `WBS.md:1000-1006` (§19 risk matrix, "Mitigation owner(s)" = components) · `WBS.md:1107` (R-5 "LIVE AS POLICY")
- `CLAUDE.md §5` (component map — 12 subsystems) · `CLAUDE.md §10` (nine agent-roles + `claude-review`) · `CLAUDE.md §11` (RULE-1..11)
- `.claude/rules/00-global.md` RULE-1 (Doc), RULE-3 (QA/tests), RULE-4 (no invented scope), RULE-8 (CTO approves), RULE-9 (Security co-sign — the seven), RULE-10 (claude-review sole reviewer), RULE-11 (board ownership)
- `.claude/commands/cto.md` (CTO authority) · `.claude/commands/clar-resolve.md` (OWNER domain → CTO approver)
- `docs/OPEN-DECISIONS-2026-06-02.md` Part 3 (CLAR-OWNER-01), Part 2 §E (CORP-03 routed here), Part 5 item 6 ("assign owners — cheap; do it early")
- `docs/DECISION-PART2-2026-06-03.md` §8 Q4 (line 231 — CORP-03 deferred, "rolls into CLAR-OWNER-01"), §6 (corpus campaign), §9 (cross-cutting co-signs)
- `docs/DECISION-PARAM-01-kappa-2026-06-03.md` (format + governance template)
- Project memory: *falsifier-gates-need-math-review* (R-3/TRI-02 → QA+Security); *PR body must use the template* (RULE-10)

---

*Decision record — PROPOSED. Ratify the role-based ownership map (§6 Q1) — or supply named individuals — then on your go-ahead a `/doc-agent` pass creates `docs/cross-cutting/DOC-OWNERS.md` from §5, `/sync-wbs` reconciles the board, and `CLAR-OWNER-01` is recorded back into `WBS.md §17`. `CLAR-CORP-03` stays DEFERRED with the corpus campaign.*

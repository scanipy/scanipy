# Decision Record — Part 5: the one-page meeting summary (post-analysis)

**ID:** `DECISION-PART5` · **Prepared:** 2026-06-03 · **Author:** CTO consolidation pass over Parts 1–4, advisor-reviewed
**Supersedes:** `docs/OPEN-DECISIONS-2026-06-02.md` **Part 5** (the pre-analysis one-page summary).
**Companion to (the four records this digests):**
`docs/DECISION-PARAM-01-kappa-2026-06-03.md` (Part 1 — κ/π₀) ·
`docs/DECISION-PART2-2026-06-03.md` (Part 2 — groups A–F + the six answered §8 human decisions) ·
`docs/DECISION-PART3-ownership-2026-06-03.md` (Part 3 — ownership, ratified role-based) ·
`docs/DECISION-PART4-register-defects-2026-06-03.md` (Part 4 — register defects, option ① applied).
**Status:** **SUMMARY.** This is a meeting digest only. It edits **no** source-of-truth file, flips **no** `CLAR-*`
status, and writes **no** code. (The Part-4 fixes were applied separately on 2026-06-03 — this only *reports*
that state.) Every claim traces to one of the four records above or to `OPEN-DECISIONS`.

> **Read this in 5 minutes.** Four analysis passes turned the 42-open backlog into a short, mostly-decided
> list. The headline shift: **κ is no longer the cork in the bottle.** It has no runtime consumer and gates
> only a post-hoc *economics* test, so `CMP-CORE-01` development **unblocks now** against a correct SNAP-02
> (PARAM-01 D-7). What is left to decide is genuinely small: **one new open well-posedness item
> (`CLAR-PARAM-04`)**, one number nobody has supplied (**the LLM rate-limit budget**), and a **one-sitting
> ratification batch** (incl. two ARBs — SNAP-02 schema, SCM-02 ADO webhook). The six money/legal/headcount
> questions are **already answered to the safe default** (no new spend in v3.2). Three items are not decisions
> but **engineering bugs to action** (SNAP-02, SCM-02, CP-02-01).

---

## 1. Decision-state ledger — the whole 72-item register

Read this as **two layers**: (a) what the *formal* register (`WBS.md §17`) actually says today, and
(b) what was *decided this cycle but not yet written back* (Parts 1–3 are PROPOSED records; only Part 4 was
applied). Conflating the two is the failure mode — the human answers in Part 2 §8 and Part 3 are **recorded
in the records, not yet in `WBS.md`**.

### (a) Formal register tally — `WBS.md §17`

| State | 2026-06-02 baseline | After this cycle | What moved |
|---|---|---|---|
| **RESOLVED** | 30 | **31** | `CLAR-TRI-01` flipped `OPEN`→`RESOLVED` (Part 4 D-2, applied — PR #255 in effect) |
| **OPEN** | 31 | **30** | −1 (the CLAR-TRI-01 flip) |
| **DEFERRED** | 11 | **11** | unchanged |
| **Total** | **72** | **72** | unchanged |

Two non-tally facts: the **`CLAR-MIGRATION-01`→`-02` renumber** (Part 4 D-1, applied) **de-collides an ID;
it is not a new item and does not change the split** (both questions were already separate rows in the 72).
The proposed-new **`CLAR-PARAM-04`** is **not yet in the register** — once written back it makes the count
**31 RESOLVED / 31 OPEN / 11 DEFERRED = 73** (see §3).

### (b) Decided this cycle, pending write-back (the real progress)

| Bucket | Disposition | Where |
|---|---|---|
| Part 2 §8 — six human decisions | **ANSWERED, all to safe default** | DECISION-PART2 §8 Q1–Q6 |
| Part 3 — ownership | **RATIFIED role-based** (names pending) | DECISION-PART3 §6 Q1 |
| Part 4 — six register/doc defects | **option ① applied** to working tree (**D-6 held**) | DECISION-PART4 §5a |
| Part 1 — κ ruling | **PROPOSED** (D-1..D-8); core dev unblocked via D-7 | DECISION-PARAM-01 §0 |
| Group A/C/D ratifications (Part 2) | **PROPOSED**, awaiting one sign-off sitting | DECISION-PART2 §2/§4/§5 |

---

## 2. What is already DECIDED (2026-06-03)

| Decision | Outcome | Source |
|---|---|---|
| **Q1** new-language front-ends (FE-01/02) | **Delay all** — Go/Ruby/PHP stay oracle-passthrough (`front-end-blocked`); no spend | PART2 §8 Q1 |
| **Q2** OWASP GPL-2.0 (CORP-18) | **Keep fetch-on-demand** — no GPL vendored; sha256-pinned | PART2 §8 Q2 |
| **Q3** GitHub branch protection (DEPLOY-17) | **Keep process shims** — fail-closed loud-red checks, no cost | PART2 §8 Q3 |
| **Q4** corpus sourcing campaign (CORP-05/19/03) | **Defer** — scaffolds stay honest; CORP-03 rolls into OWNER-01 | PART2 §8 Q4 |
| **Q5** legacy v2 artifacts (SCM-01, MIGRATION-973) | **No — rescope/defer** `AC-SCM-02b` + `AC-DET-03b` to shape contracts | PART2 §8 Q5 |
| **Q6** v2→v3.2 data migration (MIGRATION-931) | **New-environment-only** — no migration scoped | PART2 §8 Q6 |
| **Ownership** (OWNER-01) | **Role-based map ratified** (Part 3 §6 Q1 → option 1). Subsystem→role + R-*→role is the v3.2 working assignment. **Pending:** named individuals; `DOC-OWNERS.md` **not yet created** (triggerable `/doc-agent` follow-up); `CLAR-OWNER-01` still **DEFERRED** in WBS until written back | PART3 §6 |
| **Register defects** (Part 4) | **option ① applied** — D-1..D-5 to working tree (TRI-01 flip, MIGRATION renumber + code-comment, three doc fixes). **D-6 HELD** (gated on SCM-02 ARB). Not committed/pushed — enters `main` via normal PR + `claude-review` | PART4 §5a |
| **κ ruling (D-7 — the unblock)** | Interim dev **κ = 50** (inert, never feeds the still-xfail hard gate `TST-AC-SNAP-02a`); κ **decoupled** as a property-(b) *economics* gate so **`CMP-CORE-01` dev unblocks now** against a correct SNAP-02; certified κ pinned **per-language at Stage-A go-live** | PARAM-01 §0 D-1..D-7, §6 |

---

## 3. Still genuinely OPEN — awaiting a human or a named phase (do not drop these)

| Item | What's needed | Owner | On critical path? |
|---|---|---|---|
| **`CLAR-PARAM-04`** *(new)* | κ **well-posedness** fix: affine `+C₀` term vs delta-only/copy-on-write persistence vs ratified corpus floor — removes the O(\|graph\|) serialization floor that makes ρ diverge on small commits. **Gates the *certified* κ pin** (not core dev). Proposed-new row; not yet in WBS. | **Architect / CTO** | **Yes** — sole remaining κ blocker (for Stage-A go-live cert) |
| **`CLAR-SLA-02`** LLM rate-limit budget | A real **RPM / tokens-per-day** number. None proposed anywhere. Fail-closed interim (deny when unset) is safe; real numbers need capacity/cost input **before Stage-A go-live**. (FYI in PART2 §8.) | SRE + **human (cost)** | Yes — before Stage-A go-live |
| **Group A/C/D RR ratifications** | One-sitting confirm of the provisional/fail-closed defaults (DET-01, DET-02*, CP-01-01, CP-06-01, API-01; CP-04-01, CP-05-01/02, CP-06-02, DB-02, SLA-02-API, SARIF-01; CP-02-01). Mostly "yes, accept default." | Architect / SRE / Security (one review) | Partly — needed before Stage-A go-live |
| **`CLAR-SNAP-02`** (ARB) | Schema arbitration — shipped terminal-record schema is canonical; the state-machine doc is the corrected one. **Unblocks CMP-SNAP-05 design.** Needs sign-off. | **Architect** (+ CTO, PLAN/SDD) | When SNAP-05 starts |
| **`CLAR-SCM-02`** (ARB) | ADO webhook — verify via `basicAuthPassword` secret-equality (native ADO sends no HMAC). Needs sign-off; **gates Part-4 D-6** (the held doc edit). | **Architect + Security** (RULE-9) | When SCM-03/ADO ships |
| **π₀ (`CLAR-PARAM-02`)** | Per-class **certified** π₀ values **+** the per-class **evaluation-stream definition** (pin the stream first). Interim uniform 0.80, α=0.05 fixed; martingale holds for any π₀. | Security + Architect | **No** — DEFERRED to Phase 5 |
| **Ownership names + `CLAR-CORP-03`** | Named individuals per component/risk; the reflection **second reviewer** (distinct from the builder). Role-based map in force meanwhile; CORP-03 DEFERRED with the corpus campaign. | CTO (when teams seat) | No — DEFERRED |

\* **DET-02** ratification carries a **binding Security condition** (pin `parse_spec` on the `register()` path + a negative test); APPROVE-WITH-CONDITIONS, not a clean ratify (PART2 §2).

---

## 4. Three engineering findings to ACTION (bugs, not decisions)

| Finding | What it is | Fix path | Gated on |
|---|---|---|---|
| **SNAP-02** | Spec↔spec **schema conflict** (async state-machine doc vs shipped terminal-record schema). | Resolved by the **source-of-truth hierarchy** — shipped schema (DOC-DB §4.7) is canonical; the state-machine DOC is the corrected document. State-machine deferred to SNAP-05. | the SNAP-02 **ARB** sign-off (§3) |
| **SCM-02** | **Real bug:** native ADO sends **no HMAC**, so the interim verifier (`requires X-Hub-Signature-256`) **rejects every genuine delivery**; `AC-SCM-03b` passes only vacuously. | **Free fix:** verify by **`basicAuthPassword` secret-equality** (already wired in `register_webhook`) + add a **positive-control** test. | the SCM-02 **ARB** sign-off → which gates Part-4 **D-6** |
| **CP-02-01** | **Real bug:** documented KMS **500/503** error paths **do not execute against real boto3**; CI is green only via typed fakes (a real `ClientError` is mislabeled 403). | Security ruling = **narrow DOC §7 toward fail-closed**, but **split `KMSKeyMissingError` out of the tenant-isolation alarm** + add a **botocore-`ClientError`-shaped** test; SRE owns the throttle-retry disposition. | the CP-02-01 Security ruling (§3 batch) |

---

## 5. Decide in this order (the updated critical path)

| # | Decision | On true critical path? | Owner |
|---|---|---|---|
| **1** | **κ well-posedness — `CLAR-PARAM-04`.** κ itself is decided (interim 50 inert; D-7 already unblocks CORE-01 **dev**). PARAM-04 is the *only* remaining κ blocker — it gates the **certified** pin at Stage-A go-live. | **YES** (cert path; dev already unblocked) | Architect / CTO |
| **2** | **The one-sitting RR/ARB ratification batch** — group A/C/D defaults **incl. `CLAR-SNAP-02`** (unblocks SNAP-05 design) and **`CLAR-SCM-02`** (gates D-6). | Partly — before go-live / when those CMPs ship | Architect / SRE / Security |
| **3** | **LLM rate-limit budget number** (`CLAR-SLA-02`). | **YES** — before Stage-A go-live | SRE + human (cost) |
| **4** | **Corpus campaign go/defer** — **already DEFERRED** (Q4). Revisit only to fund language coverage beyond Java+Python. | No | CTO + budget |
| **5** | **Ownership names** — if/when human teams seat (role-based map in force now). | No | CTO |

Original Part-5 items 3 (money/legal) and 6 (assign owners) are now **answered** (Q1–Q3) and **ratified
role-based** respectively — they drop from "to decide" to "confirm / do when convenient."

---

## 6. What is safe right now while undecided (the honest-default posture)

- **Java + Python only** on the core path; **every other language is `front-end-blocked`** (INV-6) — no inflated recall numbers.
- **All undecided thresholds fail-closed** (Auth0 outage → 503; fidelity-gate env mismatch → fail; LLM budget unset → deny; KMS error → fail-closed 403).
- **Interim κ = 50 is inert** — never feeds the still-xfail hard gate; cannot weaken soundness (κ is property-(b) economics only).
- **Interim π₀ = 0.80** exercises the (green) Gate-4 martingale plumbing without vacating it; certified values DEFERRED.
- **Corpus scaffolds are versioned and explicitly NOT claimed gate-strength**; ratifying an `N`/method does not flip CMP-CP-06 to GATE-PASS.
- **GPL OWASP ships fetch-on-demand** — zero copyleft exposure.
- **Deployment substrate fully resolved** (AWS stack pinned); GitHub enforcement via fail-closed process shims.

Nothing on the open list is unsafe while it waits.

---

## 7. Governance boundary

- **Does:** consolidate Parts 1–4 into a meeting-ready digest; reconcile the register tally; sweep up every live thread.
- **Does NOT:** edit `PLAN.md`/`SDD.md`/`WBS.md`; flip any `CLAR-*` status; write code; re-apply the Part-4 fixes (already applied separately).
- **Open write-backs the human may trigger:** record the §8 answers + Part-3 role-based map into `WBS.md §17`; create `docs/cross-cutting/DOC-OWNERS.md`; add the `CLAR-PARAM-04` row; ratify the group A/C/D batch; apply Part-4 **D-6** once `CLAR-SCM-02` is signed off.

---

*Decision record — SUMMARY. Decide §5 in order: `CLAR-PARAM-04` first (κ cert path; core dev already
unblocked), then the one-sitting RR/ARB batch (incl. SNAP-02, SCM-02), then the LLM-budget number. Everything
else is answered, deferred to the safe default, or done.*

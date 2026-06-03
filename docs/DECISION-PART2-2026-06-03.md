# Decision Record — Part 2: the team-input decisions (groups A–F)

**ID:** `DECISION-PART2` · **Prepared:** 2026-06-03 · **Author:** orchestrated role-agent analysis pass (Architect · CTO · SRE · Security · Corpus · external-info), advisor-reviewed
**Resolves (the engineering analysis behind):** `docs/OPEN-DECISIONS-2026-06-02.md` **Part 2** (§A–§F) — the decisions "grouped by who should make them."
**Companion to:** `docs/DECISION-PARAM-01-kappa-2026-06-03.md` (Part 1 — κ/π₀). Same governance posture.
**Status:** **PROPOSED — ratifiable items (groups A/C/D) await Architect / SRE / Security sign-off; the six human decisions (§8) are ANSWERED (2026-06-03), all to the safe default.** This memo edits **no** source-of-truth file. It does **not** flip any `CLAR-*` status, does **not** touch `PLAN.md`/`SDD.md`/`WBS.md`, and writes **no** production code. It is a decision *record* for humans to ratify; the genuine human decisions in §8 have been recorded.

> **One-paragraph summary.** Part 2's ~30 open decisions split cleanly by who can actually decide them. **Most (groups A, C, D) are agent-decidable ratifications** — a provisional/fail-closed default already exists in the register or the DOC, and the role-agent recommendation is a confident "ratify + one residual risk." **A genuine handful (groups B, E, F) commit money, legal sign-off, headcount, or depend on a fact that lives outside this repo** — those are surfaced as plain-English questions in §8 (RULE-4: an agent may not invent them). Three items are not ratifications but real findings: **CLAR-SNAP-02** is a spec↔spec conflict resolved by the source-of-truth hierarchy (shipped schema wins); **CLAR-SCM-02** is a latent **bug** (the native Azure DevOps webhook emits no HMAC header at all, so the interim verifier rejects every genuine delivery) with a free fix; and **CLAR-CP-02-01** is a real **bug** (the documented KMS 500/503 paths do not execute against live boto3 — CI is green only via typed fakes). Every undecided item already has a **safe, honest default in force**, so nothing here is unsafe while it waits.

---

## 0. How this was produced, and the tier legend

Six role-agents each analyzed one decision group **read-only** (no SoT/code edits), grounded every claim in repo evidence (`file:line`), and classified each item. The outputs were advisor-reviewed; one cross-seam gap (the DET-02 Security co-sign, RULE-9/INV-4) was caught and closed; one item (SCM-02) was reclassified from "human" to "architect-decidable" once public Azure docs settled it.

**Tier legend** (every item carries exactly one):

| Tier | Meaning | Who acts |
|---|---|---|
| **RR** — Recommend-Ratify | A provisional/default exists; the recommendation + one residual risk is the answer. Confirmation is a formality. | Architect/CTO/SRE ratify |
| **RR-COND** — Recommend-Ratify-with-Conditions | RR, but a binding condition must be recorded (it spawns a small follow-up). | Owner ratifies + tracks the condition |
| **RR-CONFIRM** — Recommend-Ratify-but-Confirm | RR, but the recommendation rests on data the repo lacks (named below). | Ratify as interim; pin real value later |
| **ARB** — Proposed-Awaiting-Architect | A genuine PLAN↔SDD/spec conflict or design fork; arbitrated here, needs architect/CTO sign-off. | Architect/CTO rule |
| **HUMAN** — Human-Decides | Commits money, legal sign-off, headcount, or depends on a fact not in this repo. **Asked in §8.** | The human |

---

## 1. One-page summary (decide in this order)

**A. Clear the ratification batch in one sitting** (groups A + C + D + DEPLOY-18). All have provisionals; recommendations below. Two carry a binding condition (DET-02, CP-02-01) and one is a real arbitration (SNAP-02). *Owner: Architect / SRE / Security in one review.*

**B. The money/legal/policy questions are ANSWERED** (§8 Q1–Q4, 2026-06-03): **delay** all new front-ends (FE-01/02), **keep** OWASP fetch-on-demand (CORP-18), **keep** the GitHub process shims (DEPLOY-17), **defer** the corpus sourcing campaign (CORP-05/19/03). All four to the safe default — no new spend in v3.2.

**C. The legacy-v2 questions are ANSWERED** (§8 Q5–Q6): no v2 artifacts available → **rescope/defer** `AC-SCM-02b` + `AC-DET-03b` (SCM-01 + MIGRATION-973); launch is **new-environment-only** (MIGRATION-931).

**D. Note the three findings** (not decisions): SNAP-02 (schema arbitration), SCM-02 (ADO webhook bug + free fix), CP-02-01 (KMS error-path bug). These need an engineering follow-up, framed below.

**E. Two register defects** (§10) — duplicate `CLAR-MIGRATION-01` id; stale `CLAR-TRI-01` status — are one-line `/sync-wbs` fixes, not team decisions.

**What is already safe while undecided:** every language beyond Java+Python is honestly `front-end-blocked` (INV-6, no inflated recall); all undecided thresholds are fail-closed; the corpus scaffolds are versioned and explicitly *not* claimed as gate-strength; the GPL corpus ships fetch-on-demand (no copyleft exposure).

---

## 2. Group A — Architect / CTO (algorithm shape & scope; decidable now)

### CLAR-DET-01 — detector-registry persistence surface — **RR**
- **Plain question:** Should accepted detectors live in a SQL table, or stay as on-disk YAML loaded into memory (with accepted specs saved separately)?
- **Ruling:** **Ratify the provisional** — on-disk version-controlled YAML manifests (the source of truth) + in-memory `DetectorRegistry`; accepted DSL ASTs persist via `spec_versions.spec_set`. This satisfies AC-DET-02b's "persisted." A SQL `detectors` table is a purely additive upgrade for a later CLAR if dashboards need queryable rows.
- **Evidence:** `DOC-CMP-DET-02.md:179-191,289` (AC-DET-02b field list + "no DB writes"); `DOC-DB.md:276-298` (`spec_versions`, no detectors table); `detectors/registry.py:224-272` (loads `manifest.yaml` at startup).
- **Residual risk:** "Persisted" is read as on-disk-SoT + loaded registry, not a queryable row; a future admin-dashboard SQL/audit need is a separate additive CLAR, not a re-litigation.
- **Cross-links:** CMP-DET-02, CMP-CP-03; INV-1 (registry derives `determinism_partition`).

### CLAR-DET-02 — closure-check depth at registration — **RR-COND** (Security co-sign: APPROVE-WITH-CONDITIONS)
- **Plain question:** When a detector is registered, must the registry re-run the full distributivity proof, or is the lighter "engine/spec shape is consistent" check enough (trusting the DSL parser)?
- **Ruling:** **Ratify the narrower shape check as defense-in-depth — WITH a binding condition.** CMP-DET-01's `parse_spec` is the authoritative INV-4 distributivity gate; `closure_check` is a consistency re-check, not a re-parse. **But the Security co-sign found the architect's stated justification is factually wrong:** `parse_spec` is on every *production* path (`load_manifests`→`_build_detector`→`_load_core_spec`→`parse_spec`), **not** on the public `register()` API path (which runs only the shape-only `closure_check`). A caller-built `Spec` can today carry **unparsed escape-hatch pattern content** (raw regex / embedded `semgrep`/`lambda` text in an `AccessPathPattern`) past `register()` → a one-sided INV-4 false negative.
- **Mitigant (verified, narrows the risk):** the `Clause` grammar (`Source|Sink|Sanitize|Propagate`, `primitives.py:70`) has no sequencing/conditional/fixpoint node, and `compose:clause_union` is a discharged distributivity obligation (`proofs.py:45,124-133`), so a hand-built `Spec` **cannot encode a non-distributive composition** — the residual surface is unparsed pattern content only, not arbitrary non-distributive specs.
- **Binding conditions (record with the ratification):** (1) Pin `parse_spec` as a registration-path invariant — either `register()` re-parses the carried core spec from source text, or `Spec` is made constructible only via `parse_spec` (parser-only constructor, which also closes the escape-hatch surface at the type level). (2) Add a `register()`-path negative test (`TST-INV-4-DET-01` gap): a core `Detector` carrying an escape-hatch `AccessPathPattern` built without `parse_spec` must be rejected — failing against today's code, passing after condition 1. (3) Correct the wording "parse_spec runs on every registration path" → "every *production* path; `register()` pinned by condition 1."
- **Evidence:** `detectors/registry.py:161-220` (`closure_check` shape-only), `:266,441` (production parse), `:291,303` (public `register()` → shape-only), `:241-243`; `analysis/ifds/dsl/spec.py:65`, `primitives.py:26-28,70`, `proofs.py:45,124-133`; `DOC-CMP-DET-02.md §3.3`; `tests/unit/test_det_specs.py:745` (existing falsifier parses text directly, does **not** exercise the `register()` path).
- **Cross-links:** CMP-DET-02, CMP-CORE-01; **INV-4**; RULE-9 (Security sign-off — delivered: APPROVE-WITH-CONDITIONS).

### CLAR-CP-01-01 — is the API guard an INV-2 emitter? — **RR**
- **Plain question:** Does the scan-API guard need its own "did it stamp the version fields" test, or does that obligation belong downstream where findings are actually created?
- **Ruling:** **Ratify the provisional** — CP-01 is a non-emitting routing/authz guard; it never constructs a `Finding`, so it stamps no `S_version`/`env_digest` and is **not** an INV-2 emitter. The obligation is discharged at CMP-ORCH-03 / CMP-FND-01..03. `validate_s_version` checks an *input* and warrants a negative AC test (unknown `S_version` → 422), not a `TST-INV-2` emitter test.
- **Evidence:** `DOC-CMP-CP-01.md:128-146` (`validate_s_version` validates input, forwards to ORCH-01), `:204` (DOC lists INV-2 + `TST-INV-2-CP-01 [FORTHCOMING]`); `WBS.md §14` (CP-01 not in the INV-2 emitter table); `.claude/rules/02-provenance.md`.
- **Residual risk / doc-hygiene:** This ruling makes `TST-INV-2-CP-01 [FORTHCOMING]` a phantom obligation — retire it from DOC-CMP-CP-01 §204 on ratification.
- **Cross-links:** CMP-CP-01 test scope; INV-2 (N/A at this layer).

### CLAR-SNAP-02 — `snapshots` table: async state-machine vs shipped terminal-record schema — **ARB**
- **Plain question:** Two documents describe the `snapshots` table differently — one with a job-progress state machine, one a simpler completed-record shape already shipped in the migration. Which is the real contract?
- **Ruling (arbitrated by the source-of-truth hierarchy):** **The shipped schema (DOC-DB §4.7) is canonical; the DOC-CMP-SNAP-01 §3.3/§4.4 state machine is the corrected document, not the schema.** Four supports: (1) DOC-CMP-* is the lowest authority (CLAUDE.md §1); the state machine appears *only* there and contradicts both its parent SDD and the sibling DOC-DB. (2) SDD ACs SNAP-01a/b/c require only the five artifacts + a precondition-status of exactly one of three values + `env_digest` — **no AC requires a `state` column**. (3) The shipped `precondition_status` **NOT NULL + CHECK** *mechanically forbids* a `queued`-state insert (the hardest evidence — the schema can't represent the state machine). (4) SDD §97 "enqueues a snapshot job" genuinely licenses async, but job *progress* lives off-row (ORCH-01's `POST /api/v1/jobs/{job_id}/status`); `snapshots` is a terminal artifact record (single-insert when verdict + 5 URIs are known). The `GET /snapshots/{id}/status` surface is served by row-existence (absent ⇒ 202; present ⇒ ready), no `state` column needed; no AC tests it.
- **Evidence:** `db/migrations/versions/20260524_0001_initial_tenancy_tables.py:172-208` (NOT NULL `precondition_status` + CHECK; no `state`/`snapshot_digest`/`completed_at`); `DOC-DB.md:233-255` (§4.7 matches the migration); `DOC-CMP-SNAP-01.md:108-127,186-210,234-248` (the outlier state machine); SDD §95-101,§284. Corroboration: `snapshot_digest` already lives on `provenance_records:487` — off-row is its right home.
- **Residual risk:** The unbuilt CMP-SNAP-05 `report_status` callback (state machine + `snapshot_digest` persistence) is a **separate future decision** — off-row tracking vs a deliberate CP-03 migration amendment — and must not be re-litigated as this same conflict. This ruling **unblocks CMP-SNAP-05 design**.
- **Cross-links:** CMP-SNAP-01, CMP-SNAP-05; overlaps CLAR-API-01's `/api/v1/jobs/{job_id}/status` callback. **Needs architect/CTO sign-off (PLAN/SDD arbitration).**

### CLAR-CP-06-01 — persist fidelity verdicts to Postgres, or JSON-only? — **RR-CONFIRM**
- **Plain question:** Should per-language CPG-fidelity gate results go into a DB table (for dashboards/trends), or is the existing JSON file enough?
- **Ruling:** **Keep JSON-only; ratify it canonical for v3.2.** No in-scope AC or consumer needs a table: AC-CP-06b is satisfied by JSON literally; `/stage-gate` and `/sync-wbs` read the JSON; CP-04 has no fidelity-trend view. A `fidelity_results` table is justified only by a *future* product capability and is a pure additive, JSON-backfillable migration — so deferring costs nothing.
- **Confirm (missing data):** whether the product roadmap commits to historical/per-customer fidelity-trend dashboards. This does **not** make it HUMAN-DECIDES — the fact governs only a *future* additive CLAR, not today's ruling.
- **Evidence:** `DOC-CMP-CP-06.md:146-175` (JSON "canonical persistence surface for v3.2"); `DOC-DB.md §4` (no table); `DOC-CMP-CP-04.md` (no fidelity-trend view).
- **Cross-links:** CMP-CP-06; CMP-CP-04 (future readiness view); INV-6.

### CLAR-API-01 — align two API URLs under `/api/v1/`? — **RR**
- **Plain question:** Two endpoints use inconsistent prefixes (`POST /snapshots` vs `/api/v1/...`). Unify now?
- **Ruling:** **Ratify the provisional — SDD paths stand; revisit pre-GA.** The inconsistency is real but internal to the normative SDD; the architect can't rewrite SDD paths (SoT fence); it blocks nothing. Lowest priority of the six. *(Do not elevate to ARB — there is a provisional and the fix is out of architect write-scope.)*
- **Evidence:** `DOC-API.md:541-546` (§9, "Blocks: none"); SDD §97 vs §193 (the split is internal to SDD).
- **Cross-links:** overlaps SNAP-02's off-row progress callback; no INV touched.

---

## 3. Group B — CTO / Business (money, licensing, vendor)

> Four of five are **HUMAN** (asked in §8 Q1–Q3); each is framed there with options + a recommended default. DEPLOY-18 is a CTO formality ratification.

### CLAR-FE-01 — Ruby/PHP front-end: build / buy / delay — **HUMAN** (§8 Q1)
- Recommended default: **Delay** (keep oracle-passthrough) for v3.2 — no Stage-D customer committed; Java+Python core is the deliverable; the honest `front-end-blocked` default (INV-6) is already safe. Build = sustained FE headcount over multiple cycles; Buy = recurring license + integration + a new `Env` digest to pin; both must still clear CMP-CP-06.
- **Evidence:** `.claude/rules/04-staging.md:30-35`; `PLAN.md:138`; `WBS.md:928`. **Cross-links:** gates Stage D; sits above CORP-15/16 (Ruby/PHP corpora).

### CLAR-FE-02 — Go front-end points-to investment scope — **HUMAN** (§8 Q1)
- Recommended default: **Andersen-style baseline *if/when* Go is funded** — cheapest path to clear the fidelity gate; richer (context/field-sensitive) analysis is an upgrade only if the baseline misses the gate. No schedule pressure: Go's CMP-CP-06 is itself gated by CLAR-CORP-14 (Go corpus N), so there's no near-term critical path forcing the spend.
- **Evidence:** `.claude/rules/04-staging.md:24-28`; `PLAN.md:137`; `WBS.md:929`. **Cross-links:** gates Stage C; depends on CMP-CP-06 Go (CLAR-CORP-14).

### CLAR-CORP-18 — vendor GPL-2.0 OWASP BenchmarkJava, or keep fetch-on-demand — **HUMAN** (§8 Q2)
- Recommended default: **Keep fetch-on-demand** — pinned commit + `upstream_sha256` gives deterministic ground truth with **zero copyleft exposure**, so there is no legal reason to vendor; the only cost is upstream-availability (made verifiable by the sha256 pin). Vendoring GPL-2.0 into a product repo is a legal/copyleft sign-off, not an engineering call.
- **Evidence:** `WBS.md:958`; `tests/corpora/vuln/LICENSES.md`; `tests/corpora/vuln/corpus.lock:14-17`; `DOC-CMP-CORP-VULN-01.md:172`. **Cross-links:** **gates the OWASP portion of CORP-19** (Juliet/BigVul unaffected). **Doc defect (noted):** `DOC-CMP-CORP-VULN-01.md:172` prose elsewhere mislabels OWASP as "Apache-2.0/GA-cleared," contradicting the authoritative GPL-2.0 record (CLAR row, `LICENSES.md`, `corpus.lock`) — a doc-agent correction.

### CLAR-DEPLOY-17 — native branch protection (paid plan / public repo) vs process shims — **HUMAN** (§8 Q3)
- Recommended default: **Keep the process-level shims** through v3.2 — they already deliver fail-closed, highly-visible enforcement at no cost; wiring native protection is a one-step change once the org is on Team for other reasons. Live alternatives: upgrade to GitHub Team/Pro (recurring per-seat cost) or make the repo public (source-disclosure of a proprietary SAST platform — a product/security call). Due before Stage-A go-live per RULE-8.
- **Evidence:** `WBS.md:920`; `DOC-CMP-CI-01.md:66-70`; `DOC-CMP-DEPLOY-04.md:78-80`; `.github/workflows/enforce-pr-only-merges.yml`; RULE-10.

### CLAR-DEPLOY-18 — production IaC under DEPLOY-01 or first task of DEPLOY-02 — **RR** (CTO sign-off)
- **Ruling:** **IaC as the first task of CMP-DEPLOY-02.** The CTO already approved deferring IaC from the DEPLOY-01 AC (PR #238, 2026-05-25); all 16 CLAR-DEPLOY-* substrate decisions are RESOLVED; DEPLOY-02 is the package that first provisions real AWS. Ratifying this cleanly closes issue #3. Pure work-sequencing, no new money/scope — **but the register says "requires CTO ratification before Phase 4," so record it as a CTO sign-off, not a silent decision.**
- **Evidence:** `WBS.md:921`; `services/substrate/` (contract present); empty `infra/`; `DOC-CMP-DEPLOY-04.md:78`. **Cross-links:** CMP-DEPLOY-02..05, CMP-SNAP-05.

---

## 4. Group C — SRE / DevOps (operational thresholds)

> All seven are agent-recommendable; none is HUMAN. Two are RR-CONFIRM (no capacity/empirical baseline). One carries an **inversion** flag (CP-05-02). Two need **Security co-sign** (CP-04-01, DB-02 — delivered in §5).

### CLAR-SLA-02 — per-tenant rate-limit & LLM budgets — **RR-CONFIRM**
- **Ruling:** Ratify the DOC-API §7 **general-API** numbers as interim enforcement: **60 req/s sustained per org (bucket cap 120), 200 req/s burst for 5 s; `POST /api/v1/scans` 600/hr; `POST /snapshots` 1200/hr; webhooks uncapped/deduped; `429 rate_limited` on exceed.** For the **LLM RPM/TPD budget there is no proposed number** — set a conservative fail-closed interim (deny when unset) and pin real values at Stage-A go-live.
- **Missing data:** (a) LLM RPM/TPD numbers don't exist anywhere (need the Anthropic per-account quota under CLAR-DEPLOY-14 + expected per-tenant triage volume); (b) even the general-API numbers carry no capacity-planning basis (tenant concurrency, Fargate throughput, RDS/SQS headroom unmeasured). **The LLM budget has a cost dimension** — surfaced to the human as an FYI (see §8 note), not blocking now because the fail-closed interim is safe.
- **Evidence:** `DOC-API.md:500-517` (numbers), `:507-513` (LLM TBD); `WBS.md:933`. **Cross-links:** CLAR-DEPLOY-14, CMP-CP-01.

### CLAR-CP-04-01 — Auth0 outage: degraded read-only vs fail-closed — **RR** (Security co-sign: fail-closed)
- **Ruling:** **Stay fail-closed — 503 + `Retry-After: 60`, no degraded read-only mode in v3.2.** Blast radius is the dashboard auth surface only: scan/worker execution uses the `system` role (BYPASSRLS), not Auth0 JWTs, so the deterministic core keeps running during an Auth0 outage — which is exactly why fail-closed is cheap here. (SRE owns the operational call; Security co-signs — see §5.)
- **Evidence:** `DOC-CMP-CP-04.md:246,258,323`; `DOC-DB.md:78-84` (`system` role). **Residual risk:** full dashboard read-unavailability during an outage; backstop = `Retry-After` + Auth0 SLA + OTel; core scanning unaffected. **Cross-links:** RULE-9 (Security).

### CLAR-CP-05-01 — oracle reproduction-rate alarm thresholds — **RR-CONFIRM**
- **Ruling:** Ratify the working assumption as interim: **OTel alarm when the rolling-7-day oracle reproduction rate < 99%; investigation ticket at < 95%; never a hard CI fail** (consistent with the two-pipeline contract). Keep both config-driven.
- **Missing data:** no empirical oracle reproduction baseline collected — the natural re-run variance of Semgrep/CodeQL under fixed `env_digest` is unmeasured, so 99%/95% are placeholders (parallels the κ/π₀ "calibrate in a named phase" posture). **Residual risk is bounded:** rate-only design means a mis-set threshold can't block a release or corrupt the core partition — it only tunes alerting; retune freely once a baseline exists.
- **Evidence:** `DOC-CMP-CP-05.md:78-79,267,339`; `.claude/rules/05-determinism.md`.

### CLAR-CP-05-02 — attestor CI cadence (every push to `main` vs path filter) — **RR (inversion: broaden)**
- **Ruling — recommend the *broadening*, not the status quo:** **Run the core attestor pipeline on every push to `main`** (drop the `paths:` restriction for `main`; keep `paths:` on `pull_request` for PR-cost economy; add `workflow_dispatch`). A determinism gate whose trigger filter can't be *proven* to capture every `Env` input (tool-digest pins editable in `infra/` or anywhere outside the filtered paths) is effectively **fail-open**. Fail-closed = the trigger that cannot miss an Env change. A *provably-complete* `paths:` filter is a valid later optimization once that file-set is enumerated.
- **Evidence:** `.github/workflows/attestor.yml:5-13` (filter omits `infra/`); `DOC-CMP-CP-05.md:41,70` (AC-CP-05c "every Env change"); `CLAUDE.md §2/§4` (`Env` = image + tool digests); `WBS.md:945`.

### CLAR-CP-06-02 — hard-enforce fidelity-gate env_digest match — **RR** (bootstrap caveat)
- **Ruling:** **Ratify hard-enforce (fail-closed):** the gate fails if its `env_digest` ≠ the pinned production worker image — a verdict on a non-production `Env` can't back a production INV-6 claim. **Bootstrap caveat:** the comparison target (the production `env_digest`) doesn't exist until CMP-SNAP-05 publishes the worker image, so until then the check is **record-and-warn**; flip to hard-fail the moment the production digest is pinned.
- **Evidence:** `DOC-CMP-CP-06.md:188,290,304,364,383`. **Cross-links:** CMP-SNAP-05 (env_digest source); INV-6; RULE-7.

### CLAR-DB-02 — Postgres RLS session-variable scheme — **RR** (Security co-sign: APPROVE-WITH-CONDITIONS)
- **Ruling (operational angle):** **Ratify the §3.2 scheme** (`app.org_id`/`app.user_id`/`app.role`, `SET LOCAL` per checkout, `current_setting('…', true)` template). Operationally sound: the §3.4 pool guard makes a forgotten `SET LOCAL` fail *closed* (NULL → zero rows, integration-tested), and `SET LOCAL` scopes vars to the transaction so they can't leak across pooled connections. SRE owns DB-ops; **Security co-signs the privilege boundary — APPROVE-WITH-CONDITIONS (see §5).**
- **Evidence:** `DOC-DB.md:70-107` (§3.2-3.4); `WBS.md:935`. **Cross-links:** CMP-CP-01, CMP-CP-03, CMP-DEPLOY-05; RULE-9.

### CLAR-SARIF-01 — public hosting URL for the SARIF-extension schema — **RR**
- **Ruling:** **Vendor the schema file locally now** (check it into the CI gate's schema dir); keep `https://schemas.scanipy.io/sarif-extension/v1.0.0.json` as the schema `$id` (an identifier, not a fetch dependency). CI validates against the vendored copy → the SARIF gate is unblocked today; standing up the public URL is a pre-GA task (only needed if external consumers dereference `$id` over the network).
- **Evidence:** `DOC-SARIF.md:343,345,351,396-406`; `WBS.md:936`. **Residual risk:** if the public URL is later stood up with different content, `$id`/content diverge — pin the public URL to the byte-identical vendored content at GA.

---

## 5. Group D — Security (sign-offs)

### CLAR-CP-02-01 — KMS decrypt-failure taxonomy — **RR-COND** (real bug found)
- **Plain question:** Add boto3 `ClientError` introspection + a `ThrottlingException` retry to honour DOC §7's 3-way 403/500/503 taxonomy, or narrow DOC §7 to the current fail-closed catch-all (every opaque KMS error → `TenantIsolationError`/403)?
- **Load-bearing finding (a real bug, not just a wording choice):** DOC §7's documented **500 (missing-key) and 503 (throttle) paths do not execute against real boto3 KMS today.** The code has one `try/except`: re-raise typed `CredentialEncryptionError`, else catch-all → `TenantIsolationError`; there is **no** `ClientError` introspection and **no** retry/backoff. CI is green only because the test **fake** pre-raises typed `KMSKeyMissingError` (`test_credential_encryption.py:78,92,109-110`); a real `botocore.ClientError` (`NotFoundException`/`ThrottlingException`) falls into the catch-all and is **mislabeled 403**. The API error table has no `KMS_UNAVAILABLE`/`KMS_KEY_MISSING` codes to map to at all.
- **Ruling (Security is the authority):** **Narrow DOC §7 toward fail-closed — WITH one mandatory code split.** The throttle-retry/503 limb is an availability concern the SRE may defer (fail-closed never leaks; a transient throttle just fails the op, recoverable upstream) — narrowing it is RULE-4-safe. **But** the missing-key case **must** be classified separately from the tenant-isolation case: collapsing them launders an operational fault (deleted CMK) into `tenant_isolation_violation`/403, which is the platform's **cross-tenant-attack alarm** (DOC §7 emits a WARN OTel event) — polluting the forensic channel with false positives and letting a real probe hide in noise. Neither fork leaks plaintext; the fine-grained path introduces no usable error-oracle (the distinctions are KMS control-plane states, not secret-dependent; the only attacker-reachable limb stays an opaque 403).
- **Records as follow-up work (this is a hybrid, not a clean ratify):** (1) split `NotFoundException` → `KMSKeyMissingError` (operational, page SRE) out of the tenant-isolation event; (2) add a **botocore-`ClientError`-shaped positive/negative test** so the real-client classification is proven (the typed-fake masks it); (3) record the throttle-retry/503 disposition (defer or implement) in DOC §7. SRE owns the availability/retry sub-decision.
- **Evidence:** `DOC-CMP-CP-02.md:283-285,288`; `services/credential_encryption.py:240-255`; `services/control_plane/constants.py:39-48` (no KMS codes); `tests/unit/test_credential_encryption.py:78,92,109-114` (typed-fake masking). **Cross-links:** RULE-9; team memory *green tests can pass a broken impl* / [[falsifier-gates-need-math-review]].

### CLAR-DB-02 (security co-sign) — **APPROVE-WITH-CONDITIONS**
The RLS scheme is sound for tenant isolation (per-table RLS; missing GUC → NULL → zero rows = fail-closed). Conditions for full approve: **(1) `SET LOCAL`, never `SET`** — mandatory, not stylistic: a plain `SET` persists the GUC onto a pooled connection so the next tenant inherits the prior `app.org_id` → cross-tenant read; require every checkout inside a transaction + an integration test that a *recycled* pooled connection with no fresh `SET LOCAL` reads **zero** rows. **(2) `BYPASSRLS` only on the dedicated `scanipy_system` role** — the request-path app role must be distinct and non-BYPASSRLS, and must not be able to flip itself to `app.role='system'`. **(3) `scanipy_triage` non-BYPASSRLS** and unable to widen its own grants (its `REVOKE ALL ON findings` is an INV-3 control, orthogonal to tenant isolation, and still needs the same `SET LOCAL` discipline). *Evidence:* `DOC-DB.md:70-107,296-301,476-479`; `services/control_plane/constants.py:13-15`; `guard.py:140-197`.

### CLAR-CP-04-01 (security co-sign) — **fail-closed is the Security-recommended default**
Serving on cached-JWT validation past JWKS TTL "would risk JWT-revocation bypass": a token revoked during the outage (deprovisioned user, compromised session, role downgrade) keeps reading tenant findings/provenance for the outage duration — an unbounded confidentiality regression. A safe read-only mode would minimally need an **outage-resilient revocation channel** (a server-side revocation list checked per request) — effectively unsatisfiable when the whole premise is "Auth0 is unreachable." **Recommend: ratify fail-closed (503); keep CLAR-CP-04-01 open as a post-GA enhancement gated on a revocation-channel design.** *Evidence:* `DOC-CMP-CP-04.md:246,258,323`.

---

## 6. Group E — Corpus / Data (test-corpus sourcing)

> **Standing discipline:** ratifying a target `N`, a scoring rule, or a ground-truth method does **NOT** flip CMP-CP-06 to GATE-PASS. v0.1.0 corpora stay versioned scaffolds, explicitly *not* gate-strength; every non-Java/Python language stays `front-end-blocked` (INV-6); dependent gate tests stay xfail / non-authoritative until both (a) the pinned ground-truth toolchain lands and (b) the sourced real-OSS floor is met. These gate **language coverage beyond Java+Python**, never the core engine. (`CLAR-CORP-01` is already RESOLVED — N≥50/reflection-category — and is the accepted-bar precedent, not re-proposed.)

**The cut:** only **three** items are genuinely HUMAN (budget/headcount): **CORP-05 + CORP-19** (sourcing budget — one campaign) and **CORP-03** (named reviewer). Everything else is **RR — propose a concrete answer the human ratifies in one stroke.** Per-language N's are framed for **Corpus-lead + CTO ratification** (the CORP approver rule).

### Ratifiable now (RR)
| CLAR | Proposed ruling (RR) | One residual risk |
|---|---|---|
| **CORP-04** (reflection scoring) | **Score separately** — mutation-injected items do NOT substitute toward the per-category hand-curated N≥50. Rationale = the CORP-06 finding (mutation seeds collapse to ~1–3 distinct trees; counting near-duplicates would inflate the Gate-2/INV-4 safety claim). | If overridden, the zero-FN claim rests on ~1–3 trees masquerading as ~20 — tie this ruling to CORP-06 being fixed. |
| **CORP-06** (reflection generator) | **Yes** — v1.0.0 generator must make `seed` produce structurally-distinct trees (vary call-context/identifiers/nesting/dispatch shape); add a lock-level `distinct_trees` count. A buildable engineering acceptance criterion, not a budget. | Until fixed, mutation-track power is ~1–3, not 20; ratifying ≠ gate-strength. |
| **CORP-08** (Java JDK) | **Pin JDK 17** as the v1.0.0 extraction baseline (matches DOC + Stage-A worker image); accept v0.1.0 `-source 17` compile-under-21 as a valid interim. | Compiling under 21 can admit a 17-incompatible construct if `-source 17` is dropped — pin 17 in the extraction image. |
| **CORP-10** (Java generated-code balance) | **Confirm ≥10%** (program-count denominator) and flip the WARN → hard refuse at v1.0.0 (≥⌈0.10·N⌉ generated-code programs). | Count denominator gameable by trivial stubs — pair with the edge-volume floor (CORP-09). |
| **CORP-17** (refactor topology) | **Propose N ≥ 24 distinct `(class, language, sink-topology)` cells** (8 current class×lang cells × ≥3 structurally-distinct sink topologies), scaling toward the 50-seed count as sourcing lands. Real-repo seed sourcing is the campaign. | Until expanded, `TST-AC-CORE-02a/b` must not be read as a 50-independent-topology falsifier (lock records `distinct_topologies: 8` honestly). |
| **CORP-09/13/14/15** (per-lang CPG N) | **Coverage-min ≥3 programs per construct-tag / module-system×surface / idiom cell** for Java/JS-TS/Go/Ruby (edge-power-aware; CPG metrics are edge-level, so power lives in edge count — a few *real* programs each carry thousands of edges). Sourced real-OSS floor = campaign. | Coverage-min ≠ gate-pass; languages stay `front-end-blocked` until toolchain + sourced floor land. |
| **CORP-07/11/12** (CPG toolchains) | **Document the v0.1.0 method now** (in-repo extractor for Python/JS-TS; by-inspection for Java) as the explicitly **non-authoritative** v0.1.0 ground truth; **lean: provision the pinned tools** (Soot/WALA; scalpel/Pyan3/Pyre on py3.10; Jelly 1.4 + tsc) for v1.0.0 gate authority — build-env work, part of the campaign. | "Ratify the extractor" must NOT read as "gate numbers are trustworthy"; CP-06 verdicts on v0.1.0 ground truth stay non-authoritative. |

### RR-CONFIRM
- **CORP-16** (PHP) — the per-axis **N is RR** (≥3 programs/dynamism-axis + framework distribution Laravel/Symfony/WordPress/pure-PHP ∝ prevalence); the **PHP worker-image digest cannot be stated** — it doesn't exist until CMP-SNAP-05 publishes the PHP worker image (the BUT-CONFIRM). *Evidence:* `php/methodology.md §1`; `WBS.md:960`.

### HUMAN (asked in §8 Q4)
- **CORP-03** — name a second reviewer for the reflection dual-review, or fold into CLAR-OWNER-01 (Part 3). Headcount; the reviewer must be distinct from the corpus builder. (`reflection/corpus.lock:4` shows `hand_curated_second_pass: 0` everywhere.)
- **CORP-05 + CORP-19** — fund **one** multi-PR sourcing campaign (reflection bulk-source ~800 items + CPG real-OSS sourced floors across 5 languages + refactor real seeds + real Juliet/BigVul + OWASP pending CORP-18). The split methodology + never-train-on-held-out machinery is *already built and sound* (`bigvul_heldout/heldout_split.lock`: deterministic `sha256(row_id)%10==9`, `disjoint_assertion`); what's missing is **scale**, which is money + people.

**Campaign summary (one go/defer call):** real OSS sourcing + license screening + dual review to lift the v0.1.0 scaffolds to gate-strength, covering reflection (CORP-05, needs CORP-03), CPG sourced floors (CORP-09/13/14/15/16) + toolchain provisioning (CORP-07/11/12), refactor topologies (CORP-17), and vuln scale-up (CORP-19, OWASP portion gated on CORP-18; Juliet/BigVul proceed regardless). **Defer is safe** — every corpus stays an honest scaffold, every non-Stage-A language stays `front-end-blocked`, all dependent gate tests stay xfail. The per-N/method/scoring ratifications above are independent and can be cleared now without funding.

---

## 7. Group F — External / legacy-v2 information

### CLAR-SCM-01 — location of the legacy v2 GitHub connector — **HUMAN** (§8 Q5)
- **What's missing:** the byte-for-byte regression baseline for `AC-SCM-02b` (retry/rate-limit/tiered-star behaviour preserved verbatim). `SDD.md:71` + `WBS §5` presume `integrations/github/github.py` (legacy v2) exists — it does not. It lives in v2 git history / a vendored copy / a golden-fixture archive, with whoever has v2 access.
- **In-repo evidence (absence confirmed):** the only `github.py` is the *fresh* v3.2 `integrations/scm/github.py`; the compat shim `integrations/github/__init__.py:62-71` `_v2_argv_shim` raises `NotImplementedError("v2 argv adapter pending CLAR-SCM-01 baseline capture")`; `DOC-CMP-SCM-02.md:248,257`.
- **What the human must supply / decide:** name & supply the v2 baseline, **or** rule that `AC-SCM-02b` is rescoped (the DOC §3.5 shape contract becomes binding) if no baseline is recoverable. *(`AC-SCM-02c` shape contract is independently dischargeable, not blocked.)*

### CLAR-SCM-02 — Azure DevOps webhook signature — **ARB** (reclassified; a bug found)
- **Finding (settled by public Azure docs, no longer a "find the header" lookup):** native Azure DevOps "Web Hooks" service-hooks emit **no per-delivery HMAC body signature and no signature header at all** — only HTTP Basic auth (`basicAuthUsername`/`basicAuthPassword`) + optional *static* headers. So the spec premise that ADO "pins HMAC-SHA-256 over the body" is **unrealizable on native ADO**. `X-Vss-Activityid` is a correlation id, not a signature.
- **The bug to surface (a finding, not a question):** the implemented interim `verify_webhook` (`integrations/scm/ado.py:416-441`) requires `X-Hub-Signature-256: sha256=<hmac>` — which native ADO never sends — so it would **reject every genuine native ADO delivery**. `AC-SCM-03b` (forgery rejection) passes **vacuously**: a negative-only test can't detect that the verifier also rejects all legitimate traffic.
- **Recommended ruling (Architect + Security — free, native, no infra):** verify ADO deliveries by the **shared secret echoed in `basicAuthPassword`** (a secret-equality check, the GitLab `X-Gitlab-Token` pattern). `register_webhook` already sets `consumerInputs.basicAuthPassword = secret` (`ado.py:362-384`), so the realizable option is already wired — change `verify_webhook` to read the Basic-auth credential instead of an HMAC header, correct the spec's "pins HMAC-SHA-256" wording, and **add a positive-control test** (a genuine ADO-shaped delivery must *verify*). It becomes a HUMAN cost question *only* if the architect instead chooses a signing-proxy (which the secret-equality option makes unnecessary).
- **Evidence:** `DOC-CMP-SCM-03.md:102-104`; `DOC-API.md:74`; `ado.py:23-26,362-384,416-447`. Public: Microsoft Learn "Webhooks with Azure DevOps" / "Service Hook Consumers" (no signature option; signing-proxy is the documented workaround). **Cross-links:** CMP-SCM-03 (ADO only; GitLab/Bitbucket unaffected); RULE-9 (Security).

### CLAR-MIGRATION-01 (row ~931) — is v2→v3.2 DATA migration in scope? — **HUMAN** (§8 Q6)
- **Plain question:** At launch, must we carry over existing v2 customer data (past findings, codebase membership, stored credentials), or is v3.2 a fresh start?
- **Status:** business decision contingent on whether any v2 customer migration is contractually committed + v2 prod-data state. Default = **new-environment-only** (`WBS.md:931`). No migration code exists (correct — none should until ruled in). If committed: scope the findings/membership/credential migration (incl. credential re-encryption under the new KMS envelope) before Phase 11.

### CLAR-MIGRATION-01 (row ~973) — legacy detector artifacts + CVE baseline — **HUMAN** (§8 Q5) · *duplicate ID*
- **What's missing (three external artifacts, all absent):** (1) legacy `tarslip.yaml` path-traversal taint defs; (2) C/C++ memory-safety CodeQL `*.ql`/`*.qll`; (3) the **CVE-2025-61765 baseline** = the Stage-A repo commit the historical scan ran against + the canonical witness to assert. All live with v2 detector-content access.
- **In-repo evidence:** no `*.ql`/`*.qll` anywhere; `tarslip.yaml` only *referenced* (`PLAN.md:159`, `SDD.md:154`, `DOC-CMP-DET-03.md:33,82-100`, `tests/unit/test_det_specs.py:736 # TODO: CLAR-MIGRATION-01`); CVE only a *target* (`SDD.md:157,197`; `tests/integration/test_orch_specs.py:64-89` stub). `WBS.md:973`.
- **Also blocked on build order:** `AC-DET-03b` needs the unbuilt CMP-CORE-01 + CMP-ORCH-01 to run a real Stage-A scan — a sequencing fact, not a decision. CMP-DET-03 ships the scaffold (`AC-DET-03a`) only.
- **What the human must supply:** locate `tarslip.yaml`, the CodeQL queries, and the CVE baseline (commit + witness) — or accept they're permanently unavailable and rescope `AC-DET-03b`.

---

## 8. Human decisions — pending your input

> These six commit money, legal sign-off, headcount, or depend on a fact outside this repo. Per RULE-4, an agent may not invent them. Each carries a **recommended default**. *(Answers are recorded here once given; they are NOT written into `WBS.md §17` unless you ask for that follow-up.)*

| # | Question (plain) | Options (recommended first) | **Your decision (2026-06-03)** |
|---|---|---|---|
| **Q1** | Fund new language **front-end** work (Go / Ruby / PHP) now, or delay? (FE-01, FE-02) | **Delay all** · Fund Go baseline only · Fund Go + Ruby/PHP | ✅ **Delay all** — Go/Ruby/PHP stay oracle-passthrough (`front-end-blocked`, INV-6); FE-01 + FE-02 remain DEFERRED; no spend. |
| **Q2** | **GPL license** — keep OWASP BenchmarkJava as fetch-on-demand, or vendor the GPL-2.0 content? (CORP-18) | **Keep fetch-on-demand** · Approve vendoring GPL-2.0 | ✅ **Keep fetch-on-demand** — no GPL vendored; pinned commit + sha256 stands; CORP-18 resolvable as fetch-on-demand (no copyleft exposure). |
| **Q3** | **GitHub plan** — process shims, paid upgrade, or public repo? (DEPLOY-17) | **Keep shims** · Upgrade to Team/Pro · Make repo public | ✅ **Keep process shims** — fail-closed loud-red-check enforcement at no cost; wire native protection if/when the org upgrades for other reasons. |
| **Q4** | **Corpus sourcing campaign** — fund now or defer past Java+Python? (CORP-05, CORP-19, CORP-03) | **Defer** · Fund now | ✅ **Defer** — the whole campaign (incl. the CORP-03 second reviewer) waits; scaffolds stay honest, languages stay `front-end-blocked`, dependent gate tests stay xfail; CORP-03 rolls into CLAR-OWNER-01. |
| **Q5** | **Legacy v2 artifacts** — can you supply them? (SCM-01, MIGRATION-973) | Yes · **No — rescope/defer** · Some | ✅ **No — rescope/defer** — no v2 artifacts available; `AC-SCM-02b` (byte-for-byte) and `AC-DET-03b` (`tarslip.yaml`/CodeQL migration + CVE-2025-61765) rescope to their shape contracts / defer; nothing faked (RULE-4). |
| **Q6** | **v2→v3.2 data migration** — committed, or new-env-only? (MIGRATION-931) | **New-environment-only** · A migration is committed | ✅ **New-environment-only** — no v2 data carried; MIGRATION-931 resolvable as new-env-only; no migration work scoped. |

**All six human decisions resolved to the recommended safe default** — nothing here commits new money, legal exposure, or headcount in v3.2.

**FYI (not a blocking question, still open):** the **LLM rate-limit budget** (RPM/tokens-per-day) under CLAR-SLA-02 has a real cost dimension and no proposed number — the fail-closed interim is safe, but real numbers need your capacity/cost input before Stage-A go-live.

---

## 9. Cross-cutting dependencies & co-signs (don't double-record)

- **DB-02** and **CP-04-01** each need **both** SRE (operational) **and** Security (co-sign) — recorded once, with SRE owning the decision and Security's verdict folded in (§4 + §5). Don't record them twice.
- **DET-02** needs **Security co-sign** (RULE-9/INV-4) — delivered: APPROVE-WITH-CONDITIONS (§2). Do not present DET-02 as fully ratified until its binding condition is tracked.
- **CP-02-01** is the Security authority's call but **spawns SRE follow-up** (throttle-retry disposition).
- **CORP-18** (CTO/legal) **gates the OWASP portion of CORP-19**; Juliet/BigVul are independent.
- **CORP-03** depends on **CLAR-OWNER-01** (Part 3) if not named directly.
- **CP-06-02** hard-enforce and **CORP-16** PHP digest both **bootstrap on CMP-SNAP-05** (production worker image / digest).
- **FE-02** (Go) sits behind **CORP-14** (Go corpus N); **FE-01** (Ruby/PHP) above **CORP-15/16**.
- **SNAP-02** ruling **unblocks CMP-SNAP-05 design**; its `report_status` callback is a separate downstream decision.

---

## 10. Register defects spotted (noted, NOT fixed — read-only, per Part 4)

1. **Duplicate `CLAR-MIGRATION-01` id** — `WBS.md:931` (v2 data migration) and `WBS.md:973` (legacy detector artifacts) are two different questions under one id. Recommend renumbering the detector-artifact row → **`CLAR-MIGRATION-02`**. *(OPEN-DECISIONS Part 4 item 1.)*
2. **Stale `CLAR-TRI-01` status** — notes say "resolved-with-PR-255" (merged) but status still reads `OPEN`; should flip to `RESOLVED`. *(Part 4 item 2.)*
3. **`TST-INV-2-CP-01 [FORTHCOMING]` phantom** — made vestigial by the CP-01-01 ruling; retire from `DOC-CMP-CP-01 §204`.
4. **`DOC-CMP-CORP-VULN-01.md:172`** prose mislabels OWASP as Apache-2.0/GA-cleared, contradicting the authoritative GPL-2.0 record — doc-agent correction.
5. **`DOC-CMP-DET-02 §3.2`** says `load_manifests` "calls register(...)"; the code calls `closure_check` directly (no invariant lost) — one-line wording fix.
6. **`DOC-CMP-SCM-03 §3.3` / `DOC-API §2.4`** "pins HMAC-SHA-256" for ADO is unrealizable — correct under the SCM-02 ruling.

These are one-line `/sync-wbs` / `/doc-agent` edits, not team decisions.

---

## 11. Governance boundary & next steps

- **This memo does:** produce the Part-2 decision record; ground every item in repo evidence; classify human-vs-ratifiable; frame the §8 questions.
- **This memo does NOT:** edit `PLAN.md`/`SDD.md`/`WBS.md`; flip any `CLAR-*` status; change a verbatim AC; write production code.
- **Ratification path:** Architect rules on group A (DET-01/02, CP-01-01, SNAP-02, CP-06-01, API-01) + the SCM-02 design; SRE ratifies group C; Security signs DET-02/DB-02/CP-04-01/CP-02-01 (RULE-9); CTO answers §8 Q1–Q4 and signs DEPLOY-18; product/v2-access answers §8 Q5–Q6.
- **After the §8 answers are recorded here:** on your go-ahead, the rulings can be written back into `WBS.md §17` (status flips + decision summaries) and the §10 defects fixed in one `/sync-wbs` + `/doc-agent` pass — a follow-up you trigger, not done unprompted.

---

*Decision record — PROPOSED. Ratify the group-A/C/D batch, answer §8, action the three findings (SNAP-02, SCM-02, CP-02-01), then record the rulings back into `WBS.md §17`.*

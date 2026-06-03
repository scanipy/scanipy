# Decision Record — Part 4: register defects (housekeeping)

**ID:** `DECISION-PART4` · **Prepared:** 2026-06-03 · **Author:** WBS-Sync / CTO role-agent analysis pass (read-only), advisor-reviewed
**Resolves (the housekeeping behind):** `docs/OPEN-DECISIONS-2026-06-02.md` **Part 4** (the two named register defects) **and** consolidates the four further defects surfaced in `docs/DECISION-PART2-2026-06-03.md §10`.
**Companion to:** `docs/DECISION-PARAM-01-kappa-2026-06-03.md` (Part 1 — κ/π₀) and `docs/DECISION-PART2-2026-06-03.md` (Part 2 — groups A–F). Same governance posture.
**Status:** **APPLIED 2026-06-03 — go-ahead given (option ①, "Fix all in one pass").** D-1..D-5 were applied to the working tree; **D-6 is HELD** pending the `CLAR-SCM-02` (ARB) ruling, exactly as flagged. See the **Apply log (§5a)** for the per-edit record. _As originally authored this memo edited no source-of-truth file and merely specified the exact patches; the application recorded in §5a was performed by the orchestrator on your go-ahead, separately from the memo's analysis. Changes were applied to the working tree only — not committed/pushed; they enter `main` through your normal PR + `claude-review` flow (RULE-10)._

> **One-paragraph summary.** Six register/doc defects, all verified at exact `file:line`. Two are the Part-4 named items (**duplicate `CLAR-MIGRATION-01` id**; **stale `CLAR-TRI-01` status**); four were surfaced in Part-2 §10 (CP-01 phantom test obligation, VULN-01 OWASP license mislabel, DET-02 `load_manifests` wording, ADO HMAC unrealizability). They are **not** team decisions — but they split into three authority tiers: one is a **pure status-code flip** (CLAR-TRI-01 `OPEN`→`RESOLVED`, individually safe, in normal WBS write-scope); one **needs explicit CTO/human sanction** (renumbering `CLAR-MIGRATION-01`→`-02` is a *content* edit to an existing id, **outside** the normally-allowed "§17 append / §18 append / status flip" write-scope, and it ripples into one code-comment re-point); and four are **doc-agent edits** outside WBS entirely. The single human question is *"apply now, or hold for one follow-up `/sync-wbs` + `/doc-agent` pass?"* — recommended: record the exact patches here, apply them in one human-triggered pass.

---

## 0. The ruling (what we are recommending, and who may apply it)

| # | Defect | Source | Fix | **Authority tier** |
|---|---|---|---|---|
| **D-1** | Duplicate `CLAR-MIGRATION-01` id (`WBS.md:931` data-migration sense vs `WBS.md:973` detector-artifact sense) | **Part 4 item 1** | Renumber the **detector-artifact row (973)** → `CLAR-MIGRATION-02`; re-point its **two** live references | **NEEDS-CTO-SANCTION** (id content-edit, outside normal WBS write-scope; ripples into a code comment) |
| **D-2** | Stale `CLAR-TRI-01` status (`WBS.md:975`): notes say "resolved-with-PR-255", status column reads `OPEN` | **Part 4 item 2** | Flip status column `OPEN` → `RESOLVED` | **IN-SCOPE WBS EDIT** (a pure status-code flip — CLAUDE.md §1; individually safe) |
| **D-3** | `TST-INV-2-CP-01 [FORTHCOMING]` phantom obligation (`DOC-CMP-CP-01.md:204`) | **Part 2 §10 item 3** | Retire only the `TST-INV-2-CP-01` clause; **keep** `TST-AC-CP-01a` | **doc-agent edit** (rests on the CP-01-01 RR ruling) |
| **D-4** | OWASP license mislabel (`DOC-CMP-CORP-VULN-01.md:172`): "OWASP (Apache-2.0) … are GA-cleared" | **Part 2 §10 item 4** | Correct OWASP → **GPL-2.0**, fetch-on-demand (CLAR-CORP-18); leave BigVul/Juliet unchanged | **doc-agent edit** (pure fact-correction) |
| **D-5** | `load_manifests` "Calls register(...) for each" (`DOC-CMP-DET-02.md:81`, §3.2) | **Part 2 §10 item 5** | Reword: `load_manifests` calls `closure_check(...)` directly, not `register()` | **doc-agent edit** (pure fact-correction) |
| **D-6** | ADO "pins HMAC-SHA-256" (`DOC-CMP-SCM-03.md:104` §3.3 + `DOC-API.md:74` §2.4) | **Part 2 §10 item 6** | Correct to the realizable scheme (basicAuthPassword secret-equality) | **doc-agent edit — GATED on the CLAR-SCM-02 ARB ruling being adopted** |

**Tier legend** (every defect carries exactly one):

| Tier | Meaning | Who may apply | CLAUDE.md basis |
|---|---|---|---|
| **IN-SCOPE WBS EDIT** | A pure status-code flip in a `WBS.md` row's status column. | `/sync-wbs` (or `/cto`), no extra sanction. | §1 "allowed WBS.md edits: … status-code flips (§1.2)". |
| **NEEDS-CTO-SANCTION** | A content edit to an existing `WBS.md §17` row (an id rename) — **not** an append and **not** a status flip, so outside the normally-allowed write-scope. | Only on explicit human/CTO OK. | §1 fence: appends + status flips only; an id rename is neither. |
| **doc-agent edit** | A `DOC-CMP-*` / `DOC-API` correction, outside WBS entirely. | `/doc-agent` (the doc-agent owns these files; writes no production code). | §10 doc-agent scope; `.claude/commands/doc-agent.md`. |

---

## 1. Why this is housekeeping, not a decision

None of the six is an open question requiring an empirical baseline, money, legal sign-off, or a fact outside this repo. Each is a *recorded* fact contradicting itself in two places, or a wording artifact. The "real decision" this memo asks for is not *what* the fix is (verified below) but *who may apply it and under what authority* — because one of the six (D-1, the id renumber) falls **outside** the normally-allowed WBS write-scope (`CLAUDE.md §1`: "allowed writes to `WBS.md`: §17 CLAR-* **appends**, §18 OOS-* **appends**, **status-code flips** (§1.2)"). Renaming an existing CLAR id is a content edit to an existing row — neither an append nor a status flip — so it must be sanctioned, not done silently by `/sync-wbs`. Everything else is either a sanctioned status flip (D-2) or a doc-agent file outside WBS (D-3..D-6).

---

## 2. Part-4 defect D-1 — duplicate `CLAR-MIGRATION-01` id

### 2.1 The collision (verified)

| Row | Sense | Status | Blocks | Verbatim trigger |
|---|---|---|---|---|
| `WBS.md:931` | **v2→v3.2 DATA migration** (findings, codebase membership, credentials) — in scope vs new-env-only | `DEFERRED` | CMP-CP-03 | "Legacy data migration plan from v2 to v3.2 …" |
| `WBS.md:973` | **Legacy DETECTOR ARTIFACTS** — `tarslip.yaml` taint defs + C/C++ CodeQL queries + CVE-2025-61765 baseline | `OPEN` | CMP-DET-03 (`AC-DET-03b`); ties CMP-ORCH-01 | "Where are the legacy `tarslip.yaml` taint definitions …" |

Two genuinely different questions under one id. Same class of bug as the already-fixed `CLAR-DB-02` collision this cycle (`DECISION-PART2 §1.E`, `OPEN-DECISIONS:144`).

### 2.2 The fix and **why 973, not 931**

Renumber the **detector-artifact row (973)** → **`CLAR-MIGRATION-02`**. Rationale (one line): row 931 is the canonical MIGRATION-domain sense and carries **six** references; row 973 carries only **two** live references → renumbering 973 minimizes ripple. (This matches the Part-4 recommendation and Part-2 §10.)

### 2.3 Ripple — the complete reference enumeration (the deliverable for D-1)

This is the load-bearing part: renaming an id orphans references, and **the task's starting-list hint contained two traps**, both confirmed against `grep -rn "CLAR-MIGRATION-01" .` (unrestricted, `.git`/`node_modules` excluded — the enumeration below is airtight):

> **TRAP 1 — the three `DOC-CMP-CP-0x` refs are the DATA-migration sense (931), NOT the detector-artifact sense. Do NOT re-point them.** The hint listed "likely refs in … DOC-CMP-CP-03" *as if they follow the renumber*. They do not — every CP-0x ref is about v2 *data*/credential migration (DEFERRED, new-env-only, credential re-encryption under the new KMS envelope). Re-pointing them would be the failure mode.
>
> **TRAP 2 — the predicted `DOC-CMP-DET-03` ref does not exist.** The hint predicted a `CLAR-MIGRATION-01` ref in `DOC-CMP-DET-03`. Grep found **none**: `DOC-CMP-DET-03.md` cites `tarslip.yaml` and CVE-2025-61765 but never the CLAR id. Nothing to re-point there.

| File:line | Verbatim sense | Action |
|---|---|---|
| **`WBS.md:973`** | detector-artifact (the row itself) | **RE-POINT → `CLAR-MIGRATION-02`** (the renumber) |
| **`tests/unit/test_det_specs.py:736`** | `# TODO: CLAR-MIGRATION-01 — migrate_tarslip then assert single canonical finding` (detector-artifact) | **RE-POINT → `CLAR-MIGRATION-02`** *(a code-comment edit — part of the D-1 ripple; flags the renumber as not a pure WBS edit)* |
| `WBS.md:931` | v2 DATA migration (the canonical 931 row) | **KEEP** `CLAR-MIGRATION-01` |
| `docs/components/DOC-CMP-CP-01.md:321` | "v2 → v3.2 data migration … DEFERRED" (DATA) | **KEEP** |
| `docs/components/DOC-CMP-CP-02.md:335` | "v2 → v3.2 data migration … credentials re-encrypted" (DATA) | **KEEP** |
| `docs/components/DOC-CMP-CP-03.md:256` | "DEFERRED via `CLAR-MIGRATION-01` … new-env-only" (DATA) | **KEEP** |
| `docs/components/DOC-CMP-CP-03.md:328` | "Legacy data migration plan … DEFERRED" (DATA) | **KEEP** |
| `docs/OPEN-DECISIONS-2026-06-02.md:124` | "the other one … v2→v3.2 data migration" (DATA) | **KEEP** *(superseded register doc)* |
| `docs/DECISION-PART2-2026-06-03.md:210` | "### CLAR-MIGRATION-01 (row ~931) — DATA migration" (DATA) | **KEEP** *(dated decision record)* |

**Meta / dated decision-record references — mention the defect, do NOT retro-edit (this Part-4 record supersedes them; chasing a renumber through dated records is revisionist):**
`docs/DECISION-PARAM-01-kappa-2026-06-03.md:397`, `docs/OPEN-DECISIONS-2026-06-02.md:123` (already self-annotated *"see defect note below"*) and `:141`, `docs/DECISION-PART2-2026-06-03.md:38`, `:214` (already self-annotated *"· duplicate ID"*), `:216`, `:256`. These describe the defect; they are not live pointers into a tracking workflow.

**Net live re-point set = exactly two:** `WBS.md:973` (the renumber) + `tests/unit/test_det_specs.py:736` (the TODO comment). The presence of a **code-file** edit in the ripple is precisely why D-1 cannot be a `/sync-wbs`-only action.

> *Note (parallel work):* `docs/DECISION-PART3-ownership-2026-06-03.md` was created by a parallel agent after this enumeration's grep. It does not change the re-point set — decision records are meta/superseded by nature and are never live pointers into a tracking workflow; even if it names the id, the action is "don't re-point." The "exactly two live re-points" claim holds.

### 2.4 Specified patch (D-1)

1. `WBS.md:973` — change the first table cell `| CLAR-MIGRATION-01 |` → `| CLAR-MIGRATION-02 |` (status `OPEN` and all other columns unchanged; the row's *question* is unchanged).
2. `tests/unit/test_det_specs.py:736` — `# TODO: CLAR-MIGRATION-01 — migrate_tarslip …` → `# TODO: CLAR-MIGRATION-02 — migrate_tarslip …` (comment only; no behavior change; the `pytest.skip` on line 737 is untouched).

*(Optional, additive, IN-SCOPE: a `WBS.md §17` note on the new `CLAR-MIGRATION-02` row cross-referencing the old shared id, so historical reads resolve. This is an append, allowed; not required.)*

---

## 3. Part-4 defect D-2 — stale `CLAR-TRI-01` status

### 3.1 The defect (verified)

`WBS.md:975`, the `CLAR-TRI-01` row, column 4 reads `resolved-with-PR-255` while column 5 (status) reads **`OPEN`**. The two contradict.

### 3.2 PR #255 verification — **CONFIRMED MERGED, decision in effect** (not trusting the note)

| Check | Result |
|---|---|
| `git log --all --grep="255"` | `a67f2df Merge pull request #255 from scanipy/feat/cmp-tri-02-eprocess-gate` + `28886fa fix(cmp-tri-02): address PR #255 review (CLAR-TRI-01, …)` |
| `gh pr view 255` | `state: MERGED`, `mergedAt: 2026-06-02T13:26:01Z`, merge commit `a67f2df` |
| Code claim (the float-primitive decision) | `services/triage/spec_inference.py:185` — `def update_e_process(state: EProcessState, outcome: float)`; docstring `:203-207`: *"a bounded `[0,1]` outcome rather than DOC-CMP-TRI-02 §3's `observation: AdjudicatedFinding`. The adjudication->outcome projection (`AdjudicatedFinding.label` -> `tp=1.0`/`fp=0.0`) is **the caller's responsibility**"*; `:210-211` enforces the `[0,1]` bound. finding_id traceability lives on `proposed_specs.e_process_state` at the caller layer. |

The decision (keep the float primitive; adjudication→outcome projection is the caller's job) is **literally in effect in the merged code** — exactly what the WBS notes column already records. The flip is justified.

### 3.3 Specified patch (D-2) — an allowed status-code flip

`WBS.md:975`, `CLAR-TRI-01` row, **status column (column 5)**: `OPEN` → `RESOLVED`. All other columns unchanged. This is a pure status-code flip per `CLAUDE.md §1` — **individually safe to apply** with no extra sanction; the rationale already lives verbatim in the notes column. *(If a "RESOLVED (date): …" stamp is desired in the notes column for parity with other resolved rows, that is an append, also allowed.)*

---

## 4. Part-2 §10 defects (consolidated here — NOT part of OPEN-DECISIONS Part 4)

> These four were surfaced as side-findings in `DECISION-PART2 §10`. They are folded into this single housekeeping record so one apply-pass clears them. All four are **doc-agent edits** (outside WBS); D-6 carries a dependency.

### 4.1 D-3 — `TST-INV-2-CP-01 [FORTHCOMING]` phantom obligation

- **Verified:** `DOC-CMP-CP-01.md:204` — the INV-2 row's Test cell reads: *"`TST-AC-CP-01a [FORTHCOMING]` (negative test: unknown `S_version` rejected); `TST-INV-2-CP-01 [FORTHCOMING]`"*.
- **Why vestigial:** the CP-01-01 ruling (`DECISION-PART2 §2`, **RR**) classifies CP-01 as a non-emitting routing/authz guard — it never constructs a `Finding`, so it stamps no `S_version`/`env_digest` and is **not** an INV-2 emitter. The INV-2 *emitter* obligation is discharged at CMP-ORCH-03 / CMP-FND-01..03. So `TST-INV-2-CP-01` is a phantom test obligation.
- **Surgical patch (keep `TST-AC-CP-01a`):** in line 204's Test cell, delete only the trailing clause `; \`TST-INV-2-CP-01 [FORTHCOMING]\``, leaving `\`TST-AC-CP-01a [FORTHCOMING]\` (negative test: unknown \`S_version\` rejected)`. **Do not** remove `TST-AC-CP-01a` — the CP-01-01 ruling explicitly *keeps* the unknown-`S_version`→422 negative test. (For full alignment the doc-agent may also soften the INV-2 row's "How discharged" prose from an emitter framing to an input-validation framing, but the load-bearing edit is the clause deletion.)
- **Dependency:** rests on the **CP-01-01 RR ruling** being ratified (Architect, `DECISION-PART2 §2`). Low-risk — RR means a provisional already exists and confirmation is a formality.

### 4.2 D-4 — OWASP license mislabel in DOC-CMP-CORP-VULN-01

- **Verified:** `DOC-CMP-CORP-VULN-01.md:172` reads: *"OWASP (Apache-2.0), Juliet (Public Domain), and BigVul (MIT) are GA-cleared."*
- **Authoritative records contradict only the OWASP clause:** `tests/corpora/vuln/corpus.lock:15-17` → `bigvul: MIT`, `juliet: Public Domain (NIST)`, `owasp_benchmark: GPL-2.0 (fetch-on-demand; off vendor allow-list, CLAR-CORP-18)`; `tests/corpora/vuln/LICENSES.md` → OWASP BenchmarkJava **GPL-2.0, NOT vendored, ships fetch-on-demand**. **BigVul=MIT and Juliet=Public Domain on line 172 are CORRECT — leave them.**
- **Two-part fix (scoped to OWASP only):** OWASP must (i) change `Apache-2.0` → `GPL-2.0` **and** (ii) move *out* of the "are GA-cleared" group (GPL-2.0 is off the vendor allow-list; per CLAR-CORP-18, answered Q2 = keep fetch-on-demand). Suggested replacement for line 172's relevant clause: *"Juliet (Public Domain) and BigVul (MIT) are on the vendor allow-list. **OWASP BenchmarkJava is GPL-2.0 — off the allow-list; it ships fetch-on-demand (pinned commit + `upstream_sha256`), not vendored (CLAR-CORP-18).**"* — grounded verbatim in `LICENSES.md`.
- **Dependency:** none — pure fact-correction. (Consistent with the already-answered Q2 in `DECISION-PART2 §8`.)

### 4.3 D-5 — DOC-CMP-DET-02 §3.2 `load_manifests` wording

- **Verified:** `DOC-CMP-DET-02.md:81` (in the §3.2 `load_manifests` docstring) reads *"…validate the native query file exists. **Calls register(...) for each.**"*
- **Code contradicts:** `detectors/registry.py:238-289` — `load_manifests` calls `_build_detector` (line 266) then `closure_check(detector)` **directly** (line 272) and admits into a `staged` dict (273); the loop **never calls `register()`**. The in-code comment (267-271) is explicit: closure_check runs "inside register path semantics; here we admit into the staging area atomically … (PR #235 F-4: removed the unreachable post-build re-check)." `register()` (line 291) is the separate public single-detector API.
- **One-line patch:** replace *"Calls register(...) for each."* → *"For each detector: runs `closure_check(...)` and admits it into the atomic staging area (it does **not** call the public `register()` API; see `registry.py` `load_manifests`)."* No invariant is lost — `closure_check` (INV-4 defense-in-depth) still runs on every detector.
- **Dependency:** none — pure code↔doc fact-correction.

### 4.4 D-6 — ADO "pins HMAC-SHA-256" unrealizability

- **Verified:** `DOC-CMP-SCM-03.md:104` (§3.3 `verify_webhook`) — the Azure DevOps row states *"…the connector **pins HMAC-SHA-256** and rejects subscriptions configured otherwise."* `DOC-API.md:74` (§2.4 SCM webhooks) — *"Azure DevOps: HMAC via service-hook subscription."*
- **Why unrealizable:** per the CLAR-SCM-02 finding (`DECISION-PART2 §7`), native Azure DevOps service-hooks emit **no per-delivery HMAC body signature and no signature header** — only HTTP Basic auth (`basicAuthUsername`/`basicAuthPassword`) + optional static headers; `X-Vss-Activityid` is a correlation id, not a signature. The implemented interim `verify_webhook` (`integrations/scm/ado.py:416-441`) requires `X-Hub-Signature-256` which native ADO never sends → it would reject every genuine delivery.
- **Patch (encodes the CLAR-SCM-02 recommended ruling) — rewrite the WHOLE ADO row, not just one cell:** `DOC-CMP-SCM-03.md:104` is a three-cell table row and **all three cells assert HMAC** that native ADO does not perform — Header cell ("`X-Vss-Activityid` and body HMAC where applicable"), Algorithm cell ("HMAC-SHA-1 or HMAC-SHA-256 per service-hook config"), and Notes cell ("pins HMAC-SHA-256 and rejects subscriptions configured otherwise"). Patching only the Notes cell would leave the row still implying ADO does HMAC. Replace the **entire** ADO row with the realizable scheme — Header: `(none — Basic-auth credential)`; Algorithm: **shared-secret equality on the `basicAuthPassword` consumer input** (the GitLab `X-Gitlab-Token` pattern; `register_webhook` already sets `consumerInputs.basicAuthPassword = secret`, `ado.py:362-384`); Notes: "Native ADO service-hooks emit no body HMAC and no signature header (CLAR-SCM-02); verify by constant-time equality of the echoed Basic-auth secret." **(Bitbucket row 103 is genuinely HMAC-SHA-256 — leave it.)** Correspondingly soften `DOC-API.md:74` from "Azure DevOps: HMAC via service-hook subscription." to "Azure DevOps: shared-secret (Basic-auth `basicAuthPassword`) echo verification — native ADO emits no body HMAC (CLAR-SCM-02)."
- **⚠ Dependency (this one is GATED, unlike D-4/D-5):** the corrected wording **encodes the CLAR-SCM-02 ruling, which is `ARB` — still awaiting Architect + Security sign-off** (`DECISION-PART2 §7`, RULE-9). So D-6 is a doc-agent edit **conditional on that ruling being adopted**; it is **not** freely-appliable like the two pure fact-corrections. If the architect instead chooses a signing-proxy, the corrected wording changes. **Hold D-6 until CLAR-SCM-02 is ratified;** the other five do not depend on it.

---

## 5. The human question to frame

> **Question (plain):** Apply these six register/doc fixes **now**, or hold them for a single follow-up `/sync-wbs` + `/doc-agent` pass?
>
> | Option (recommended first) | What it means |
> |---|---|
> | **① Record the exact patches here, apply them in one human-triggered pass** *(recommended)* | This memo specifies every patch at `file:line`; on your go-ahead, `/sync-wbs` applies D-2 (the safe status flip) + the **CTO-sanctioned** D-1 renumber (WBS row + the one code comment), and `/doc-agent` applies D-3/D-4/D-5 (and D-6 *iff* CLAR-SCM-02 is ratified). One atomic housekeeping PR. |
> | ② Apply only the individually-safe items now, hold the rest | Apply **D-2 now** (pure status flip, in normal WBS write-scope, no sanction needed). Hold **D-1** (needs your explicit OK — id rename is outside the normal WBS write-scope and touches a code file) and D-3/D-4/D-5/D-6 for the doc-agent pass. |
> | ③ Hold everything | No drift risk — every defect is a self-contradiction already documented here; nothing is unsafe while it waits. Clears in the next scheduled `/sync-wbs` + `/doc-agent` pass. |

**Which are individually safe vs which need your explicit OK:**
- **Safe to apply with no extra sanction:** **D-2** (CLAR-TRI-01 `OPEN`→`RESOLVED`) — a pure status-code flip, squarely in the normally-allowed WBS write-scope (`CLAUDE.md §1`).
- **Needs your explicit OK (CTO sanction):** **D-1** (renumber `CLAR-MIGRATION-01`→`-02`) — renaming an existing CLAR id is a *content* edit to an existing §17 row, **neither an append nor a status flip**, so outside the normal WBS write-scope; it also ripples into a code comment (`test_det_specs.py:736`), a non-WBS file. **D-6** additionally needs the CLAR-SCM-02 ARB ruling adopted first.
- **doc-agent's call (outside WBS):** **D-3/D-4/D-5** — doc hygiene; D-4/D-5 are pure fact-corrections, D-3 rests on the (RR, low-risk) CP-01-01 ruling.

**Recommended default: ① — record the exact patches here (done), apply them in one human-triggered pass.**

**YOUR DECISION (2026-06-03): ① — "Fix all in one pass."** Applied to the working tree on go-ahead; see §5a.

---

## 5a. Apply log (2026-06-03) — what was actually changed

> Performed by the orchestrator after your option-① go-ahead. **Working-tree edits only — not committed or pushed.** D-6 deliberately HELD.

| Defect | File:line | Change applied | Authority used |
|---|---|---|---|
| **D-2** | `WBS.md:975` (`CLAR-TRI-01` row) | status col `OPEN` → `RESOLVED`; date `—` → `2026-06-02`; notes reworded `Provisional:` → `**Resolved (PR #255, merged 2026-06-02):**` with the in-effect code ref | IN-SCOPE WBS status flip (CLAUDE.md §1) |
| **D-1a** | `WBS.md:973` | id cell `CLAR-MIGRATION-01` → `CLAR-MIGRATION-02`; appended a cross-ref note to the row | **CTO-sanctioned** (your explicit OK — id rename is outside the normal WBS write-scope) |
| **D-1b** | `tests/unit/test_det_specs.py:736` | `# TODO: CLAR-MIGRATION-01` → `# TODO: CLAR-MIGRATION-02` (comment only; `pytest.skip` untouched) | the D-1 ripple (a non-WBS code-comment, why D-1 ≠ a `/sync-wbs`-only edit) |
| **D-3** | `DOC-CMP-CP-01.md:204` | deleted the trailing `; \`TST-INV-2-CP-01 [FORTHCOMING]\`` clause; **kept** `TST-AC-CP-01a` | doc-agent fact-fix — applied **in anticipation of the high-confidence RR `CP-01-01` ratification, which is itself still pending sign-off (carried as OPEN in Part 5 §3); reversible** (re-add the `TST-INV-2-CP-01` clause) if `CP-01-01` is instead ruled an INV-2 emitter. The other two doc fixes (D-4 GPL fact, D-5 code↔doc fact) carry no such dependency. |
| **D-4** | `DOC-CMP-CORP-VULN-01.md:172` | OWASP `Apache-2.0`/GA-cleared → **GPL-2.0, off the allow-list, fetch-on-demand (CLAR-CORP-18)**; BigVul/Juliet untouched | doc-agent fact-fix |
| **D-5** | `DOC-CMP-DET-02.md:81` | "Calls register(...) for each." → "runs `closure_check(...)` and admits into the atomic staging area; does **not** call `register()`" | doc-agent fact-fix |
| **D-6** | `DOC-CMP-SCM-03.md:104` + `DOC-API.md:74` | **NOT APPLIED — HELD.** The corrected wording encodes the `CLAR-SCM-02` ruling, which is still `ARB` (Architect + Security sign-off pending, RULE-9). Apply only once that ruling is adopted. | — (gated) |

**Verification (2026-06-03):** `WBS.md` now carries `CLAR-MIGRATION-01` (data sense, row 931) and `CLAR-MIGRATION-02` (detector sense, row 973), no collision; no detector-sense `CLAR-MIGRATION-01` reference remains under `tests/`; `CLAR-TRI-01` status reads `RESOLVED`. D-6 left intact and HELD.

---

## 6. Governance boundary — what this memo does and does not do

- **Does:** verify all six defects at exact `file:line`; verify PR #255 is merged and the CLAR-TRI-01 decision is in effect in code; enumerate the complete, sense-disambiguated `CLAR-MIGRATION-01` reference set (net two live re-points); specify every patch verbatim; classify each fix by who may apply it and under what authority; frame the single human question with a recommended default.
- **Does not:** edit `PLAN.md`/`SDD.md`/`WBS.md`; flip any `CLAR-*` status; edit any `DOC-CMP-*`/`DOC-API` file; rename any id; write or edit production code. **The patches are specified, not applied** — a human triggers the pass.
- **Apply path (on go-ahead):** **D-2** → `/sync-wbs` (allowed status flip). **D-1** → CTO sanction, then `/sync-wbs` applies the WBS row + the `test_det_specs.py:736` comment together (one atomic change). **D-3/D-4/D-5** → `/doc-agent`. **D-6** → `/doc-agent`, **gated on CLAR-SCM-02 (ARB) being ratified** (Architect + Security, RULE-9).

---

## 7. References

- `docs/OPEN-DECISIONS-2026-06-02.md` Part 4 (the two named defects) + `:123-124` (the duplicate-id pair) · `docs/DECISION-PART2-2026-06-03.md §10` (the four further defects) + `§2` (CP-01-01 RR) + `§3` (CORP-18/Q2) + `§7` (CLAR-SCM-02 ARB) + `§8` (answered human decisions)
- `WBS.md:931` (MIGRATION data sense, DEFERRED) · `WBS.md:973` (MIGRATION detector-artifact sense, OPEN → renumber) · `WBS.md:975` (CLAR-TRI-01, status OPEN → RESOLVED)
- `tests/unit/test_det_specs.py:736-737` (the CLAR-MIGRATION-01 TODO comment + skip)
- PR #255: merge commit `a67f2df` (2026-06-02), `28886fa` (CLAR-TRI-01 review fix) · `services/triage/spec_inference.py:185-211` (the float-primitive decision in effect)
- `docs/components/DOC-CMP-CP-01.md:204` (CP-01 phantom test row) · `docs/components/DOC-CMP-CP-02.md:335`, `DOC-CMP-CP-03.md:256,328`, `DOC-CMP-CP-01.md:321` (the DATA-migration refs — KEEP)
- `docs/components/DOC-CMP-CORP-VULN-01.md:172` (OWASP mislabel) · `tests/corpora/vuln/corpus.lock:14-17` + `tests/corpora/vuln/LICENSES.md` (authoritative: OWASP=GPL-2.0, BigVul=MIT, Juliet=Public Domain)
- `docs/components/DOC-CMP-DET-02.md:77-82` (§3.2 load_manifests docstring) · `detectors/registry.py:238-289` (calls `closure_check` directly, never `register()`) + `:291-307` (`register()` public API)
- `docs/components/DOC-CMP-SCM-03.md:96-104` (§3.3 verify_webhook, ADO HMAC) · `docs/cross-cutting/DOC-API.md:69-74` (§2.4 SCM webhooks) · `integrations/scm/ado.py:362-384,416-441` (basicAuthPassword set; interim verifier requires X-Hub-Signature-256)
- `CLAUDE.md §1` (allowed WBS edits: appends + status flips only) · `.claude/commands/sync-wbs.md` (status-flip scope) · `.claude/commands/cto.md` (CLAR authority) · `.claude/commands/doc-agent.md` (DOC-* scope, no production code) · `.claude/rules/00-global.md` RULE-4/RULE-9/RULE-10

---

*Decision record — PROPOSED, awaiting your go-ahead to apply. Recommended: option ① — D-2 is an individually-safe status flip; D-1 needs your explicit CTO OK (id rename outside normal WBS write-scope + one code-comment re-point); D-3/D-4/D-5 are doc-agent fact-corrections; D-6 is a doc-agent edit gated on the CLAR-SCM-02 ruling.*

# DOC-CMP-TRI-01 — LLM triage ranking

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §9 CMP-TRI-01` (Purpose; AC-TRI-01a, AC-TRI-01b — quoted verbatim in §9)
- `SDD.md §2 INV-3` — *"No LLM output may influence a `deterministic-core` finding except via an accepted version-pinned spec in `S`. Triage never deletes findings."*
- `PLAN.md §"Locked decisions"` — *"LLM for triage and spec inference only"*
- `docs/cross-cutting/DOC-INV.md §5` — INV-3 owner exposition (four discharge mechanisms — mirrored verbatim in §5 below)
- `docs/cross-cutting/DOC-DB.md §4.12` (split-table note) and **§4.14** (`triage_scores` schema + `GRANT INSERT ON triage_scores TO scanipy_triage; REVOKE ALL ON findings FROM scanipy_triage;`)
- `docs/cross-cutting/DOC-PARTITION.md §2` — `LLM_TRIAGE=off` discipline in the core Attestor pipeline
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md §CLAR-DEPLOY-14` — LLM provider `claude-sonnet-4-6`; per-tenant quotas via `CMP-CP-01`
- `.claude/rules/00-global.md` (RULE-6, RULE-9), `.claude/rules/01-invariants.md §INV-3`, `.claude/rules/02-provenance.md` (TRI-01 write surface table)
- `WBS.md §11 (CMP-TRI-01)` task list T-CMP-TRI-01-01..04
- `WBS.md §17 CLAR-DEPLOY-14` (RESOLVED 2026-05-23) — Anthropic API `claude-sonnet-4-6`

This document is the **implementation contract** for `CMP-TRI-01`. It is an **INV-3-critical** component: the contract that this component CANNOT influence `origin`, detection content, or `status` of `deterministic-core` findings is non-negotiable, schema-enforced, and tested in three independent ways.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-TRI-01` |
| Subsystem | Triage & Spec Inference (`SDD.md §9`) |
| Staging | post-core (after Stage A; runnable only once `CMP-FND-02` is `DONE`) |
| Depends-On | `CMP-FND-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| INV-* touched | **INV-3 OWNER** (LLM off the detection path); INV-1 (must not flip `origin`); INV-2 (writes its own `S_version`/`env_digest` into `triage_scores` but never mutates them on `findings`) |
| Feature flag | `LLM_TRIAGE` — **default OFF** in production (`T-CMP-TRI-01-03`). The Attestor's core pipeline runs with `LLM_TRIAGE=off` (`AC-CP-05a`, `DOC-PARTITION §2`). |
| LLM provider | Anthropic API, model `claude-sonnet-4-6` (`CLAR-DEPLOY-14` RESOLVED). Per-tenant RPM / TPD quotas enforced by `CMP-CP-01`. |
| Write surface | **`triage_scores` only.** Schema-grant level: `GRANT INSERT ON triage_scores TO scanipy_triage; REVOKE ALL ON findings FROM scanipy_triage;` (`DOC-DB §4.14`). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §9 CMP-TRI-01`):**

> Score `(likely_exploitable, likely_test_code, likely_fp)` from the SARIF blob plus a bounded code window; write `triage_score`/`triage_reason`. Feature-flagged, default off. Never deletes findings.

**Operational role.** `CMP-TRI-01` is a **post-hoc, additive ranker** that helps human triagers prioritize work. It runs **after** the deterministic core has emitted a finding into the `findings` table. It reads a restricted, read-only view of each finding (`id, class, rule_id, severity, physical_location, message`; per `DOC-DB §4.14`'s grants block) plus a bounded source-code window, sends both to the LLM, and writes the resulting score and natural-language reason **into a separate table** (`triage_scores`). It is not on any detection path, not on any attestation path, and not in the signed provenance chain that backs reproducibility theorem (a).

**What this component is forbidden to do** (binding, INV-3-critical):

1. It **MUST NOT** write to `findings` (any column — schema-revoked).
2. It **MUST NOT** delete a finding (`AC-TRI-01b`; *"never delete a finding"*, `T-CMP-TRI-01-04`).
3. It **MUST NOT** set `findings.status = 'suppressed'` (or any other status transition) based on its own output. Status transitions are the prerogative of human adjudication via the dashboard (`CMP-CP-04`).
4. It **MUST NOT** influence `origin`, `S_version`, `env_digest`, `slice_fingerprint`, `cpg_order_hash`, `fingerprint_class`, `determinism_partition`, `engine`, or any detection-content column on `findings`.
5. It **MUST NOT** read or write `spec_versions`, `proposed_specs`, or `provenance_records`. (Spec acceptance is `CMP-TRI-02`'s contract.)

A counter-example violation is captured in `DOC-INV §5.6`:

```python
# WRONG — LLM signal suppresses a finding
if llm_output.likely_fp > 0.9:
    finding.status = "suppressed"                    # INV-3 violation: triage deleting findings
```

---

## 3. Interface contract

`CMP-TRI-01` is invoked **post-emission**, asynchronously, by a worker that consumes from the SQS triage queue (per `CLAUDE.md §8`). It is **never** invoked inline during scan execution.

Pure function signature (Python, `services/triage/triage.py`):

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

@dataclass(frozen=True)
class FindingView:
    """Read-only projection of a `findings` row, scoped to columns CMP-TRI-01 may SELECT.

    Matches the GRANT in DOC-DB §4.14:
      GRANT SELECT (id, class, rule_id, severity, physical_location, message)
        ON findings TO scanipy_triage;
    """
    id: UUID
    class_: str          # 'class' is reserved; renamed in the dataclass
    rule_id: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    physical_location: dict       # uri, start_line, end_line (jsonb)
    message: str

@dataclass(frozen=True)
class TriageInput:
    finding: FindingView
    code_window: str              # bounded; max BYTE_BUDGET (T-CMP-TRI-01-01)
    sarif_excerpt: str            # bounded; just the result region of the SARIF blob
    S_version: str                # propagated from findings row (read-only)
    env_digest: str               # propagated from findings row (read-only)

@dataclass(frozen=True)
class TriageScore:
    finding_id: UUID
    triage_score: Decimal         # numeric(5,4) in [0, 1]
    triage_reason: str            # bounded JSON-encoded payload
    model_id: str                 # 'claude-sonnet-4-6' (CLAR-DEPLOY-14)
    model_version: str            # API-reported version stamp
    S_version: str                # stamped into triage_scores row (INV-2 — for this row)
    env_digest: str               # stamped into triage_scores row (INV-2 — for this row)

def triage_finding(inp: TriageInput) -> TriageScore: ...
```

### 3.1 Allowed write set (the load-bearing list)

```python
# services/triage/triage.py
ALLOWED_TRIAGE_COLUMNS = {
    "finding_id", "triage_score", "triage_reason",
    "model_id", "model_version", "S_version", "env_digest",
}
# Target table: triage_scores ONLY. Never findings, never provenance_records,
# never spec_versions, never proposed_specs.
```

The implementation MUST assert `set(update.keys()) <= ALLOWED_TRIAGE_COLUMNS` and MUST target only `triage_scores` (the database role `scanipy_triage` has no other grants per `DOC-DB §4.14`).

### 3.2 LLM client contract

| Aspect | Requirement |
|---|---|
| Provider | Anthropic API (`CLAR-DEPLOY-14`) |
| Model | `claude-sonnet-4-6` (record exactly as `model_id`) |
| Prompt-caching | Required (per `CLAR-DEPLOY-14` consequences). System-prompt + class-specific instructions cached. |
| Per-tenant quota | RPM and TPD enforced by `CMP-CP-01` proxy. On quota exhaustion the worker DLQs the message; no fallback that could leak un-quota'd LLM cost. |
| Determinism | LLM output is NOT required to be reproducible. The Attestor pipeline runs with `LLM_TRIAGE=off` precisely so that core-partition byte-identity is independent of triage drift (`DOC-PARTITION §2`, `TST-INV-3-CP-05`). |
| `LLM_TRIAGE` flag | Default OFF. When OFF, `triage_finding` is **not invoked**; no `triage_scores` row is written; no LLM call is made. |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `FindingView` | Read-only SELECT on `findings` (column-restricted grant; `DOC-DB §4.14`) | The triage role cannot SELECT `origin`, `slice_fingerprint`, `cpg_order_hash`, `status`, etc. The restricted view is enforced at the SQL grant boundary. |
| `code_window` | Worker reads bounded window around `physical_location` from the snapshot artifact (S3) | Bounded byte budget. |
| `sarif_excerpt` | The result region of the SARIF blob (`CMP-FND-01` output) | Bounded; never the full SARIF. |
| `S_version`, `env_digest` | Propagated from the `findings` row (read-only — TRI-01 cannot mutate) | Stamped onto the `triage_scores` row for that row's INV-2 compliance (this is *not* an INV-2 mutation of the source finding). |
| `LLM_TRIAGE` flag | Tenant config (default OFF) | If OFF, the worker exits without making an LLM call or writing a row. |

### 4.2 Outputs

A single row in `triage_scores` per `(finding_id, model_id, model_version)` (UNIQUE constraint per `DOC-DB §4.14`):

| Column written | Constraint |
|---|---|
| `finding_id` | FK to `findings(id)` — chosen by the worker; not mutated. |
| `triage_score` | `numeric(5,4)` in `[0, 1]`. |
| `triage_reason` | Bounded JSON-encoded payload (`{likely_exploitable, likely_test_code, likely_fp, free_text}` per `SDD §9 CMP-TRI-01 Purpose`). |
| `model_id`, `model_version` | Exact identifiers from the LLM API response. |
| `S_version`, `env_digest` | INV-2 fields on the `triage_scores` row itself. **NOT** a mutation of the source finding's INV-2 fields. |

**Nothing else is written.** The triage cycle never inserts into `provenance_records` (the signed audit chain), never updates `findings`, never inserts into `spec_versions` or `proposed_specs`.

---

## 5. Invariants touched

`CMP-TRI-01` is one of the four owner components for INV-3 (alongside CMP-TRI-02, CMP-TRI-03, CMP-CP-05). Per `DOC-INV §5.3`, INV-3 has **four discharge mechanisms that compose; any one alone is insufficient.** All four apply to `CMP-TRI-01`:

| # | Mechanism | Implementation in CMP-TRI-01 | Failure surface |
|---|---|---|---|
| **(a)** | **Column-restriction at the database write surface** | `triage_scores` is a separate table; the `scanipy_triage` DB role holds `GRANT INSERT ON triage_scores` only; `REVOKE ALL ON findings FROM scanipy_triage` (`DOC-DB §4.14`). A misbehaving worker that tries to `UPDATE findings` fails with a Postgres permission error at the connection boundary — not at application code. | `TST-INV-3-TRI-01`: assert no `findings` column changes between pre- and post-triage row diffs over a representative scan. |
| **(b)** | **Default-OFF feature flag** | `LLM_TRIAGE=off` is the production default (`T-CMP-TRI-01-03`). The worker short-circuits before any LLM call when the flag is OFF. A finding row's detection content is therefore independent of triage in the canonical configuration. | `TST-AC-TRI-01a`: with the flag OFF, no `triage_scores` row is created and no `findings` column changes. |
| **(c)** | **Attestor enforcement** | `CMP-CP-05` runs the core Attestor pipeline with `LLM_TRIAGE=off` (`AC-CP-05a`, `DOC-PARTITION §2`) and asserts byte-identical SARIF over `origin=deterministic-core`. If LLM output ever leaked into the core path, the Attestor's diff would be non-zero and CI would hard-fail. | `TST-INV-3-CP-05` (owned by CMP-CP-05, depended on by TRI-01 contract). |
| **(d)** | **Pinned-`S_version` discipline** | Triage's only legitimate path to influencing a deterministic-core finding is by *proposing* a spec to `CMP-TRI-02`, which gates acceptance via the e-process (Algorithm 6) and writes a *new* `S_version`. Even then, the LLM never directly influences a deterministic-core finding's detection content; the core reads only pinned `S_version`s. | Owned upstream by `CMP-TRI-02` (`AC-TRI-02c`); `CMP-TRI-01` discharges this by never reading or writing `spec_versions` itself. |

### 5.1 INV-1 (Origin partition) — indirect

`CMP-TRI-01` MUST NOT mutate `findings.origin`. This is co-resident with INV-3: the same code path that violates INV-3 violates INV-1 (`DOC-INV §3.6`). The schema grant in `DOC-DB §4.14` discharges both invariants simultaneously by preventing TRI-01 from writing to the `findings` table at all.

Tests: `TST-INV-1-TRI-01` (no triage-induced `origin` flips on a representative scan), `TST-AC-TRI-01a` (verbatim AC — see §9).

### 5.2 INV-2 (Versioned parameters) — own-row only

`CMP-TRI-01` stamps `S_version` and `env_digest` on the `triage_scores` row it writes. It MUST NOT mutate `S_version` or `env_digest` on the source `findings` row (the grant prevents this anyway). This distinction matters: "no INV-2 fields" ≠ "no INV-2 anywhere". The triage row is itself an INV-2-bearing record; the source finding's INV-2 fields are read-only inputs.

### 5.3 INV-3 (LLM off the detection path) — **OWNER**

`CMP-TRI-01` is the primary INV-3 surface in the system. Every section of this document reinforces that the LLM call here CANNOT influence `deterministic-core` findings' `origin`, detection content, or `status`. See §5 (this section), §3.1 (allowed-write list), §7 (failure modes — none of which open an LLM-to-core leak), §8 (provenance threading — TRI-01 does not enter the signed chain at all).

### 5.4 Triage non-deletion contract

Per `SDD.md §9 CMP-TRI-01 Purpose` (*"Never deletes findings."*) and `T-CMP-TRI-01-04` (*"Make ranking strictly additive — never delete a finding."*): the triage worker MUST NOT issue `DELETE FROM findings` (revoked by grant), MUST NOT set `findings.status = 'suppressed'` (revoked by grant), and MUST NOT exclude a finding from any output stream on the basis of `triage_score`. Suppression is a separate human-adjudication path recorded via the dashboard with its own audit trail.

---

## 6. Dependency contract

| Depends-on | Why | Reference |
|---|---|---|
| `CMP-FND-02` | The `findings` table must exist with its NOT NULL constraints on `origin`, `S_version`, `env_digest`, `cpg_order_hash` and the split-table design (`triage_scores` + column-restricted grants) in place before any triage write surface is meaningful. The grants block in `DOC-DB §4.14` is itself a `CMP-FND-02` deliverable. | `WBS.md §20`; `DOC-DB §4.14` |

Per `RULE-2` (`.claude/rules/00-global.md`), implementation of `CMP-TRI-01` MUST NOT start until `CMP-FND-02` is `DONE` (every `TST-AC-FND-02-*` green). The `LLM_TRIAGE` feature flag remains OFF in production until `CMP-CP-05` (`AC-CP-05a`) has run at least one Attestor cycle with `LLM_TRIAGE=off` and reported byte-identical SARIF over `deterministic-core` (the canonical proof that triage cannot leak).

Downstream consumers: `CMP-CP-04` (dashboard reads `triage_scores` for ranking display).

---

## 7. Failure modes

| Failure | Detection | Response | INV-3 impact |
|---|---|---|---|
| LLM API rate-limit hit (per-tenant quota exhausted at `CMP-CP-01`) | HTTP 429 from `CMP-CP-01` proxy | Worker NACKs the message; SQS retries with exponential backoff; on DLQ depth threshold, alarm fires. **No fallback writes anything to `findings`.** | None — flag-off equivalent. |
| LLM API timeout | Configured client timeout | NACK; retry. On repeated failures, DLQ. | None. |
| LLM API hard error (auth, malformed response) | Anthropic SDK exception | DLQ immediately; alarm. | None — no row is written; no `findings` mutation possible. |
| Schema-mismatch in LLM response (score outside `[0, 1]`, missing fields) | Application-level validation against the `TriageScore` schema | Reject the response, DLQ; alarm. | None — `triage_scores.triage_score` has CHECK (0..1); a non-conforming row is rejected at the DB boundary. |
| Worker attempts to write to `findings` (bug) | Postgres permission error from the `scanipy_triage` role | Connection-level failure; the transaction aborts; the row is never written. **This is the grant-level discharge of INV-3.** | **The mechanism that prevents the violation from landing.** Alarm + incident. |
| `LLM_TRIAGE=off` flag is honored | Worker reads the flag once per message, short-circuits if OFF | No LLM call, no row write, no `findings` mutation. | The default-state INV-3 discharge. |
| Adversarial LLM output (e.g. injection attempt in `triage_reason`) | Bounded JSON-encoded payload validation | Reject; DLQ. The payload bound prevents the LLM from inflating cost or breaking downstream renderers. | None — even an adversarial response cannot escape the `triage_scores` write surface to affect `findings`. |

**Critical:** there is no failure mode that opens an LLM-to-core leak. The grant boundary (`DOC-DB §4.14`) is the operative discharge; every other layer is defense-in-depth.

---

## 8. Provenance threading

`CMP-TRI-01` writes only to `triage_scores`. It does **not** write to `provenance_records` (the signed audit chain — `CMP-FND-03`). The triage cycle is deliberately outside the signed-provenance chain, because the chain backs reproducibility theorem (a) and reproducibility is asserted only over the core partition under `LLM_TRIAGE=off`.

| Field | Where it is set | Threading rule |
|---|---|---|
| `triage_score`, `triage_reason` | `triage_scores` row | The only finding-related columns TRI-01 may write (`DOC-DB §4.14`; `.claude/rules/02-provenance.md` per-component table). |
| `S_version`, `env_digest` (on the `triage_scores` row) | INV-2 for the triage row | Copied **read-only** from the source `findings` row at write time. Never mutated on `findings`. |
| `model_id`, `model_version` | INV-3 audit trail | The LLM provider identifier (`claude-sonnet-4-6` per `CLAR-DEPLOY-14`) and the API-reported version stamp. |
| `findings.origin`, `findings.S_version`, `findings.env_digest`, `findings.slice_fingerprint`, `findings.cpg_order_hash`, `findings.status`, `findings.spec_provenance` | **MUST NOT touch** | Grant-blocked. |
| `provenance_records` (signed audit chain) | **MUST NOT write** | TRI-01 is not in the signed chain; the LLM output is not auditable as a reproducible artifact. |

The `.claude/rules/02-provenance.md` per-component table (`CMP-TRI-01` row) is authoritative:

> CMP-TRI-01 — *Must NOT touch `origin`, `S_version`, `env_digest`; writes only `triage_*` columns.*

(Read: must not mutate those columns on `findings`. The `triage_scores` row carries its own copy as immutable witness of the scan context the LLM ran in.)

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §9 CMP-TRI-01`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact | Notes |
|---|---|---|---|
| **AC-TRI-01a** | > With the triage flag off, no finding row's `origin` or detection content is affected (INV-3). | `TST-AC-TRI-01a` `[FORTHCOMING]` | Run a scan with `LLM_TRIAGE=off`, snapshot `findings` rows, run again, diff. Expect zero diffs. Also `TST-INV-1-TRI-01`, `TST-INV-3-TRI-01`. |
| **AC-TRI-01b** | > Ranking writes only `triage_*` columns. | `TST-AC-TRI-01b` `[FORTHCOMING]` | Integration test using the `scanipy_triage` DB role; verify that an attempted UPDATE on any `findings` column fails with a permission error; verify the only inserts during a triage cycle target `triage_scores`. |

Invariant tests cross-referenced (mirrored verbatim from `WBS.md §11 (CMP-TRI-01)` and `DOC-INV §5.8`):

- `TST-INV-1-TRI-01 [FORTHCOMING]` — triage write surface excludes `origin`.
- `TST-INV-3-TRI-01 [FORTHCOMING]` — with triage enabled, only `triage_*` columns (in `triage_scores`) change between pre- and post-triage state; no `findings` columns are mutated.

Related cross-component tests (consumed by TRI-01 contract but owned elsewhere):

- `TST-INV-3-CP-05 [FORTHCOMING]` — Attestor core pipeline runs with `LLM_TRIAGE=off`; byte-identical SARIF over `deterministic-core`. Owned by `CMP-CP-05`. This is the empirical proof that mechanism (c) discharges INV-3 for TRI-01.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-TRI-01 |
|---|---|---|---|
| `CLAR-DEPLOY-14` | LLM provider for triage + spec inference; pricing/quota controls | **RESOLVED** (2026-05-23) | Anthropic API `claude-sonnet-4-6`; per-tenant RPM/TPD enforced by `CMP-CP-01`. No further action. |
| `CLAR-SLA-02` | Numeric per-tenant rate-limit budgets (general API RPM/burst + LLM RPM/TPD) | **DEFERRED** | Per-tenant LLM quotas (RPM/TPD) need concrete numbers before production enable. Documented defaults are proposed in `DOC-API.md §7`. TRI-01 implementation should consume the values from config, not hardcode. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |
| `CLAR-PARAM-04` *(NOT FILED — explicit non-action)* | Bound on `code_window` byte budget for the LLM prompt | n/a | The `code_window` byte budget is an implementation choice not constrained by any AC. Treat as an Anthropic prompt-caching-cost tradeoff; document the chosen value in the implementation PR. Not load-bearing — file a CLAR only if implementation reveals a correctness or safety constraint. |

No new CLAR-TRI-* are filed by this document. The INV-3 contract is fully specified by `SDD §2 INV-3` + `SDD §9 CMP-TRI-01` + `DOC-DB §4.14` + `DOC-INV §5`.

---

## 11. References

- `SDD.md §2 INV-3` — verbatim invariant.
- `SDD.md §9 CMP-TRI-01` — verbatim Purpose and ACs.
- `PLAN.md §"Locked decisions"` — LLM confined to triage and spec inference.
- `docs/cross-cutting/DOC-INV.md §5` — INV-3 four-discharge-mechanism canonical exposition (this document mirrors mechanisms (a)–(d) verbatim in §5).
- `docs/cross-cutting/DOC-DB.md §4.12` (split-table note), **§4.14** (`triage_scores` schema + grants block — the schema-level INV-3 discharge).
- `docs/cross-cutting/DOC-PARTITION.md §2` — `LLM_TRIAGE=off` in the core Attestor pipeline.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md §CLAR-DEPLOY-14` — Anthropic `claude-sonnet-4-6`; per-tenant quotas.
- `docs/components/DOC-CMP-TRI-02.md` (sibling) — spec acceptance via Algorithm 6.
- `docs/components/DOC-CMP-TRI-03.md` (sibling) — per-customer revalidation + drift monitor.
- `docs/components/DOC-CMP-FND-02.md` (forthcoming) — the schema owner; the grant block lives there.
- `docs/components/DOC-CMP-CP-05.md` (forthcoming) — Attestor; runs with `LLM_TRIAGE=off`.
- `WBS.md §11 (CMP-TRI-01)` — task list T-CMP-TRI-01-01..04; test list.
- `WBS.md §17 CLAR-DEPLOY-14` (RESOLVED), `CLAR-SLA-02` (DEFERRED), `CLAR-OWNER-01` (DEFERRED).
- `.claude/rules/00-global.md` (RULE-6, RULE-9 — Security Analyst review required for any INV-3-touching component).
- `.claude/rules/01-invariants.md §INV-3` — operational quick reference.
- `.claude/rules/02-provenance.md` — TRI-01 write-surface table.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-TRI-01`. **INV-3 is non-negotiable**: every PR touching this component requires Security Analyst sign-off per `RULE-9`.*

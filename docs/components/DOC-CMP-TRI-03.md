# DOC-CMP-TRI-03 — Per-customer revalidation + drift monitor

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §9 CMP-TRI-03` (Purpose; AC-TRI-03a, AC-TRI-03b — quoted verbatim in §9)
- `SDD.md §2 INV-3` — *"No LLM output may influence a `deterministic-core` finding except via an accepted version-pinned spec in `S`."*
- `PLAN.md §"Algorithm 6 — Covariate shift"` — *"`S = S_global ∪ S_customer`. `S_global` passed the global-stream e-process; `S_customer` must additionally clear the customer-stream e-process before affecting that customer's findings."*
- `docs/cross-cutting/DOC-ALGS.md §7.4` (continuous revalidation / drift), §7.8 (failure modes)
- `docs/cross-cutting/DOC-INV.md §5.3` mechanism (d) — pinned-`S_version` discipline; §5.5 compliant example
- `docs/cross-cutting/DOC-DB.md §4.9` (`spec_versions` with `spec_provenance ∈ {'global-unrevalidated','global-revalidated','customer'}`); §4.12 (`findings.spec_provenance` NULL when not dependent on a revalidatable spec)
- `docs/cross-cutting/DOC-PROVENANCE.md` (spec_provenance state machine)
- `WBS.md §11 (CMP-TRI-03)` task list T-CMP-TRI-03-01..04
- `WBS.md §17 CLAR-PARAM-02` (DEFERRED — π₀ per detector class also required for customer-stream e-process)
- `.claude/rules/00-global.md` (RULE-6, RULE-9), `.claude/rules/01-invariants.md §INV-3`

This document is the **implementation contract** for `CMP-TRI-03`. The component reuses the e-process instrument from `CMP-TRI-02` (the same mathematical object) and owns the **spec_provenance state machine** (`global-unrevalidated` → `global-revalidated` → `customer`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-TRI-03` |
| Subsystem | Triage & Spec Inference (`SDD.md §9`) |
| Staging | post-core (after Stage A) |
| Depends-On | `CMP-TRI-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| Shared instrument | The **same e-process** maintained by `CMP-TRI-02`; run on the **customer's adjudicated stream** instead of the global stream. *"Acceptance gate and drift monitor now share one mathematical object"* (`PLAN.md §"Algorithm 6"`). |
| INV-* touched | **INV-3** (same as TRI-02 — pinned `S_version` discipline; no direct LLM→core influence); **INV-2** (per-scan pinning of `S = S_global ∪ S_customer`) |
| State machine owned | `spec_provenance ∈ {'global-unrevalidated', 'global-revalidated', 'customer'}` (`DOC-DB §4.9`, `DOC-PROVENANCE`) |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §9 CMP-TRI-03`):**

> `S = S_global ∪ S_customer`; the same e-process instrument run on the customer's adjudicated stream; auto-quarantine on a floor breach; `spec_provenance = global-unrevalidated` labeling until customer revalidation.

**Operational role.** `CMP-TRI-03` is the **per-customer guardrail** for specs that passed the global e-process gate (`CMP-TRI-02`) but have not yet been revalidated on a specific customer's distribution. Covariate shift between the global evaluation stream and any given customer's codebase / threat profile can cause a globally-accepted spec to under-perform on that customer's data. The mitigation is structural:

1. Every scan composes `S = S_global ∪ S_customer` and pins both sets per scan (`T-CMP-TRI-03-01`). Per-scan pinning preserves determinism (a) under fixed `(S_version, env_digest)`.
2. The same e-process from `CMP-TRI-02` runs **independently on the customer's adjudicated stream** for each `S_global` spec the customer's findings depend on (`T-CMP-TRI-03-02`).
3. While the customer-stream e-process has not yet cleared for a given global spec, findings dependent on that spec carry `spec_provenance = 'global-unrevalidated'` (`T-CMP-TRI-03-04`, `AC-TRI-03b`).
4. On floor-breach in the customer-stream e-process (the complementary null `H1: true precision ≥ π₀` rejected on the customer stream), the spec is **auto-quarantined for that customer** (`T-CMP-TRI-03-03`, `AC-TRI-03a`). The customer's subsequent scans pin `S` without the quarantined spec; previously emitted findings are not deleted (INV-3 non-deletion contract).

**What this component is forbidden to do.**

1. It MUST NOT mutate `findings.origin`, detection content, or `status` based on drift signal. Drift detection is a *labeling* and *future-applicability* mechanism, not a finding-modification one. Previously emitted findings remain in the DB with their original `S_version`; the historical artifact is preserved.
2. It MUST NOT update `findings` directly. The `spec_provenance` column on `findings` is set at emission time by `CMP-ORCH-03` from the consumed `spec_versions.spec_provenance` value; state-machine transitions on `spec_versions` propagate to *future* findings, not historical ones.
3. It MUST NOT operate without `CMP-TRI-02`'s Gate 4 (martingale unit test) green — the same instrument requires the same statistical correctness.

---

## 3. Interface contract

`CMP-TRI-03` lives alongside `CMP-TRI-02` in `services/triage/spec_inference.py`. It exposes per-customer revalidation and drift-monitoring entry points that reuse the e-process update primitives.

```python
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

@dataclass(frozen=True)
class CustomerEvaluationStream:
    org_id: UUID
    spec_version_id: UUID          # the global spec being revalidated
    pi_zero: float                 # customer's π₀ (may differ per tenant policy)
    alpha: float                   # α (typically the same 0.05 confirmed by CLAR-PARAM-02)

@dataclass(frozen=True)
class CustomerEProcessState:
    """One per (org_id, spec_version_id). Persisted as a jsonb side-table
    or as `spec_versions.customer_e_process_state` (schema location TBD —
    not blocking; see §10)."""
    org_id: UUID
    spec_version_id: UUID
    log_wealth_revalidate: float   # E_t for revalidation null (H0: precision < π₀)
    log_wealth_drift: float        # E_t for complementary drift null
    n_observations: int

@dataclass(frozen=True)
class RevalidationResult:
    org_id: UUID
    spec_version_id: UUID
    decision: Literal["pending", "revalidated", "quarantined"]
    e_value_revalidate: float      # current E_t for the revalidation null
    e_value_drift: float           # current E_t for the drift / complementary null

def revalidate_spec(spec_version_id: UUID, customer_id: UUID,
                    state: CustomerEProcessState) -> RevalidationResult:
    """Decision step on the customer-stream e-process.

    Reuses the same Algorithm 6 instrument (CMP-TRI-02's update primitive)
    on the customer's adjudicated stream. Acceptance of the revalidation
    null transitions spec_provenance to 'global-revalidated' for this
    customer-scoped pin. Drift-null acceptance triggers auto-quarantine.
    """

def monitor_drift(customer_id: UUID) -> list[RevalidationResult]:
    """Sweep the customer's active S_global pins; for each, report the
    current revalidation/drift e-values. Quarantine fires when the drift
    e-process crosses 1/α."""
```

### 3.1 The shared-instrument property

Per `PLAN.md §"Algorithm 6 — Continuous revalidation / drift"`:

> The per-customer drift monitor is the *same instrument* run on the customer's adjudicated stream against the same `H0(σ)` with the customer's `π₀`. When the customer-stream e-process crosses the rejection threshold for the *complementary* null (precision has fallen below floor), `σ` is auto-quarantined for that customer.

**Implementation consequence.** The `update_e_process` and `evaluate_proposed_spec` primitives from `CMP-TRI-02` are reused verbatim. The only differences are: (a) the input stream (customer-adjudicated rather than global-adjudicated), (b) the persistence target (`CustomerEProcessState` rows keyed by `(org_id, spec_version_id)`), and (c) the action on threshold crossing (state-machine transition on `spec_versions.spec_provenance` for this customer's scope, OR a new `customer`-scoped `spec_versions` row + a quarantine record). The mathematical guarantees from `CMP-TRI-02` apply unchanged because it is the same instrument.

### 3.2 Per-scan pinning of `S = S_global ∪ S_customer`

`T-CMP-TRI-03-01`: every scan submission pins **both** sets:

```
S := S_global   (the latest globally-accepted spec_versions with spec_provenance != 'global-unrevalidated'
                 for this customer, OR with 'global-unrevalidated' if no quarantine applies)
   ∪ S_customer (customer-scoped spec_versions rows with scope='customer' and spec_provenance='customer')
```

The set is **frozen** at scan submission; `CMP-ORCH-01` records the pinned `S_version` set into the scan row. The deterministic core consumes only the pinned set, never a "current S" view (`AC-TRI-02c`; `DOC-INV §5.5`).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Customer-adjudicated `AdjudicatedFinding` stream | Customer's human triagers labeling findings as `tp` / `fp` via the dashboard (`CMP-CP-04`) | One bounded `[0, 1]` outcome per adjudicated finding. Per-customer scoped (org_id-bounded). |
| `spec_version_id` (global) | Active `S_global` row that this customer is currently consuming | Drawn from `spec_versions` where `scope='global'` and the customer's scans have pinned it. |
| Customer-specific `π₀` | Tenant policy (defaults to global `π₀` per `CLAR-PARAM-02`) | May be tightened per tenant (e.g. a high-assurance customer demands π₀=0.95 where global is 0.90). |

### 4.2 Outputs

**On every customer-adjudicated observation:** an update to `CustomerEProcessState` for the relevant `(org_id, spec_version_id)`. No `findings` rows are touched.

**On revalidation acceptance** (customer-stream e-process for `H0` crosses `1/α`): a state-machine transition on the customer-scoped view of the spec — either by inserting a customer-scoped `spec_versions` row with `scope='customer'`, `spec_provenance='global-revalidated'`, referencing the global parent; or by recording a per-customer revalidation event whose effect is to label *future* findings emitted under this customer's scans with `spec_provenance='global-revalidated'`. The precise schema mechanism is documented in `DOC-DB §4.9` (the `spec_provenance` enum is on `spec_versions`); a clarification on the exact per-customer revalidation persistence is filed as `CLAR-DB-05` (see §10).

**On quarantine** (customer-stream e-process for the complementary drift null crosses `1/α`): the spec's `decision` is `'quarantined'` for that customer. Subsequent scans for the same `org_id` MUST NOT include the quarantined spec in their pinned `S`. Existing emitted findings are NOT deleted; their historical `S_version` is preserved.

**`findings.spec_provenance` at emission time** (set by `CMP-ORCH-03`, not by `CMP-TRI-03` — but the field's allowed values and their meaning are owned by this component):

| Value | Meaning | When set |
|---|---|---|
| `NULL` | Finding does not depend on a revalidatable spec (e.g. it came from a base-rule detector, not a learned spec). | `CMP-ORCH-03` at emission; `DOC-DB §4.12` allows NULL. |
| `'global-unrevalidated'` | Finding depends on an `S_global` spec that this customer's stream has not yet revalidated. | Emission time, when the pinned `S_global` spec has `spec_provenance='global-unrevalidated'` for this customer. |
| `'global-revalidated'` | Finding depends on an `S_global` spec that *has* cleared this customer's revalidation e-process. | Emission time after the customer-stream e-process has accepted. |
| `'customer'` | Finding depends on an `S_customer` spec accepted via the customer-stream e-process from the customer's own proposals. | Emission time when consuming a customer-scoped `spec_versions` row. |

---

## 5. Invariants touched

### 5.1 INV-3 — same discipline as TRI-02

`CMP-TRI-03` is bound by the same INV-3 discipline as `CMP-TRI-02` (`DOC-INV §5`). The LLM influences neither: drift detection is computed over **adjudicated outcomes** (human labels), not over LLM scores. The customer-stream e-process is a statistical instrument; its inputs are labels, not LLM outputs. The deterministic core continues to read only **pinned `S_version`s** per scan; the only effect of a quarantine decision is to **exclude** a spec from a future scan's pinned `S` for one customer.

Tests: `TST-INV-3-TRI-02` covers the shared instrument's INV-3 discipline; no separate `TST-INV-3-TRI-03` is enumerated in `WBS.md §11` because the discipline is the same — but every PR touching `CMP-TRI-03` requires Security Analyst review per `RULE-9`.

### 5.2 INV-2 — per-scan pinning of `S = S_global ∪ S_customer`

Per `T-CMP-TRI-03-01`, every scan pins both partitions; the union is materialized into the scan's pinned `S_version` set at submission. Determinism (a) is preserved because the applicable `S` partition and `S_version` are pinned per scan and recorded in provenance (`PLAN.md §"Algorithm 6 — Covariate shift"`).

### 5.3 The `spec_provenance` state machine

This component **owns the transitions**. The valid transitions are:

```
                       (customer-stream e-process accepts H0)
   global-unrevalidated ────────────────────────────────────► global-revalidated
            │                                                       │
            │ (customer's own proposal cleared via                  │ (no further
            │  customer-stream e-process from CMP-TRI-02)           │  transition;
            │                                                       │  spec remains
            ▼                                                       ▼  revalidated
        customer                                                customer
        (terminal for                                          (or quarantined
         customer-scope)                                        for that org)
```

Transition rules (binding):

| From | To | Trigger | Owner |
|---|---|---|---|
| (new global accept) | `global-unrevalidated` | `CMP-TRI-02` accepts a global spec; default per `DOC-DB §4.9`. | `CMP-TRI-02` |
| `global-unrevalidated` | `global-revalidated` | Customer-stream e-process accepts `H0(σ)` for this `(org_id, spec_version_id)`. | **`CMP-TRI-03`** |
| `global-unrevalidated` or `global-revalidated` | (quarantined for that org — schema-encoded via excluding the spec from that org's future pinned `S`) | Customer-stream drift e-process (complementary null) crosses `1/α`. | **`CMP-TRI-03`** |
| (new customer-scope proposal) | `customer` | Customer's own proposal cleared via the customer-stream e-process from `CMP-TRI-02`. | `CMP-TRI-02` (writing scope='customer' row) |

A spec **never** transitions back from `global-revalidated` to `global-unrevalidated` for a given customer once cleared; if subsequent drift occurs, the path is quarantine, not de-revalidation. Quarantine is per-customer; the same global spec remains active for other customers whose streams have not breached.

Tests: `TST-AC-TRI-03b [FORTHCOMING]` exercises the `global-unrevalidated` labeling discipline; `TST-AC-TRI-03a [FORTHCOMING]` exercises the auto-quarantine on adversarial customer distribution.

---

## 6. Dependency contract

| Depends-on | Why | Reference |
|---|---|---|
| `CMP-TRI-02` | Reuses the e-process update primitive and the betting confidence sequence implementation. The Gate-4 martingale-property unit test (`AC-TRI-02b`) applies to the same instrument running here; `CMP-TRI-03` cannot be production-enabled if `CMP-TRI-02` is not. | `WBS.md §20` |

Per `RULE-2`, implementation of `CMP-TRI-03` MUST NOT start until `CMP-TRI-02` is `DONE`. Production-enable of per-customer revalidation is additionally gated by **Gate 4** (`AC-TRI-02b`) and the falsifier `TST-AC-TRI-02a` being green per `CMP-TRI-02`'s contract.

Downstream consumers: `CMP-CP-04` (dashboard surfaces `spec_provenance` per-finding and per-spec, and surfaces quarantine events); `CMP-ORCH-03` (sets `findings.spec_provenance` at emission time from the consumed `spec_versions.spec_provenance` for the current pinned scope); `CMP-ORCH-01` (pins `S = S_global ∪ S_customer` at scan submission, excluding quarantined specs for the org).

---

## 7. Failure modes

| Failure | Detection | Response | Invariant impact |
|---|---|---|---|
| Drift detected on a global-accepted spec for a specific customer | Customer-stream drift e-process crosses `1/α` | **Auto-quarantine for that customer.** Open an incident (`DOC-RUNBOOK` — drift incident procedure). The customer's subsequent scans exclude the spec from pinned `S`. Previously emitted findings under that spec retain their historical `S_version` and are **not deleted** (INV-3 non-deletion contract). | None — by design. Determinism (a) preserved because the historical scan's `S_version` was pinned. |
| Customer has zero adjudicated findings for a long period | `n_observations = 0` indefinitely | `spec_provenance` remains `'global-unrevalidated'`; this is by design (`PLAN.md §"Covariate shift"`: *"for a customer with no labeled sample, `S_global` specs apply but contributed findings are labeled `spec_provenance = global-unrevalidated`"*). No alarm. | None. The labeling discipline is the correctness guarantee here. |
| Customer-stream `π₀` differs from global | Per-tenant policy override | The e-process uses the customer's `π₀`. The same Ville's-inequality guarantee holds at the customer's chosen floor. | None. The instrument is parametric in `π₀`. |
| Two concurrent revalidation transitions for the same `(org_id, spec_version_id)` | Application-level locking | First-writer wins; the second observes the post-transition state. | None. State-machine transitions are idempotent under the same e-process state. |
| Adversarial customer floods the labeling channel with biased labels | Drift-detection sensitivity tunes via π₀ / α | The instrument is anytime-valid; abuse manifests as spurious quarantines (a per-tenant DoS surface). Rate-limit customer adjudications at `CMP-CP-04`. | None to INV-3 / INV-2. Operational concern only. |
| `CMP-TRI-02`'s Gate 4 turns red after `CMP-TRI-03` is enabled | CI gate fail (`TST-AC-TRI-02b`) | Disable both `CMP-TRI-02` acceptance and `CMP-TRI-03` revalidation for production traffic; the implementation bug invalidates the guarantee for the shared instrument. | INV-3 anytime-valid guarantee suspended until Gate 4 is green again. |
| Drift detection itself modifies a `deterministic-core` field on `findings` (bug) | Schema-grant level (the `scanipy_triage_spec` role has no UPDATE grant on `findings` detection columns) | Permission error from Postgres; transaction aborts; alarm. | INV-3 violation prevented at the grant boundary. |

---

## 8. Provenance threading

`CMP-TRI-03` writes to two surfaces:

| Field | Where | Threading rule |
|---|---|---|
| `spec_versions.spec_provenance` | Updated to `'global-revalidated'` for the customer-scoped pin upon revalidation acceptance, OR a new `scope='customer'` row is created (schema mechanism: `CLAR-DB-05` see §10). | Transitions are append-only in spirit (specs are immutable; revalidation is recorded as either an attribute update on a scope='customer' shadow row or as a separate per-customer revalidation event row — exact persistence pattern is the open `CLAR-DB-05`). |
| `findings.spec_provenance` | Set at emission time by `CMP-ORCH-03` from the consumed `spec_versions.spec_provenance` (per-scope view) | `CMP-TRI-03` does NOT write to `findings`. The schema grants exclude this; the state-machine transitions affect *future* emissions only. |
| Quarantine event | A `provenance_records` row with `record_type='spec-acceptance'` reused or a new record_type for quarantine — exact mechanism via `CMP-FND-03` signing helpers; KMS-signed per `CLAR-DEPLOY-04`. | Append-only; signed; carries `S_version`, `env_digest`, `org_id`. |

Per `.claude/rules/02-provenance.md`:

- `CMP-TRI-03` is NOT enumerated in the per-component table as a direct mutator of any finding-level provenance field. Its surface is `spec_versions.spec_provenance` (for the per-customer view) and the customer-stream e-process state (a side-table jsonb).
- The four mandatory finding-level fields (`origin`, `S_version`, `env_digest`, `cpg_order_hash + annotation`) are NOT touched by this component. They are pinned at scan time (`CMP-ORCH-01` / `CMP-SNAP-01`) and emitted by `CMP-ORCH-03`.

Drift detection itself MUST NOT modify deterministic-core fields. The "drift was detected" signal is materialized as: (1) a state-machine transition on `spec_versions` for that customer's pin; (2) a logged event with KMS signature; (3) the **exclusion of the spec from future pinned `S` sets** for that customer at scan submission. No historical finding is mutated.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §9 CMP-TRI-03`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact | Notes |
|---|---|---|---|
| **AC-TRI-03a** | > A global-accepted spec on an adversarial customer distribution is quarantined by the shared e-process. | `TST-AC-TRI-03a` `[FORTHCOMING]` `[FALSIFIER]` | Construct a synthetic customer stream where a globally-accepted σ has true precision below π₀; assert auto-quarantine within bounded observations. Demonstrates the shared-instrument property (`PLAN.md §"Algorithm 6"`). |
| **AC-TRI-03b** | > Findings dependent on an unrevalidated global spec carry `global-unrevalidated` until revalidation. | `TST-AC-TRI-03b` `[FORTHCOMING]` `[INVARIANT]` | Run a customer scan that depends on a `spec_versions` row with `spec_provenance='global-unrevalidated'`; assert emitted findings carry `spec_provenance='global-unrevalidated'`. Verify transition to `'global-revalidated'` after customer-stream e-process clears. |

Cross-referenced upstream tests (consumed but not owned):

- `TST-AC-TRI-02b` (Gate 4 — martingale-property unit test) — applies to the shared instrument; must be green for `CMP-TRI-03` to operate correctly.
- `TST-AC-TRI-02a` (adversarial unbounded continuation) — applies to the global stream; the customer-stream variant is `TST-AC-TRI-03a`.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-TRI-03 |
|---|---|---|---|
| `CLAR-PARAM-02` | π₀ per detector class, α, per-class evaluation-stream definition (global) | **DEFERRED** (until Phase 5) | The customer-stream evaluation-stream definition for each detector class inherits from the global definition; per-tenant overrides are a policy concern, not blocking for implementation. |
| `CLAR-DB-05` *(NEW — FILED BY THIS DOCUMENT)* | Exact persistence pattern for per-customer revalidation/quarantine state | **OPEN** | Two viable schemas: (a) update `spec_versions.spec_provenance` on a customer-scoped shadow row with `scope='customer'` and an FK back to the global parent; (b) a dedicated `spec_revalidations` table keyed by `(org_id, spec_version_id)` with the e-process state, decision, and KMS-signed transition record. The SDD/PLAN does not pin one; the implementation PR will propose a design and request CTO sign-off. Both options preserve INV-2 (specs append-only) and INV-3 (pinned per scan). Blocks: nothing immediate — implementation should proceed with option (b) as the default unless `/cto` decides otherwise. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |
| `CLAR-PARAM-06` *(NOT FILED — explicit non-action)* | Customer-stream drift detection sensitivity / minimum observations before quarantine fires | n/a | The e-process is anytime-valid; there is no minimum-observation requirement. Spurious quarantines from low-`n` are mitigated by α being small (0.05); no separate parameter is needed. Implementation may add a soft-warning at low `n` but the quarantine threshold remains `E_t ≥ 1/α`. |

**New CLAR filed by this document:**

```
| CLAR-DB-05 | Per-customer revalidation/quarantine persistence pattern: customer-scope shadow row vs. dedicated spec_revalidations table | CMP-TRI-03 schema | Before Phase 8 enable |
```

To be appended to `WBS.md §17` by the next `WBS.md` editor (this document does not modify `WBS.md` directly per the SoT rule).

---

## 11. References

- `SDD.md §2 INV-3` — verbatim invariant.
- `SDD.md §9 CMP-TRI-03` — verbatim Purpose and ACs.
- `PLAN.md §"Algorithm 6 — Continuous revalidation / drift"` — shared-instrument property.
- `PLAN.md §"Algorithm 6 — Covariate shift"` — `S = S_global ∪ S_customer`; the `global-unrevalidated` labeling discipline.
- `docs/cross-cutting/DOC-ALGS.md §7.4, §7.8` — drift; failure modes.
- `docs/cross-cutting/DOC-INV.md §5.3` mechanism (d) — pinned-`S_version` discipline; §5.5 compliant example.
- `docs/cross-cutting/DOC-DB.md §4.9` (`spec_versions` with `spec_provenance` enum), §4.12 (`findings.spec_provenance` NULL semantics).
- `docs/cross-cutting/DOC-PROVENANCE.md` — `spec_provenance` enum description.
- `docs/components/DOC-CMP-TRI-01.md` (sibling) — LLM triage / proposing engine.
- `docs/components/DOC-CMP-TRI-02.md` (sibling) — e-process gate; provides the update primitive reused here.
- `docs/components/DOC-CMP-ORCH-01.md` (forthcoming) — pins `S = S_global ∪ S_customer` at scan submission.
- `docs/components/DOC-CMP-ORCH-03.md` (forthcoming) — sets `findings.spec_provenance` at emission time from the per-scope view of `spec_versions.spec_provenance`.
- `docs/components/DOC-CMP-FND-02.md` (forthcoming) — schema owner; `spec_versions` and `findings.spec_provenance` constraints.
- `docs/components/DOC-CMP-CP-04.md` (forthcoming) — dashboard surfaces `spec_provenance` and quarantine events.
- `WBS.md §11 (CMP-TRI-03)` — task list T-CMP-TRI-03-01..04.
- `WBS.md §17 CLAR-PARAM-02` (DEFERRED), `CLAR-DB-05` (NEW — filed by this document).
- `.claude/rules/00-global.md` (RULE-6, RULE-9 — Security Analyst review required).
- `.claude/rules/01-invariants.md §INV-3`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-TRI-03`. The shared-instrument property means this component cannot be production-enabled while `CMP-TRI-02`'s Gate 4 (`TST-AC-TRI-02b`) or falsifier (`TST-AC-TRI-02a`) is red.*

# DOC-CMP-TRI-02 — Anytime-valid e-process spec gate (Algorithm 6)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §9 CMP-TRI-02` (Purpose; AC-TRI-02a, AC-TRI-02b, AC-TRI-02c — quoted verbatim in §9)
- `SDD.md §2 INV-3` — *"No LLM output may influence a `deterministic-core` finding except via an accepted version-pinned spec in `S`."*
- `SDD.md §15 R-3` — *"Spec gate misuse — an e-process used without the martingale unit test invalidates the guarantee. Mitigation: AC-TRI-02b is a hard production-enablement gate."*
- `PLAN.md §"Algorithm 6 — Spec inference with an anytime-valid precision gate (item-3 design change)"` — load-bearing source for the algorithm
- `docs/cross-cutting/DOC-ALGS.md §7` — Algorithm 6 procedural form (mirrored in §3 and §6 below)
- `docs/cross-cutting/DOC-INV.md §5.5` — compliant spec-acceptance example
- `docs/cross-cutting/DOC-DB.md §4.8` (`proposed_specs`), §4.9 (`spec_versions`), §4.13 (`provenance_records` with `record_type='spec-acceptance'`)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md §CLAR-DEPLOY-04` — AWS KMS envelope encryption for signing the spec-acceptance provenance record
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md §CLAR-DEPLOY-14` — Anthropic `claude-sonnet-4-6` (proposing engine only; not on the acceptance path)
- `WBS.md §11 (CMP-TRI-02)` task list T-CMP-TRI-02-01..05; *"Risk owned: R-3"*
- `WBS.md §17 CLAR-PARAM-02` (**DEFERRED**) — π₀ per detector class collected in Phase 5; α=0.05 confirmed
- `CLAUDE.md §15` — Gate 4 (e-process unit) `AC-TRI-02b` — blocks customer-enablement deploy
- `.claude/rules/00-global.md` (RULE-6, RULE-7, RULE-9), `.claude/rules/01-invariants.md §INV-3`

This document is the **implementation contract** for `CMP-TRI-02`. The component owns the **R-3 risk** and the load-bearing **Gate 4** (`AC-TRI-02b` — martingale-property unit test; pre-customer-enablement deploy blocker per `CLAUDE.md §15`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-TRI-02` |
| Subsystem | Triage & Spec Inference (`SDD.md §9`) |
| Staging | post-core (after Stage A) |
| Depends-On | `CMP-DET-02`, `CMP-FND-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| Algorithm | Algorithm 6 — anytime-valid e-process for the precision-floor null `H0(σ): true precision of σ < π₀`. Acceptance: `E_t(σ) ≥ 1/α`. Multiplicity: e-process averaging (closed under averaging). |
| INV-* touched | **INV-2** (accepted spec written as a new pinned `S_version` row); **INV-3** (the only legitimate LLM→core pathway — gated by the e-process, never on the detection path) |
| Risk owned | **R-3** (`SDD §15`). Mitigation: `AC-TRI-02b` martingale unit test is a hard production-enablement gate. |
| CI gate | **Gate 4** (e-process unit) per `CLAUDE.md §15` — `AC-TRI-02b` blocks customer-enablement deploy. |
| KMS signing | AWS KMS (`CLAR-DEPLOY-04`) — signs the `provenance_records` row with `record_type='spec-acceptance'` on every acceptance event. |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §9 CMP-TRI-02`):**

> An e-process per candidate spec for the precision-floor null `H0(σ): true precision < π₀`, valid under unbounded optional continuation (Ville's inequality); acceptance when `E_t(σ) ≥ 1/α`; multiplicity over selected specs by e-process averaging; no information horizon.

**Operational role.** `CMP-TRI-02` is the **gate** between the LLM-proposing engine (`CMP-TRI-01` and `CMP-RES-01` research mode) and the deterministic core's spec set `S`. It is the **only INV-3-compliant pathway** by which an LLM-derived artifact can ever influence a `deterministic-core` finding. The pathway is:

1. An LLM proposes a candidate spec (an AST in the combinator DSL — `CMP-DET-01`). The candidate is written to `proposed_specs` (`DOC-DB §4.8`) with `decision = 'pending'`.
2. Adjudicated findings (true-positive / false-positive labels) flow into the e-process `E_t(σ)`, one bounded `[0, 1]` outcome per finding.
3. When `E_t(σ) ≥ 1/α`, the candidate is accepted. A new row is written to `spec_versions` (`DOC-DB §4.9`) with a fresh semver `S_version`; the `proposed_specs.decision` is flipped to `'accepted'` with the FK pointing to the new `spec_versions` row.
4. A signed `provenance_records` row with `record_type='spec-acceptance'` is appended (`DOC-DB §4.13`); signing uses the AWS KMS CMK per `CLAR-DEPLOY-04`.
5. From this point, future scans that pin the new `S_version` consume the spec from the deterministic core. The LLM has NOT directly influenced any finding — the spec is now a frozen identifier.

The e-process is **anytime-valid** (Ville's inequality): the guarantee *"with probability ≥ 1−α, the accepted set `S` never, at any point in its unbounded evaluation history, contains a spec whose true precision on the evaluation stream is below π₀"* holds simultaneously for all looks and all specs, **without** an information horizon. This is the corrected v3.2 design that supersedes v3.1's α-spending function (`PLAN.md §"Algorithm 6"`, item-3 fix).

**What this component is forbidden to do.**

1. It MUST NOT mutate any existing `spec_versions` row. Acceptance materializes a *new* row; specs are append-only and version-pinned (`DOC-INV §4.6`).
2. It MUST NOT update `findings` directly; influence on findings is mediated solely by the new `S_version` being consumed by a later scan via `CMP-DET-02` / `CMP-CORE-01`.
3. It MUST NOT operate without the martingale-property unit test (`AC-TRI-02b`) passing — feature must be flag-gated by Gate-4 status.

---

## 3. Interface contract

`CMP-TRI-02` lives in `services/triage/spec_inference.py`. It exposes two principal entry points: an online update consumed per adjudicated finding, and a decision step that returns an `AcceptanceVerdict`.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

@dataclass(frozen=True)
class CandidateSpec:
    id: UUID                       # PK of the proposed_specs row
    org_id: UUID                   # tenant scoping (global proposers may set a system org_id)
    spec_body: dict                # DSL AST per DOC-DSL
    detector_class: str            # e.g. "injection", "ssrf"
    pi_zero: float                 # π₀ per class (CLAR-PARAM-02 — DEFERRED until Phase 5)
    alpha: float                   # type-I error; α = 0.05 (CLAR-PARAM-02 confirmed)

@dataclass(frozen=True)
class AdjudicatedFinding:
    finding_id: UUID
    label: Literal["tp", "fp"]     # bounded [0, 1] outcome (tp=1, fp=0)
    spec_id: UUID                  # which σ this finding contributes to
    adjudicated_at: str            # iso-8601

@dataclass(frozen=True)
class EProcessState:
    """Persisted as `proposed_specs.e_process_state` (jsonb)."""
    spec_id: UUID
    log_wealth: float              # log E_t(σ) — stored in log-space for numerical stability
    n_observations: int            # number of adjudicated findings processed
    last_bet_state: dict           # betting strategy internal state (T-CMP-TRI-02-02)

@dataclass(frozen=True)
class AcceptanceVerdict:
    spec_id: UUID
    decision: Literal["pending", "accepted", "quarantined"]
    e_value: float                 # current E_t(σ)
    threshold: float               # 1/α
    accepted_S_version: str | None # semver of the new spec_versions row, on accept

def update_e_process(state: EProcessState,
                     observation: AdjudicatedFinding) -> EProcessState:
    """One O(1) update to the e-process wealth.

    Implements a betting confidence sequence for a bounded [0,1] mean
    (Waudby-Smith & Ramdas 2024). Updates `log_wealth` by a multiplicative
    factor derived from the chosen betting strategy (T-CMP-TRI-02-02).
    """

def evaluate_proposed_spec(spec: CandidateSpec,
                           state: EProcessState) -> AcceptanceVerdict:
    """Decision step. Acceptance when E_t(σ) ≥ 1/α. Materializes a new
    `spec_versions` row + signed `provenance_records` row on accept."""
```

### 3.1 Decision rule (verbatim from `PLAN.md` Algorithm 6)

```
threshold := 1.0 / spec.alpha          # α = 0.05 ⇒ threshold = 20.0
e_value   := exp(state.log_wealth)

if e_value >= threshold:
    new_S_version := next_semver_for_class(spec.detector_class)
    spec_versions.insert(
        S_version       = new_S_version,
        scope           = 'global',     # or 'customer' for customer-specific gates
        spec_set        = spec.spec_body,
        spec_provenance = 'global-unrevalidated',   # CMP-TRI-03 transitions this
    )
    proposed_specs.update(
        id                          = spec.id,
        decision                    = 'accepted',
        accepted_as_spec_version_id = <new row id>,
        decided_at                  = now_utc(),
    )
    provenance_records.insert(
        record_type            = 'spec-acceptance',
        S_version              = new_S_version,
        env_digest             = analysis_env_digest(),
        cpg_order_hash         = <not applicable; pinned literal placeholder>,
        chain_payload          = { e_value, threshold, evaluation_stream_id,
                                   pi_zero, alpha, spec_id },
        signature_key_id       = KMS_CMK_ARN,        # CLAR-DEPLOY-04
        signature_algorithm    = 'ecdsa-p256-sha256',
        signature_value        = kms.sign(chain_payload).
    )
    return AcceptanceVerdict('accepted', e_value, threshold, new_S_version)

return AcceptanceVerdict(spec.id, 'pending', e_value, threshold, None)
```

The decision rule is **anytime-valid** (no horizon). It may be invoked after every observation (`update_e_process`) and the guarantee holds at every such look (Ville's inequality — `PLAN.md §"Algorithm 6"`).

### 3.2 Multiplicity / selection over N specs

Per `DOC-ALGS §7.5` and `PLAN.md §"Algorithm 6 — Multiplicity and selection"`:

> Selecting the maximum-recall candidate across `N` specs is handled by **maintaining one e-process per spec and combining by averaging** (an e-process is closed under averaging). This controls the family-wise error over the *selected* spec without a Bonferroni horizon.

Implementation: one `EProcessState` per `(spec_id)`; the combined-e-process for "any-accept" is the arithmetic mean of the individual `E_t(σ)` values; the guarantee `P(ever accept σ with true precision < π₀) ≤ α` holds simultaneously for all `σ` and all looks (`T-CMP-TRI-02-04`).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `CandidateSpec` | `proposed_specs` row inserted by an LLM proposer (`CMP-TRI-01` worker or `CMP-RES-01` Research mode). | The spec body is a DSL AST validated by `CMP-DET-02`'s closure check at proposal time. A spec that fails closure cannot reach `CMP-TRI-02`. |
| `AdjudicatedFinding` stream | Customer triage actions (human-labeled tp/fp) flow into the evaluation stream; Research mode contributes CVE-labeled findings. | Each observation is a bounded `[0, 1]` outcome. The evaluation-stream definition per detector class is itself `CLAR-PARAM-02` (DEFERRED). |
| `π₀` per detector class | `CLAR-PARAM-02` (DEFERRED — Phase 5 empirical baseline) | Per-class precision floor. Wired from config; not hardcoded. |
| `α` | `CLAR-PARAM-02` confirms `α = 0.05`. | Type-I error rate; the guarantee is `P(ever accept σ with true precision < π₀) ≤ α`. |

### 4.2 Outputs

**On every adjudicated observation:** an update to `proposed_specs.e_process_state` (jsonb). No `findings` row is touched.

**On acceptance:** three durable writes, in a single transaction:

1. `spec_versions` insert — new row with fresh `S_version` semver, `scope='global'` (or `'customer'` for customer-specific gates per `CMP-TRI-03`), `spec_provenance='global-unrevalidated'` (per `DOC-DB §4.9` default).
2. `proposed_specs` update — `decision='accepted'`, `accepted_as_spec_version_id=<new row id>`, `decided_at=now()`.
3. `provenance_records` insert — `record_type='spec-acceptance'`, KMS-signed chain payload capturing `{ e_value, threshold, π₀, α, spec_id, evaluation_stream_id }` (`DOC-DB §4.13`). The signature uses `signature_algorithm IN ('ecdsa-p256-sha256','ecdsa-p384-sha384')`; the CMK is per `CLAR-DEPLOY-04`.

**On quarantine** (when the customer-stream e-process for the complementary null crosses threshold — owned by `CMP-TRI-03`, but the spec's `decision` flips to `'quarantined'` here): `proposed_specs.decision='quarantined'`, no `spec_versions` mutation (specs are append-only).

---

## 5. Invariants touched

### 5.1 INV-3 — the gated LLM→core pathway

`CMP-TRI-02` is, by design, the **single legitimate INV-3-compliant pathway** from an LLM proposal to the deterministic core's spec set `S`. The component discharges INV-3 by composition of two mechanisms:

1. **The e-process gate.** The LLM's proposal does not become `S` until `E_t(σ) ≥ 1/α`, where the e-process is anytime-valid under Ville's inequality. The statistical guarantee `P(ever accept σ with true precision < π₀) ≤ α` holds simultaneously for all looks and all specs (`PLAN.md §"Algorithm 6"`; `DOC-ALGS §7.4`).
2. **Pinned `S_version` discipline.** Acceptance materializes a **new** `spec_versions` row with a fresh semver. The deterministic core reads only pinned `S_version` values per scan (never a mutable "current spec" pointer). The LLM thereby influences detection only via a frozen, signed, version-pinned artifact — never directly (`DOC-INV §5.5`; `AC-TRI-02c`).

Test: `TST-INV-3-TRI-02 [FORTHCOMING]` — an accepted spec materializes as a *new* `S_version`; no existing row is mutated.

### 5.2 INV-2 — pinned `S_version` materialization

Acceptance always writes a **new** `spec_versions` row, never updates an existing one. The `S_version` semver is the operational identifier the core consumes (`AC-TRI-02c`). Schema-level append-only discipline is enforced by the absence of UPDATE/DELETE grants on `spec_versions` outside the `scanipy_triage_spec` role and by the unique-constraint on `(scope='global', S_version)` (`DOC-DB §4.9`).

Test: `TST-INV-2-TRI-02 [FORTHCOMING]` — accepted specs are version-pinned (mirrored verbatim from `WBS.md §11` and `DOC-INV §4.7`).

### 5.3 R-3 risk — owned

`SDD §15 R-3`: *"Spec gate misuse — an e-process used without the martingale unit test invalidates the guarantee. Mitigation: AC-TRI-02b is a hard production-enablement gate."* The mitigation is enforced by **Gate 4** (`CLAUDE.md §15`): the martingale-property unit test `TST-AC-TRI-02b` is a CI gate that blocks customer-enablement deploy. A failing martingale test means the implementation does not satisfy `E[E_τ | H0] ≤ 1` and therefore the anytime-valid guarantee does not hold for this implementation regardless of theoretical pedigree.

---

## 6. Dependency contract

| Depends-on | Why | Reference |
|---|---|---|
| `CMP-DET-02` | The detector registry enforces the combinator-DSL closure check at proposal time (`AC-DET-02a`); a non-DSL spec is rejected before it can reach `CMP-TRI-02`. Algorithm 2's distributivity precondition (the licence for IFDS/IDE order-independence) holds *only* for DSL-members — `CMP-TRI-02` relies on this. | `WBS.md §20`; `DOC-INV §6.2.b` |
| `CMP-FND-02` | The `proposed_specs`, `spec_versions`, and `provenance_records` tables (and their grants) must exist with their constraints before `CMP-TRI-02` can write. The split-table + grants discipline that backs INV-3 (`DOC-DB §4.14` for triage; §4.8/§4.9 for spec acceptance) is delivered by `CMP-FND-02`. | `WBS.md §20`; `DOC-DB §4.8`, §4.9 |

Per `RULE-2` (`.claude/rules/00-global.md`), implementation of `CMP-TRI-02` MUST NOT start until both `CMP-DET-02` and `CMP-FND-02` are `DONE`. Production-enable of the spec-inference pathway is additionally gated by **Gate 4** (`AC-TRI-02b`) per `CLAUDE.md §15`.

Downstream consumers: `CMP-TRI-03` (per-customer revalidation reuses the same e-process instrument); `CMP-CORE-01` / `CMP-DET-02` (consume accepted `S_version` rows in subsequent scans); `CMP-RES-01` (Research mode contributes labeled-CVE findings into the evaluation stream).

---

## 7. Failure modes

| Failure | Detection | Response | Invariant impact |
|---|---|---|---|
| Martingale-property unit test fails in CI | `TST-AC-TRI-02b` red | **Gate 4 fail** — release blocked; customer-enablement deploy blocked. Implementation bug; fix and re-run. Production traffic must not flow through this component while this test is red. | R-3 risk realized; INV-3 guarantee suspended until green. |
| Adversarial unbounded-continuation campaign exceeds α | `TST-AC-TRI-02a` red | **Pre-customer-enablement gate** fails (`PLAN.md §"Falsifier"`, SDD R-3). Re-examine betting strategy, π₀ defaults, and the evaluation-stream definition. | Anytime-validity guarantee in question; do not promote to production. |
| KMS signing of `spec-acceptance` provenance row fails | KMS API error during the acceptance transaction | The entire transaction (spec_versions insert, proposed_specs update, provenance_records insert) MUST rollback atomically. The candidate remains `pending`. Alarm. | INV-2/INV-3 preserved (no partial state — the new `S_version` does not exist until its signed chain exists). |
| Evaluation-stream label corruption (an adjudicated finding's label is wrong) | Out-of-band — drift detection in `CMP-TRI-03` (the customer-stream e-process for the complementary null catches it eventually) | The contaminated update is recorded in the e-process; corruption shows up as a quarantine event downstream. The audit trail (`provenance_records` history) supports post-hoc forensics. | INV-3 anytime-valid guarantee is conditional on `H0` being well-defined; gross label corruption is a stream-quality issue, not an algorithm failure. |
| Numerical overflow in `E_t(σ)` over very long histories | Log-space wealth representation (`EProcessState.log_wealth`) | Mitigated by maintaining log-wealth; periodically renormalize betting state per `T-CMP-TRI-02-02`. | None when mitigated; an overflow would compromise the guarantee. |
| Two concurrent acceptance attempts for the same spec | Application-level locking on `proposed_specs.id` | One transaction wins; the other observes `decision='accepted'` and exits. `spec_versions.S_version` uniqueness (per scope) is enforced by the schema (`DOC-DB §4.9` UNIQUE constraint). | INV-2 preserved (no duplicate `S_version`). |
| LLM proposes a spec outside the DSL | `CMP-DET-02` closure check at proposal time | Rejected before reaching `CMP-TRI-02`; the `proposed_specs` row is never created. | INV-4 (DSL owner) preserved upstream. |

---

## 8. Provenance threading

`CMP-TRI-02` writes three kinds of records, all signed end-to-end:

| Field | Where | Threading rule |
|---|---|---|
| `spec_versions.S_version` (semver) | New row per acceptance | The semver is the operational pinned-spec identifier the core reads; once written, never mutated (append-only). |
| `spec_versions.spec_provenance` | Default `'global-unrevalidated'` (`DOC-DB §4.9`) | Set to `'global-unrevalidated'` at acceptance. State machine transitions are owned by `CMP-TRI-03` (see `DOC-CMP-TRI-03 §5.3`). |
| `proposed_specs.e_process_state` | jsonb update per observation | Persisted log-space wealth + betting state; supports anytime-valid recompute. |
| `provenance_records` row | New row per acceptance, `record_type='spec-acceptance'` | KMS-signed via the per-tenant CMK (`CLAR-DEPLOY-04`). Signature payload includes `{ e_value, threshold, π₀, α, spec_id, evaluation_stream_id }`. Append-only (no UPDATE/DELETE grants — `DOC-DB §4.13`). |
| `S_version`, `env_digest` on the `provenance_records` row | INV-2 fields on the signed chain row | `env_digest` is the analysis-env digest at acceptance time; `S_version` is the **new** semver being accepted. |

`CMP-TRI-02` MUST NOT write to `findings` (its DB role has no such grant). Influence on findings is mediated solely via the new pinned `S_version` being consumed by a later scan. Per `.claude/rules/02-provenance.md` per-component table:

> CMP-TRI-02 — *writes accepted spec as new `S_version` row in `spec_versions`; core consumes only pinned `S_version`.* Out-of-contract: write `provenance_records` directly (delegated through `CMP-FND-03` signing helpers).

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §9 CMP-TRI-02`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact | Gate |
|---|---|---|---|
| **AC-TRI-02a** | > **[Adversarial unbounded continuation]** Over many repeated campaigns with an over-broad spec and no finite horizon supplied, realized ever-false-acceptance rate ≤ α. | `TST-AC-TRI-02a` `[FORTHCOMING]` `[FALSIFIER]` | Pre-customer-enablement (`PLAN.md §"Falsifier"`, SDD R-3). |
| **AC-TRI-02b** | > The e-process implementation passes a martingale-property unit test (empirical `E[E_τ\|H0] ≤ 1` across simulated stopping times) before production enablement. | `TST-AC-TRI-02b` `[FORTHCOMING]` `[UNIT]` | **Gate 4** per `CLAUDE.md §15` — blocks customer-enablement deploy. |
| **AC-TRI-02c** | > An accepted spec is written version-pinned as a new `S_version`; the deterministic core only ever consumes pinned specs (INV-3). | `TST-AC-TRI-02c` `[FORTHCOMING]` `[INVARIANT]` | Standard release. |

Invariant tests cross-referenced (mirrored verbatim from `WBS.md §11 (CMP-TRI-02)` and `DOC-INV §4.7, §5.8`):

- `TST-INV-2-TRI-02 [FORTHCOMING]` — accepted specs are version-pinned; no in-place spec mutation.
- `TST-INV-3-TRI-02 [FORTHCOMING]` — accepted spec materializes as a new `S_version`; existing rows untouched.

Algorithm-level tests (cross-referenced from `DOC-ALGS §7.9`):

- `TST-AC-TRI-03a [FORTHCOMING]` — global-accepted spec on adversarial customer distribution is quarantined by the shared e-process (consumed by `CMP-TRI-03`; demonstrates the shared-instrument property).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-TRI-02 |
|---|---|---|---|
| `CLAR-PARAM-02` | π₀ per detector class, α, per-class evaluation-stream definition | **DEFERRED** (until Phase 5 empirical baseline) | π₀ values must be wired from config, not hardcoded. α=0.05 is confirmed and may be inlined as a default but should remain config-overridable. The per-class evaluation-stream definition affects which adjudicated findings contribute to which σ — a config-driven mapping is mandatory before the gate is meaningful on real traffic. |
| `CLAR-DEPLOY-04` | KMS / envelope-encryption vendor + rotation primitive | **RESOLVED** (2026-05-23) | AWS KMS; per-tenant CMKs; annual rotation. Spec-acceptance provenance row is signed via `kms:Sign` with `ecdsa-p256-sha256` (or `-p384-sha384`). |
| `CLAR-DEPLOY-14` | LLM provider (proposing engine only — not on the acceptance path) | **RESOLVED** (2026-05-23) | Anthropic `claude-sonnet-4-6`. Proposers (`CMP-TRI-01` / `CMP-RES-01`) emit candidates into `proposed_specs`; `CMP-TRI-02` does not call the LLM. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |
| `CLAR-PARAM-05` *(NOT FILED — explicit non-action)* | Specific betting-strategy choice within the Waudby-Smith & Ramdas 2024 family (e.g. coin-betting vs. ONS-style updates) | n/a | Implementation detail under `T-CMP-TRI-02-02`. `DOC-ALGS §7.10` flags this as a known sensitivity; not load-bearing. Document the chosen strategy in the implementation PR. |

No new CLAR-TRI-* are filed by this document. `CLAR-PARAM-02`'s resolution is the precondition for production enablement; on top of that, **Gate 4 (`TST-AC-TRI-02b`) and the falsifier `TST-AC-TRI-02a`** must both be green before the feature flag is turned on for any customer.

---

## 11. References

- `SDD.md §2 INV-3` — verbatim invariant.
- `SDD.md §9 CMP-TRI-02` — verbatim Purpose and ACs.
- `SDD.md §15 R-3` — owned risk.
- `PLAN.md §"Algorithm 6 — Spec inference with an anytime-valid precision gate (item-3 design change)"` — the algorithm itself, verbatim source.
- `PLAN.md §"Literature grounding"` — Robbins (1970); Howard, Ramdas, McAuliffe, Sekhon (2021); Ramdas, Grünwald, Vovk, Shafer (2023); Waudby-Smith & Ramdas (2024).
- `docs/cross-cutting/DOC-ALGS.md §7` — Algorithm 6 procedural form, complexity, invariants discharged, falsifier list.
- `docs/cross-cutting/DOC-INV.md §5` — INV-3 four-mechanism discharge; §5.5 compliant `maybe_accept` example.
- `docs/cross-cutting/DOC-DB.md §4.8` (`proposed_specs`), §4.9 (`spec_versions`), §4.13 (`provenance_records` with `record_type='spec-acceptance'`).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md §CLAR-DEPLOY-04` (AWS KMS) and `§CLAR-DEPLOY-14` (Anthropic `claude-sonnet-4-6`).
- `docs/components/DOC-CMP-TRI-01.md` (sibling) — LLM triage / proposing engine.
- `docs/components/DOC-CMP-TRI-03.md` (sibling) — per-customer revalidation + drift monitor (same instrument, customer stream).
- `docs/components/DOC-CMP-DET-02.md` (forthcoming) — detector registry / DSL closure check at proposal time.
- `docs/components/DOC-CMP-FND-02.md` (forthcoming) — schema owner.
- `docs/components/DOC-CMP-FND-03.md` (forthcoming) — signed-provenance writer (KMS signing helper).
- `WBS.md §11 (CMP-TRI-02)` — task list T-CMP-TRI-02-01..05; *Risk owned: R-3*.
- `WBS.md §17 CLAR-PARAM-02` (DEFERRED), `CLAR-DEPLOY-04` (RESOLVED), `CLAR-DEPLOY-14` (RESOLVED).
- `CLAUDE.md §15` — Gate 4 (`AC-TRI-02b`) — the customer-enablement deploy blocker.
- `.claude/rules/00-global.md` (RULE-6, RULE-7, RULE-9 — Security Analyst review required).
- `.claude/rules/01-invariants.md §INV-3`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-TRI-02`. The Gate 4 unit test (`TST-AC-TRI-02b`) and the falsifier (`TST-AC-TRI-02a`) are the load-bearing tests; the component cannot be production-enabled while either is red.*

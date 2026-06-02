"""CMP-TRI-02 -- Anytime-valid e-process spec gate (Algorithm 6).

Implementation contract: ``docs/components/DOC-CMP-TRI-02.md``.
Cross-cutting refs: ``PLAN.md §"Algorithm 6 -- Spec inference with an anytime-valid
precision gate"``, ``docs/cross-cutting/DOC-ALGS.md §7`` (procedural form),
``docs/cross-cutting/DOC-INV.md §5`` (INV-3), ``DOC-DB §4.8`` (``proposed_specs``),
``§4.9`` (``spec_versions``), ``§4.13`` (``provenance_records`` with
``record_type='spec-acceptance'``), ``.claude/rules/01-invariants.md`` (INV-2, INV-3),
``.claude/rules/02-provenance.md`` (threading rules).

This module is the **single INV-3-compliant pathway** from an LLM-proposed spec
to the deterministic core's spec set ``S``. An LLM proposal never directly
mutates the core: a candidate becomes ``S`` only when its anytime-valid e-process
wealth crosses ``E_t(sigma) >= 1/alpha``, at which point a **new** version-pinned
``spec_versions`` row is materialised and a signed ``spec-acceptance``
provenance record is appended. The core only ever reads pinned ``S_version``
rows; the e-process is a gate ahead of ``S``, never on the detection path.

The e-process (Algorithm 6, ``PLAN.md``) is a **betting confidence sequence for a
bounded ``[0, 1]`` mean** (Waudby-Smith & Ramdas 2024). The null is
``H0(sigma): true precision of sigma < pi_0``; the bet wagers that the mean exceeds ``pi_0``.
The wealth process ``E_t`` is a nonnegative supermartingale under ``H0`` with
``E_0 = 1`` and ``E[E_tau | H0] <= 1`` at every stopping time ``tau`` (Ville's
inequality), so the decision rule is valid under unbounded optional continuation
with **no information horizon**.

Betting-strategy choice (CLAR-PARAM-05 -- *documented, not filed*, per
DOC-CMP-TRI-02 §10): an **adaptive, variance-free Kelly-style** bet
``lambda_t = clip(kappa * (mu_hat_{t-1} - pi_0), 0, c/pi_0)`` keyed to the running precision
estimate ``mu_hat_{t-1}`` over outcomes strictly *before* ``X_t``. Three properties
make this a valid e-process, each guarded in :func:`update_e_process`:

1. **Predictability.** ``lambda_t`` is read from ``state`` (``mu_hat`` over ``X_1..X_{t-1}``)
   *before* ``X_t`` influences anything. Using ``X_t`` to pick ``lambda_t`` would
   silently break the supermartingale property.
2. **One-sided ``lambda >= 0``.** Under ``H0`` (``mu < pi_0``) the expected wealth factor
   ``E[1 + lambda(X - pi_0)] = 1 + lambda(mu - pi_0) <= 1`` exactly because ``lambda >= 0`` and
   ``mu - pi_0 < 0``. The clip-at-zero floor is the whole guarantee.
3. **Nonnegative wealth.** With ``lambda <= c/pi_0`` and ``c < 1`` the worst case
   ``X = 0`` gives a factor ``1 - lambda*pi_0 >= 1 - c > 0``; ``log1p`` is always
   defined. Wealth is accumulated in log-space for numerical stability over long
   histories (DOC-CMP-TRI-02 §7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID, uuid4

from services.scan.provenance import (
    CPG_ORDER_HASH_ANNOTATION,
    DEFAULT_SIGNATURE_ALG,
    KMSAsymmetricSigner,
    ProvenanceRecord,
    ProvenanceStore,
    SignatureAlg,
    SignedProvenanceRecord,
    sign_provenance,
)

# alpha = 0.05 is pinned (CLAR-PARAM-02 confirms alpha; only pi_0 per-class is DEFERRED).
# The acceptance threshold is 1/alpha = 20.0. alpha stays config-overridable on the
# CandidateSpec so the gate math works for any configured alpha.
DEFAULT_ALPHA: float = 0.05

# Betting-strategy constants (CLAR-PARAM-05 -- documented here, not filed).
# ``_BET_C`` (< 1) bounds the bet so the worst-case wealth factor stays
# >= (1 - c) > 0; ``_BET_KAPPA`` is the aggressiveness gain on the (mu_hat - pi_0) signal.
_BET_C: float = 0.5
_BET_KAPPA: float = 2.0

Decision = Literal["pending", "accepted", "quarantined"]


@dataclass(frozen=True)
class CandidateSpec:
    """A pending LLM-proposed spec under evaluation (``proposed_specs`` row).

    ``pi_zero`` is the per-class precision floor wired from config / the proposed
    row -- **never hardcoded** (CLAR-PARAM-02 leaves pi_0 per-class DEFERRED, but the
    gate math is valid for any configured pi_0). ``alpha`` defaults to the pinned
    0.05 but stays overridable.
    """

    id: UUID
    org_id: UUID
    spec_body: dict[str, object]
    detector_class: str
    pi_zero: float
    alpha: float = DEFAULT_ALPHA


@dataclass(frozen=True)
class EProcessState:
    """Persisted log-space e-process wealth + betting state.

    Stored as ``proposed_specs.e_process_state`` (jsonb). ``log_wealth`` is
    ``log E_t(sigma)``; ``E_0 = 1`` ==> ``log_wealth = 0.0`` at construction.
    The running ``sum_outcomes`` / ``n_observations`` give ``mu_hat_{t-1}`` -- the
    precision estimate over the outcomes seen *so far*, used to pick the next
    (predictable) bet.
    """

    spec_id: UUID
    pi_zero: float
    alpha: float = DEFAULT_ALPHA
    log_wealth: float = 0.0
    n_observations: int = 0
    sum_outcomes: float = 0.0
    last_bet_state: dict[str, float] = field(default_factory=dict)

    @property
    def e_value(self) -> float:
        """Current wealth ``E_t(sigma) = exp(log_wealth)``."""
        return math.exp(self.log_wealth)

    @property
    def threshold(self) -> float:
        """Acceptance threshold ``1/alpha`` (alpha = 0.05 ==> 20.0)."""
        return 1.0 / self.alpha

    @property
    def mean_estimate(self) -> float:
        """``mu_hat_{t-1}`` -- running mean of outcomes seen so far (0.0 cold start)."""
        if self.n_observations == 0:
            return 0.0
        return self.sum_outcomes / self.n_observations


@dataclass(frozen=True)
class AcceptanceVerdict:
    """Decision-step result (DOC-CMP-TRI-02 §3.1).

    A single finding is never ``mixed``; ``decision`` is one of
    ``pending`` / ``accepted`` / ``quarantined``. On accept,
    ``accepted_S_version`` carries the fresh semver of the new
    ``spec_versions`` row.
    """

    spec_id: UUID
    decision: Decision
    e_value: float
    threshold: float
    # `S_version` is the spec'd field name (DOC-CMP-TRI-02 §3.1; matches the
    # `S_version` convention used across the codebase, e.g. provenance records).
    accepted_S_version: str | None = None  # noqa: N815


def initial_state(spec: CandidateSpec) -> EProcessState:
    """Construct ``E_0 = 1`` (``log_wealth = 0``) for ``spec`` -- no observations yet."""
    return EProcessState(
        spec_id=spec.id,
        pi_zero=spec.pi_zero,
        alpha=spec.alpha,
        log_wealth=0.0,
        n_observations=0,
        sum_outcomes=0.0,
        last_bet_state={},
    )


def _predictable_bet(state: EProcessState) -> float:
    """Choose ``lambda_t`` from ``state`` ALONE (predictable -- no ``X_t`` here).

    ``lambda_t = clip(kappa * (mu_hat_{t-1} - pi_0), 0, c/pi_0)``. The clip-at-zero floor makes the
    bet one-sided (it only ever wagers the mean is *above* pi_0), which is exactly
    what keeps the wealth a supermartingale under ``H0`` (mu < pi_0). The upper clip
    ``c/pi_0`` (c < 1) keeps the worst-case (``X = 0``) factor ``1 - lambda*pi_0 >= 1 - c``
    strictly positive, so wealth never goes non-positive and ``log1p`` is always
    defined. Cold start (no observations) ==> mu_hat = 0 ==> lambda = 0 (harmless).
    """
    pi_zero = state.pi_zero
    raw = _BET_KAPPA * (state.mean_estimate - pi_zero)
    upper = _BET_C / pi_zero if pi_zero > 0.0 else 0.0
    if raw < 0.0:
        return 0.0
    if raw > upper:
        return upper
    return raw


def update_e_process(state: EProcessState, outcome: float) -> EProcessState:
    """One O(1) anytime-valid e-process update for a bounded ``[0, 1]`` outcome.

    ``outcome`` is one adjudicated finding's label mapped to ``[0, 1]``
    (tp = 1.0, fp = 0.0; partial labels permitted). The update is a betting
    confidence sequence for the bounded mean (Waudby-Smith & Ramdas 2024):

    1. **Read** the predictable bet ``lambda_t`` from ``state`` (``mu_hat`` over
       ``X_1..X_{t-1}``) -- *before* ``outcome`` touches anything.
    2. **Apply** the multiplicative wealth factor in log-space:
       ``log_wealth += log1p(lambda_t * (outcome - pi_0))``.
    3. **Fold** ``outcome`` into the running stats for the *next* step's bet.

    Ordering 1->2->3 is the predictability guarantee: ``X_t`` enters the wealth and
    the stats but never the choice of ``lambda_t``. Reordering would silently void the
    supermartingale property (and 02a/02b would pass while being unsound).

    CLAR-TRI-01 (WBS §17): this primitive deliberately operates on the bounded
    ``[0, 1]`` ``outcome`` rather than DOC-CMP-TRI-02 §3's ``observation:
    AdjudicatedFinding``. The adjudication->outcome projection
    (``AdjudicatedFinding.label`` -> ``tp = 1.0`` / ``fp = 0.0``) is the caller's
    responsibility; ``finding_id`` traceability lives on
    ``proposed_specs.e_process_state`` at the evaluate/caller layer, not threaded
    into this O(1) statistical update. See CLAR-TRI-01 for the sanctioned deviation.
    """
    if not (0.0 <= outcome <= 1.0):
        raise ValueError(f"outcome must be bounded in [0, 1]; got {outcome!r}")

    pi_zero = state.pi_zero

    # (1) Predictable bet -- depends ONLY on state, never on `outcome`.
    lam = _predictable_bet(state)

    # (2) Multiplicative wealth update in log-space. With lambda <= c/pi_0 (c < 1) and
    # outcome in [0, 1], the factor (1 + lambda(outcome - pi_0)) in [1 - c, 1 + lambda(1 - pi_0)]
    # is strictly positive, so log1p is always defined.
    factor_minus_one = lam * (outcome - pi_zero)
    new_log_wealth = state.log_wealth + math.log1p(factor_minus_one)

    # (3) Fold the outcome into the running stats AFTER betting on it.
    return replace(
        state,
        log_wealth=new_log_wealth,
        n_observations=state.n_observations + 1,
        sum_outcomes=state.sum_outcomes + outcome,
        last_bet_state={"last_lambda": lam, "last_outcome": outcome},
    )


def combined_e_value(states: list[EProcessState]) -> float:
    """Combined "any-accept" e-value over ``N`` specs -- arithmetic mean of ``E_t``.

    An e-process is closed under averaging (DOC-ALGS §7.5, PLAN §"Algorithm 6 --
    Multiplicity and selection"); the mean of the per-spec ``E_t(sigma)`` is itself an
    e-process, so the family-wise guarantee ``P(ever accept sigma with true precision
    < pi_0) <= alpha`` holds over the *selected* spec without a Bonferroni horizon.
    """
    if not states:
        return 1.0
    return sum(s.e_value for s in states) / len(states)


# --------------------------------------------------------------------------- #
# Persistence ports (injected; in-memory fakes in tests -- DI pattern of        #
# services/scan/provenance + tests/fnd03_fakes.py / tests/tri01_fakes.py).     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SpecVersionRow:
    """An append-only ``spec_versions`` row (DOC-DB §4.9).

    ``S_version`` is the pinned semver the deterministic core reads. The
    e-process detail ``{e_value, threshold, pi_0, alpha}`` is persisted *here* (not
    inlined in the provenance record -- CLAR-FND-01). Append-only: once written a
    row is never mutated (specs are version-pinned, INV-2).
    """

    id: UUID
    org_id: UUID | None
    S_version: str
    scope: Literal["global", "customer"]
    spec_set: dict[str, object]
    spec_provenance: Literal["global-unrevalidated", "global-revalidated", "customer"]
    e_process_detail: dict[str, float]


@runtime_checkable
class SpecVersionStore(Protocol):
    """Append-only persistence port for ``spec_versions`` (DOC-DB §4.9).

    No ``update`` / ``delete`` method -- faithfully models the absence of
    UPDATE/DELETE grants outside ``scanipy_triage_spec`` (INV-2 append-only).
    """

    def all_for_class(
        self, detector_class: str, *, scope: str = "global"
    ) -> list[SpecVersionRow]: ...

    def insert(self, row: SpecVersionRow) -> None: ...


@runtime_checkable
class ProposedSpecStore(Protocol):
    """Persistence port for ``proposed_specs`` decision flips (DOC-DB §4.8)."""

    def mark_accepted(
        self, spec_id: UUID, *, accepted_as_spec_version_id: UUID, decided_at: datetime
    ) -> None: ...

    def mark_quarantined(self, spec_id: UUID) -> None: ...


def _bump_patch(version: str) -> str:
    """Increment the patch component of a ``MAJOR.MINOR.PATCH`` semver string."""
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"not a MAJOR.MINOR.PATCH semver: {version!r}")
    major, minor, patch = (int(p) for p in parts)
    return f"{major}.{minor}.{patch + 1}"


def next_semver_for_class(
    detector_class: str,
    spec_versions: SpecVersionStore,
    *,
    scope: str = "global",
) -> str:
    """Next fresh semver for ``detector_class``: bump the highest existing patch.

    Specs are version-pinned and append-only, so acceptance always allocates a
    NEW semver; it never reuses or mutates an existing one. With no prior version
    the first accepted spec for a class is ``1.0.0``.
    """
    existing = spec_versions.all_for_class(detector_class, scope=scope)
    if not existing:
        return "1.0.0"

    def _key(row: SpecVersionRow) -> tuple[int, int, int]:
        major, minor, patch = (int(p) for p in row.S_version.split("."))
        return (major, minor, patch)

    highest = max(existing, key=_key)
    return _bump_patch(highest.S_version)


def _spec_acceptance_record(
    spec: CandidateSpec,
    *,
    new_S_version: str,  # noqa: N803 -- `S_version` is the spec'd field name (DOC-CMP-TRI-02 §3.1)
    env_digest: str,
    scan_id: UUID,
) -> ProvenanceRecord:
    """Build the ``record_type='spec-acceptance'`` provenance record (DOC §3.1).

    Scan-level (``finding_id`` NULL). Carries INV-2 fields ``S_version`` (the
    *new* semver) and ``env_digest``. ``cpg_order_hash`` is not applicable to a
    spec acceptance, so it is NULL -- but the INV-5 annotation MUST still be the
    pinned literal ``CPG_ORDER_HASH_ANNOTATION`` (``sign_provenance`` rejects any
    other value, defence-in-depth, even when the hash is NULL). The source /
    snapshot links are not applicable to a scan-level spec acceptance; defensible
    sentinel values are used (DOC-CMP-TRI-02 §4.2 records the e-process detail on
    the spec_versions row, not the provenance link fields).
    """
    return ProvenanceRecord(
        id=uuid4(),
        parent_record_id=None,
        record_type="spec-acceptance",
        scan_id=scan_id,
        finding_id=None,  # scan-level acceptance, not a per-finding record
        org_id=spec.org_id,
        codebase_id=spec.org_id,  # sentinel: no codebase for a spec acceptance
        commit_sha="0" * 40,  # sentinel: spec acceptance is not tied to a commit
        scm_provider="n/a",
        snapshot_id=spec.id,  # sentinel: link the proposed-spec id for traceability
        snapshot_digest="sha256:" + ("0" * 64),  # type: ignore[arg-type]
        precondition_status="closed-world",
        S_version=new_S_version,  # type: ignore[arg-type]  # INV-2: the NEW semver
        env_digest=env_digest,  # type: ignore[arg-type]  # INV-2
        cpg_order_hash=None,  # not applicable to spec acceptance
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,  # INV-5: pinned literal
        fingerprint_class=None,
        witness_blob_uri=None,
        slice_fingerprint=None,
        rule_id=None,
        spec_id=str(spec.id),
        detector_id=None,
        detector_engine=None,
        sarif_hash=None,
        origin=None,  # not a finding; origin guard only fires for chain/repartition
        determinism_partition=None,
        repartition_reason=None,
        repartition_oracle_id=None,
        claim_label="UNCONDITIONAL",  # anytime validity via Ville's inequality
    )


def evaluate_proposed_spec(
    spec: CandidateSpec,
    state: EProcessState,
    *,
    spec_versions: SpecVersionStore | None = None,
    proposed_specs: ProposedSpecStore | None = None,
    provenance_store: ProvenanceStore | None = None,
    signer: KMSAsymmetricSigner | None = None,
    kms_key_arn: str = "arn:aws:kms:us-east-1:000000000000:key/spec-acceptance",
    env_digest: str = "sha256:" + ("e" * 64),
    scan_id: UUID | None = None,
    signature_alg: SignatureAlg = DEFAULT_SIGNATURE_ALG,
    decided_at: datetime | None = None,
) -> AcceptanceVerdict:
    """Decision step. Acceptance when ``E_t(sigma) >= 1/alpha`` (alpha = 0.05 ==> 20.0).

    On acceptance, three durable writes are performed (DOC-CMP-TRI-02 §4.2),
    INV-2 / INV-3 compliant:

    1. A **new** ``spec_versions`` row with a fresh semver ``S_version`` (no
       existing row mutated -- append-only).
    2. ``proposed_specs.decision = 'accepted'`` with the FK to the new row.
    3. A signed ``provenance_records`` row ``record_type='spec-acceptance'``
       (delegated to CMP-FND-03 :func:`sign_provenance`), carrying ``S_version``
       + ``env_digest`` (INV-2).

    The deterministic core thereafter reads only the pinned ``S_version``; the
    LLM never directly influences a ``deterministic-core`` finding (INV-3). The
    persistence ports are injected so the component is testable offline (the
    in-memory fakes mirror ``tests/fnd03_fakes.py`` / ``tests/tri01_fakes.py``);
    if none are supplied the decision is computed without side effects.

    ATOMICITY (DOC-CMP-TRI-02 §7): the caller MUST wrap the three durable writes
    -- (1) the ``spec_versions`` insert, (2) the ``proposed_specs`` decision flip,
    and (3) the signed ``provenance_records`` insert -- in a SINGLE DB
    transaction. A KMS-signing or any write exception at ANY step MUST roll back
    ALL THREE: the new ``S_version`` must not exist until its signed chain row
    exists, and the candidate stays ``pending`` (no partial state; INV-2 / INV-3
    preserved). This function performs the writes in-order via the injected ports
    but does NOT own the transaction boundary -- that is the caller's contract.

    ``decided_at`` is the acceptance decision timestamp recorded on the
    ``proposed_specs`` flip; it defaults to ``datetime.now(timezone.utc)`` when not
    supplied (caller may pin it for deterministic / replayed acceptance).
    """
    e_value = state.e_value
    threshold = state.threshold

    if e_value < threshold:
        return AcceptanceVerdict(
            spec_id=spec.id,
            decision="pending",
            e_value=e_value,
            threshold=threshold,
            accepted_S_version=None,
        )

    new_S_version = (  # noqa: N806 -- `S_version` is the spec'd field name (DOC-CMP-TRI-02 §3.1)
        next_semver_for_class(spec.detector_class, spec_versions)
        if spec_versions is not None
        else "1.0.0"
    )

    # (1) New append-only spec_versions row (INV-2: version-pinned).
    new_row = SpecVersionRow(
        id=uuid4(),
        org_id=None,  # scope='global' ==> org_id NULL (DDL scope/org CHECK)
        S_version=new_S_version,
        scope="global",
        spec_set=spec.spec_body,
        spec_provenance="global-unrevalidated",  # CMP-TRI-03 transitions this
        e_process_detail={
            "e_value": e_value,
            "threshold": threshold,
            "pi_zero": spec.pi_zero,
            "alpha": spec.alpha,
        },
    )
    if spec_versions is not None:
        spec_versions.insert(new_row)

    # (3) Signed spec-acceptance provenance row (delegated to CMP-FND-03).
    if provenance_store is not None and signer is not None:
        record = _spec_acceptance_record(
            spec,
            new_S_version=new_S_version,
            env_digest=env_digest,
            scan_id=scan_id or uuid4(),
        )
        signed: SignedProvenanceRecord = sign_provenance(
            record,
            signer=signer,
            kms_key_arn=kms_key_arn,
            signature_alg=signature_alg,
            store=provenance_store,
        )
        # INV-2 self-check: the signed chain row carries the new semver.
        if signed.record.S_version != new_S_version:  # pragma: no cover - defensive
            raise AssertionError("spec-acceptance provenance S_version mismatch")

    # (2) Flip the proposed_specs decision with the FK to the new row.
    if proposed_specs is not None:
        proposed_specs.mark_accepted(
            spec.id,
            accepted_as_spec_version_id=new_row.id,
            # `timezone.utc` (not the 3.11+-only `datetime.UTC` alias that UP017
            # suggests) keeps this import-safe on the 3.10 validation venv too; the
            # two are the identical object on py311 -- hence the UP017 suppression.
            decided_at=decided_at or datetime.now(timezone.utc),  # noqa: UP017
        )

    return AcceptanceVerdict(
        spec_id=spec.id,
        decision="accepted",
        e_value=e_value,
        threshold=threshold,
        accepted_S_version=new_S_version,
    )


# =========================================================================== #
# CMP-TRI-03 -- Per-customer revalidation + drift monitor.                     #
#                                                                             #
# Implementation contract: ``docs/components/DOC-CMP-TRI-03.md``.             #
# Cross-cutting refs: ``PLAN.md §"Algorithm 6 -- Continuous revalidation /     #
# drift"`` + ``§"Covariate shift"``, ``docs/cross-cutting/DOC-ALGS.md §7.4    #
# / §7.8``, ``.claude/rules/01-invariants.md §INV-3``,                         #
# ``.claude/rules/02-provenance.md`` (spec_provenance state machine).         #
#                                                                             #
# TRI-03 reuses TRI-02's VERIFIED e-process instrument. ``S = S_global U      #
# S_customer``; the same anytime-valid e-process runs on the CUSTOMER's       #
# adjudicated (human-labelled) stream -- never on the LLM output, never on    #
# the detection path (INV-3). Two e-processes per (org, spec):                #
#                                                                             #
#   * REVALIDATE -- the SAME null as TRI-02 (``H0: precision < pi_0``); it     #
#     reuses :func:`update_e_process` / :func:`_predictable_bet` VERBATIM.     #
#     Crossing ``E_t >= 1/alpha`` transitions ``spec_provenance``             #
#     ``global-unrevalidated -> global-revalidated`` for this customer.       #
#                                                                             #
#   * DRIFT -- the COMPLEMENTARY null (``H0_drift: precision >= pi_0`` -- the  #
#     *good* hypothesis). Rejecting it (drift ``E_t >= 1/alpha``) means        #
#     "precision has FALLEN BELOW the floor" -> auto-quarantine sigma for      #
#     that customer (PLAN §"Algorithm 6", DOC-ALGS §7.8). It is the SYMMETRIC  #
#     MIRROR of TRI-02's construction under ``X -> 1 - X``, ``pi_0 ->          #
#     1 - pi_0``: a predictable bet ``lambda_t`` computed from                 #
#     ``mu_hat_{t-1}`` STRICTLY BEFORE ``X_t`` (predictability = the           #
#     supermartingale / Ville guarantee), log-space accumulation, wealth >= 0. #
#                                                                             #
# To make the mirror PROVABLY the verified instrument, the drift update is     #
# implemented by REDUCTION: ``drift_update(state, X) ==                       #
# update_e_process(state', 1 - X)`` where ``state'`` carries ``pi_zero =       #
# 1 - pi_0``. Predictability, the martingale property, nonnegative wealth, and #
# the CORRECT worst-case clip ``c/(1 - pi_0)`` (worst case is ``X = 1`` for    #
# the drift direction, factor ``1 - lambda*(1 - pi_0)``) all hold BY          #
# CONSTRUCTION because the body is TRI-02's already-tested code. The explicit  #
# mirror bet :func:`_predictable_drift_bet` is provided for reviewer           #
# legibility (and equality with the reduction is asserted in the tests).       #
#                                                                             #
# Quarantine is an EXCLUSION decision (a state flag) -- the spec is dropped     #
# from the org's FUTURE pinned ``S``. It NEVER mutates ``findings.origin`` /   #
# detection / ``status``, and NEVER deletes a finding (INV-3 non-deletion).    #
# The three-value ``spec_provenance`` enum never gains a 4th value and never   #
# transitions back from ``global-revalidated``.                               #
# =========================================================================== #


RevalidationDecision = Literal["pending", "revalidated", "quarantined"]

# The drift quarantine threshold is the same anytime-valid ``1/alpha`` as the
# acceptance / revalidation threshold (Ville's inequality). alpha = 0.05 ==> 20.0.


@dataclass(frozen=True)
class CustomerEvaluationStream:
    """Per-customer evaluation-stream config (DOC-CMP-TRI-03 §3).

    ``pi_zero`` is the CUSTOMER's precision floor -- config-wired from tenant
    policy, **never hardcoded** (it defaults to the global pi_0 per
    CLAR-PARAM-02 but may be tightened per tenant). ``alpha`` defaults to the
    pinned 0.05 but stays overridable so the gate math works for any configured
    alpha. One stream per ``(org_id, spec_version_id)``.
    """

    org_id: UUID
    spec_version_id: UUID  # the global spec being revalidated on this customer
    pi_zero: float
    alpha: float = DEFAULT_ALPHA


@dataclass(frozen=True)
class CustomerEProcessState:
    """Per-(org, spec) customer-stream e-process state (DOC-CMP-TRI-03 §3).

    Holds TWO log-space wealth processes over the SAME customer-adjudicated
    stream, both ``E_0 = 1`` (``log_wealth = 0.0``) at construction:

    * ``log_wealth_revalidate`` -- ``log E_t`` for the REVALIDATION null
      (``H0: precision < pi_0``; same direction as TRI-02). Crossing
      ``E_t >= 1/alpha`` ==> revalidated.
    * ``log_wealth_drift`` -- ``log E_t`` for the COMPLEMENTARY drift null
      (``H0_drift: precision >= pi_0``). Crossing ``E_t >= 1/alpha`` ==>
      quarantine ("precision has fallen below floor").

    ``sum_outcomes`` / ``n_observations`` give ``mu_hat_{t-1}`` -- the running
    precision estimate over outcomes seen *so far*, used to pick BOTH predictable
    bets for the next (strictly future) observation. Persisted via an injected
    in-memory store in tests (DI pattern of ``tests/tri02_fakes.py`` /
    ``tests/tri01_fakes.py``); the production persistence schema is deferred
    (CLAR-DB-05 -- filed by the orchestrator).
    """

    org_id: UUID
    spec_version_id: UUID
    pi_zero: float
    alpha: float = DEFAULT_ALPHA
    log_wealth_revalidate: float = 0.0
    log_wealth_drift: float = 0.0
    n_observations: int = 0
    sum_outcomes: float = 0.0

    @property
    def threshold(self) -> float:
        """Anytime-valid threshold ``1/alpha`` (alpha = 0.05 ==> 20.0)."""
        return 1.0 / self.alpha

    @property
    def e_value_revalidate(self) -> float:
        """Current revalidation wealth ``E_t = exp(log_wealth_revalidate)``."""
        return math.exp(self.log_wealth_revalidate)

    @property
    def e_value_drift(self) -> float:
        """Current drift wealth ``E_t = exp(log_wealth_drift)``."""
        return math.exp(self.log_wealth_drift)

    @property
    def mean_estimate(self) -> float:
        """``mu_hat_{t-1}`` -- running mean of outcomes so far (0.0 cold start)."""
        if self.n_observations == 0:
            return 0.0
        return self.sum_outcomes / self.n_observations


@dataclass(frozen=True)
class RevalidationResult:
    """Decision-step result for the customer-stream e-process (DOC §3).

    ``decision`` is one of ``pending`` / ``revalidated`` / ``quarantined``.
    Both e-values are surfaced so the dashboard (CMP-CP-04) can show the
    revalidation and drift wealth side by side.
    """

    org_id: UUID
    spec_version_id: UUID
    decision: RevalidationDecision
    e_value_revalidate: float
    e_value_drift: float


def initial_customer_state(stream: CustomerEvaluationStream) -> CustomerEProcessState:
    """Construct ``E_0 = 1`` (both wealths ``log_wealth = 0``) for ``stream``."""
    return CustomerEProcessState(
        org_id=stream.org_id,
        spec_version_id=stream.spec_version_id,
        pi_zero=stream.pi_zero,
        alpha=stream.alpha,
        log_wealth_revalidate=0.0,
        log_wealth_drift=0.0,
        n_observations=0,
        sum_outcomes=0.0,
    )


def _drift_view(state: CustomerEProcessState) -> EProcessState:
    """The MIRRORED ``EProcessState`` that reduces drift to TRI-02's instrument.

    Under ``X -> 1 - X``, ``pi_0 -> 1 - pi_0`` the drift e-process on the customer
    stream IS TRI-02's verified e-process on the mirrored input against the
    mirrored floor. This view carries the drift wealth, the mirrored floor
    ``1 - pi_0``, and the mirrored running stats (``sum -> n - sum``) so that
    :func:`_predictable_bet` / :func:`update_e_process` operate on it VERBATIM. The
    ``mean_estimate`` cold-start semantics (0.0 at ``n = 0``) are inherited from
    :class:`EProcessState` exactly, so the hand-mirror and the reduction agree
    everywhere (asserted in the test-suite).
    """
    return EProcessState(
        spec_id=state.spec_version_id,
        pi_zero=1.0 - state.pi_zero,
        alpha=state.alpha,
        log_wealth=state.log_wealth_drift,
        n_observations=state.n_observations,
        sum_outcomes=float(state.n_observations) - state.sum_outcomes,
    )


def _predictable_drift_bet(state: CustomerEProcessState) -> float:
    """The SYMMETRIC MIRROR of :func:`_predictable_bet` (drift direction).

    Conceptually ``lambda_t = clip(kappa * (pi_0 - mu_hat_{t-1}), 0,
    c/(1 - pi_0))`` -- TRI-02's :func:`_predictable_bet` under ``X -> 1 - X``,
    ``pi_0 -> 1 - pi_0``: the signal flips to ``(1 - pi_0) - mirror_mu_hat`` (the
    bet only ever wagers the mean is *below* pi_0), keeping the DRIFT wealth a
    supermartingale under ``H0_drift`` (precision >= pi_0). The upper clip is
    ``c/(1 - pi_0)`` -- NOT ``c/pi_0`` -- because the worst-case factor for the
    drift direction is at ``X = 1``: ``1 - lambda*(1 - pi_0)``, which stays
    ``>= 1 - c > 0`` only if ``lambda <= c/(1 - pi_0)``. (Copying TRI-02's
    ``c/pi_0`` verbatim would let ``log1p`` go non-positive for small pi_0; the
    bound is direction-specific.) Implemented by REDUCTION -- it returns
    :func:`_predictable_bet` on the mirrored :func:`_drift_view` -- so the bet IS
    TRI-02's verified, predictable bet (it reads ``state`` over ``X_1..X_{t-1}``
    ALONE, never ``X_t``), with the correct clip and cold-start by construction.
    """
    return _predictable_bet(_drift_view(state))


def update_customer_e_process(
    state: CustomerEProcessState, outcome: float
) -> CustomerEProcessState:
    """One O(1) update of BOTH customer-stream e-processes for a ``[0, 1]`` outcome.

    ``outcome`` is one customer-adjudicated finding's label mapped to ``[0, 1]``
    (tp = 1.0, fp = 0.0; partial labels permitted). The REVALIDATE wealth is
    updated by TRI-02's VERIFIED :func:`update_e_process` VERBATIM (same null,
    same instrument); the DRIFT wealth is updated by REDUCTION to the SAME
    verified instrument on the mirrored input ``1 - outcome`` against the
    mirrored floor ``1 - pi_0``. Both updates obey the predictability ordering
    1->2->3 (bet read from ``state`` BEFORE ``outcome`` touches anything), so the
    supermartingale / Ville guarantee transfers unchanged from TRI-02.

    The drift bet is ALSO available as the explicit mirror
    :func:`_predictable_drift_bet`; it is asserted equal to the reduction's bet
    in the test-suite (the proof the hand-mirror IS the verified instrument).
    """
    if not (0.0 <= outcome <= 1.0):
        raise ValueError(f"outcome must be bounded in [0, 1]; got {outcome!r}")

    pi_zero = state.pi_zero

    # (REVALIDATE) -- TRI-02's verified instrument, VERBATIM, same null.
    reval_view = EProcessState(
        spec_id=state.spec_version_id,
        pi_zero=pi_zero,
        alpha=state.alpha,
        log_wealth=state.log_wealth_revalidate,
        n_observations=state.n_observations,
        sum_outcomes=state.sum_outcomes,
    )
    reval_next = update_e_process(reval_view, outcome)

    # (DRIFT) -- the SAME verified instrument by REDUCTION: complementary null,
    # mirrored input (1 - outcome) against the mirrored floor (1 - pi_0). This is
    # literally TRI-02's tested update, so predictability + martingale + the
    # correct c/(1 - pi_0) clip all hold by construction.
    drift_next = update_e_process(_drift_view(state), 1.0 - outcome)

    return replace(
        state,
        log_wealth_revalidate=reval_next.log_wealth,
        log_wealth_drift=drift_next.log_wealth,
        n_observations=state.n_observations + 1,
        sum_outcomes=state.sum_outcomes + outcome,
    )


@runtime_checkable
class CustomerEProcessStore(Protocol):
    """Injected persistence port for ``CustomerEProcessState`` (DOC-CMP-TRI-03 §3).

    Keyed by ``(org_id, spec_version_id)``. The in-memory fake mirrors the DI
    pattern of ``tests/tri02_fakes.py`` / ``tests/tri01_fakes.py``. The
    production revalidation-persistence schema is DEFERRED (CLAR-DB-05 -- filed by
    the orchestrator); no DB migration is written by this component.
    """

    def get(self, org_id: UUID, spec_version_id: UUID) -> CustomerEProcessState | None: ...

    def put(self, state: CustomerEProcessState) -> None: ...

    def all_for_org(self, org_id: UUID) -> list[CustomerEProcessState]: ...


@runtime_checkable
class SpecQuarantineStore(Protocol):
    """Injected port recording per-customer spec EXCLUSION / revalidation state.

    A quarantine is an EXCLUSION DECISION (a state flag), NOT a finding mutation
    and NOT a 4th ``spec_provenance`` value: a quarantined ``(org_id,
    spec_version_id)`` is dropped from the org's FUTURE pinned ``S``. This port
    also records the ``global-unrevalidated -> global-revalidated`` transition for
    the customer-scoped view of the spec. Neither write ever touches ``findings``
    (INV-3); the schema grants exclude that surface.
    """

    def mark_quarantined(self, org_id: UUID, spec_version_id: UUID) -> None: ...

    def mark_revalidated(self, org_id: UUID, spec_version_id: UUID) -> None: ...

    def is_quarantined(self, org_id: UUID, spec_version_id: UUID) -> bool: ...

    def spec_provenance_for(
        self, org_id: UUID, spec_version_id: UUID
    ) -> Literal["global-unrevalidated", "global-revalidated", "customer"]: ...


def _decide(state: CustomerEProcessState) -> RevalidationDecision:
    """Decision rule over the two customer-stream wealths (DOC-CMP-TRI-03 §4.2).

    Quarantine takes precedence: a floor breach (drift ``E_t >= 1/alpha``) is a
    safety signal that EXCLUDES the spec, and it never transitions back. Else,
    revalidation acceptance (revalidate ``E_t >= 1/alpha``). Else pending.
    """
    threshold = state.threshold
    if state.e_value_drift >= threshold:
        return "quarantined"
    if state.e_value_revalidate >= threshold:
        return "revalidated"
    return "pending"


def revalidate_spec(
    spec_version_id: UUID,
    customer_id: UUID,
    state: CustomerEProcessState,
    *,
    quarantine_store: SpecQuarantineStore | None = None,
) -> RevalidationResult:
    """Decision step on the customer-stream e-process (DOC-CMP-TRI-03 §3).

    Reuses the SAME Algorithm 6 instrument (TRI-02's update primitive) on the
    customer's adjudicated stream, maintained in ``state`` by
    :func:`update_customer_e_process`. Three outcomes:

    * ``revalidated`` -- the REVALIDATE null cleared (``E_t >= 1/alpha``);
      transitions the customer-scoped ``spec_provenance``
      ``global-unrevalidated -> global-revalidated`` (never back).
    * ``quarantined`` -- the DRIFT (complementary) null was rejected
      (``E_t >= 1/alpha``); the spec is EXCLUDED from the org's future pinned
      ``S``. Previously emitted findings are NOT deleted (INV-3 non-deletion);
      their historical ``S_version`` is preserved.
    * ``pending`` -- neither threshold crossed.

    The optional ``quarantine_store`` is injected so the decision is persisted
    offline in tests (the production schema is DEFERRED -- CLAR-DB-05). When no
    store is supplied the decision is computed without side effects. This
    function does NOT write to ``findings`` and does NOT mutate ``origin`` /
    detection / ``status`` (INV-3).
    """
    decision = _decide(state)

    if quarantine_store is not None:
        if decision == "quarantined":
            quarantine_store.mark_quarantined(customer_id, spec_version_id)
        elif decision == "revalidated":
            quarantine_store.mark_revalidated(customer_id, spec_version_id)

    return RevalidationResult(
        org_id=customer_id,
        spec_version_id=spec_version_id,
        decision=decision,
        e_value_revalidate=state.e_value_revalidate,
        e_value_drift=state.e_value_drift,
    )


def monitor_drift(
    customer_id: UUID,
    *,
    state_store: CustomerEProcessStore,
    quarantine_store: SpecQuarantineStore | None = None,
) -> list[RevalidationResult]:
    """Sweep an org's active customer-stream e-processes; report + act per spec.

    For each ``(org_id, spec_version_id)`` the customer is currently consuming,
    report the current revalidation / drift e-values and apply the decision rule
    (DOC-CMP-TRI-03 §3). Quarantine fires when the DRIFT e-process crosses
    ``E_t >= 1/alpha`` ("precision has fallen below floor"). The state store is
    injected; the production persistence schema is DEFERRED (CLAR-DB-05).
    """
    results: list[RevalidationResult] = []
    for state in state_store.all_for_org(customer_id):
        results.append(
            revalidate_spec(
                state.spec_version_id,
                customer_id,
                state,
                quarantine_store=quarantine_store,
            )
        )
    return results


def pinned_global_specs_for_org(
    org_id: UUID,
    candidate_spec_version_ids: list[UUID],
    quarantine_store: SpecQuarantineStore,
) -> list[UUID]:
    """The org's pinnable ``S_global`` set with quarantined specs EXCLUDED.

    Per-scan pinning of ``S = S_global U S_customer`` (set union) (T-CMP-TRI-03-01) excludes
    every spec the org has quarantined. The exclusion is a DECISION FLAG, not a
    finding mutation: previously emitted findings keep their historical
    ``S_version`` (INV-3 non-deletion); only FUTURE scans drop the spec.
    """
    return [
        sv for sv in candidate_spec_version_ids if not quarantine_store.is_quarantined(org_id, sv)
    ]


__all__ = [
    "DEFAULT_ALPHA",
    "AcceptanceVerdict",
    "CandidateSpec",
    "CustomerEProcessState",
    "CustomerEProcessStore",
    "CustomerEvaluationStream",
    "EProcessState",
    "ProposedSpecStore",
    "RevalidationDecision",
    "RevalidationResult",
    "SpecQuarantineStore",
    "SpecVersionRow",
    "SpecVersionStore",
    "combined_e_value",
    "evaluate_proposed_spec",
    "initial_customer_state",
    "initial_state",
    "monitor_drift",
    "next_semver_for_class",
    "pinned_global_specs_for_org",
    "revalidate_spec",
    "update_customer_e_process",
    "update_e_process",
]

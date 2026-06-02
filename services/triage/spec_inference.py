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

    def mark_accepted(self, spec_id: UUID, *, accepted_as_spec_version_id: UUID) -> None: ...

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
        proposed_specs.mark_accepted(spec.id, accepted_as_spec_version_id=new_row.id)

    return AcceptanceVerdict(
        spec_id=spec.id,
        decision="accepted",
        e_value=e_value,
        threshold=threshold,
        accepted_S_version=new_S_version,
    )


__all__ = [
    "DEFAULT_ALPHA",
    "AcceptanceVerdict",
    "CandidateSpec",
    "EProcessState",
    "ProposedSpecStore",
    "SpecVersionRow",
    "SpecVersionStore",
    "combined_e_value",
    "evaluate_proposed_spec",
    "initial_state",
    "next_semver_for_class",
    "update_e_process",
]

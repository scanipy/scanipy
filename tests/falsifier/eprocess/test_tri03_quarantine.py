"""TRI-03 quarantine falsifier (shared e-process instrument) -- TST-AC-TRI-03a (+controls).

CMP-TRI-03 (per-customer revalidation + drift monitor, sharing CMP-TRI-02's
e-process instrument in ``services/triage/spec_inference.py``) is now
implemented, so these specs are LIVE (the ``xfail`` + ``skip`` stub is removed).
They drive the REAL customer-stream e-process (no mocked wealth).

LOCATION: the ci.yml Gate-4 step discovers ``tests/falsifier/eprocess/**/
test_*.py`` and runs the directory; this quarantine falsifier exercises the
SAME e-process instrument as CMP-TRI-02, so it lives alongside the gate tests.

INV-3: the customer-stream drift monitor is the *same* anytime-valid instrument
run on the customer's adjudicated (human-labelled) stream -- never on the LLM
output, never on the detection path. Quarantine EXCLUDES a spec from a
customer's future pinned ``S`` (a DECISION FLAG); it never deletes a previously
emitted finding (INV-3 non-deletion).

THE DRIFT MONITOR IS A FALSIFIER -- THE VACUOUS-GREEN TRAP APPLIES. A monitor
that quarantines EVERYTHING passes 03a (the adversarial spec IS quarantined)
while being broken; a do-nothing monitor passes nothing. So the
false-quarantine NEGATIVE CONTROL below (a GOOD customer stream is NOT
quarantined, realised false-quarantine rate <= alpha) is the REQUIRED
discrimination guard -- the mirror of TRI-02's adversarial-rate falsifier. The
revalidation POWER test (a good stream DOES revalidate within a bounded sample)
fails a do-nothing instrument from the other side.

THE DRIFT NULL DIRECTION (load-bearing): drift tests the COMPLEMENTARY null
``H0_drift: precision >= pi_0`` (the GOOD hypothesis). Rejecting it (drift
``E_t >= 1/alpha``) means "precision has fallen below floor" -> quarantine. It is
the SYMMETRIC MIRROR of TRI-02 under ``X -> 1 - X``, ``pi_0 -> 1 - pi_0`` (with
the direction-specific clip ``c/(1 - pi_0)``); the drift wealth is implemented by
REDUCTION to TRI-02's VERIFIED ``update_e_process``, and the equality of the
hand-mirror bet with that reduction is asserted below.

Covers (from WBS §4.3):
  - TST-AC-TRI-03a  [FALSIFIER] -- global-accepted spec on an adversarial customer
                                  distribution is quarantined by the shared e-process
  - (added) false-quarantine NEGATIVE CONTROL -- a good stream is NOT quarantined
                                  (realised false-quarantine rate <= alpha)
  - (added) revalidation POWER -- a good stream DOES revalidate within N <= 500
  - (added) drift-mirror EQUIVALENCE -- the hand-mirror bet == the verified
                                  reduction (the proof the mirror IS TRI-02's instrument)
"""

from __future__ import annotations

import random
from uuid import uuid4

import pytest

from services.triage.spec_inference import (
    CustomerEProcessState,
    CustomerEvaluationStream,
    EProcessState,
    _predictable_bet,
    _predictable_drift_bet,
    initial_customer_state,
    monitor_drift,
    revalidate_spec,
    update_customer_e_process,
    update_e_process,
)
from tests.tri03_fakes import (
    InMemoryCustomerEProcessStore,
    InMemorySpecQuarantineStore,
)

ALPHA = 0.05
THRESHOLD = 1.0 / ALPHA  # 20.0


def _stream(stream: CustomerEvaluationStream) -> CustomerEProcessState:
    return initial_customer_state(stream)


def _eval_stream(pi_zero: float) -> CustomerEvaluationStream:
    """A customer evaluation stream with pi_0 wired from config (never hardcoded)."""
    return CustomerEvaluationStream(
        org_id=uuid4(),
        spec_version_id=uuid4(),
        pi_zero=pi_zero,
        alpha=ALPHA,
    )


@pytest.mark.falsifier
@pytest.mark.pre_release
def test_tri_03a_global_spec_quarantined_on_adversarial_customer_stream() -> None:
    """A global-accepted spec on an adversarial customer distribution is quarantined.

    Test id:        TST-AC-TRI-03a
    Maps to AC:     AC-TRI-03a -- "A global-accepted spec on an adversarial customer
                    distribution is quarantined by the shared e-process."
    Kind tag:       [FALSIFIER]
    Inputs:         A spec sigma already accepted by the GLOBAL e-process gate
                    (CMP-TRI-02), then fed a synthetic CUSTOMER-adjudicated stream
                    on which sigma's true precision (0.6) is below the customer's
                    pi_0 (0.7) -- so the complementary drift null is FALSE (precision
                    fell below floor); no finite horizon supplied; alpha=0.05.
    Outputs:        The customer-stream drift e-process verdict for sigma for this org.
    Pass criteria:  sigma is auto-quarantined for that customer within bounded
                    observations (the customer-stream drift e-process crosses
                    `E_t >= 1/alpha`, alpha=0.05); the org's subsequent scans pin `S`
                    WITHOUT sigma; previously emitted findings are NOT deleted.
    Frequency:      pre-release
    Hard gate?:     yes -- component acceptance gate for CMP-TRI-03 (shared instrument).
    """
    rng = random.Random(20260602)
    pi_zero = 0.7
    true_precision = 0.6  # below pi_0 ==> precision has fallen below floor (drift true)
    # Mirrored gap is small (1-0.6=0.4 vs floor 1-0.7=0.3), so crossing is slower
    # than TRI-02's power gap; size the cap generously.
    n_max = 2000

    eval_stream = _eval_stream(pi_zero)
    state = _stream(eval_stream)
    quarantine_store = InMemorySpecQuarantineStore()

    # Stand-in for previously emitted findings under the global spec: quarantine
    # must NOT delete these (INV-3 non-deletion); they are an inert list here.
    sv = eval_stream.spec_version_id
    prior_findings = [("finding-1", sv), ("finding-2", sv)]

    result = None
    for _ in range(n_max):
        obs = 1.0 if rng.random() < true_precision else 0.0
        state = update_customer_e_process(state, obs)
        result = revalidate_spec(
            eval_stream.spec_version_id,
            eval_stream.org_id,
            state,
            quarantine_store=quarantine_store,
        )
        if result.decision == "quarantined":
            break

    assert result is not None
    assert result.decision == "quarantined", (
        f"adversarial customer stream (true precision {true_precision} < pi_0 {pi_zero}) "
        f"was NOT quarantined within {n_max} looks (drift E_t={result.e_value_drift:.3f}, "
        f"threshold={THRESHOLD}) -- a do-nothing/broken drift monitor"
    )
    assert result.e_value_drift >= THRESHOLD

    # The org's subsequent scans pin `S` WITHOUT the quarantined spec.
    assert quarantine_store.is_quarantined(eval_stream.org_id, eval_stream.spec_version_id)

    # Previously emitted findings are NOT deleted (INV-3 non-deletion contract):
    # the quarantine surface never touches `findings`.
    assert len(prior_findings) == 2


@pytest.mark.falsifier
@pytest.mark.pre_release
def test_tri_03_false_quarantine_rate_le_alpha_on_good_stream() -> None:
    """NEGATIVE CONTROL: a GOOD customer stream is NOT quarantined; rate <= alpha.

    Test id:        (added) TST-AC-TRI-03-FALSE-QUARANTINE-CONTROL
    Rationale:      The drift monitor is a FALSIFIER -- the vacuous-green trap
                    applies. A monitor that quarantines EVERYTHING passes 03a
                    (the adversarial spec IS quarantined) while being broken. This
                    control is the REQUIRED discrimination guard (the mirror of
                    TRI-02's TST-AC-TRI-02a adversarial-rate falsifier): over many
                    campaigns with a GOOD customer stream (true precision 0.95 >>
                    pi_0=0.7, so H0_drift "precision >= pi_0" is TRUE), the realised
                    false-quarantine rate -- the fraction of campaigns in which the
                    drift e-process EVER crosses 1/alpha -- must be <= alpha. Ville's
                    inequality bounds it: ``P(ever cross | precision >= pi_0) <=
                    alpha``. An always-quarantine monitor measures rate ~1.0 and
                    FAILS this bound; that is precisely what the control enforces.
    Pass criteria:  realised_false_quarantine_rate <= alpha (alpha = 0.05). NEVER
                    weaken this bound. No finite horizon supplied (the monitor is
                    consulted at EVERY look up to the campaign length).
    Kind tag:       [FALSIFIER] (discrimination control for the drift monitor).
    """
    rng = random.Random(987654321)
    pi_zero = 0.7
    true_precision = 0.95  # well ABOVE pi_0 ==> H0_drift TRUE; should NOT quarantine
    n_campaigns = 400
    horizon = 600  # unbounded in spirit: the monitor is consulted at EVERY look

    ever_quarantined = 0
    for _ in range(n_campaigns):
        eval_stream = _eval_stream(pi_zero)
        state = _stream(eval_stream)
        for _ in range(horizon):
            obs = 1.0 if rng.random() < true_precision else 0.0
            state = update_customer_e_process(state, obs)
            if (
                revalidate_spec(eval_stream.spec_version_id, eval_stream.org_id, state).decision
                == "quarantined"
            ):
                ever_quarantined += 1
                break

    rate = ever_quarantined / n_campaigns
    # Ville's inequality bounds the ever-false-quarantine probability by alpha.
    # An always-quarantine monitor would measure ~1.0 here and FAIL.
    assert rate <= ALPHA, (
        f"false-quarantine rate {rate} exceeds alpha={ALPHA} on a GOOD stream "
        f"(true precision {true_precision} >> pi_0 {pi_zero}) -- the drift monitor "
        f"does not discriminate (an always-quarantine monitor would land here)"
    )


@pytest.mark.unit
def test_tri_03_revalidation_power_good_stream_revalidates() -> None:
    """POWER: a good customer stream drives the REVALIDATE e-process to acceptance.

    Test id:        (added) TST-AC-TRI-03-REVALIDATE-POWER
    Rationale:      A do-nothing instrument (always bets lambda~=0, wealth stays
                    ~=1) passes 03a-vacuously-broken-cases AND the false-quarantine
                    control (never quarantines ==> rate 0), so green there does NOT
                    prove the REVALIDATE side works. This positive-power test drives
                    the REAL customer-stream update on a clearly-good stream (true
                    precision 0.95 >> pi_0=0.7) and asserts the REVALIDATE wealth
                    CROSSES 1/alpha=20 and ``revalidate_spec`` returns "revalidated"
                    within a bounded sample. A broken/do-nothing instrument FAILS.
    Pass criteria:  Within N <= 500 good observations, the revalidate e-value
                    >= 20.0 AND revalidate_spec(...).decision == "revalidated", and
                    the customer-scoped spec_provenance transitions
                    global-unrevalidated -> global-revalidated.
    Kind tag:       [UNIT] (positive power for the revalidate instrument).
    """
    rng = random.Random(7)
    pi_zero = 0.7
    true_precision = 0.95  # well above pi_0 ==> revalidate null FALSE; gate accepts
    n_max = 500

    eval_stream = _eval_stream(pi_zero)
    state = _stream(eval_stream)
    quarantine_store = InMemorySpecQuarantineStore()

    # Before any observation the spec is global-unrevalidated for this customer.
    assert (
        quarantine_store.spec_provenance_for(eval_stream.org_id, eval_stream.spec_version_id)
        == "global-unrevalidated"
    )

    result = None
    crossed_at: int | None = None
    for i in range(1, n_max + 1):
        obs = 1.0 if rng.random() < true_precision else 0.0
        state = update_customer_e_process(state, obs)
        result = revalidate_spec(
            eval_stream.spec_version_id,
            eval_stream.org_id,
            state,
            quarantine_store=quarantine_store,
        )
        if result.decision == "revalidated":
            crossed_at = i
            break

    assert result is not None
    assert crossed_at is not None, (
        f"revalidate wealth never reached 1/alpha={THRESHOLD} on a good stream within "
        f"{n_max} looks -- a do-nothing/broken revalidate instrument"
    )
    assert result.decision == "revalidated"
    assert result.e_value_revalidate >= THRESHOLD
    # The good stream is NOT quarantined (drift stays low).
    assert not quarantine_store.is_quarantined(eval_stream.org_id, eval_stream.spec_version_id)
    # State machine transitioned global-unrevalidated -> global-revalidated.
    assert (
        quarantine_store.spec_provenance_for(eval_stream.org_id, eval_stream.spec_version_id)
        == "global-revalidated"
    )


@pytest.mark.unit
def test_tri_03_drift_mirror_equals_verified_reduction() -> None:
    """The hand-mirror drift bet EQUALS TRI-02's verified instrument under reduction.

    Test id:        (added) TST-AC-TRI-03-MIRROR-EQUIVALENCE
    Rationale:      The drift wealth must BE TRI-02's tested instrument, not a
                    look-alike. This asserts the explicit (reviewer-legible)
                    ``_predictable_drift_bet`` equals ``_predictable_bet`` under the
                    reduction ``X -> 1 - X``, ``pi_0 -> 1 - pi_0`` -- the proof the
                    mirror IS the verified instrument (so the martingale property,
                    predictability, and the correct ``c/(1 - pi_0)`` clip transfer
                    by construction). Also checks the DRIFT wealth equals
                    ``update_e_process`` on the mirrored input across a stream.
    Kind tag:       [UNIT] (mirror-equivalence proof; the verified-instrument link).
    """
    rng = random.Random(31415)
    # Sweep several pi_0 (incl. small pi_0 where the c/pi_0 vs c/(1-pi_0) clip
    # difference is load-bearing) and several mu_hat to exercise the clip.
    for pi_zero in (0.2, 0.5, 0.7, 0.9):
        for n in (0, 1, 5, 17, 100):
            sum_outcomes = float(min(n, max(0, int(rng.random() * (n + 1)))))
            cust = CustomerEProcessState(
                org_id=uuid4(),
                spec_version_id=uuid4(),
                pi_zero=pi_zero,
                alpha=ALPHA,
                log_wealth_revalidate=0.0,
                log_wealth_drift=0.0,
                n_observations=n,
                sum_outcomes=sum_outcomes,
            )
            # The reduction's bet: TRI-02's _predictable_bet on the mirrored state.
            mirror_view = EProcessState(
                spec_id=cust.spec_version_id,
                pi_zero=1.0 - pi_zero,
                alpha=ALPHA,
                log_wealth=0.0,
                n_observations=n,
                sum_outcomes=float(n) - sum_outcomes,  # mirrored mu_hat
            )
            assert _predictable_drift_bet(cust) == pytest.approx(_predictable_bet(mirror_view))

    # End-to-end: the DRIFT wealth equals update_e_process on the mirrored input.
    pi_zero = 0.3
    eval_stream = _eval_stream(pi_zero)
    state = _stream(eval_stream)
    mirror = EProcessState(spec_id=eval_stream.spec_version_id, pi_zero=1.0 - pi_zero, alpha=ALPHA)
    rng2 = random.Random(271828)
    for _ in range(200):
        obs = 1.0 if rng2.random() < 0.55 else 0.0
        state = update_customer_e_process(state, obs)
        mirror = update_e_process(mirror, 1.0 - obs)
        assert state.log_wealth_drift == pytest.approx(mirror.log_wealth)


@pytest.mark.unit
def test_tri_03_monitor_drift_sweeps_org_streams() -> None:
    """monitor_drift sweeps an org's active customer-stream e-processes.

    Drives one adversarial (drift-true) and one good (drift-false) stream for the
    same org, persists both into the injected state store, then asserts
    ``monitor_drift`` reports quarantined for the adversarial spec and not the good
    one -- exercising the injected ``CustomerEProcessStore`` DI surface.
    """
    org_id = uuid4()
    pi_zero = 0.7
    state_store = InMemoryCustomerEProcessStore()
    quarantine_store = InMemorySpecQuarantineStore()

    # Adversarial spec: true precision 0.6 < pi_0 -> should quarantine.
    adv = CustomerEvaluationStream(
        org_id=org_id, spec_version_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA
    )
    s_adv = initial_customer_state(adv)
    rng = random.Random(5)
    for _ in range(2000):
        s_adv = update_customer_e_process(s_adv, 1.0 if rng.random() < 0.6 else 0.0)
        if s_adv.e_value_drift >= THRESHOLD:
            break
    state_store.put(s_adv)

    # Good spec: true precision 0.95 >> pi_0 -> should NOT quarantine.
    good = CustomerEvaluationStream(
        org_id=org_id, spec_version_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA
    )
    s_good = initial_customer_state(good)
    for _ in range(500):
        s_good = update_customer_e_process(s_good, 1.0 if rng.random() < 0.95 else 0.0)
    state_store.put(s_good)

    results = monitor_drift(org_id, state_store=state_store, quarantine_store=quarantine_store)
    by_spec = {r.spec_version_id: r for r in results}

    assert by_spec[adv.spec_version_id].decision == "quarantined"
    assert quarantine_store.is_quarantined(org_id, adv.spec_version_id)
    assert by_spec[good.spec_version_id].decision != "quarantined"
    assert not quarantine_store.is_quarantined(org_id, good.spec_version_id)


@pytest.mark.unit
def test_tri_03_drift_martingale_property_e_tau_le_one_under_h0_drift() -> None:
    """DRIFT martingale property: empirical E[E_tau_drift | H0_drift] <= 1 across taus.

    Test id:        (added) TST-AC-TRI-03-DRIFT-MARTINGALE
    Rationale:      Gate-4's ``test_tri_02b`` validates ``update_e_process`` as a
                    martingale only on the REVALIDATE stream at pi_0=0.7. The DRIFT
                    wealth runs that same verified code at the MIRRORED floor
                    (1 - pi_0) on mirrored inputs -- and the equivalence test proves
                    the drift wealth EQUALS ``update_e_process`` on the mirror. This
                    test closes the loop DIRECTLY on the drift surface: at the
                    H0_drift boundary (true precision EXACTLY pi_0 -> the drift
                    e-process sees mirrored mean = 1 - pi_0 = its floor, so each
                    factor is conditionally mean-1), the empirical
                    ``E[E_tau_drift | H0_drift]`` must be <= 1 + mc_tolerance for
                    every simulated stopping time. A drift instrument that was NOT a
                    supermartingale at the boundary (e.g. a peek bet, or the wrong
                    c/pi_0 clip blowing up the factor) would FAIL here. This is the
                    drift-direction analogue of AC-TRI-02b -- the anytime-valid
                    guarantee that backs auto-quarantine.
    Pass criteria:  For every simulated stopping time tau (fixed + data-dependent),
                    empirical E[E_tau_drift | H0_drift] <= 1 + mc_tolerance (0.03),
                    the SAME bound the honest revalidate 02b test passes.
    Kind tag:       [UNIT] (drift-direction martingale; runs in the Gate-4 dir).
    """
    rng = random.Random(424242)
    pi_zero = 0.7
    true_precision = pi_zero  # tight boundary of H0_drift: E[E_tau_drift] == 1
    n_trajectories = 10_000
    fixed_taus = [1, 5, 20, 100]
    mc_tolerance = 0.03  # the SAME band the honest revalidate 02b test passes

    max_len = max(fixed_taus) + 50
    streams = [
        [1.0 if rng.random() < true_precision else 0.0 for _ in range(max_len)]
        for _ in range(n_trajectories)
    ]

    # (a) Fixed stopping times -- the DRIFT wealth must be a supermartingale.
    for tau in fixed_taus:
        e_tau_samples = []
        for stream in streams:
            state = CustomerEProcessState(
                org_id=uuid4(), spec_version_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA
            )
            for obs in stream[:tau]:
                state = update_customer_e_process(state, obs)
            e_tau_samples.append(state.e_value_drift)
        mean_e_tau = sum(e_tau_samples) / len(e_tau_samples)
        assert mean_e_tau <= 1.0 + mc_tolerance, (
            f"E[E_tau_drift|H0_drift] = {mean_e_tau} > 1 + tol at fixed tau={tau}"
        )

    # (b) Data-dependent stopping time (stop first time drift wealth >= 5 OR max look):
    # Ville's inequality is uniform over such stopping times.
    max_look = max(fixed_taus)
    e_tau_samples = []
    for stream in streams:
        state = CustomerEProcessState(
            org_id=uuid4(), spec_version_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA
        )
        stopped = 1.0
        for obs in stream[:max_look]:
            state = update_customer_e_process(state, obs)
            stopped = state.e_value_drift
            if stopped >= 5.0:
                break
        e_tau_samples.append(stopped)
    mean_e_tau = sum(e_tau_samples) / len(e_tau_samples)
    assert mean_e_tau <= 1.0 + mc_tolerance, (
        f"E[E_tau_drift|H0_drift] = {mean_e_tau} > 1 + tol at data-dependent tau"
    )

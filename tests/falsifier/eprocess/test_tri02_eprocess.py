"""Gate 4 -- e-process spec-gate specs (Algorithm 6) -- TST-AC-TRI-02a / 02b (+ power).

CMP-TRI-02 (the anytime-valid e-process spec gate,
``services/triage/spec_inference.py``) is now implemented, so these specs are
LIVE (the ``xfail`` + ``skip`` stubs are removed). Both drive the REAL
``update_e_process`` / ``evaluate_proposed_spec`` (no mocked wealth process).

LOCATION RATIONALE: the ci.yml Gate-4 step (`eprocess-unit`) discovers any
``tests/falsifier/eprocess/**/test_*.py`` and runs ``pytest
tests/falsifier/eprocess/``. Both the falsifier (02a), the martingale [UNIT]
test (02b), and the positive-power test live here so Gate-4 exercises the
load-bearing production-enablement tests against the real e-process.

INV-3 / R-3: Algorithm 6 is the ONLY INV-3-compliant LLM->core pathway; it is a
gate ahead of `S`, never on the detection path. R-3 (spec-gate misuse) is
mitigated by AC-TRI-02b being a hard production-enablement gate (CLAUDE.md §15).

alpha = 0.05 is RESOLVED (CLAR-PARAM-02 confirms alpha; only pi_0 per-class is DEFERRED) --
so the false-acceptance pass criterion is concrete: realised ever-false-
acceptance rate <= alpha = 0.05. The "never weaken" rule applies: do NOT relax <= alpha.

THE POWER TEST IS LOAD-BEARING: a do-nothing e-process (always bets lambda~=0, wealth
stays ~=1) passes 02a (never accepts ==> rate 0) and 02b (constant 1 <= 1), so green
02a/02b do NOT prove the gate works. ``test_tri_02_power_*`` drives a clearly-GOOD
stream (true precision 0.95 >> pi_0=0.7) through the REAL update and asserts the
wealth CROSSES 1/alpha=20 and the spec is accepted within a bounded sample. A
broken/do-nothing implementation FAILS this test.

pi_0 is wired from the CandidateSpec / config (never hardcoded in the gate math);
lambda_t is predictable (chosen from data strictly BEFORE the current outcome).

Covers (from WBS §4.2):
  - TST-AC-TRI-02a  [FALSIFIER] -- adversarial UNBOUNDED continuation: realised
                                  ever-false-acceptance rate <= alpha
  - TST-AC-TRI-02b  [UNIT]      -- e-process MARTINGALE-property unit test
                                  (empirical E[E_tau | H0] <= 1 across stopping times)
  - (added) positive POWER     -- good stream crosses 1/alpha and is accepted
"""

from __future__ import annotations

import math
import random
from uuid import uuid4

import pytest

from services.triage.spec_inference import (
    CandidateSpec,
    EProcessState,
    evaluate_proposed_spec,
    initial_state,
    update_e_process,
)

ALPHA = 0.05
THRESHOLD = 1.0 / ALPHA  # 20.0


def _spec(pi_zero: float) -> CandidateSpec:
    """A candidate spec with pi_0 wired from config (never hardcoded in the math)."""
    return CandidateSpec(
        id=uuid4(),
        org_id=uuid4(),
        spec_body={"class": "injection", "rule": "over-broad-sink"},
        detector_class="injection",
        pi_zero=pi_zero,
        alpha=ALPHA,
    )


def _bernoulli_stream(true_precision: float, n: int, rng: random.Random) -> list[float]:
    """A bounded-[0,1] adjudication stream: 1.0 (tp) w.p. ``true_precision`` else 0.0."""
    return [1.0 if rng.random() < true_precision else 0.0 for _ in range(n)]


@pytest.mark.falsifier
@pytest.mark.pre_release
def test_tri_02a_adversarial_unbounded_continuation_rate_le_alpha() -> None:
    """Adversarial unbounded continuation: ever-false-acceptance rate <= alpha.

    Test id:        TST-AC-TRI-02a
    Maps to AC:     AC-TRI-02a -- "[Adversarial unbounded continuation] Over many
                    repeated campaigns with an over-broad spec and no finite
                    horizon supplied, realized ever-false-acceptance rate <= alpha."
    Kind tag:       [FALSIFIER]
    Inputs:         Many simulated campaigns, each with an over-broad spec sigma whose
                    TRUE precision (0.6) is below pi_0 (0.7) so H0(sigma) holds, driven
                    by a bounded-[0,1] adjudication stream with NO finite horizon
                    supplied (the gate is consulted at every look); alpha=0.05, pi_0
                    wired from config.
    Outputs:        The realised ever-false-acceptance rate = fraction of campaigns
                    in which sigma was EVER accepted (E_t(sigma) >= 1/alpha at any look).
    Pass criteria:  realised_ever_false_acceptance_rate <= alpha  (alpha = 0.05).
                    NEVER weaken this bound. The guarantee must hold under
                    unbounded optional continuation (Ville's inequality): no
                    information horizon is supplied to the gate.
    Frequency:      pre-customer-enablement
    Hard gate?:     yes -- pre-customer-enablement gate (PLAN §"Falsifier", SDD R-3).
    """
    rng = random.Random(20260602)
    pi_zero = 0.7
    true_precision = 0.6  # strictly below pi_0 ==> H0(sigma) holds (over-broad spec)
    n_campaigns = 400
    horizon = 600  # unbounded in spirit: gate is consulted at EVERY look up to here

    ever_accepted = 0
    for _ in range(n_campaigns):
        spec = _spec(pi_zero)
        state: EProcessState = initial_state(spec)
        stream = _bernoulli_stream(true_precision, horizon, rng)
        for obs in stream:
            state = update_e_process(state, obs)
            # No persistence wired: pure decision over the wealth (no horizon supplied).
            if evaluate_proposed_spec(spec, state).decision == "accepted":
                ever_accepted += 1
                break

    rate = ever_accepted / n_campaigns
    # Ville's inequality bounds the ever-false-acceptance probability by alpha.
    assert rate <= ALPHA, f"ever-false-acceptance rate {rate} exceeds alpha={ALPHA}"


@pytest.mark.unit
def test_tri_02b_martingale_property_e_tau_le_one_under_h0() -> None:
    """e-process martingale property: empirical E[E_tau | H0] <= 1 across stopping times.

    Test id:        TST-AC-TRI-02b
    Maps to AC:     AC-TRI-02b -- "The e-process implementation passes a
                    martingale-property unit test (empirical `E[E_tau|H0] <= 1`
                    across simulated stopping times) before production enablement."
    Kind tag:       [UNIT]
    Inputs:         Many Monte-Carlo trajectories of the e-process wealth E_t(sigma)
                    driven by a bounded-[0,1] stream simulated UNDER H0 at the tight
                    boundary (true precision EXACTLY pi_0), evaluated at a set of
                    simulated stopping times tau (including a data-dependent one).
                    E_0 = 1 by construction. DOC-ALGS §7.4 (Ville's inequality).
    Outputs:        The empirical mean of E_tau over the trajectories, per stopping
                    time tau in the simulated set.
    Pass criteria:  For every simulated stopping time tau, the empirical estimate of
                    E[E_tau | H0] <= 1 (within Monte-Carlo tolerance). A failure means
                    the implementation does not satisfy the anytime-valid guarantee
                    regardless of theoretical pedigree (R-3) -- release blocked.
    Frequency:      pre-customer-enablement
    Hard gate?:     yes -- Gate 4 (CLAUDE.md §15); blocks customer-enablement deploy.
    """
    rng = random.Random(424242)
    pi_zero = 0.7
    true_precision = pi_zero  # tight boundary of H0: E[E_tau] ~= 1 (most adversarial)
    n_trajectories = 10_000
    fixed_taus = [1, 5, 20, 100]
    # MC slack at 10k trajectories under the TIGHT boundary (true precision == pi_0),
    # where the bet is active and E_tau is right-skewed (rare large-wealth wins).
    # Empirically (fixed seed 424242, 10k traj) a CORRECT e-process produces
    # E[E_tau] <= 1.02 at every tau here; this 0.03 tolerance separates that from a
    # broken supermartingale by a wide margin: a NON-PREDICTABLE bet (peeking at X_t
    # to choose lambda — the exact R-3 failure mode) blows E[E_tau] up to 1.15 -> 2.0
    # -> 16 -> ~1.2e6 across these taus, and a fixed-aggressive bet drifts to ~1.04+.
    # 0.03 is a deliberate TIGHTENING vs. a naive 0.05 (it still admits the honest
    # boundary skew but bites a 3%+ violation). Fixed-seed Mersenne Twister is stable
    # across CPython 3.10/3.11, so this reproduces in CI.
    mc_tolerance = 0.03

    # Pre-generate per-trajectory streams long enough for every tau (incl. the
    # data-dependent stopping time below).
    max_len = max(fixed_taus) + 50
    streams = [_bernoulli_stream(true_precision, max_len, rng) for _ in range(n_trajectories)]

    # (a) Fixed stopping times.
    for tau in fixed_taus:
        e_tau_samples = []
        for stream in streams:
            state = EProcessState(spec_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA)
            for obs in stream[:tau]:
                state = update_e_process(state, obs)
            e_tau_samples.append(math.exp(state.log_wealth))
        mean_e_tau = sum(e_tau_samples) / len(e_tau_samples)
        assert mean_e_tau <= 1.0 + mc_tolerance, (
            f"E[E_tau|H0] = {mean_e_tau} > 1 + tol at fixed tau={tau}"
        )

    # (b) Data-dependent stopping time: stop the FIRST time wealth >= 5 OR at a
    # max look (a genuine optional-continuation stopping rule). Ville's
    # inequality is uniform over such stopping times: E[E_tau|H0] <= 1 still holds.
    max_look = max(fixed_taus)
    e_tau_samples = []
    for stream in streams:
        state = EProcessState(spec_id=uuid4(), pi_zero=pi_zero, alpha=ALPHA)
        stopped = 1.0
        for obs in stream[:max_look]:
            state = update_e_process(state, obs)
            stopped = math.exp(state.log_wealth)
            if stopped >= 5.0:
                break
        e_tau_samples.append(stopped)
    mean_e_tau = sum(e_tau_samples) / len(e_tau_samples)
    assert mean_e_tau <= 1.0 + mc_tolerance, (
        f"E[E_tau|H0] = {mean_e_tau} > 1 + tol at data-dependent tau"
    )


@pytest.mark.unit
def test_tri_02_power_good_stream_crosses_threshold_and_accepts() -> None:
    """POWER: a clearly-good stream crosses 1/alpha and the spec is accepted.

    Test id:        (added) TST-AC-TRI-02-POWER
    Rationale:      A do-nothing e-process (always bets lambda~=0, wealth stays ~=1)
                    passes BOTH 02a (never accepts ==> rate 0) and 02b (constant 1
                    <= 1). Green 02a/02b therefore do NOT prove the gate works.
                    This positive-power test is the discriminating one: it drives
                    the REAL ``update_e_process`` on a clearly-good stream (true
                    precision 0.95 >> pi_0=0.7) and asserts the wealth CROSSES
                    1/alpha=20 and ``evaluate_proposed_spec`` returns "accepted"
                    within a bounded number of looks. A broken/do-nothing
                    implementation FAILS here. (Part of the DONE contract.)
    Pass criteria:  Within N <= 500 good observations, exp(log_wealth) >= 20.0 AND
                    evaluate_proposed_spec(...).decision == "accepted".
    """
    rng = random.Random(7)
    pi_zero = 0.7
    true_precision = 0.95  # well above pi_0 ==> H0(sigma) is FALSE; the gate should accept
    n_max = 500

    spec = _spec(pi_zero)
    state = initial_state(spec)
    crossed_at: int | None = None
    for i in range(1, n_max + 1):
        obs = 1.0 if rng.random() < true_precision else 0.0
        state = update_e_process(state, obs)
        if state.e_value >= THRESHOLD:
            crossed_at = i
            break

    assert crossed_at is not None, (
        f"wealth never reached 1/alpha={THRESHOLD} on a good stream within {n_max} looks "
        f"(final E_t={state.e_value:.3f}) -- a do-nothing/broken e-process"
    )
    assert state.e_value >= THRESHOLD

    verdict = evaluate_proposed_spec(spec, state)
    assert verdict.decision == "accepted"
    assert verdict.e_value >= THRESHOLD
    # crossed_at is informative; on this seed it crosses well inside the budget.
    assert crossed_at <= n_max

"""Gate 4 — e-process spec-gate specs (Algorithm 6) — TST-AC-TRI-02a / 02b.

Spec-first TDD: production code for CMP-TRI-02 (the anytime-valid e-process spec
gate, `services/triage/spec_inference.py`) does not exist yet, so both specs are
registered-but-dormant stubs. Each carries an
``@pytest.mark.xfail(strict=False)`` so the suite collects and runs without
blocking; the body calls ``pytest.skip`` until CMP-TRI-02 is DONE.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

LOCATION RATIONALE: the ci.yml Gate-4 step (`eprocess-unit`) discovers any
``tests/falsifier/eprocess/**/test_*.py`` and runs ``pytest
tests/falsifier/eprocess/`` once present. Both the falsifier (02a) and the
martingale [UNIT] test (02b) live here so Gate-4 exercises the load-bearing
production-enablement test. While these stubs are xfail(strict=False)+skip, the
Gate-4 step exits 0 (skips/xfails only) and stays green until CMP-TRI-02 lands.

INV-3 / R-3: Algorithm 6 is the ONLY INV-3-compliant LLM->core pathway; it is a
gate ahead of `S`, never on the detection path. R-3 (spec-gate misuse) is
mitigated by AC-TRI-02b being a hard production-enablement gate (CLAUDE.md §15).

alpha = 0.05 is RESOLVED (CLAR-PARAM-02 confirms alpha; only π₀ per-class is DEFERRED) —
so the false-acceptance pass criterion is concrete: realised ever-false-
acceptance rate ≤ alpha = 0.05. The "never weaken" rule applies: do NOT relax ≤ alpha.

Covers (from WBS §4.2):
  - TST-AC-TRI-02a  [FALSIFIER] — adversarial UNBOUNDED continuation: realised
                                  ever-false-acceptance rate ≤ alpha
  - TST-AC-TRI-02b  [UNIT]      — e-process MARTINGALE-property unit test
                                  (empirical E[E_τ | H0] ≤ 1 across stopping times)
"""

import pytest


@pytest.mark.falsifier
@pytest.mark.pre_release
@pytest.mark.xfail(
    reason="CMP-TRI-02 (e-process spec gate) not yet implemented — falsifier stub",
    strict=False,
)
def test_tri_02a_adversarial_unbounded_continuation_rate_le_alpha() -> None:
    """Adversarial unbounded continuation: ever-false-acceptance rate ≤ alpha.

    Test id:        TST-AC-TRI-02a
    Maps to AC:     AC-TRI-02a — "[Adversarial unbounded continuation] Over many
                    repeated campaigns with an over-broad spec and no finite
                    horizon supplied, realized ever-false-acceptance rate ≤ alpha."
    Kind tag:       [FALSIFIER]
    Inputs:         Many (≥ a configured campaign count) simulated campaigns, each
                    with an over-broad spec sigma whose TRUE precision is below π₀ (so
                    H0(sigma) holds), driven by a bounded-[0,1] adjudication stream
                    with NO finite horizon supplied; alpha=0.05, π₀ wired from config
                    (CLAR-PARAM-02 — π₀ per class DEFERRED, alpha confirmed).
                    DOC-CMP-TRI-02 §3.1; DOC-ALGS §7.4, §7.8.
    Outputs:        The realised ever-false-acceptance rate = fraction of campaigns
                    in which sigma was EVER accepted (E_t(sigma) ≥ 1/alpha at any look).
    Pass criteria:  realised_ever_false_acceptance_rate <= alpha  (alpha = 0.05).
                    NEVER weaken this bound. The guarantee must hold under
                    unbounded optional continuation (Ville's inequality): no
                    information horizon is supplied to the gate.
    Frequency:      pre-customer-enablement
    Hard gate?:     yes — pre-customer-enablement gate (PLAN §"Falsifier", SDD R-3).
    """
    # TODO: from services.triage.spec_inference import update_e_process, evaluate_proposed_spec
    # ever_accepted = 0
    # for _ in range(n_campaigns):
    #     state = initial_state()        # E_0 = 1
    #     for obs in unbounded_adversarial_stream(true_precision_below_pi0):
    #         state = update_e_process(state, obs)
    #         if evaluate_proposed_spec(spec, state).decision == "accepted":
    #             ever_accepted += 1
    #             break
    # rate = ever_accepted / n_campaigns
    # assert rate <= alpha  # alpha = 0.05 — do NOT weaken
    pytest.skip("CMP-TRI-02 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-TRI-02 (e-process spec gate) not yet implemented — martingale stub",
    strict=False,
)
def test_tri_02b_martingale_property_e_tau_le_one_under_h0() -> None:
    """e-process martingale property: empirical E[E_τ | H0] ≤ 1 across stopping times.

    Test id:        TST-AC-TRI-02b
    Maps to AC:     AC-TRI-02b — "The e-process implementation passes a
                    martingale-property unit test (empirical `E[E_τ|H0] ≤ 1`
                    across simulated stopping times) before production enablement."
    Kind tag:       [UNIT]
    Inputs:         Many Monte-Carlo trajectories of the e-process wealth E_t(sigma)
                    driven by a bounded-[0,1] stream simulated UNDER H0 (true
                    precision exactly at / below π₀), evaluated at a set of
                    simulated stopping times τ (including data-dependent ones).
                    E_0 = 1 by construction. DOC-ALGS §7.4 (Ville's inequality);
                    DOC-CMP-TRI-02 §5.3 (R-3 mitigation).
    Outputs:        The empirical mean of E_τ over the trajectories, per stopping
                    time τ in the simulated set.
    Pass criteria:  For every simulated stopping time τ, the empirical estimate of
                    E[E_τ | H0] ≤ 1 (within Monte-Carlo tolerance). A failure means
                    the implementation does not satisfy the anytime-valid guarantee
                    regardless of theoretical pedigree (R-3) — release blocked.
    Frequency:      pre-customer-enablement
    Hard gate?:     yes — Gate 4 (CLAUDE.md §15); blocks customer-enablement deploy.
    """
    # TODO: from services.triage.spec_inference import update_e_process
    # mc_tolerance must be defined concretely (a NameError under xfail(strict=False)
    # records XFAIL and would leave Gate 4 green while the bound is never evaluated).
    # Use a Monte-Carlo slack of 0.01 over n_trajectories >= 10_000 (DOC-ALGS §7.4).
    # mc_tolerance = 0.01
    # for tau in simulated_stopping_times:
    #     e_tau_samples = []
    #     for _ in range(n_trajectories):
    #         state = initial_state()    # E_0 = 1
    #         for obs in stream_under_h0()[:tau]:
    #             state = update_e_process(state, obs)
    #         e_tau_samples.append(math.exp(state.log_wealth))
    #     assert mean(e_tau_samples) <= 1.0 + mc_tolerance
    pytest.skip("CMP-TRI-02 not implemented yet")

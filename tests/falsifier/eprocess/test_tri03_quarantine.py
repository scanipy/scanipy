"""TRI-03 quarantine falsifier (shared e-process instrument) — TST-AC-TRI-03a.

Spec-first TDD: production code for CMP-TRI-03 (per-customer revalidation + drift
monitor, sharing CMP-TRI-02's e-process instrument in
`services/triage/spec_inference.py`) does not exist yet, so this spec is a
registered-but-dormant stub. It carries an ``@pytest.mark.xfail(strict=False)``
so the suite collects and runs without blocking; the body calls ``pytest.skip``
until CMP-TRI-03 is DONE.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

LOCATION: the ci.yml Gate-4 step discovers ``tests/falsifier/eprocess/**/
test_*.py`` and runs the directory; this quarantine falsifier exercises the
SAME e-process instrument as CMP-TRI-02, so it lives alongside the gate tests.
While xfail(strict=False)+skip, Gate-4 stays green (skips/xfails only, exit 0).

INV-3: the customer-stream drift monitor is the *same* anytime-valid instrument
run on the customer's adjudicated (human-labelled) stream — never on the LLM
output, never on the detection path. Quarantine EXCLUDES a spec from a
customer's future pinned `S`; it never deletes a previously emitted finding.

Covers (from WBS §4.3):
  - TST-AC-TRI-03a  [FALSIFIER] — global-accepted spec on an adversarial customer
                                  distribution is quarantined by the shared e-process
"""

import pytest


@pytest.mark.falsifier
@pytest.mark.xfail(
    reason="CMP-TRI-03 (per-customer revalidation + drift) not yet implemented",
    strict=False,
)
def test_tri_03a_global_spec_quarantined_on_adversarial_customer_stream() -> None:
    """A global-accepted spec on an adversarial customer distribution is quarantined.

    Test id:        TST-AC-TRI-03a
    Maps to AC:     AC-TRI-03a — "A global-accepted spec on an adversarial customer
                    distribution is quarantined by the shared e-process."
    Kind tag:       [FALSIFIER]
    Inputs:         A spec sigma already accepted by the GLOBAL e-process gate
                    (CMP-TRI-02), then fed a synthetic CUSTOMER-adjudicated stream
                    on which sigma's true precision is below the customer's π₀ (so the
                    complementary drift null is true); no finite horizon supplied;
                    alpha=0.05 (CLAR-PARAM-02 confirms alpha; π₀ per class DEFERRED).
                    DOC-CMP-TRI-03 §3.1 (shared instrument), §4.2, §5.3.
    Outputs:        The customer-stream drift e-process verdict for sigma for this org.
    Pass criteria:  sigma is auto-quarantined for that customer within bounded
                    observations (the customer-stream drift e-process crosses
                    `E_t ≥ 1/alpha`, alpha=0.05); the org's subsequent scans pin `S`
                    WITHOUT sigma; previously emitted findings are NOT deleted and
                    retain their historical `S_version` (INV-3 non-deletion).
    Frequency:      pre-release
    Hard gate?:     yes — component acceptance gate for CMP-TRI-03 (shared instrument).
    """
    # TODO: from services.triage.spec_inference import monitor_drift, revalidate_spec
    # state = customer_e_process_state(org_id, global_spec_version_id)
    # for obs in adversarial_customer_stream(true_precision_below_pi0):
    #     state = update_customer_e_process(state, obs)
    #     result = revalidate_spec(spec_version_id, org_id, state)
    #     if result.decision == "quarantined":
    #         break
    # assert result.decision == "quarantined"
    # assert global_spec_id not in pinned_S_for_next_scan(org_id)
    pytest.skip("CMP-TRI-03 not implemented yet")

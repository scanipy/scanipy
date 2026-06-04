"""Phase-1 TST-AC specs for the Control Plane & Attestation family — UNIT side.

Spec-first TDD: production code for CMP-CP-* does not exist yet. Each test is a
registered stub (`xfail(strict=False)` + `pytest.skip`) that flips red→green when
the implementation lands. Mirrors the canonical pattern in
`tests/unit/test_dsl_proofs.py`.

Scope of this file (per the QA task layout — disjoint from the integration file):
  - TST-AC-CP-01a   [NEGATIVE] cross-org access denied
  - TST-AC-CP-04b   [UNIT/snapshot] findings view never blurs the two partitions
  - TST-AC-CP-05b   [INVARIANT] oracle pipeline reports a rate, never the theorem
  - TST-AC-CP-06a   [INVARIANT] failing language reported `front-end-blocked`
  - TST-AC-CP-06b   [UNIT] gate verdicts recorded per language + consulted by staging
  - TST-INV-3-CP-05 [INVARIANT] Attestor core pipeline runs with LLM_TRIAGE=off
  - TST-INV-6-CP-06 [INVARIANT] gate refuses to emit a recall number on a fail

Marker set is closed (`--strict-markers`): {unit, integration, falsifier, empirical,
invariant, nightly, pre_release}. The WBS "Kind tag" lives in the docstring only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from uuid import UUID

    from analysis.sarif.canonical_emit import SARIFLog
    from services.control_plane import JWTClaims

_ORG_A = "11111111-1111-1111-1111-111111111111"
_ORG_B = "22222222-2222-2222-2222-222222222222"
_USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

# Parametrization axis: (verb, resource) over the three route families named in
# the AC-CP-01a spec (findings / scans / codebases) across GET/POST/DELETE.
_VERB_RESOURCE = [
    ("GET", "findings"),
    ("POST", "scans"),
    ("DELETE", "codebases"),
    ("GET", "scans"),
    ("POST", "codebases"),
    ("DELETE", "findings"),
    ("GET", "codebases"),
    ("POST", "findings"),
    ("DELETE", "scans"),
]


def _claims_org_a(role: str = "org-admin") -> JWTClaims:
    from services.control_plane import JWTClaims

    return JWTClaims(
        user_id=_USER_A,
        org_id=_ORG_A,
        role=role,  # type: ignore[arg-type]
        issued_at=0,
        expires_at=9999999999,
    )


@pytest.mark.unit
@pytest.mark.parametrize(("method", "resource"), _VERB_RESOURCE)
def test_cp01a_cross_org_access_is_denied(method: str, resource: str) -> None:
    """Cross-org access attempt is denied — no IAM cross-bleed.

    Test id:      TST-AC-CP-01a
    Maps to AC:   AC-CP-01a (SDD §10 CMP-CP-01)
    Kind tag:     [NEGATIVE]
    Inputs:       Two orgs A and B (fixture); a valid JWT scoped to org A
                  (X-Scanipy-Org-Id=A, X-Scanipy-User-Id matching the org-A claim);
                  a request targeting an org-B resource id. Parameterized over
                  GET/POST/DELETE on findings/scans/codebases routes.
    Outputs:      HTTP 403/404 per DOC-API §6 error envelope; RLS returns zero rows
                  (DOC-DB §3.2 `app.org_id` session variable backstop).
    Pass criteria: For every (verb, route) the org-A token is denied access to an
                  org-B resource; no org-B row is ever returned; the response never
                  leaks org-B existence beyond the chosen 403/404 envelope.
    Frequency:    every CI run
    Hard gate?:   yes — Stage-A GA process gate (tenancy isolation, CLAR-DEPLOY-16).

    Exercises all three CLAR-DEPLOY-16 / DOC-CMP-CP-01 §9 layers per (verb, route):
      L1: forged X-Scanipy-Org-Id (org B) on an org-A JWT  -> 403 org_mismatch
      L2: org-A session reaching an org-B resource id      -> RLS miss -> 404
      L3: query issued before the session var is bound      -> TenantIsolationError
    """
    from services.control_plane import (
        CPGuard,
        OrgScopedStore,
        TenantIsolationError,
    )

    guard = CPGuard()
    claims = _claims_org_a()
    trace = "trace-cp01a"

    # --- Layer 1: forged tenancy header pointing at org B -------------------
    forged_headers = {"X-Scanipy-Org-Id": _ORG_B, "X-Scanipy-User-Id": _USER_A}
    l1 = guard.authorize_request(
        claims,
        forged_headers,
        method=method,
        resource=resource,  # type: ignore[arg-type]
        route=f"/api/v1/{resource}",
        trace_id=trace,
    )
    assert l1 is not None, "cross-tenant header must be rejected"
    assert l1.error_code == "org_mismatch"
    assert l1.http_status == 403
    # No org-B identifier beyond the echoed header is leaked in the message.
    assert _ORG_B not in l1.message

    # --- Layer 2: org-A session can never see an org-B resource id ----------
    store: OrgScopedStore[str] = OrgScopedStore()
    store.seed("resource-owned-by-b", _ORG_B, "secret-b-payload")
    store.set_session(_ORG_A)  # CP-01 bound app.org_id = A after a clean auth.
    assert store.query_one("resource-owned-by-b") is None, "RLS must hide org-B row"
    assert store.query() == [], "no cross-tenant rows in a tenant-scoped list"
    # The handler surfaces a non-leaking 404 for the cross-tenant miss.
    nf = guard.not_found_envelope(trace)
    assert nf.error_code == "not_found"
    assert nf.http_status == 404

    # --- Layer 3: a query before the session setter ran is a hard reject ----
    unbound: OrgScopedStore[str] = OrgScopedStore()
    unbound.seed("resource-owned-by-b", _ORG_B, "secret-b-payload")
    with pytest.raises(TenantIsolationError):
        unbound.query_one("resource-owned-by-b")
    iso = guard.isolation_error_envelope(trace)
    assert iso.error_code == "tenant_isolation_violation"
    assert iso.http_status == 403

    # --- RBAC gate is live: a same-tenant request lacking the capability is
    #     denied with role_denied (org-viewer cannot submit a scan; DOC-API §2.6).
    viewer = _claims_org_a(role="org-viewer")
    same_tenant_headers = {"X-Scanipy-Org-Id": _ORG_A, "X-Scanipy-User-Id": _USER_A}
    rbac = guard.authorize_request(
        viewer,
        same_tenant_headers,
        method="POST",
        resource="scans",
        route="/api/v1/scans",
        trace_id=trace,
    )
    assert rbac is not None
    assert rbac.error_code == "role_denied"
    assert rbac.http_status == 403

    # --- Regression: DELETE has no §2.6 capability cell for ANY role. It must
    #     deny even for org-admin (who holds update_creds on codebases). A prior
    #     bug projected DELETE onto "update_creds", silently letting org-admin
    #     DELETE codebases. The "forbidden" sentinel (held by no role) fixes it.
    admin = _claims_org_a(role="org-admin")
    for res in ("codebases", "scans", "findings", "snapshots", "attestations"):
        denied = guard.authorize_request(
            admin,
            same_tenant_headers,
            method="DELETE",
            resource=res,
            route=f"/api/v1/{res}",
            trace_id=trace,
        )
        assert denied is not None, f"DELETE {res} must be denied for org-admin"
        assert denied.error_code == "role_denied"
        assert denied.http_status == 403


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-CP-04 (auth + dashboard) not yet implemented — spec stub",
    strict=False,
)
def test_cp04b_findings_view_never_blurs_partitions() -> None:
    """Findings view never visually blurs deterministic-core and oracle-passthrough.

    Test id:      TST-AC-CP-04b
    Maps to AC:   AC-CP-04b (SDD §10 CMP-CP-04)
    Kind tag:     [UNIT] (render snapshot — stable output comparison, not Jest)
    Inputs:       A rendered findings row for one `deterministic-core` finding and
                  one `oracle-passthrough` finding (fixture finding records carrying
                  origin, S_version, env_digest, cpg_order_hash + annotation).
    Outputs:      Rendered row markup / view-model exposing a partition style token
                  per finding (DOC-CMP-CP-04 §3 visual-partition rule).
    Pass criteria: The two partitions render with distinct, non-overlapping partition
                  tokens (e.g. CSS class / badge); no shared/ambiguous token spans
                  both; no `mixed` styling token exists anywhere in the view model.
    Frequency:    every CI run
    Hard gate?:   yes — Stage-A GA process gate (INV-1 honest presentation).
    """
    # TODO: import the findings-row renderer / view-model builder from web/ (or its
    # Python view-model shim) when CMP-CP-04 is DONE; assert disjoint partition tokens
    # and the absence of any `mixed` token.
    pytest.skip("CMP-CP-04 not implemented yet")


@pytest.mark.invariant
def test_cp05b_oracle_pipeline_reports_rate_never_theorem() -> None:
    """Oracle pipeline reports a numeric reproduction rate and never asserts the theorem.

    Test id:      TST-AC-CP-05b
    Maps to AC:   AC-CP-05b (SDD §10 CMP-CP-05)
    Kind tag:     [INVARIANT]
    Inputs:       A scan with oracle-passthrough findings (hermetic synthetic-F); two
                  independent re-runs of F under fixed (S_version, env_digest), where
                  run 2 drops one of two oracle findings (DOC-PARTITION §6.2;
                  DOC-CMP-CP-05 §3.2).
    Outputs:      AttestationVerdict with partition="oracle", result="rate-only",
                  reproduction_rate ∈ [0, 1].
    Pass criteria: result is exactly "rate-only" (never "pass"/"fail"); reproduction_rate
                  is a MEASURED number — exactly 0.5 with the 1-of-2 instability above
                  (proving it is computed, not hardcoded), and exactly 1.0 on a faithful
                  oracle F; the verdict text never claims "byte-identical" or property (a)
                  over oracle findings — even at rate 1.0 (a 100% rate is empirical, not
                  theorem-licensed).
    Frequency:    every CI run (informational job)
    Hard gate?:   yes — INV-1/contract gate (oracle pipeline must never claim theorem);
                  the rate floor itself is non-blocking and tuned under CLAR-CP-05-01.

    NEGATIVE CONTROL (mutation-verified, documented in the implementing PR): an attestor
    that returns result="pass" on the oracle partition, or that hardcodes the rate (so
    the 0.5 vs 1.0 split below collapses), or that emits "byte-identical"/property-(a)
    theorem language in the verdict, FAILS these assertions.
    """
    from decimal import Decimal

    from services.scan.attestor import AttestationVerdict, attest_scan
    from tests.cp05_fakes import DroppingOracleScanRunner, oracle_f

    scan_id = _attestor_scan_id()

    # ---- MEASURED rate: run 2 drops 1 of 2 oracle findings -> rate == 0.5. ----
    dropping = attest_scan(
        scan_id,
        "oracle",
        s_version="1.4.2",
        env_digest="sha256:" + "a" * 64,
        scan_runner=DroppingOracleScanRunner(),
    )
    assert isinstance(dropping, AttestationVerdict)
    assert dropping.result == "rate-only", "oracle result is EXACTLY 'rate-only', never pass/fail"
    assert dropping.reproduction_rate == Decimal("0.5000"), (
        "the rate must be MEASURED (1 stable / 2 total = 0.5), not hardcoded"
    )
    assert Decimal("0") <= dropping.reproduction_rate <= Decimal("1")
    assert dropping.diff_summary is None  # no byte-diff incident on the oracle partition

    # ---- Anti-vacuity contrast: a faithful oracle F -> rate == 1.0, still rate-only. --
    class _StableOracle:
        def run(self, sid: UUID) -> SARIFLog:
            return oracle_f(drop_second=False)

    stable = attest_scan(
        scan_id,
        "oracle",
        s_version="1.4.2",
        env_digest="sha256:" + "a" * 64,
        scan_runner=_StableOracle(),
    )
    assert stable.result == "rate-only", "even at 100% the oracle result stays 'rate-only'"
    assert stable.reproduction_rate == Decimal("1.0000")

    # ---- The verdict must NEVER carry theorem language (the §3.3 forbidden claims). --
    # AC-CP-05b: never "byte-identical" / property (a) over oracle findings, even at 1.0.
    for verdict in (dropping, stable):
        text = " ".join(
            str(v) for v in (verdict.result, verdict.diff_summary) if v is not None
        ).lower()
        assert "byte-identical" not in text, "oracle verdict must not claim byte-identity"
        assert "property (a)" not in text, "oracle verdict must not claim property (a)"
        # The oracle result token itself is the contract: not the core "pass"/"fail".
        assert verdict.result not in ("pass", "fail"), "oracle never asserts pass/fail"


@pytest.mark.invariant
def test_inv3_cp05_attestor_core_runs_with_llm_triage_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Attestor core pipeline runs with LLM_TRIAGE=off (INV-3 discharge).

    Test id:      TST-INV-3-CP-05
    Maps to AC:   INV-3 (CLAUDE.md §3; DOC-INV §5) via CMP-CP-05 §5
    Kind tag:     [INVARIANT]
    Inputs:       Attestor core-pipeline invocation environment; the env-var check in
                  attest_scan(scan_id, "core") (DOC-CMP-CP-05 §7 INV-3 backstop).
    Outputs:      Core pipeline either runs under LLM_TRIAGE=off or hard-fails with an
                  explicit "core pipeline requires LLM_TRIAGE=off" error.
    Pass criteria: With LLM_TRIAGE leaked to "on", the core pipeline REFUSES to run
                  (raises AttestorConfigurationError, explicit message); with
                  LLM_TRIAGE=off it proceeds and attests. The byte-identity claim is never
                  asserted while triage could be active. The ORACLE pipeline, by contrast,
                  is NOT required to be off (oracle findings are not theorem-covered).
    Frequency:    every CI run
    Hard gate?:   yes — Gate 3 (Attestor; RULE-9 INV-3 component, Security sign-off).

    NEGATIVE CONTROL (mutation-verified, documented in the implementing PR): removing the
    LLM_TRIAGE guard from attest_scan's core branch makes the LLM_TRIAGE=on case proceed
    (no raise), FAILING the pytest.raises leg below — so this guard has power.
    """
    from services.scan.attestor import (
        AttestorConfigurationError,
        attest_scan,
    )
    from tests.cp05_fakes import make_runner, oracle_f

    scan_id = _attestor_scan_id()
    s_version = "1.4.2"
    env_digest = "sha256:" + "a" * 64

    # ---- LLM_TRIAGE=on -> the CORE pipeline is REJECTED fail-closed. ----------
    monkeypatch.setenv("LLM_TRIAGE", "on")
    with pytest.raises(AttestorConfigurationError, match="requires LLM_TRIAGE=off"):
        attest_scan(
            scan_id, "core", s_version=s_version, env_digest=env_digest, scan_runner=make_runner()
        )

    # ---- LLM_TRIAGE=off -> the CORE pipeline proceeds and attests pass. -------
    monkeypatch.setenv("LLM_TRIAGE", "off")
    verdict = attest_scan(
        scan_id, "core", s_version=s_version, env_digest=env_digest, scan_runner=make_runner()
    )
    assert verdict.result == "pass", "under LLM_TRIAGE=off the faithful core F attests pass"

    # ---- The ORACLE pipeline is NOT gated on LLM_TRIAGE (DOC-CMP-CP-05 §3.2). -
    # Even with triage leaked on, the oracle pipeline runs (it makes no theorem claim).
    monkeypatch.setenv("LLM_TRIAGE", "on")

    class _StableOracle:
        def run(self, sid: UUID) -> SARIFLog:
            return oracle_f(drop_second=False)

    oracle = attest_scan(
        scan_id, "oracle", s_version=s_version, env_digest=env_digest, scan_runner=_StableOracle()
    )
    assert oracle.result == "rate-only", "oracle pipeline runs regardless of LLM_TRIAGE"


def _attestor_scan_id() -> UUID:
    """The synthetic-F scan id (good_job().scan_id) the Attestor re-runs."""
    from uuid import UUID

    return UUID(int=2)


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-CP-06 (CPG-fidelity gate harness) not yet implemented — spec stub",
    strict=False,
)
def test_cp06a_failing_language_reported_front_end_blocked() -> None:
    """A language failing the gate is reported `front-end-blocked`, not a recall failure.

    Test id:      TST-AC-CP-06a
    Maps to AC:   AC-CP-06a (SDD §10 CMP-CP-06) — INV-6
    Kind tag:     [INVARIANT]
    Inputs:       A synthetic fidelity corpus where the front-end achieves call-edge
                  recall = 0.60 (< the 0.85 threshold, CLAR-CORP-02 RESOLVED 2026-05-23);
                  evaluate_fidelity(language, corpus) (DOC-CMP-CP-06 §3.2/§9).
    Outputs:      FidelityVerdict with overall="GATE-FAIL",
                  failing_metrics==["call_edge_recall"], latest.json written; reporting
                  label "front-end-blocked".
    Pass criteria: The language surfaces as `front-end-blocked` (with the failing metric
                  + value < threshold); it is NEVER surfaced as a "recall failure" and
                  NO recall number is reported for any (class, language) pair on the
                  failing language (INV-6 forbidden phrasings, DOC-CMP-CP-06 §3.3).
    Frequency:    every CI run
    Hard gate?:   yes — INV-6 hard discharge (PR-blocking on violation, DOC-CMP-CP-06 §7).
    """
    # TODO: build the recall=0.60 synthetic corpus fixture; assert overall=="GATE-FAIL",
    # failing_metrics==["call_edge_recall"], and that the reporting layer emits
    # `front-end-blocked` with no recall number, once CMP-CP-06 is DONE.
    pytest.skip("CMP-CP-06 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-CP-06 (CPG-fidelity gate harness) not yet implemented — spec stub",
    strict=False,
)
def test_cp06b_gate_results_recorded_per_language_and_consulted() -> None:
    """Gate results are recorded per language and consulted by the WBS staging logic.

    Test id:      TST-AC-CP-06b
    Maps to AC:   AC-CP-06b (SDD §10 CMP-CP-06)
    Kind tag:     [UNIT]
    Inputs:       A passing language (Java → GATE-PASS) and a failing language
                  (Go → GATE-FAIL) run through evaluate_fidelity + persist_verdict
                  (DOC-CMP-CP-06 §3.4/§9).
    Outputs:      Per-language tests/results/cpg_fidelity/{language}/latest.json verdicts
                  matching the §3.4 schema; staging consultation reads them.
    Pass criteria: Both verdicts persist to the per-language latest.json path with the
                  documented schema (language, corpus_version, env_digest, four metrics,
                  overall, failing_metrics, evaluated_at); staging logic admits Java to
                  Algorithm 2 benchmarking and refuses Go (RULE-7).
    Frequency:    every CI run
    Hard gate?:   yes — Stage-gate process gate (per-language staging consultation).
    """
    # TODO: assert persist_verdict writes the per-language latest.json schema for both a
    # GATE-PASS and a GATE-FAIL language, and that the staging consumer admits/refuses
    # accordingly, once CMP-CP-06 is DONE.
    # NOTE: a DB-backed `fidelity_results` table is out of baseline scope (CLAR-CP-06-01);
    # this spec asserts the JSON persistence surface only.
    pytest.skip("CMP-CP-06 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-CP-06 (CPG-fidelity gate harness) not yet implemented — spec stub",
    strict=False,
)
def test_inv6_cp06_gate_refuses_recall_number_on_fail() -> None:
    """Gate produces a pass/fail per language and refuses to emit a recall number on fail.

    Test id:      TST-INV-6-CP-06
    Maps to AC:   INV-6 owner-side discharge (DOC-INV §8) via CMP-CP-06 §5/§9
    Kind tag:     [INVARIANT]
    Inputs:       A GATE-FAIL FidelityVerdict for a language (e.g. Go, call-edge
                  recall < 0.85); the reporting / honest-labeling surface.
    Outputs:      A `front-end-blocked` label classified [STAGED] in the honest-labeling
                  ledger; no [EMPIRICAL] recall number for the failing language.
    Pass criteria: The owner-side reporting path emits exactly one of {GATE-PASS,
                  GATE-FAIL/front-end-blocked} per language and structurally cannot emit
                  a recall number for a non-gate-passing (class, language) pair (INV-6).
    Frequency:    every CI run
    Hard gate?:   yes — INV-6 (per-language honesty; owner-side discharge).
    """
    # TODO: assert the reporting path raises / omits when asked for a recall number on a
    # GATE-FAIL language, and only emits `front-end-blocked`, once CMP-CP-06 is DONE.
    pytest.skip("CMP-CP-06 not implemented yet")

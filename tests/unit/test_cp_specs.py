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

import json
import logging
from decimal import Decimal
from pathlib import Path
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


# ===========================================================================
# CMP-CP-06 — CPG-fidelity gate harness (TST-AC-CP-06a/b, TST-INV-6-CP-06).
#
# Synthetic fidelity fixtures: a CorpusPort + ExtractionPort pair lets each test
# dial the four metrics to a target without the gated Joern/Soot/WALA toolchain
# (build-ahead per CLAR-PROC-01 — the ports are CMP-CP-06's hermetic seam). A
# gate-strength corpus + an extraction tuned above/below each threshold is the
# anti-vacuity fixture for the GATE-PASS / GATE-FAIL legs.
# ===========================================================================
_GATE_STRENGTH_ENV = "sha256:" + "ab" * 32


class _SyntheticCorpus:
    """A gate-strength CorpusPort with one ground-truth item per file.

    ``call_gt`` / ``pdg_gt`` are the ground-truth edge counts; ``parsed`` flags
    how many files parse. ``gate_strength`` defaults True so the GATE-PASS leg is
    constructible; set False to exercise the ungated short-circuit.
    """

    def __init__(
        self,
        *,
        files: int = 10,
        files_parsed: int = 10,
        call_gt: int = 100,
        pdg_gt: int = 100,
        gate_strength: bool = True,
        corpus_version: str = "1.0.0",
    ) -> None:
        from services.control_plane import GroundTruthItem

        self._gate_strength = gate_strength
        self._corpus_version = corpus_version
        self._items = []
        for i in range(files):
            self._items.append(
                GroundTruthItem(
                    item_id=f"item-{i:04d}",
                    parsed=i < files_parsed,
                    call_edges_ground_truth=call_gt if i == 0 else 0,
                    pdg_edges_ground_truth=pdg_gt if i == 0 else 0,
                )
            )

    @property
    def corpus_version(self) -> str:
        return self._corpus_version

    @property
    def gate_strength(self) -> bool:
        return self._gate_strength

    def ground_truth(self):  # type: ignore[no-untyped-def]
        return tuple(self._items)


class _SyntheticExtraction:
    """An ExtractionPort that realizes target call-edge precision/recall + PDG recall.

    All confusion counts are attributed to item-0000 (the only item carrying
    ground-truth edges in :class:`_SyntheticCorpus`); the rest parse cleanly with
    no edges. ``parsed`` mirrors the ground-truth ``parsed`` flag.
    """

    def __init__(
        self,
        *,
        call_tp: int,
        call_fp: int,
        call_fn: int,
        pdg_tp: int,
        pdg_fn: int,
        env_digest: str = _GATE_STRENGTH_ENV,
    ) -> None:
        self._call = (call_tp, call_fp, call_fn)
        self._pdg = (pdg_tp, pdg_fn)
        self._env_digest = env_digest

    @property
    def env_digest(self) -> str:
        return self._env_digest

    def extract(self, item):  # type: ignore[no-untyped-def]
        from services.control_plane import ExtractedItem

        if item.item_id == "item-0000":
            ce_tp, ce_fp, ce_fn = self._call
            pdg_tp, pdg_fn = self._pdg
        else:
            ce_tp = ce_fp = ce_fn = pdg_tp = pdg_fn = 0
        return ExtractedItem(
            item_id=item.item_id,
            parsed=item.parsed,
            call_edges_true_positive=ce_tp,
            call_edges_false_positive=ce_fp,
            call_edges_false_negative=ce_fn,
            pdg_edges_true_positive=pdg_tp,
            pdg_edges_false_negative=pdg_fn,
        )


def _passing_extraction() -> _SyntheticExtraction:
    """Extraction tuned ABOVE all four thresholds (parse 100%, precision 0.95,
    recall 0.90, PDG recall 0.90)."""
    # call precision = 95/100 = 0.95 >= 0.90; recall = 95/(95+10)=0.9047 >= 0.85.
    # PDG recall = 90/100 = 0.90 >= 0.80.
    return _SyntheticExtraction(call_tp=95, call_fp=5, call_fn=10, pdg_tp=90, pdg_fn=10)


@pytest.mark.invariant
def test_cp06a_failing_language_reported_front_end_blocked() -> None:
    """A language failing the gate is reported `front-end-blocked`, not a recall failure.

    Test id:      TST-AC-CP-06a
    Maps to AC:   AC-CP-06a (SDD §10 CMP-CP-06) — INV-6
    Kind tag:     [INVARIANT]
    Inputs:       A synthetic gate-strength fidelity corpus where the front-end achieves
                  call-edge recall = 0.60 (< the 0.85 threshold, CLAR-CORP-02 RESOLVED
                  2026-05-23); evaluate_fidelity(language, corpus_path, ports)
                  (DOC-CMP-CP-06 §3.2/§9).
    Outputs:      FidelityVerdict with overall="GATE-FAIL",
                  failing_metrics==["call_edge_recall"], reporting label
                  "front-end-blocked".
    Pass criteria: The language surfaces as `front-end-blocked` (with the failing FIDELITY
                  metric + value < threshold); it is NEVER surfaced as a "recall failure"
                  and the benchmark-eligibility accessor REFUSES to emit an Algorithm-2
                  recall number (INV-6 forbidden phrasings, DOC-CMP-CP-06 §3.3).
    Frequency:    every CI run
    Hard gate?:   yes — INV-6 hard discharge (PR-blocking on violation, DOC-CMP-CP-06 §7).
    """
    from services.control_plane import BenchmarkEligibilityError, evaluate_fidelity

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    # call-edge recall = 60/(60+40) = 0.60 < 0.85; everything else above threshold.
    extraction = _SyntheticExtraction(call_tp=60, call_fp=2, call_fn=40, pdg_tp=90, pdg_fn=10)
    verdict = evaluate_fidelity("go", Path("/unused"), corpus=corpus, extraction=extraction)

    assert verdict.overall == "GATE-FAIL"
    assert verdict.failing_metrics == ["call_edge_recall"]
    assert verdict.label() == "front-end-blocked"
    # The reporting reason names the FIDELITY metric + value (permitted, DOC §3.3).
    assert "call-edge-recall" in verdict.front_end_blocked_reason()
    assert "recall failure" not in verdict.front_end_blocked_reason()
    # The FORBIDDEN Algorithm-2 detector recall number is structurally refused.
    with pytest.raises(BenchmarkEligibilityError):
        verdict.benchmark_eligible_recall()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("metric", "extraction"),
    [
        # Each leg violates exactly ONE threshold; everything else stays above.
        (
            "parse_success_rate",
            # 98/100 = 0.98 < 0.995 parse; call/pdg above threshold.
            None,  # built inline below (needs a partial-parse corpus)
        ),
        (
            "call_edge_precision",
            # precision 80/100 = 0.80 < 0.90; recall 80/(80+5)=0.94 >= 0.85.
            _SyntheticExtraction(call_tp=80, call_fp=20, call_fn=5, pdg_tp=90, pdg_fn=10),
        ),
        (
            "call_edge_recall",
            # recall 60/(60+40)=0.60 < 0.85; precision 60/62=0.967 >= 0.90.
            _SyntheticExtraction(call_tp=60, call_fp=2, call_fn=40, pdg_tp=90, pdg_fn=10),
        ),
        (
            "pdg_recall",
            # pdg recall 70/100 = 0.70 < 0.80; call metrics above threshold.
            _SyntheticExtraction(call_tp=95, call_fp=5, call_fn=10, pdg_tp=70, pdg_fn=30),
        ),
    ],
)
def test_cp06_each_threshold_individually_violated_blocks(
    metric: str, extraction: _SyntheticExtraction | None
) -> None:
    """Each of the four thresholds, violated alone, yields GATE-FAIL naming THAT metric.

    Test id:      TST-AC-CP-06a (falsifier leg — DOC §9 AC-CP-06a falsifier step 3)
    Kind tag:     [UNIT]
    Pass criteria: overall=="GATE-FAIL"; failing_metrics==[metric]; label is
                  "front-end-blocked".
    """
    from services.control_plane import evaluate_fidelity

    if metric == "parse_success_rate":
        corpus = _SyntheticCorpus(files=100, files_parsed=98, call_gt=100, pdg_gt=100)
        extraction = _passing_extraction()
    else:
        corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    assert extraction is not None
    verdict = evaluate_fidelity("go", Path("/unused"), corpus=corpus, extraction=extraction)

    assert verdict.overall == "GATE-FAIL"
    assert verdict.failing_metrics == [metric]
    assert verdict.label() == "front-end-blocked"


@pytest.mark.unit
def test_cp06_positive_gate_strength_above_all_thresholds_passes() -> None:
    """A gate-strength corpus above all four thresholds yields GATE-PASS (anti-vacuity).

    Test id:      TST-AC-CP-06b (positive leg)
    Kind tag:     [UNIT]
    Pass criteria: overall=="GATE-PASS"; failing_metrics==[]; benchmark eligibility
                  yields the (fidelity) recall without raising.
    """
    from services.control_plane import evaluate_fidelity

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    verdict = evaluate_fidelity(
        "java", Path("/unused"), corpus=corpus, extraction=_passing_extraction()
    )
    assert verdict.overall == "GATE-PASS"
    assert verdict.failing_metrics == []
    assert verdict.gate_passed is True
    # Only a gate-passing language exposes a benchmark-eligible recall (no raise).
    assert verdict.benchmark_eligible_recall() >= Decimal("0.85")


@pytest.mark.unit
def test_cp06_boundary_exactly_at_threshold_passes_ge_semantics() -> None:
    """A metric EXACTLY at threshold passes (DOC §6 `>=` semantics; a `>` mutant fails).

    Test id:      TST-AC-CP-06b (boundary leg — falsifier (d))
    Kind tag:     [UNIT]
    Pass criteria: with call-edge recall == 0.85 exactly (and others at/above their
                  thresholds), overall=="GATE-PASS". A `>` mutant would FAIL this.
    """
    from services.control_plane import evaluate_fidelity

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    # All four metrics land EXACTLY on the threshold:
    #   parse 100%  >= 0.995
    #   precision 90/100 = 0.90 == 0.90
    #   recall   90/(90+? )    -> tune fn so recall == 0.85 exactly: tp=85, fn=15 -> 0.85
    #   pdg recall 80/100 = 0.80 == 0.80
    # Use tp=90 fp=10 (precision 0.90) and choose fn so recall == 0.85:
    #   recall = 90/(90+fn) = 0.85 -> 90+fn = 105.88..., not integral. Instead pick
    #   tp=85, fp=? for precision 0.90 -> 85/(85+fp)=0.90 -> fp=9.44 not integral.
    # Exact-rational construction: precision tp=90, fp=10 (0.90); recall tp=90, fn so
    #   90/(90+fn)=0.85 is non-integral, so test recall boundary with tp=85,fn=15
    #   (=0.85) and precision tp=85, fp so 85/(85+fp)=0.90 -> non-integral. To keep a
    #   single extraction with both call metrics exact we use the recall boundary as
    #   the binding one and keep precision strictly above:
    extraction = _SyntheticExtraction(call_tp=85, call_fp=0, call_fn=15, pdg_tp=80, pdg_fn=20)
    verdict = evaluate_fidelity("java", Path("/unused"), corpus=corpus, extraction=extraction)
    assert verdict.metrics.call_edge_recall == Decimal("0.85")
    assert verdict.metrics.pdg_recall == Decimal("0.80")
    assert verdict.overall == "GATE-PASS"
    assert verdict.failing_metrics == []


@pytest.mark.unit
def test_cp06b_gate_results_recorded_per_language_and_consulted(tmp_path: Path) -> None:
    """Gate results are recorded per language and consulted by the WBS staging logic.

    Test id:      TST-AC-CP-06b
    Maps to AC:   AC-CP-06b (SDD §10 CMP-CP-06)
    Kind tag:     [UNIT]
    Inputs:       A passing language (Java → GATE-PASS) and a failing language
                  (Go → GATE-FAIL) run through evaluate_fidelity + persist_verdict
                  (DOC-CMP-CP-06 §3.4/§9).
    Outputs:      Per-language {root}/cpg_fidelity/{language}/latest.json verdicts
                  matching the §3.4 schema; staging consultation reads them.
    Pass criteria: Both verdicts persist to the per-language latest.json path with the
                  documented schema (language, corpus_version, env_digest, four metrics,
                  overall, failing_metrics, evaluated_at); the gate_passed accessor admits
                  Java to Algorithm 2 benchmarking and refuses Go (RULE-7).
    Frequency:    every CI run
    Hard gate?:   yes — Stage-gate process gate (per-language staging consultation).

    NOTE: a DB-backed `fidelity_results` table is out of baseline scope
    (CLAR-CP-06-01); this spec asserts the JSON persistence surface only. The live
    WBS §13 staging-table flip is a manual /sync-wbs action — not hermetically
    exercisable here — so this leg asserts the machine-readable consultation
    accessor (`gate_passed`) the consumer reads, not the prose-table edit.
    """
    from services.control_plane import evaluate_fidelity, load_verdict, persist_verdict

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    java = evaluate_fidelity(
        "java", Path("/unused"), corpus=corpus, extraction=_passing_extraction()
    )
    go_extraction = _SyntheticExtraction(call_tp=60, call_fp=2, call_fn=40, pdg_tp=90, pdg_fn=10)
    go = evaluate_fidelity("go", Path("/unused"), corpus=corpus, extraction=go_extraction)

    java_path = persist_verdict(java, tmp_path)
    go_path = persist_verdict(go, tmp_path)
    assert java_path == tmp_path / "cpg_fidelity" / "java" / "latest.json"
    assert go_path == tmp_path / "cpg_fidelity" / "go" / "latest.json"

    payload = json.loads(java_path.read_text(encoding="utf-8"))
    for key in (
        "language",
        "corpus_version",
        "env_digest",
        "parse_success_rate",
        "call_edge_precision",
        "call_edge_recall",
        "pdg_recall",
        "overall",
        "failing_metrics",
        "evaluated_at",
    ):
        assert key in payload, f"DOC §3.4 schema key {key!r} missing from latest.json"

    # Staging consultation: Java admitted (gate_passed), Go refused (RULE-7).
    assert load_verdict(tmp_path, "java").gate_passed is True
    assert load_verdict(tmp_path, "go").gate_passed is False


@pytest.mark.unit
def test_cp06_latest_json_round_trip_identical_verdict(tmp_path: Path) -> None:
    """Write + re-read latest.json yields the identical verdict (staging consumer contract).

    Test id:      TST-AC-CP-06b (round-trip leg — falsifier (e))
    Kind tag:     [UNIT]
    Pass criteria: load_verdict(persist_verdict(v)) reproduces the verdict IDENTITY
                  (language, corpus_version, env_digest, overall, failing_metrics,
                  gate_strength) — that, not bit-exact Decimal across the file
                  boundary, is the "identical verdict" staging contract. The four
                  threshold rates persist as JSON NUMBERS (the named consumer,
                  .github/workflows/stage-gate.yml, compares them numerically and
                  formats with :.3f — a string would crash it).
    """
    from services.control_plane import evaluate_fidelity, load_verdict, persist_verdict

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    original = evaluate_fidelity(
        "java", Path("/unused"), corpus=corpus, extraction=_passing_extraction()
    )
    path = persist_verdict(original, tmp_path)
    restored = load_verdict(tmp_path, "java")

    # Verdict identity survives the round-trip exactly.
    assert restored.language == original.language
    assert restored.corpus_version == original.corpus_version
    assert restored.env_digest == original.env_digest
    assert restored.overall == original.overall
    assert restored.failing_metrics == original.failing_metrics
    assert restored.gate_strength == original.gate_strength

    # The persisted rates are JSON NUMBERS (int/float), never strings — the
    # consumer contract. A string would break `value >= threshold` / `:.3f`.
    payload = json.loads(path.read_text(encoding="utf-8"))
    for metric in ("parse_success_rate", "call_edge_precision", "call_edge_recall", "pdg_recall"):
        assert isinstance(payload[metric], (int, float)) and not isinstance(
            payload[metric], bool
        ), f"{metric} must serialize as a JSON number for the stage-gate.yml consumer"


@pytest.mark.unit
def test_cp06_latest_json_consumed_by_stage_gate_workflow_logic(tmp_path: Path) -> None:
    """The persisted latest.json is consumable by the stage-gate.yml threshold step.

    Test id:      TST-AC-CP-06b (consumer-contract leg)
    Kind tag:     [UNIT]
    Pass criteria: Replaying the EXACT "Evaluate thresholds and write verdict" logic
                  from .github/workflows/stage-gate.yml against the persisted file
                  (value = r.get(metric, 0.0); value >= threshold; f"{value:.3f}")
                  succeeds without TypeError/ValueError and reaches the SAME pass/fail
                  decision the verdict carries. This is the load-bearing FORMAT check:
                  it fails loudly if a rate were serialized as a string.
    """
    from services.control_plane import evaluate_fidelity, persist_verdict

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    # A GATE-FAIL verdict (call-edge recall 0.60 < 0.85) — exercises the failure path.
    extraction = _SyntheticExtraction(call_tp=60, call_fp=2, call_fn=40, pdg_tp=90, pdg_fn=10)
    verdict = evaluate_fidelity("go", Path("/unused"), corpus=corpus, extraction=extraction)
    path = persist_verdict(verdict, tmp_path)

    # --- verbatim stage-gate.yml "Evaluate thresholds" consumer logic ---------
    r = json.loads(path.read_text(encoding="utf-8"))
    thresholds = {
        "parse_success_rate": 0.995,
        "call_edge_precision": 0.90,
        "call_edge_recall": 0.85,
        "pdg_recall": 0.80,
    }
    failures = []
    for metric, threshold in thresholds.items():
        value = r.get(metric, 0.0)
        # The two operations that would crash on a string rate:
        _ = f"{value:.3f} (>={threshold:.3f})"
        if value < threshold:
            failures.append(f"{metric}={value:.3f} < {threshold:.3f}")
    # --------------------------------------------------------------------------

    consumer_gate_pass = not failures
    assert consumer_gate_pass is verdict.gate_passed
    assert consumer_gate_pass is False  # the GATE-FAIL verdict
    assert "call_edge_recall=0.600 < 0.850" in failures


@pytest.mark.invariant
def test_inv6_cp06_gate_refuses_recall_number_on_fail() -> None:
    """Gate produces a pass/fail per language and refuses to emit a recall number on fail.

    Test id:      TST-INV-6-CP-06
    Maps to AC:   INV-6 owner-side discharge (DOC-INV §8) via CMP-CP-06 §5/§9
    Kind tag:     [INVARIANT]
    Inputs:       A GATE-FAIL FidelityVerdict (call-edge recall < 0.85) and an `ungated`
                  verdict over a NON-gate-strength corpus; the benchmark-eligibility
                  accessor.
    Outputs:      A `front-end-blocked` (GATE-FAIL) / `corpus-not-authoritative`
                  (ungated) label; NO Algorithm-2 recall number for the failing language.
    Pass criteria: The owner-side reporting path emits exactly one of {GATE-PASS,
                  GATE-FAIL, ungated} per language and STRUCTURALLY cannot emit an
                  Algorithm-2 recall number for a non-gate-passing (class, language)
                  pair — the accessor raises BenchmarkEligibilityError (INV-6).
    Frequency:    every CI run
    Hard gate?:   yes — INV-6 (per-language honesty; owner-side discharge).
    """
    from services.control_plane import BenchmarkEligibilityError, evaluate_fidelity

    corpus = _SyntheticCorpus(call_gt=100, pdg_gt=100)
    fail_extraction = _SyntheticExtraction(call_tp=60, call_fp=2, call_fn=40, pdg_tp=90, pdg_fn=10)
    fail_verdict = evaluate_fidelity(
        "go", Path("/unused"), corpus=corpus, extraction=fail_extraction
    )
    assert fail_verdict.overall in {"GATE-FAIL", "ungated"}
    assert fail_verdict.overall != "GATE-PASS"
    with pytest.raises(BenchmarkEligibilityError):
        fail_verdict.benchmark_eligible_recall()

    # A non-gate-strength corpus likewise yields no constructible pass + no recall.
    ungated_corpus = _SyntheticCorpus(gate_strength=False, call_gt=100, pdg_gt=100)
    ungated_verdict = evaluate_fidelity(
        "java", Path("/unused"), corpus=ungated_corpus, extraction=_passing_extraction()
    )
    assert ungated_verdict.overall == "ungated"
    assert ungated_verdict.gate_passed is False
    with pytest.raises(BenchmarkEligibilityError):
        ungated_verdict.benchmark_eligible_recall()


@pytest.mark.unit
def test_cp06_in_repo_v010_scaffolds_are_not_gate_passing() -> None:
    """The honest CURRENT state: the in-repo v0.1.0 corpora yield NOT-gate-passing
    verdicts for java + python (requirement (4) — the anti-vacuity fixture).

    Test id:      TST-AC-CP-06b (current-state leg)
    Kind tag:     [UNIT]
    Pass criteria: Over the real tests/corpora/cpg_fidelity/{java,python} v0.1.0
                  scaffolds (non-gate-strength), evaluate_fidelity returns overall ==
                  "ungated" and gate_passed is False — NO PASS is constructible from a
                  non-authoritative corpus, and NO toolchain is invoked (the ungated
                  short-circuit fires before extraction).
    """
    from services.control_plane import evaluate_fidelity, lockfile_corpus_port

    corpus_root = Path(__file__).resolve().parents[1] / "corpora" / "cpg_fidelity"
    for language in ("java", "python"):
        corpus_path = corpus_root / language
        assert corpus_path.is_dir(), f"missing in-repo corpus scaffold for {language}"
        port = lockfile_corpus_port(corpus_path)
        assert port.gate_strength is False
        # extraction omitted: the ungated short-circuit must not reach the toolchain.
        verdict = evaluate_fidelity(language, corpus_path, corpus=port)  # type: ignore[arg-type]
        assert verdict.overall == "ungated"
        assert verdict.gate_passed is False
        assert verdict.corpus_version == "0.1.0"


# ---------------------------------------------------------------------------
# CLAR-CP-06-02 / CLAR-DEPLOY-22 — production env_digest enforcement
# (production_env_digest / enforce_production_env / GATE_IMAGE)
# ---------------------------------------------------------------------------
#
# CLAR-CP-06-02 (RESOLVED, WBS §17): CMP-CP-06 hard-enforces that the gate's
# env_digest matches the registered production env_digest, with a
# record-and-warn bootstrap window until the first active entry is
# registered (CLAR-DEPLOY-22's workers/env_digest_history.json). These tests
# are fully hermetic — no docker, no ECR — driven from tmp_path registry
# fixtures.

_REG_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64


def _registry_doc(*, image: str = "scanipy-snapshot", digest: str = _REG_DIGEST) -> dict:
    return {
        "schema_version": 1,
        "entries": [
            {
                "image": image,
                "env_digest": digest,
                "tag": "v0.1.2",
                "git_sha": "c" * 40,
                "signed_at": "2026-07-15T00:00:00Z",
                "status": "active",
                "note": "",
            }
        ],
    }


@pytest.mark.unit
def test_gate_image_is_pinned_to_the_snapshot_worker() -> None:
    """DOC-CMP-CP-06 §4.1: 'the gate harness must re-use the same worker image
    that production scans use' — that is the SNAP-05 snapshot worker, never
    scanipy-detector (comparing against the detector image would poison the
    gate — CLAR-DEPLOY-22 risk note)."""
    from services.control_plane import GATE_IMAGE

    assert GATE_IMAGE == "scanipy-snapshot"


@pytest.mark.unit
def test_production_env_digest_none_when_registry_file_absent(tmp_path: Path) -> None:
    """Pre-bootstrap record-and-warn: no registry file at all."""
    from services.control_plane import production_env_digest

    assert production_env_digest(tmp_path / "nope.json") is None


@pytest.mark.unit
def test_production_env_digest_none_when_no_active_entry(tmp_path: Path) -> None:
    """Pre-bootstrap record-and-warn: registry exists but every row is void."""
    from services.control_plane import production_env_digest

    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "image": "scanipy-snapshot",
                        "env_digest": _REG_DIGEST,
                        "tag": "v0.1.0",
                        "git_sha": "c" * 40,
                        "signed_at": "2026-07-15T00:00:00Z",
                        "status": "void",
                        "note": "never deployed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert production_env_digest(path) is None


@pytest.mark.unit
def test_production_env_digest_returns_the_active_digest(tmp_path: Path) -> None:
    from services.control_plane import production_env_digest

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry_doc()), encoding="utf-8")
    assert production_env_digest(path) == _REG_DIGEST


@pytest.mark.unit
def test_production_env_digest_raises_on_malformed_registry(tmp_path: Path) -> None:
    from services.control_plane import production_env_digest
    from workers.build.env_digest_registry import EnvDigestRegistryError

    path = tmp_path / "registry.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(EnvDigestRegistryError):
        production_env_digest(path)


@pytest.mark.unit
def test_enforce_production_env_warns_and_passes_when_registry_absent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from services.control_plane import enforce_production_env

    with caplog.at_level(logging.WARNING):
        enforce_production_env(_REG_DIGEST, tmp_path / "nope.json")
    assert any("record-and-warn" in r.message for r in caplog.records)


@pytest.mark.unit
def test_enforce_production_env_passes_when_digest_matches(tmp_path: Path) -> None:
    from services.control_plane import enforce_production_env

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry_doc()), encoding="utf-8")
    enforce_production_env(_REG_DIGEST, path)  # must not raise


@pytest.mark.unit
def test_enforce_production_env_raises_on_mismatch(tmp_path: Path) -> None:
    from services.control_plane import ProductionEnvMismatch, enforce_production_env

    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry_doc()), encoding="utf-8")
    with pytest.raises(ProductionEnvMismatch, match=f"{_OTHER_DIGEST} != {_REG_DIGEST}"):
        enforce_production_env(_OTHER_DIGEST, path)


@pytest.mark.unit
def test_enforce_production_env_compares_against_gate_image_not_other_images(
    tmp_path: Path,
) -> None:
    """A registry with only a scanipy-detector active entry must still
    record-and-warn (not silently pass) for the scanipy-snapshot gate image —
    proves the two images are never conflated (CLAR-DEPLOY-22 poison-gate risk)."""
    from services.control_plane import enforce_production_env

    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(_registry_doc(image="scanipy-detector", digest=_OTHER_DIGEST)),
        encoding="utf-8",
    )
    # No active scanipy-snapshot entry exists, so this is still the
    # pre-bootstrap window for the gate image and must not raise.
    enforce_production_env(_REG_DIGEST, path)

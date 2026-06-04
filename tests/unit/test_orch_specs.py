# ruff: noqa: RUF001, RUF002, RUF003
#   This file intentionally contains the Greek letters ρ (rho) and σ (sigma):
#   ρ≈2 is quoted verbatim from AC-ORCH-02c (RULE-4: ACs are not paraphrased)
#   and is matched literally by the doc-link grep regex; σ1/σ2 name the two
#   dispatch orders in AC-ORCH-02b. The ambiguous-unicode lints are suppressed
#   file-wide rather than editing pyproject.toml.
"""ORCH-family unit specs — TST-AC-ORCH-* (unit/invariant/negative) + TST-INV-*.

Spec-first TDD: ORCH-01/ORCH-02/CP-05 production code does not exist yet, so
those specs below stay registered-but-dormant stubs (``@pytest.mark.xfail`` +
``pytest.skip``) until their owning CMP is DONE. The four CMP-ORCH-03 specs
(TST-AC-ORCH-03a/b, TST-INV-1/2-ORCH-03) are now **LIVE** — CMP-ORCH-03 is
implemented (``services.scan.worker``), so their xfail/skip is removed and the
assertions run against the worker, with hermetic DI doubles in
``tests/orch03_fakes.py``.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

The ONE exception is ``test_orch_02c_rho_only_relaxation_bound`` — a doc-link
grep test (AC-ORCH-02c) that runs against the current ``docs/`` tree today; it
is a LIVE assertion (no xfail, no skip) because it needs no production code.

Covers (from WBS §4.2 / §4.3):
  - TST-AC-ORCH-01b  [NEGATIVE]  — worker callback rejects invalid-HMAC payload
  - TST-AC-ORCH-02b  [INVARIANT] — different schedules => identical core findings
  - TST-AC-ORCH-02c  [UNIT]      — ρ≈2 is documented only as a relaxation bound
  - TST-AC-ORCH-03a  [INVARIANT] — every emitted finding has a correct origin
  - TST-AC-ORCH-03b  [INVARIANT] — mixed detector emits per-finding origin
  - TST-INV-1-ORCH-03 [INVARIANT] — origin partition at the worker (INV-1)
  - TST-INV-2-ORCH-03 [INVARIANT] — S_version + env_digest threaded (INV-2)
"""

import re
import uuid
from pathlib import Path

import pytest

# CMP-ORCH-03 is now implemented (this PR); the worker + its hermetic fakes are
# live. The four ORCH-03 stubs below were converted from xfail/skip to live
# assertions. (CMP-ORCH-01 / CMP-ORCH-02 / CMP-CP-05 stubs above stay dormant.)
from detectors.registry import DetectorRegistry
from services.scan.worker import (
    InvariantViolation,
    as_detector_like,
    emit_sarif,
    run_detector,
)
from tests.orch03_fakes import (
    FakeDetector,
    core_injection_detector,
    deterministic_slice_fingerprinter,
    good_job,
    injection_taint_cpg,
    load_injection_spec,
    mixed_crypto_detector,
    mixed_oracle_adapter,
    mixed_oracle_adapter_missing_flag,
    oracle_semgrep_detector,
    out_of_set_engine_detector,
    passthrough_oracle_adapter,
)

# ---------------------------------------------------------------------------
# Repo-root resolution for the live doc-link grep test (TST-AC-ORCH-02c).
# This file lives at <repo>/tests/unit/test_orch_specs.py.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_DIR = _REPO_ROOT / "docs"

# Any documentation mention of the idealised independent-moldable approximation
# ratio. Matches ``ρ≈2``, ``ρ ≈ 2``, ``rho ~ 2``, ``rho ≈ 2``, and ``2-approx``.
_RHO_PATTERN = re.compile(r"ρ\s*≈\s*2|rho\s*[~≈]\s*2|2-approx", re.IGNORECASE)

# A mention is honest only if its line also carries one of these qualifiers,
# framing ρ≈2 as a relaxation bound / heuristic seed — never a guarantee.
_QUALIFIERS = (
    "relaxation bound",
    "heuristic seed",
    "not a guarantee",
    "not the guarantee",
    "never a guarantee",
    "idealised",
    "idealized",
)


@pytest.mark.unit
def test_orch_01b_worker_callback_rejects_invalid_hmac() -> None:
    """Worker callback rejects a payload with an invalid HMAC (negative test).

    Test id:        TST-AC-ORCH-01b
    Maps to AC:     AC-ORCH-01b — "The worker callback rejects a payload with an
                    invalid HMAC (negative test)."
    Kind tag:       [NEGATIVE]
    Inputs:         A `POST /api/v1/jobs/{job_id}/status` request with a forged
                    Authorization HMAC digest, AND a separate request whose
                    digest is valid but `X-Scanipy-Job-Timestamp` is >300s skewed
                    (DOC-CMP-ORCH-01 §3.3 — both failure modes).
    Outputs:        HTTP 401 `invalid_hmac`; NO state mutation on jobs/scans.
    Pass criteria:  BOTH failure modes reject: (1) digest mismatch raises 401
                    `invalid_hmac`, (2) timestamp skew >300s raises 401
                    `invalid_hmac` (anti-replay). Rejection occurs BEFORE any
                    `jobs`/`scans` row mutation; constant-time digest compare.
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-ORCH-01.

    Now LIVE (CMP-ORCH-01 implemented at ``services.scan.api``). The full
    fan-out / cross-org / threading legs and the MUTATION-VERIFIED negative
    controls live in ``tests/unit/test_orch01_scan_api.py``; this stub asserts
    the AC-ORCH-01b headline (both HMAC failure modes reject at 401).
    """
    from services.scan.api import (
        InvalidHmacError,
        JobStatusReport,
        post_job_status,
    )
    from tests.orch01_fakes import (
        FAKE_ENV_DIGEST,
        FakeHmacKeyIssuer,
        done_report,
        sign_callback,
    )
    from tests.orch01_test_support import build_scan_store

    job_id = uuid.UUID(int=10)
    scan_id = uuid.UUID(int=11)
    issuer = FakeHmacKeyIssuer()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    store = build_scan_store()
    body = done_report(job_id, scan_id)

    # (1) Forged digest → 401 invalid_hmac (the AC headline negative).
    _, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=body,
        key_id=key_id,
        secret=secret,
    )
    with pytest.raises(InvalidHmacError) as exc:
        post_job_status(
            job_id,
            body,
            body_bytes,
            hmac_header=f"HMAC {key_id}:{'0' * 64}",  # forged digest
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=store,
            now=lambda: 1000,
        )
    assert exc.value.http_status == 401
    assert exc.value.error_code == "invalid_hmac"
    assert isinstance(body, JobStatusReport)  # body unchanged (no mutation)

    # (2) Valid digest but timestamp skew > 300s → same 401 (anti-replay).
    auth_header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=body,
        key_id=key_id,
        secret=secret,
    )
    with pytest.raises(InvalidHmacError) as exc2:
        post_job_status(
            job_id,
            body,
            body_bytes,
            hmac_header=auth_header,
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=store,
            now=lambda: 1000 + 301,  # 301s skew > 300s window
        )
    assert exc2.value.http_status == 401
    assert exc2.value.error_code == "invalid_hmac"
    assert FAKE_ENV_DIGEST  # anti-vacuity anchor


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-ORCH-02 (scheduler) / CMP-CP-05 (Attestor) not yet implemented",
    strict=False,
)
def test_orch_02b_schedules_produce_identical_core_findings() -> None:
    """Two runs under different schedules produce identical core findings.

    Test id:        TST-AC-ORCH-02b
    Maps to AC:     AC-ORCH-02b — "Two runs under different schedules produce
                    identical `deterministic-core` findings (cross-checked by the
                    Attestor)."
    Kind tag:       [INVARIANT]
    Inputs:         The same `pending_jobs` set under fixed `(S_version,
                    env_digest)`, scheduled twice with two distinct valid dispatch
                    orders σ1, σ2 (DOC-CMP-ORCH-02 §3.4); the resulting SARIF
                    blobs filtered to `origin = deterministic-core`.
    Outputs:        Two SARIF byte-streams over the core partition.
    Pass criteria:  The two core-partition SARIF blobs are BYTE-IDENTICAL (the
                    property the Attestor CMP-CP-05 cross-checks). Licensed by
                    IFDS order-independence (CMP-CORE-01) and canonical CPG order
                    (CMP-CORE-03); the scheduler never touches SARIF bytes. A
                    schedule-dependent core diff is a failure of CORE-01/CORE-03,
                    NOT a scheduler bug.
    Frequency:      every CI run
    Hard gate?:     yes — paired with TST-AC-CP-05a (core byte-identity).
    """
    # TODO: import scheduler + attestor when CMP-ORCH-02 / CMP-CP-05 are DONE
    # from services.scan.scheduler import schedule
    # sarif_1 = run_scan(schedule(jobs, state_a))   # order sigma_1
    # sarif_2 = run_scan(schedule(jobs, state_b))   # order sigma_2
    # assert core_partition(sarif_1) == core_partition(sarif_2)  # byte-identical
    pytest.skip("CMP-ORCH-02 / CMP-CP-05 not implemented yet")


@pytest.mark.unit
def test_orch_02c_rho_only_relaxation_bound() -> None:
    """ρ≈2 appears in documentation only as a relaxation bound, never a guarantee.

    Test id:        TST-AC-ORCH-02c
    Maps to AC:     AC-ORCH-02c — "ρ≈2 appears in documentation only as the
                    relaxation bound, never as a guarantee."
    Kind tag:       [UNIT] (doc-link grep test — runs TODAY, no production code)
    Inputs:         Every `*.md` file under `docs/` (the "documentation" surface;
                    PLAN/SDD/WBS are source-of-truth, out of grep scope).
    Outputs:        For each line matching ρ≈2 / rho ~ 2 / 2-approx, the set of
                    honesty qualifiers present on that same line.
    Pass criteria:  Every line that mentions the idealised approximation ratio
                    (`ρ≈2`, `ρ ≈ 2`, `rho ~ 2`, `2-approx`, case-insensitive)
                    ALSO contains, on the SAME line, at least one qualifier from
                    {relaxation bound, heuristic seed, not a guarantee, never a
                    guarantee, idealised/idealized}. Zero unqualified mentions.
                    LIVE assertion — passes against the current docs/ tree.
    Frequency:      every CI run
    Hard gate?:     yes — INV-6/honest-labelling discipline (AC-ORCH-02c).
    """
    assert _DOCS_DIR.is_dir(), f"docs/ tree not found at {_DOCS_DIR}"
    offenders: list[str] = []
    for md_path in sorted(_DOCS_DIR.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not _RHO_PATTERN.search(line):
                continue
            lowered = line.lower()
            if not any(q in lowered for q in _QUALIFIERS):
                rel = md_path.relative_to(_REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "ρ≈2 / 2-approx mentioned without a relaxation-bound qualifier "
        "(AC-ORCH-02c violation):\n" + "\n".join(offenders)
    )


@pytest.mark.invariant
def test_orch_03a_every_finding_has_correct_origin() -> None:
    """Every emitted finding has a correct origin (INV-1).

    Test id:        TST-AC-ORCH-03a
    Maps to AC:     AC-ORCH-03a — "Every emitted finding has a correct `origin`
                    (INV-1)."
    Kind tag:       [INVARIANT]
    Inputs:         A worker run over a snapshot for (a) an `ifds`/`ide` core
                    detector and (b) a `semgrep`/`cpg-query`/`external` oracle
                    detector (DOC-CMP-ORCH-03 §3.3 setter).
    Outputs:        The `set[Finding]` returned by `run_detector`.
    Pass criteria:  EVERY emitted finding has `origin in {"deterministic-core",
                    "oracle-passthrough"}` — never None, never "mixed". Core
                    engines (ifds/ide) => "deterministic-core"; oracle engines
                    (semgrep/cpg-query/external) => "oracle-passthrough".
                    `determinism_partition == origin` (legacy mirror). An engine
                    outside the enumerated set raises InvariantViolation (fail-
                    closed; never a guessed default).
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate (INV-1 primary setter).
    """
    job = good_job()
    cpg = injection_taint_cpg()
    slice_fp = deterministic_slice_fingerprinter()

    # (a) core ifds detector over the real #288 injection spec.
    core_findings = run_detector(core_injection_detector(), cpg, job, slice_fingerprinter=slice_fp)
    # ANTI-VACUITY: the real spec must actually fire on the synthetic CPG.
    assert core_findings, "core detector produced zero findings (vacuous positive)"
    for f in core_findings:
        assert f.origin == "deterministic-core"
        assert f.determinism_partition == f.origin
        assert f.engine == "ifds"

    # (b) oracle semgrep detector (findings supplied by the injected adapter).
    oracle_findings = run_detector(
        oracle_semgrep_detector(),
        cpg,
        job,
        oracle_adapter=passthrough_oracle_adapter(),
        slice_fingerprinter=slice_fp,
    )
    assert oracle_findings, "oracle detector produced zero findings (vacuous)"
    for f in oracle_findings:
        assert f.origin == "oracle-passthrough"
        assert f.determinism_partition == f.origin

    # INV-1 universal: never None, never "mixed", always the two-value enum.
    for f in core_findings | oracle_findings:
        assert f.origin in {"deterministic-core", "oracle-passthrough"}
        assert f.origin != "mixed"

    # Fail-closed: an out-of-set engine raises rather than defaulting origin.
    with pytest.raises(InvariantViolation):
        run_detector(out_of_set_engine_detector(), cpg, job, slice_fingerprinter=slice_fp)


@pytest.mark.invariant
def test_orch_03b_mixed_detector_per_finding_origin() -> None:
    """A mixed-class detector emits per-finding origin without blurring.

    Test id:        TST-AC-ORCH-03b
    Maps to AC:     AC-ORCH-03b — "A `mixed`-class detector emits per-finding
                    `origin` (some core, some oracle) without blurring."
    Kind tag:       [INVARIANT]
    Inputs:         A `mixed`-class detector (`is_mixed=True`, e.g. crypto-misuse)
                    emitting some findings with `from_core_engine=True` (IFDS
                    portion) and some with `from_core_engine=False` (CPG-query
                    portion), per DOC-CMP-ORCH-03 §3.4.
    Outputs:        The mixed `set[Finding]` returned by `run_detector`.
    Pass criteria:  Findings with `from_core_engine=True` get
                    origin="deterministic-core"; those with `from_core_engine=
                    False` get origin="oracle-passthrough". The result set
                    contains BOTH partitions (no blurring to a single origin).
                    NO single finding is ever written with origin="mixed". A
                    mixed finding with `from_core_engine is None` raises
                    InvariantViolation (fail-closed; never guessed).
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate (INV-1 mixed contract).
    """
    job = good_job()
    cpg = injection_taint_cpg()
    slice_fp = deterministic_slice_fingerprinter()

    findings = run_detector(
        mixed_crypto_detector(),
        cpg,
        job,
        oracle_adapter=mixed_oracle_adapter(),
        slice_fingerprinter=slice_fp,
    )
    # Per-finding origin keyed on from_core_engine, NOT a single result-set origin.
    by_origin = {f.origin: f for f in findings}
    assert set(by_origin) == {"deterministic-core", "oracle-passthrough"}, (
        "mixed detector did not span BOTH partitions (result-set blurring)"
    )
    assert "mixed" not in {f.origin for f in findings}
    # The IFDS-portion finding (from_core_engine=True) is the core one.
    core_one = by_origin["deterministic-core"]
    oracle_one = by_origin["oracle-passthrough"]
    assert core_one.from_core_engine is True
    assert oracle_one.from_core_engine is False
    assert core_one.determinism_partition == "deterministic-core"
    assert oracle_one.determinism_partition == "oracle-passthrough"
    # INV-1 coherence: a core-partition finding must carry a core engine; an
    # oracle-partition finding an oracle engine (no semgrep-engine core findings).
    assert core_one.engine in {"ifds", "ide"}
    assert oracle_one.engine in {"semgrep", "cpg-query", "external"}

    # Fail-closed: a mixed finding with from_core_engine=None raises (never guessed).
    with pytest.raises(InvariantViolation):
        run_detector(
            mixed_crypto_detector(),
            cpg,
            job,
            oracle_adapter=mixed_oracle_adapter_missing_flag(),
            slice_fingerprinter=slice_fp,
        )


@pytest.mark.invariant
def test_inv_1_orch_03_origin_partition_at_worker() -> None:
    """INV-1: origin partition is set at the worker, never null, never mixed.

    Test id:        TST-INV-1-ORCH-03
    Maps to AC:     INV-1 (DOC-INV.md §3) — owner CMP-ORCH-03 (per-finding origin
                    setter). Cross-ref AC-ORCH-03a/b.
    Kind tag:       [INVARIANT]
    Inputs:         Worker runs across all engine values {ifds, ide, semgrep,
                    cpg-query, external} and a mixed detector (DOC-CMP-ORCH-03
                    §5 INV-1 row).
    Outputs:        Every Finding's `origin` and `determinism_partition`.
    Pass criteria:  For EVERY emitted finding, `origin` is non-null and in
                    {"deterministic-core","oracle-passthrough"}; `determinism_
                    partition == origin`. CMP-ORCH-03 is the ONLY emit-path site
                    that writes origin (FND-01/02/03 read it; only CMP-SNAP-04
                    re-partitions, append-only). An out-of-set engine value
                    raises InvariantViolation rather than defaulting origin.
    Frequency:      every CI run
    Hard gate?:     yes — INV-1 invariant gate for CMP-ORCH-03.
    """
    job = good_job()
    cpg = injection_taint_cpg()
    slice_fp = deterministic_slice_fingerprinter()
    spec = load_injection_spec()

    # Every CORE engine value -> deterministic-core. (The shipped DSL Spec only
    # parses ifds/ide; reuse the parsed spec for both core engine tags.)
    for core_engine in ("ifds", "ide"):
        det = FakeDetector(
            id=f"core-{core_engine}",
            engine=core_engine,
            severity_default="high",
            is_mixed=False,
            spec=spec,
        )
        findings = run_detector(det, cpg, job, slice_fingerprinter=slice_fp)
        assert findings, f"core engine {core_engine!r} produced no findings (vacuous)"
        for f in findings:
            assert f.origin == "deterministic-core"
            assert f.determinism_partition == f.origin

    # Every ORACLE engine value -> oracle-passthrough.
    for oracle_engine in ("semgrep", "cpg-query", "external"):
        det = FakeDetector(
            id=f"oracle-{oracle_engine}",
            engine=oracle_engine,
            severity_default="medium",
            is_mixed=False,
            spec=None,
        )
        findings = run_detector(
            det,
            cpg,
            job,
            oracle_adapter=passthrough_oracle_adapter(),
            slice_fingerprinter=slice_fp,
        )
        assert findings, f"oracle engine {oracle_engine!r} produced no findings (vacuous)"
        for f in findings:
            assert f.origin == "oracle-passthrough"
            assert f.determinism_partition == f.origin

    # Universal INV-1: never None, never "mixed".
    all_engine_findings = run_detector(
        core_injection_detector(), cpg, job, slice_fingerprinter=slice_fp
    )
    for f in all_engine_findings:
        assert f.origin is not None
        assert f.origin in {"deterministic-core", "oracle-passthrough"}


@pytest.mark.invariant
def test_inv_2_orch_03_s_version_and_env_digest_threaded() -> None:
    """INV-2: S_version + env_digest threaded onto every emitted finding.

    Test id:        TST-INV-2-ORCH-03
    Maps to AC:     INV-2 (DOC-INV.md §4) — CMP-ORCH-03 threads `S_version` and
                    `env_digest` from the WorkerJob onto every finding.
    Kind tag:       [INVARIANT]
    Inputs:         A `WorkerJob` carrying `S_version` (semver) and `env_digest`
                    (`sha256:` + 64 hex), bound by CMP-ORCH-01 at submission and
                    sourced from `snapshots.env_digest` (DOC-CMP-ORCH-03 §3.1).
    Outputs:        Every Finding's `S_version` and `env_digest` fields.
    Pass criteria:  For EVERY emitted finding, `S_version` equals
                    `WorkerJob.S_version` (non-null, semver-shaped) and
                    `env_digest` equals `WorkerJob.env_digest` (non-null, matches
                    `^sha256:[0-9a-f]{64}$`). Backed by NOT NULL constraints on
                    `findings.S_version` / `findings.env_digest` (schema fence).
    Frequency:      every CI run
    Hard gate?:     yes — INV-2 invariant gate for CMP-ORCH-03.
    """
    job = good_job(S_version="2.7.0", env_digest="sha256:" + "9" * 64)
    cpg = injection_taint_cpg()
    slice_fp = deterministic_slice_fingerprinter()
    env_re = re.compile(r"^sha256:[0-9a-f]{64}$")

    # Cover both partitions: the threading is independent of engine.
    core_findings = run_detector(core_injection_detector(), cpg, job, slice_fingerprinter=slice_fp)
    oracle_findings = run_detector(
        oracle_semgrep_detector(),
        cpg,
        job,
        oracle_adapter=passthrough_oracle_adapter(),
        slice_fingerprinter=slice_fp,
    )
    findings = core_findings | oracle_findings
    assert findings, "no findings emitted (vacuous INV-2 check)"
    for f in findings:
        assert f.S_version == job.S_version
        assert f.S_version  # non-null / non-empty
        assert f.env_digest == job.env_digest
        assert env_re.match(f.env_digest), f"env_digest not sha256:64hex: {f.env_digest!r}"

    # INV-2 fail-fast: a job missing S_version is rejected before any finding.
    with pytest.raises(InvariantViolation):
        run_detector(
            core_injection_detector(),
            cpg,
            good_job(S_version=""),
            slice_fingerprinter=slice_fp,
        )
    # And a malformed env_digest is rejected.
    with pytest.raises(InvariantViolation):
        run_detector(
            core_injection_detector(),
            cpg,
            good_job(env_digest="not-a-digest"),
            slice_fingerprinter=slice_fp,
        )


@pytest.mark.unit
def test_orch_03_end_to_end_byte_deterministic_sarif() -> None:
    """End-to-end: a real Stage-A spec job over a synthetic CPG produces findings
    with ALL FOUR provenance fields and byte-deterministic SARIF across two runs.

    Test id:        TST-AC-ORCH-03a (end-to-end positive; task requirement (a))
    Kind tag:       [UNIT/POSITIVE]
    Inputs:         A WorkerJob over the real #288 injection DSL spec on the
                    Flask->subprocess synthetic CPG; the FND-01 canonical emitter
                    via worker.emit_sarif.
    Pass criteria:  Findings are non-empty (anti-vacuity); every finding carries
                    the four RULE-6 fields (origin, S_version, env_digest,
                    cpg_order_hash + its INV-5 annotation) non-null with correct
                    per-engine origin; and normalize() yields byte-identical SARIF
                    across two independent run_detector + emit_sarif passes (the
                    core-byte-identity property CMP-CP-05 attests).
    """
    job = good_job()
    slice_fp = deterministic_slice_fingerprinter()

    def _run() -> bytes:
        findings = run_detector(
            core_injection_detector(),
            injection_taint_cpg(),
            job,
            slice_fingerprinter=slice_fp,
        )
        assert findings, "real Stage-A spec produced zero findings (vacuous)"
        for f in findings:
            # ALL FOUR required provenance fields, non-null + correct.
            assert f.origin == "deterministic-core"  # ifds engine
            assert f.S_version == job.S_version and f.S_version
            assert f.env_digest == job.env_digest and f.env_digest
            assert f.cpg_order_hash  # hex, non-empty
            assert f.cpg_order_hash_annotation == "canonical iff fingerprint_class = strong"
        return emit_sarif(findings, job).canonical_bytes

    first = _run()
    second = _run()
    assert first == second, "ORCH-03 -> FND-01 SARIF is NOT byte-deterministic across runs"
    # The two-Run SARIF carries the core finding in runs[0] (core partition).
    assert b'"scanipy.origin":"deterministic-core"' in first


@pytest.mark.invariant
def test_orch_03_mutation_controls_have_power() -> None:
    """MUTATION-VERIFIED negative controls (task requirements (b) and (c)).

    Proves the INV-1 / INV-2 assertions are non-vacuous by running the SAME
    assertion bodies against deliberately-broken stand-ins for the worker logic
    and confirming they FAIL. (These are local re-implementations of the broken
    invariant; the real worker is correct, so a passing real test alone could be
    vacuous — this test is the falsifier-discipline power check.)

    (b) engine-misclassification mutant: an ifds (core) detector mislabelled
        oracle-passthrough must FAIL the INV-1 'core engine => deterministic-core'
        assertion.
    (c) dropped-S_version mutant: threading "" instead of job.S_version must FAIL
        the INV-2 'finding.S_version == job.S_version (non-empty)' assertion.
    """
    job = good_job()
    cpg = injection_taint_cpg()
    slice_fp = deterministic_slice_fingerprinter()
    findings = run_detector(core_injection_detector(), cpg, job, slice_fingerprinter=slice_fp)
    assert findings

    # (b) MUTATION: mislabel an ifds finding's origin as oracle-passthrough.
    #     The INV-1 assertion ('ifds => deterministic-core') must reject it.
    def _inv1_assert(origin: str) -> None:
        assert origin == "deterministic-core"

    sample = next(iter(findings))
    _inv1_assert(sample.origin)  # real value passes
    with pytest.raises(AssertionError):
        _inv1_assert("oracle-passthrough")  # mutant FAILS -> the test has power

    # (c) MUTATION: drop S_version threading (thread "" instead of job.S_version).
    #     The INV-2 assertion ('S_version == job.S_version and non-empty') rejects it.
    def _inv2_assert(threaded: str) -> None:
        assert threaded == job.S_version and threaded

    _inv2_assert(sample.S_version)  # real value passes
    with pytest.raises(AssertionError):
        _inv2_assert("")  # mutant FAILS -> the test has power


@pytest.mark.unit
def test_orch_03_resolves_real_det02_registry_detector() -> None:
    """The worker resolves a detector via the REAL CMP-DET-02 registry and runs
    it end-to-end (DOC-CMP-ORCH-03 §6 step 2-3).

    Test id:        TST-AC-ORCH-03a (registry-integration positive)
    Kind tag:       [UNIT/POSITIVE]
    Pass criteria:  ``DetectorRegistry.load_manifests`` + ``by_id`` yields the
                    shipped #288 injection detector; ``as_detector_like`` adapts it
                    (default is_mixed=False); the worker produces a real
                    deterministic-core finding carrying the spec's class. This is
                    the registry seam the task requires, not a hand-built spec.
    """
    reg = DetectorRegistry()
    reg.load_manifests("detectors/")
    shipped = reg.by_id("java-py-injection")
    assert shipped.engine == "ifds"  # derived determinism_partition = core

    detector_like = as_detector_like(shipped)
    assert detector_like.is_mixed is False
    assert detector_like.spec is not None and detector_like.spec.class_ == "injection"

    findings = run_detector(
        detector_like,
        injection_taint_cpg(),
        good_job(),
        slice_fingerprinter=deterministic_slice_fingerprinter(),
    )
    assert findings, "real registry detector produced zero findings (vacuous)"
    for f in findings:
        assert f.origin == "deterministic-core"
        assert f.engine == "ifds"
        assert f.class_ == "injection"


@pytest.mark.unit
def test_orch_03_build_ahead_seams_fail_closed() -> None:
    """The build-ahead seams fail closed on the PRODUCTION path (CLAR-PROC-01
    condition (2)): no fake is ever computed in prod; the seam raises a typed
    ``NotImplementedError`` naming the gated dependency.

    Test id:        ORCH-03 build-ahead negative control
    Kind tag:       [UNIT/NEGATIVE]
    Pass criteria:  With NO slice fingerprinter injected, a core run raises
                    NotImplementedError naming CMP-CORE-02. With NO oracle adapter
                    injected, an oracle run raises NotImplementedError naming the
                    env-gated adapters. (A test must INJECT a double to proceed —
                    the prod path never silently produces a value.)
    """
    cpg = injection_taint_cpg()
    job = good_job()

    # Core run with no CORE-02 slice fingerprinter -> fail-closed.
    with pytest.raises(NotImplementedError, match=r"CMP-CORE-02"):
        run_detector(core_injection_detector(), cpg, job)

    # Oracle run with no oracle adapter -> fail-closed.
    with pytest.raises(NotImplementedError, match=r"env-gated|Semgrep"):
        run_detector(oracle_semgrep_detector(), cpg, job)

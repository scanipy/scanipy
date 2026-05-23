# ruff: noqa: RUF001, RUF002, RUF003
#   This file intentionally contains the Greek letters ρ (rho) and σ (sigma):
#   ρ≈2 is quoted verbatim from AC-ORCH-02c (RULE-4: ACs are not paraphrased)
#   and is matched literally by the doc-link grep regex; σ1/σ2 name the two
#   dispatch orders in AC-ORCH-02b. The ambiguous-unicode lints are suppressed
#   file-wide rather than editing pyproject.toml.
"""ORCH-family unit specs — TST-AC-ORCH-* (unit/invariant/negative) + TST-INV-*.

Spec-first TDD: production code for the Orchestration subsystem does not exist
yet, so every component-dependent spec below is a registered-but-dormant stub.
Each carries an ``@pytest.mark.xfail(strict=False)`` so the suite collects and
runs without blocking; the body calls ``pytest.skip`` until the owning CMP is
DONE, at which point the skip is removed and the stubbed assertion goes live.

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
from pathlib import Path

import pytest

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
@pytest.mark.xfail(
    reason="CMP-ORCH-01 (Scan API) not yet implemented",
    strict=False,
)
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
    """
    # TODO: import the scan API from services.scan.api when CMP-ORCH-01 is DONE
    # from services.scan.api import post_job_status, InvalidHmacError
    # with pytest.raises(InvalidHmacError) as exc:  # forged digest
    #     post_job_status(job_id, body, hmac_header="HMAC k1:deadbeef", ...)
    # assert exc.value.http_status == 401 and exc.value.error_code == "invalid_hmac"
    # # second case: valid digest, timestamp skew > 300s -> same rejection
    pytest.skip("CMP-ORCH-01 not implemented yet")


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
@pytest.mark.xfail(
    reason="CMP-ORCH-03 (detector-agnostic worker) not yet implemented",
    strict=False,
)
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
    # TODO: import the worker from tools.scan.worker.worker when CMP-ORCH-03 is DONE
    # from tools.scan.worker.worker import run_detector
    # for f in run_detector(core_detector, snapshot, spec_set):
    #     assert f.origin == "deterministic-core" and f.determinism_partition == f.origin
    # for f in run_detector(oracle_detector, snapshot, spec_set):
    #     assert f.origin == "oracle-passthrough"
    pytest.skip("CMP-ORCH-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-ORCH-03 (detector-agnostic worker) not yet implemented",
    strict=False,
)
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
    # TODO: import the worker from tools.scan.worker.worker when CMP-ORCH-03 is DONE
    # findings = run_detector(mixed_detector, snapshot, spec_set)
    # origins = {f.origin for f in findings}
    # assert origins == {"deterministic-core", "oracle-passthrough"}
    # assert "mixed" not in origins
    # with pytest.raises(InvariantViolation):  # from_core_engine None on mixed
    #     run_detector(mixed_detector_missing_flag, snapshot, spec_set)
    pytest.skip("CMP-ORCH-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-ORCH-03 (detector-agnostic worker) not yet implemented",
    strict=False,
)
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
    # TODO: import the worker from tools.scan.worker.worker when CMP-ORCH-03 is DONE
    # for f in run_detector(any_detector, snapshot, spec_set):
    #     assert f.origin in {"deterministic-core", "oracle-passthrough"}
    #     assert f.determinism_partition == f.origin
    pytest.skip("CMP-ORCH-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-ORCH-03 (detector-agnostic worker) not yet implemented",
    strict=False,
)
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
    # TODO: import the worker from tools.scan.worker.worker when CMP-ORCH-03 is DONE
    # job = WorkerJob(..., S_version="1.4.2", env_digest="sha256:" + "a" * 64)
    # for f in run_detector(detector, snapshot_for(job), spec_set):
    #     assert f.S_version == job.S_version
    #     assert f.env_digest == job.env_digest
    pytest.skip("CMP-ORCH-03 not implemented yet")

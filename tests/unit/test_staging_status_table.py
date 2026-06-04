"""Unit + drift-guard tests for the AC-driven staging-status table (CMP-CI-01).

WBS §21 line L9: "the Stage A..D status table is AC-driven, not prose." This file
proves the generator is HONEST (a missing verdict never becomes a pass) and that the
committed table cannot silently rot back into prose (the drift guard).

Falsifier discipline (per the project's falsifier rules):
  - ANTI-VACUITY POSITIVE: feed GATE-PASS + attested + AC-green fixtures and assert the
    stage renders `ready`. Without this, the honesty test below is vacuously satisfied
    by a generator that ALWAYS emits not-ready.
  - MUTATION-VERIFIED NEGATIVES (documented in the PR, run by hand, diff-restored):
      (a) a generator that defaults a MISSING fidelity verdict to gate-pass FAILS the
          honesty test (`test_missing_verdict_is_never_ready`).
      (b) hand-editing the committed table FAILS the drift guard
          (`test_committed_table_matches_regeneration`).

This module is NOT a fifth CI gate (DOC-CMP-CI-01 §7.1). It is a developer-experience
quality bar carried in the existing `unit-tests` job, the same class as lint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from services.staging.status_table import (
    DEFAULT_AC_RESULTS_ROOT,
    DEFAULT_ATTESTATION_ROOT,
    DEFAULT_FIDELITY_ROOT,
    DEFAULT_OUTPUT_PATH,
    STAGES,
    GeneratorInputs,
    generate_table,
    main,
    render_current,
    render_markdown,
)

if TYPE_CHECKING:
    from services.staging.status_table import StageStatus

# Repo root: tests/unit/test_staging_status_table.py -> parents[2] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _gate_pass_verdict(language: str) -> dict[str, object]:
    """A synthetic CP-06 latest.json in the DOC-CMP-CP-06 §3.4 GATE-PASS shape."""
    return {
        "language": language,
        "corpus_version": "sha256:fixturecorpus",
        "env_digest": "sha256:fixtureenv",
        "parse_success_rate": 0.997,
        "call_edge_precision": 0.93,
        "call_edge_recall": 0.88,
        "pdg_recall": 0.84,
        "evaluated_at": "2026-05-23T10:00:00Z",
        "overall": "GATE-PASS",
        "failing_metrics": [],
    }


def _gate_fail_verdict(language: str) -> dict[str, object]:
    """A synthetic CP-06 latest.json in the GATE-FAIL shape (call-edge recall miss)."""
    return {
        "language": language,
        "corpus_version": "sha256:fixturecorpus",
        "env_digest": "sha256:fixtureenv",
        "parse_success_rate": 0.997,
        "call_edge_precision": 0.93,
        "call_edge_recall": 0.62,
        "pdg_recall": 0.84,
        "evaluated_at": "2026-05-23T10:00:00Z",
        "overall": "GATE-FAIL",
        "failing_metrics": ["call_edge_recall"],
    }


def _write_fidelity(root: Path, verdict: dict[str, object]) -> None:
    language = str(verdict["language"])
    path = root / language / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict), encoding="utf-8")


def _write_attestation(root: Path, stage_id: str, result: str) -> None:
    path = root / f"stage-{stage_id.lower()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"result": result}), encoding="utf-8")


def _write_ac(root: Path, ac_id: str, result: str) -> None:
    path = root / f"{ac_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"result": result}), encoding="utf-8")


def _stage(stages: tuple[StageStatus, ...], stage_id: str) -> StageStatus:
    return next(s for s in stages if s.stage_id == stage_id)


# ---------------------------------------------------------------------------
# Honesty: a missing verdict is NEVER ready (the negative direction).
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_missing_verdict_is_never_ready(tmp_path: Path) -> None:
    """Empty artifact roots → every stage `ungated`, none `ready`.

    Test id:    TST-AC-CI-01-staging-honesty
    Kind tag:   [NEGATIVE / honesty]
    Pass:       with no verdict files present, every stage token is `ungated`;
                no stage is `ready`/`not-attested`; no stage is attested or AC-green.

    NEGATIVE CONTROL (mutation-verified): a generator that defaults a MISSING
    fidelity verdict to `gate-pass` (e.g. `_language_status` returning `gate-pass`
    on `verdict is None`) makes Stage A's token leave `ungated`, FAILING this test.
    """
    inputs = GeneratorInputs(
        fidelity_root=tmp_path / "cpg_fidelity",
        attestation_root=tmp_path / "attestation",
        ac_results_root=tmp_path / "ac",
    )
    stages = generate_table(inputs)

    assert len(stages) == len(STAGES)
    for stage in stages:
        assert stage.status == "ungated", f"stage {stage.stage_id} must be ungated"
        assert stage.attested is False
        assert stage.acs_green is False
        for ls in stage.languages:
            assert ls.status == "ungated"
            assert ls.overall is None

    # The rendered markdown must not show a `ready` STATUS in any table row.
    # (The explanatory prose / legend may mention the word `ready`; what is
    # forbidden is a stage ROW whose Status cell is `ready`.)
    md = render_markdown(stages)
    row_lines = [
        ln
        for ln in md.splitlines()
        if any(ln.startswith(f"| Stage {sid} |") for sid in ("A", "B", "C", "D"))
    ]
    assert len(row_lines) == len(STAGES), "expected one data row per stage"
    for ln in row_lines:
        assert "`ready`" not in ln, f"no stage row may be ready: {ln}"
        assert "`ungated`" in ln


# ---------------------------------------------------------------------------
# Anti-vacuity POSITIVE: full green fixtures → the stage is ready.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_full_green_stage_is_ready(tmp_path: Path) -> None:
    """All gates green for Stage A → token `ready` (proves it CAN flip).

    Test id:    TST-AC-CI-01-staging-positive
    Kind tag:   [POSITIVE / anti-vacuity]
    Pass:       Stage A's two languages gate-pass + CP-05 attested + both named ACs
                green → Stage A token is `ready`, attested True, acs_green True.
                Without verdicts, Stage B/C/D stay `ungated` (not contaminated).
    """
    fidelity_root = tmp_path / "cpg_fidelity"
    attestation_root = tmp_path / "attestation"
    ac_root = tmp_path / "ac"

    stage_a_def = next(s for s in STAGES if s.stage_id == "A")
    for language in stage_a_def.languages:
        _write_fidelity(fidelity_root, _gate_pass_verdict(language))
    _write_attestation(attestation_root, "A", "pass")
    for ac_id in stage_a_def.ac_ids:
        _write_ac(ac_root, ac_id, "green")

    inputs = GeneratorInputs(
        fidelity_root=fidelity_root,
        attestation_root=attestation_root,
        ac_results_root=ac_root,
    )
    stages = generate_table(inputs)
    a = _stage(stages, "A")
    assert a.status == "ready"
    assert a.attested is True
    assert a.acs_green is True
    for ls in a.languages:
        assert ls.status == "gate-pass"

    # Other stages have no verdicts → still ungated (no cross-stage contamination).
    assert _stage(stages, "B").status == "ungated"
    assert _stage(stages, "C").status == "ungated"
    assert _stage(stages, "D").status == "ungated"

    # The rendered table now shows a ready ROW for Stage A.
    md = render_markdown(stages)
    assert "| Stage A | java, python | `ready` |" in md


# ---------------------------------------------------------------------------
# Intermediate honest tokens: gate-pass but not attested → not-attested;
# a gate failure → front-end-blocked (INV-6: never a recall number).
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_gate_pass_without_attestation_is_not_attested(tmp_path: Path) -> None:
    """Languages gate-pass but no CP-05 attestation → `not-attested`, not `ready`."""
    fidelity_root = tmp_path / "cpg_fidelity"
    for language in ("java", "python"):
        _write_fidelity(fidelity_root, _gate_pass_verdict(language))
    inputs = GeneratorInputs(
        fidelity_root=fidelity_root,
        attestation_root=tmp_path / "attestation",
        ac_results_root=tmp_path / "ac",
    )
    a = _stage(generate_table(inputs), "A")
    assert a.status == "not-attested"
    assert a.attested is False


@pytest.mark.unit
def test_gate_fail_is_front_end_blocked_without_recall_number(tmp_path: Path) -> None:
    """A GATE-FAIL language → `front-end-blocked`; the cell names the metric, not a number.

    INV-6 / AC-CP-06a: a front-end-blocked pair is NEVER reported as a recall number.
    The 0.62 recall value from the verdict must NOT appear in the rendered cell.
    """
    fidelity_root = tmp_path / "cpg_fidelity"
    _write_fidelity(fidelity_root, _gate_pass_verdict("java"))
    _write_fidelity(fidelity_root, _gate_fail_verdict("python"))
    inputs = GeneratorInputs(
        fidelity_root=fidelity_root,
        attestation_root=tmp_path / "attestation",
        ac_results_root=tmp_path / "ac",
    )
    stages = generate_table(inputs)
    a = _stage(stages, "A")
    assert a.status == "front-end-blocked"
    py = next(ls for ls in a.languages if ls.language == "python")
    assert py.status == "front-end-blocked"
    assert "call_edge_recall" in py.failing_metrics

    md = render_markdown(stages)
    # INV-6: the metric NAME may appear; the recall NUMBER must not.
    assert "call_edge_recall" in md
    assert "0.62" not in md
    assert "front-end-blocked" in md


@pytest.mark.unit
def test_corrupt_verdict_fails_closed_to_ungated(tmp_path: Path) -> None:
    """A corrupt / non-object verdict file is treated as no verdict (honest negative)."""
    fidelity_root = tmp_path / "cpg_fidelity"
    bad = fidelity_root / "java" / "latest.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not valid json", encoding="utf-8")
    inputs = GeneratorInputs(
        fidelity_root=fidelity_root,
        attestation_root=tmp_path / "attestation",
        ac_results_root=tmp_path / "ac",
    )
    a = _stage(generate_table(inputs), "A")
    assert a.status == "ungated"


@pytest.mark.unit
def test_render_current_and_main_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI path (`main`) writes exactly what `render_current` returns.

    Exercises the regenerate entrypoint without clobbering the committed table:
    `DEFAULT_OUTPUT_PATH` is monkeypatched to a temp file.
    """
    expected = render_current()
    assert expected.startswith("<!--")
    out_path = tmp_path / "DOC-STAGING-STATUS.md"
    monkeypatch.setattr("services.staging.status_table.DEFAULT_OUTPUT_PATH", out_path)
    main()
    assert out_path.read_text(encoding="utf-8") == expected


@pytest.mark.unit
def test_render_is_deterministic_no_wallclock(tmp_path: Path) -> None:
    """Two renders of the same inputs are byte-identical (no wall-clock in output)."""
    fidelity_root = tmp_path / "cpg_fidelity"
    _write_fidelity(fidelity_root, _gate_pass_verdict("java"))
    inputs = GeneratorInputs(
        fidelity_root=fidelity_root,
        attestation_root=tmp_path / "attestation",
        ac_results_root=tmp_path / "ac",
    )
    first = render_markdown(generate_table(inputs))
    second = render_markdown(generate_table(inputs))
    assert first == second
    # Guard against an accidental wall-clock year creeping into the rendered file:
    # the only dates allowed are fixture evaluated_at values, none of which is "now".
    assert "2026-06" not in first  # today's month must not leak in via datetime.now()


# ---------------------------------------------------------------------------
# DRIFT GUARD: the committed table must equal a fresh regeneration.
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_committed_table_matches_regeneration() -> None:
    """The committed DOC-STAGING-STATUS.md must byte-match a fresh regeneration.

    Test id:    TST-AC-CI-01-staging-drift
    Kind tag:   [DRIFT GUARD]
    Pass:       the on-disk committed table equals `render_current()` computed from
                the real default artifact roots. This is what stops the table rotting
                back into hand-edited prose.

    NEGATIVE CONTROL (mutation-verified): hand-editing the committed table (e.g.
    flipping a `ungated` cell to `ready`) makes the committed bytes diverge from the
    regeneration, FAILING this test.
    """
    committed_path = _REPO_ROOT / DEFAULT_OUTPUT_PATH
    assert committed_path.is_file(), (
        f"committed staging-status table missing at {committed_path}; "
        "regenerate with `python -m services.staging`"
    )
    committed = committed_path.read_text(encoding="utf-8")
    # Resolve the default (cwd-relative) artifact roots against the repo root so the
    # drift guard is independent of pytest's invocation directory.
    inputs = GeneratorInputs(
        fidelity_root=_REPO_ROOT / DEFAULT_FIDELITY_ROOT,
        attestation_root=_REPO_ROOT / DEFAULT_ATTESTATION_ROOT,
        ac_results_root=_REPO_ROOT / DEFAULT_AC_RESULTS_ROOT,
    )
    regenerated = render_markdown(generate_table(inputs))
    assert committed == regenerated, (
        "Committed DOC-STAGING-STATUS.md has drifted from a regeneration. "
        "Do NOT hand-edit it — edit the verdict inputs and run "
        "`python -m services.staging`."
    )

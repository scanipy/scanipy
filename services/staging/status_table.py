"""AC-driven staging-status table generator (CMP-CI-01 / WBS §21-L9).

Pure file-consumer that turns machine verdicts into the Stage A..D status table.
No CP-06 harness import (CLAR-PROC-01 — consume the FILE format, not the module).
No DB. No wall-clock in the output (determinism — see package docstring).

Token model
-----------
Per-language token (read from the CP-06 fidelity verdict file):

  - ``ungated``            — no ``latest.json`` present for the language.
  - ``front-end-blocked``  — verdict present, ``overall`` is ``GATE-FAIL`` /
                             ``front-end-blocked``. INV-6: never a recall number.
  - ``gate-pass``          — verdict present, ``overall`` is ``GATE-PASS``.

Per-stage token (the conjunction over the stage's languages plus the attestation
and AC gates):

  - ``ungated``            — at least one language has no fidelity verdict.
  - ``front-end-blocked``  — every language gated, but at least one failed the gate.
  - ``not-attested``       — every language is ``gate-pass`` but the stage's
                             CP-05 attestation and/or named ACs are not green.
  - ``ready``              — every language ``gate-pass`` AND CP-05-attested AND
                             every named AC green. The ONLY token that asserts the
                             stage is in the core partition.

The generator NEVER defaults a stage to ``ready``/``passed``. A missing input is the
honest negative token, by construction (see ``_stage_status``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

# --- Canonical default artifact roots / output path -------------------------
#
# DOC-CMP-CP-06 §3.4 pins the CP-06 verdict file at
# ``tests/results/cpg_fidelity/{language}/latest.json``. The CP-05 attestation
# verdict and the named-AC-outcome files have NO path pinned in any DOC today;
# the paths below are this module's working assumption, surfaced for ratification
# in CLAR-CI-02 (the staging-status-table CLAR).
DEFAULT_FIDELITY_ROOT = Path("tests/results/cpg_fidelity")
# INTERFACE-SHAPE DEVIATION (CLAR-CI-02):
# DOC-CMP-CP-05 pins NO on-disk verdict artifact — ``AttestationVerdict`` is
# in-memory / DB-bound (a repo-wide grep for a CP-05 verdict JSON path was empty).
# This generator reads an OPTIONAL per-stage attestation verdict file; absent →
# ``not-attested``. It never invents a CP-05 format and renders it as real.
DEFAULT_ATTESTATION_ROOT = Path("tests/results/attestation")
# INTERFACE-SHAPE DEVIATION (CLAR-CI-02):
# the named-AC-outcome file path is likewise undefined in any DOC; absent → not green.
DEFAULT_AC_RESULTS_ROOT = Path("tests/results/ac_outcomes")
# DOC-STAGING §7.3 points the AC-driven table at WBS §13 prose, which is NOT editable
# by an implementation agent (allowed WBS writes are §17/§18 appends + status flips).
# Per the task fallback, the generated table lives here (generated, DO-NOT-HAND-EDIT);
# placement surfaced for ratification in the staging-status-table CLAR.
DEFAULT_OUTPUT_PATH = Path("docs/cross-cutting/DOC-STAGING-STATUS.md")

LanguageToken = Literal["ungated", "front-end-blocked", "gate-pass"]
StageToken = Literal["ungated", "front-end-blocked", "not-attested", "ready"]


@dataclass(frozen=True)
class _Stage:
    """One Stage row's definition (DOC-STAGING §2)."""

    stage_id: str
    label: str
    languages: tuple[str, ...]
    # Named ACs whose outcome gates this stage (DOC-CMP-CI-01 §9 / DOC-STAGING §7.1).
    ac_ids: tuple[str, ...]


# Stage A..D definitions, verbatim language membership from DOC-STAGING §2.
# (Corpus language keys: js covers JS/TS per tests/corpora/cpg_fidelity/.)
STAGES: tuple[_Stage, ...] = (
    _Stage(
        stage_id="A",
        label="Java + Python",
        languages=("java", "python"),
        ac_ids=("AC-CP-05c", "AC-CORE-01b"),
    ),
    _Stage(
        stage_id="B",
        label="JS / TS",
        languages=("js",),
        ac_ids=("AC-CP-05c", "AC-CORE-01b"),
    ),
    _Stage(
        stage_id="C",
        label="Go",
        languages=("go",),
        ac_ids=("AC-CP-05c", "AC-CORE-01b"),
    ),
    _Stage(
        stage_id="D",
        label="Ruby + PHP",
        languages=("ruby", "php"),
        ac_ids=("AC-CP-05c", "AC-CORE-01b"),
    ),
)


@dataclass(frozen=True)
class LanguageStatus:
    """Resolved per-language fidelity token plus the evidence that produced it."""

    language: str
    status: LanguageToken
    # Source detail for the honest rendering. None when the verdict file is absent.
    overall: str | None
    failing_metrics: tuple[str, ...]
    corpus_version: str | None
    evaluated_at: str | None


@dataclass(frozen=True)
class StageStatus:
    """Resolved per-stage token plus its constituent language statuses."""

    stage_id: str
    label: str
    languages: tuple[LanguageStatus, ...]
    attested: bool
    acs_green: bool
    status: StageToken


@dataclass(frozen=True)
class GeneratorInputs:
    """Injectable artifact roots. Tests point these at fixtures; CI uses defaults."""

    fidelity_root: Path = DEFAULT_FIDELITY_ROOT
    attestation_root: Path = DEFAULT_ATTESTATION_ROOT
    ac_results_root: Path = DEFAULT_AC_RESULTS_ROOT


def _read_json(path: Path) -> Mapping[str, object] | None:
    """Read a JSON object fail-closed. Absent / unreadable / non-object → None."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # Fail-closed: a corrupt verdict is treated as no verdict (honest negative),
        # never silently coerced into a pass.
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _language_status(language: str, fidelity_root: Path) -> LanguageStatus:
    """Resolve one language's fidelity token from its CP-06 ``latest.json``.

    Trusts the verdict's ``overall`` field; it does NOT recompute the CLAR-CORP-02
    thresholds (re-encoding them here would be a contract break — DOC-CMP-CP-06 §3.1).
    """
    verdict = _read_json(fidelity_root / language / "latest.json")
    if verdict is None:
        return LanguageStatus(
            language=language,
            status="ungated",
            overall=None,
            failing_metrics=(),
            corpus_version=None,
            evaluated_at=None,
        )

    overall_raw = verdict.get("overall")
    overall = overall_raw if isinstance(overall_raw, str) else None
    failing_raw = verdict.get("failing_metrics")
    failing = tuple(str(m) for m in failing_raw) if isinstance(failing_raw, list) else ()
    corpus_version_raw = verdict.get("corpus_version")
    corpus_version = corpus_version_raw if isinstance(corpus_version_raw, str) else None
    evaluated_at_raw = verdict.get("evaluated_at")
    evaluated_at = evaluated_at_raw if isinstance(evaluated_at_raw, str) else None

    # Only an explicit GATE-PASS is a pass. Anything else (GATE-FAIL,
    # front-end-blocked, or an unrecognised / missing verdict string) is the
    # honest negative — fail-closed, never defaulted to pass.
    if overall == "GATE-PASS":
        status: LanguageToken = "gate-pass"
    else:
        status = "front-end-blocked"

    return LanguageStatus(
        language=language,
        status=status,
        overall=overall,
        failing_metrics=failing,
        corpus_version=corpus_version,
        evaluated_at=evaluated_at,
    )


def _stage_attested(stage: _Stage, attestation_root: Path) -> bool:
    """True only when a CP-05 attestation verdict file marks this stage passing.

    Absent file or any non-``pass`` result → False (``not-attested``).
    """
    verdict = _read_json(attestation_root / f"stage-{stage.stage_id.lower()}.json")
    if verdict is None:
        return False
    return verdict.get("result") == "pass"


def _stage_acs_green(stage: _Stage, ac_results_root: Path) -> bool:
    """True only when every named AC for the stage has an explicit green outcome."""
    for ac_id in stage.ac_ids:
        verdict = _read_json(ac_results_root / f"{ac_id}.json")
        if verdict is None or verdict.get("result") != "green":
            return False
    return True


def _stage_status_token(
    languages: tuple[LanguageStatus, ...], attested: bool, acs_green: bool
) -> StageToken:
    """Combine language statuses + attestation + AC gates into the stage status token.

    The order is fail-closed: any missing fidelity verdict short-circuits to
    ``ungated``; any gate failure short-circuits to ``front-end-blocked``; a stage
    reaches ``ready`` ONLY when every gate is satisfied.
    """
    language_states = {ls.status for ls in languages}
    if "ungated" in language_states:
        return "ungated"
    if "front-end-blocked" in language_states:
        return "front-end-blocked"
    # Every language is gate-pass here.
    if attested and acs_green:
        return "ready"
    return "not-attested"


def _stage_status(stage: _Stage, inputs: GeneratorInputs) -> StageStatus:
    languages = tuple(_language_status(lang, inputs.fidelity_root) for lang in stage.languages)
    attested = _stage_attested(stage, inputs.attestation_root)
    acs_green = _stage_acs_green(stage, inputs.ac_results_root)
    status = _stage_status_token(languages, attested, acs_green)
    return StageStatus(
        stage_id=stage.stage_id,
        label=stage.label,
        languages=languages,
        attested=attested,
        acs_green=acs_green,
        status=status,
    )


def generate_table(inputs: GeneratorInputs | None = None) -> tuple[StageStatus, ...]:
    """Resolve every stage's status from the injected (or default) artifact roots."""
    resolved = inputs if inputs is not None else GeneratorInputs()
    return tuple(_stage_status(stage, resolved) for stage in STAGES)


# --- Markdown rendering -----------------------------------------------------

_DO_NOT_HAND_EDIT_HEADER = """<!--
  DO NOT HAND-EDIT. This file is GENERATED by services.staging.status_table
  (CMP-CI-01) from machine verdicts:
    - CP-06 fidelity verdicts: tests/results/cpg_fidelity/{language}/latest.json
    - CP-05 attestation verdicts (per-stage, optional; CLAR-tracked path)
    - named-AC outcomes (optional; CLAR-tracked path)
  Regenerate with:  python -m services.staging
  A drift guard (tests/unit/test_staging_status_table.py) FAILS CI if the
  committed copy diverges from a regeneration. Edit the verdicts, not this file.
-->"""


def _language_detail(ls: LanguageStatus) -> str:
    """Honest per-language cell. INV-6: a blocked language never shows a recall number.

    Instead it names the failing metric(s) qualitatively (the metric NAME, not a
    recall value), per DOC-CMP-CP-06 §3.3's required phrasing.
    """
    if ls.status == "ungated":
        return f"`{ls.language}`: ungated (no CP-06 verdict)"
    if ls.status == "front-end-blocked":
        if ls.failing_metrics:
            metrics = ", ".join(ls.failing_metrics)
            return f"`{ls.language}`: front-end-blocked (failing: {metrics})"
        return f"`{ls.language}`: front-end-blocked"
    return f"`{ls.language}`: gate-pass"


def render_markdown(stages: tuple[StageStatus, ...]) -> str:
    """Render the staging-status table as deterministic markdown.

    Pure function of ``stages``: no wall-clock, no environment reads. The only
    freshness signal is each language's ``evaluated_at`` (sourced from the verdict
    file), surfaced in the per-language detail column when present.
    """
    lines: list[str] = []
    lines.append(_DO_NOT_HAND_EDIT_HEADER)
    lines.append("")
    lines.append("# DOC-STAGING-STATUS — AC-driven Stage A..D status table")
    lines.append("")
    lines.append(
        "Generated by `services.staging.status_table` (CMP-CI-01) from machine "
        "verdicts. This is the mechanism that makes `WBS.md §21` line L9 "
        '("the Stage A..D status table is AC-driven, not prose") met-as-mechanism: '
        "the tokens below are read from CP-06 / CP-05 / AC verdict files, never "
        "hand-authored. A stage is shown `ready` ONLY when every one of its "
        "languages is CP-06 `gate-pass`, the stage is CP-05-attested, and every "
        "named AC is green. Missing verdicts render as the honest token "
        "(`ungated` / `front-end-blocked` / `not-attested`) — never `ready`."
    )
    lines.append("")
    lines.append(
        "INV-6: a `front-end-blocked` language is reported by the name of its "
        "failing metric, NEVER as a recall number."
    )
    lines.append("")
    lines.append("| Stage | Languages | Status | Attested | ACs green | Per-language |")
    lines.append("|---|---|---|---|---|---|")
    for stage in stages:
        lang_names = ", ".join(ls.language for ls in stage.languages)
        attested = "yes" if stage.attested else "no"
        acs = "yes" if stage.acs_green else "no"
        detail = "; ".join(_language_detail(ls) for ls in stage.languages)
        lines.append(
            f"| Stage {stage.stage_id} | {lang_names} | `{stage.status}` | "
            f"{attested} | {acs} | {detail} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Token legend:* `ungated` = no CP-06 verdict for at least one language · "
        "`front-end-blocked` = a language failed the CP-06 gate (INV-6) · "
        "`not-attested` = all languages gate-pass but CP-05 attestation / named ACs "
        "are not yet green · `ready` = core partition for this stage is honestly "
        "earned (all gates green)."
    )
    lines.append("")
    return "\n".join(lines)


def render_current() -> str:
    """Render the table from the default artifact roots (the committed-table source)."""
    return render_markdown(generate_table())


def main() -> None:
    """Write the generated table to the canonical output path (CLI entrypoint)."""
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_PATH.write_text(render_current(), encoding="utf-8")


if __name__ == "__main__":
    main()

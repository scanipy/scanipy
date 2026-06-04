"""CMP-CI-01 — AC-driven staging-status table generator.

This package produces the Stage A..D status table (`WBS.md §21` line L9: "the
Stage A..D status table is AC-driven, not prose") by **reading machine verdicts**,
never by hand-authoring prose. It is a pure, hermetic file-consumer:

- It reads `CMP-CP-06` per-language fidelity verdicts (`latest.json`, the
  `DOC-CMP-CP-06 §3.4` JSON format) via a typed reader.
- It reads `CMP-CP-05` attestation verdicts where present.
- It reads named AC-test outcomes.
- It renders a generated markdown table whose tokens are an honest function of
  those inputs.

**Boundary discipline (CLAR-PROC-01, RESOLVED 2026-06-04).** This module is built
ahead of `CMP-CP-06` (whose harness lands in a parallel worktree). Per CLAR-PROC-01
it consumes the verdict **FILE format** through a typed reader; it never imports the
CP-06 harness module (`services.control_plane.fidelity`). The contract this code
honours is the on-disk JSON shape documented in `DOC-CMP-CP-06 §3.4`.

**Honesty posture (INV-6).** A missing or absent verdict input renders as the honest
token — `ungated`, `not-attested`, or `front-end-blocked` — and a stage is NEVER
defaulted to `ready`/`passed`. A `front-end-blocked` language never surfaces a recall
number (INV-6, `AC-CP-06a`). The generator's correctness is the negative direction:
on the current honest state (no verdicts present) it emits a table where nothing has
passed, which is the truth.

**Determinism.** The rendered markdown is a pure function of the input files. There is
no wall-clock timestamp in the output (a wall-clock stamp would make every regeneration
differ from the committed file and self-defeat the drift guard, and would violate the
repo's reproducibility posture). Any freshness signal is derived from the inputs'
`evaluated_at` fields, not from `datetime.now()`.

**This package is NOT a fifth CI gate.** Per `DOC-CMP-CI-01 §7.1`, no fifth Gate-class
check may be added without an SDD-level AC. The committed-table drift guard
(`tests/unit/test_staging_status_table.py`) is a developer-experience quality bar in
the existing `unit-tests` job — the same class as lint — never a release blocker.

See `docs/components/DOC-CMP-CI-01.md`, `docs/cross-cutting/DOC-STAGING.md`, and
`docs/components/DOC-CMP-CP-06.md` for the contracts this module consumes.
"""

from __future__ import annotations

from services.staging.status_table import (
    DEFAULT_AC_RESULTS_ROOT,
    DEFAULT_ATTESTATION_ROOT,
    DEFAULT_FIDELITY_ROOT,
    DEFAULT_OUTPUT_PATH,
    STAGES,
    GeneratorInputs,
    LanguageStatus,
    StageStatus,
    generate_table,
    render_markdown,
)

__all__ = [
    "DEFAULT_AC_RESULTS_ROOT",
    "DEFAULT_ATTESTATION_ROOT",
    "DEFAULT_FIDELITY_ROOT",
    "DEFAULT_OUTPUT_PATH",
    "STAGES",
    "GeneratorInputs",
    "LanguageStatus",
    "StageStatus",
    "generate_table",
    "render_markdown",
]

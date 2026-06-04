"""CMP-FND-01 — SARIF 2.1.0 canonical emission.

The wire-format boundary between the analysis core / oracle adapters and every
downstream SARIF consumer (Attestor CMP-CP-05, attestation export, dashboard,
GitHub code-scanning). See :mod:`analysis.sarif.canonical_emit` for the
normative two-Run emitter (``normalize``) and the canonical serialiser.
"""

from __future__ import annotations

from analysis.sarif.canonical_emit import (
    CanonicalEmissionFailure,
    InvariantViolation,
    SARIFExtensionViolation,
    SARIFLog,
    SARIFRun,
    SARIFSchemaViolation,
    WorkerFinding,
    normalize,
    normalize_split,
    validate_sarif_210,
)

__all__ = [
    "CanonicalEmissionFailure",
    "InvariantViolation",
    "SARIFExtensionViolation",
    "SARIFLog",
    "SARIFRun",
    "SARIFSchemaViolation",
    "WorkerFinding",
    "normalize",
    "normalize_split",
    "validate_sarif_210",
]

"""CMP-FND-01 — findings-normalizer service entry point.

DOC-CMP-FND-01 §1 names two module paths for this component:
``analysis/sarif/canonical_emit.py`` (the pure canonical serialiser + the
``normalize`` two-Run emitter) and ``services/scan/findings_normalizer.py`` (the
service-layer surface the scan pipeline calls).

The whole emitter is pure and dependency-light, so this service module is a thin
re-export of the canonical core: the scan service imports ``normalize`` /
``normalize_split`` from here, while ``analysis.sarif`` stays free of any
``services`` import (layering: ``services`` depends on ``analysis``, never the
reverse).
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

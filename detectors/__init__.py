"""CMP-DET-02 — detector catalog: registry + closure check.

The registry is the single gatekeeper between authored detector content (DSL
specs and oracle queries) and the analysis pipeline. Specs are admitted here or
not at all; a rejected spec is never seen by CMP-CORE-01 / CMP-ORCH-03.

Public surface (DOC-CMP-DET-02 §3):
  - :class:`Detector` — one frozen registry row.
  - :class:`DetectorRegistry` — process-singleton, frozen after ``load_manifests``.
  - :func:`derive_partition` — engine -> determinism_partition (AC-DET-02c).
  - :func:`closure_check` — defense-in-depth shape re-validation (INV-4).
  - :class:`RegistryError`, :class:`RegistryLoadError`, re-exported :class:`DSLError`.
"""

from __future__ import annotations

from detectors.registry import (
    CORE_ENGINES,
    ORACLE_ENGINES,
    Detector,
    DetectorRegistry,
    DSLError,
    RegistryError,
    RegistryLoadError,
    closure_check,
    derive_partition,
)

__all__ = [
    "CORE_ENGINES",
    "ORACLE_ENGINES",
    "DSLError",
    "Detector",
    "DetectorRegistry",
    "RegistryError",
    "RegistryLoadError",
    "closure_check",
    "derive_partition",
]

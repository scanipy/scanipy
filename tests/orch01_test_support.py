"""Shared construction helpers for the CMP-ORCH-01 spec tests.

Keeps the wiring (a loaded DET-02 registry, an :class:`OrgScopedScanStore`, the
in-memory queue) in one place so both ``tests/unit/test_orch_specs.py`` (the
AC-ORCH-01b stub) and ``tests/unit/test_orch01_scan_api.py`` (the full leg set)
build identical hermetic fixtures.
"""

from __future__ import annotations

from services.scan.api import OrgScopedScanStore


def build_scan_store() -> OrgScopedScanStore:
    """A fresh RLS-backed scan store (over CMP-CP-01's OrgScopedStore)."""
    return OrgScopedScanStore()


__all__ = ["build_scan_store"]

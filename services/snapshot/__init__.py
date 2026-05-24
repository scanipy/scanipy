"""Snapshotter services package.

Currently exports CMP-SNAP-03 (`CW-DETECT`), the closed-world precondition
detector that is the INV-4 owner for Algorithm 1's precondition. Sibling
snapshot services (CMP-SNAP-01/02/04/05) land in this package as they are
implemented.
"""

from services.snapshot.cw_detect import (
    CW_DETECT_VERSION,
    SUPPORTED_LANGUAGES,
    CwDetectRequest,
    CwDetectVerdict,
    ReflectionKind,
    ReflectionSite,
    RoutingRateReport,
    Snapshot,
    detect,
    measure_routing_rate,
)

__all__ = [
    "CW_DETECT_VERSION",
    "SUPPORTED_LANGUAGES",
    "CwDetectRequest",
    "CwDetectVerdict",
    "ReflectionKind",
    "ReflectionSite",
    "RoutingRateReport",
    "Snapshot",
    "detect",
    "measure_routing_rate",
]

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
from services.snapshot.diff_oracle import (
    CORE_ENGINES,
    InMemoryOracleRunStore,
    OracleReflectionSite,
    OracleRunRecord,
    OracleRunStore,
    OracleVerdict,
    RepartitionProvenanceStore,
    RepartitionResult,
    effective_origin,
    record_oracle_run,
    record_safe_default_agreement,
    repartition_snapshot,
)
from services.snapshot.models import PreconditionStatus, SnapshotRow
from services.snapshot.service import (
    EnvDigestProvider,
    InMemorySnapshotStore,
    SnapshotAccepted,
    SnapshotRequest,
    SnapshotService,
    SnapshotStore,
    env_var_env_digest_provider,
)

__all__ = [
    "CORE_ENGINES",
    "CW_DETECT_VERSION",
    "SUPPORTED_LANGUAGES",
    "CwDetectRequest",
    "CwDetectVerdict",
    "EnvDigestProvider",
    "InMemoryOracleRunStore",
    "InMemorySnapshotStore",
    "OracleReflectionSite",
    "OracleRunRecord",
    "OracleRunStore",
    "OracleVerdict",
    "PreconditionStatus",
    "ReflectionKind",
    "ReflectionSite",
    "RepartitionProvenanceStore",
    "RepartitionResult",
    "RoutingRateReport",
    "Snapshot",
    "SnapshotAccepted",
    "SnapshotRequest",
    "SnapshotRow",
    "SnapshotService",
    "SnapshotStore",
    "detect",
    "effective_origin",
    "env_var_env_digest_provider",
    "measure_routing_rate",
    "record_oracle_run",
    "record_safe_default_agreement",
    "repartition_snapshot",
]

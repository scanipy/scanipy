"""CMP-CP-01 — Multi-tenant scan API guard.

Implementation contract: ``docs/components/DOC-CMP-CP-01.md``.

This package is the **first hop** for every authenticated control-plane request:
it enforces the tenancy-header / JWT-claim agreement (``org_mismatch``), the RBAC
role gate (``role_denied``), and the CLAR-DEPLOY-16 layer-2 RLS backstop (an
in-memory :class:`~services.control_plane.guard.OrgScopedStore` that returns no
cross-tenant rows and refuses to run a query before its session variables are
set). All three layers are fail-closed.

CP-01 is a **non-emitting** component: it never writes ``findings``,
``provenance_records``, ``triage_scores``, ``attestations`` or ``spec_versions``
rows (DOC-CMP-CP-01 §8). RULE-6 provenance threading (``S_version``,
``env_digest``, ``origin``, ``cpg_order_hash``) is therefore **not applicable** to
this layer — those fields are stamped downstream by ``CMP-ORCH-03`` /
``CMP-FND-01..03``. CP-01's threading responsibility is solely to bind
``app.org_id`` / ``app.user_id`` / ``app.role`` for the request so RLS-scoped
downstream reads inherit the correct tenant.
"""

from services.control_plane.constants import (
    ERROR_ORG_MISMATCH,
    ERROR_ROLE_DENIED,
    ERROR_TENANT_ISOLATION_VIOLATION,
    HEADER_ORG_ID,
    HEADER_USER_ID,
    RBAC,
    SESSION_VAR_ORG_ID,
    SESSION_VAR_ROLE,
    SESSION_VAR_USER_ID,
    Action,
    Resource,
    Role,
)
from services.control_plane.fidelity import (
    THRESHOLDS,
    BenchmarkEligibilityError,
    CorpusPort,
    ExtractedItem,
    ExtractionPort,
    FidelityGateError,
    FidelityMetrics,
    FidelityVerdict,
    GroundTruthItem,
    compute_metrics,
    evaluate_fidelity,
    load_verdict,
    lockfile_corpus_port,
    persist_verdict,
    verdict_path,
)
from services.control_plane.guard import (
    CPGuard,
    ErrorEnvelope,
    JWTClaims,
    OrgScopedStore,
    TenantIsolationError,
)

__all__ = [
    "ERROR_ORG_MISMATCH",
    "ERROR_ROLE_DENIED",
    "ERROR_TENANT_ISOLATION_VIOLATION",
    "HEADER_ORG_ID",
    "HEADER_USER_ID",
    "RBAC",
    "SESSION_VAR_ORG_ID",
    "SESSION_VAR_ROLE",
    "SESSION_VAR_USER_ID",
    "THRESHOLDS",
    "Action",
    "BenchmarkEligibilityError",
    "CPGuard",
    "CorpusPort",
    "ErrorEnvelope",
    "ExtractedItem",
    "ExtractionPort",
    "FidelityGateError",
    "FidelityMetrics",
    "FidelityVerdict",
    "GroundTruthItem",
    "JWTClaims",
    "OrgScopedStore",
    "Resource",
    "Role",
    "TenantIsolationError",
    "compute_metrics",
    "evaluate_fidelity",
    "load_verdict",
    "lockfile_corpus_port",
    "persist_verdict",
    "verdict_path",
]

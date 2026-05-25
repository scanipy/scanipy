"""CMP-CP-01 constants — session-variable names, RBAC matrix, error codes.

Single source of truth so a rename of the RLS session-variable scheme
(CLAR-DB-02 DEFERRED) is a one-line change (DOC-CMP-CP-01 §10, CLAR-DB-02).
"""

from __future__ import annotations

from typing import Literal

# --- RLS session variables (DOC-DB §3.2, CLAR-DB-02 working assumption) -------
# Kept here so the eventual CLAR-DB-02 ratification renames them in one place.
SESSION_VAR_ORG_ID = "app.org_id"
SESSION_VAR_USER_ID = "app.user_id"
SESSION_VAR_ROLE = "app.role"

# --- Tenancy headers (DOC-API §2.5) -------------------------------------------
HEADER_ORG_ID = "X-Scanipy-Org-Id"
HEADER_USER_ID = "X-Scanipy-User-Id"

# --- RBAC roles (CLAR-DEPLOY-12 RESOLVED; DOC-API §2.6) ------------------------
Role = Literal["org-admin", "org-viewer", "scanner"]

# The literal X-Scanipy-User-Id value carried by scanner tokens (DOC-CMP-CP-01
# §3.1: "For scanner tokens the header is the literal string 'scanner'").
SCANNER_USER_ID = "scanner"

# --- Reserved error codes CP-01 may emit (DOC-API §6.1) -----------------------
ERROR_UNAUTHENTICATED = "unauthenticated"
ERROR_ROLE_DENIED = "role_denied"
ERROR_ORG_MISMATCH = "org_mismatch"
ERROR_TENANT_ISOLATION_VIOLATION = "tenant_isolation_violation"
ERROR_NOT_FOUND = "not_found"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_LLM_QUOTA_EXCEEDED = "llm_quota_exceeded"
ERROR_INVARIANT_INV2_VIOLATION = "invariant_inv2_violation"

# Maps each reserved code to its HTTP status (DOC-API §6.1).
ERROR_HTTP_STATUS: dict[str, int] = {
    ERROR_UNAUTHENTICATED: 401,
    ERROR_ROLE_DENIED: 403,
    ERROR_ORG_MISMATCH: 403,
    ERROR_TENANT_ISOLATION_VIOLATION: 403,
    ERROR_NOT_FOUND: 404,
    ERROR_RATE_LIMITED: 429,
    ERROR_LLM_QUOTA_EXCEEDED: 429,
    ERROR_INVARIANT_INV2_VIOLATION: 422,
}

# --- Resources and actions exposed to the RBAC gate ---------------------------
# Resource names mirror the route families the AC-CP-01a test parametrizes over
# (DOC-API §4: scans / codebases / findings). Actions are the verb→capability
# projection from the §2.6 matrix.
Resource = Literal["scans", "snapshots", "codebases", "findings", "attestations"]
Action = Literal["read", "submit", "create", "update_creds", "patch_status"]

# RBAC matrix verbatim from DOC-API §2.6 (CLAR-DEPLOY-12). A role may take an
# action on a resource iff the action is in the set below. "own only" scoping
# (scanner) is enforced at the data-row layer by RLS, not here (DOC-CMP-CP-01
# §3.1); the role gate only checks the capability.
RBAC: dict[Role, dict[Resource, frozenset[Action]]] = {
    "org-admin": {
        "scans": frozenset({"submit", "read"}),
        "snapshots": frozenset({"submit", "read"}),
        "codebases": frozenset({"create", "read", "update_creds"}),
        "findings": frozenset({"read", "patch_status"}),
        "attestations": frozenset({"read"}),
    },
    "org-viewer": {
        "scans": frozenset({"read"}),
        "snapshots": frozenset({"read"}),
        "codebases": frozenset({"read"}),
        "findings": frozenset({"read"}),
        "attestations": frozenset({"read"}),
    },
    "scanner": {
        "scans": frozenset({"submit", "read"}),
        "snapshots": frozenset({"submit", "read"}),
        "codebases": frozenset(),  # scanner has no codebase capability at all.
        "findings": frozenset({"read"}),
        "attestations": frozenset({"read"}),
    },
}

__all__ = [
    "ERROR_HTTP_STATUS",
    "ERROR_INVARIANT_INV2_VIOLATION",
    "ERROR_LLM_QUOTA_EXCEEDED",
    "ERROR_NOT_FOUND",
    "ERROR_ORG_MISMATCH",
    "ERROR_RATE_LIMITED",
    "ERROR_ROLE_DENIED",
    "ERROR_TENANT_ISOLATION_VIOLATION",
    "ERROR_UNAUTHENTICATED",
    "HEADER_ORG_ID",
    "HEADER_USER_ID",
    "RBAC",
    "SCANNER_USER_ID",
    "SESSION_VAR_ORG_ID",
    "SESSION_VAR_ROLE",
    "SESSION_VAR_USER_ID",
    "Action",
    "Resource",
    "Role",
]

"""CMP-CP-01 — Multi-tenant scan API guard (pure, offline-testable core).

DOC-CMP-CP-01 §3.1 specifies the production surface as a FastAPI middleware stack
(``Request, call_next``). FastAPI is not in the analysis environment, and the
guard logic is independent of the web framework, so the framework-agnostic seam
is exposed here: :class:`CPGuard` operates on plain values (a :class:`JWTClaims`
dataclass, a header mapping, a route's resource + verb) and returns either
``None`` (request may proceed) or a typed :class:`ErrorEnvelope` short-circuit.
A thin FastAPI adapter (the four ``async def ...(request, call_next)`` middlewares
of §3.1) is deliberately **not** built here — no test in scope exercises it, and
wiring it would require an un-pinned framework dependency.

Three CLAR-DEPLOY-16 / DOC-CMP-CP-01 §9 cross-tenant layers are enforced:

  * **Layer 1** — ``X-Scanipy-Org-Id`` header ≠ ``jwt_claims.org_id`` →
    ``403 org_mismatch`` (the AC-CP-01a observation point).
  * **Layer 2** — caller scoped to org A reaches for an org-B resource id;
    :class:`OrgScopedStore` (the in-memory RLS stand-in) returns nothing, so the
    handler sees ``not_found`` and never leaks org-B's existence.
  * **Layer 3** — a query issued before the session-variable setter ran raises
    :class:`TenantIsolationError` (``current_setting('app.org_id', true) IS NULL``
    RLS backstop), which the API maps to ``403 tenant_isolation_violation``.

Everything fails closed: any inability to positively confirm same-tenant +
sufficient-role access results in denial, never in a pass-through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from services.control_plane.constants import (
    ERROR_HTTP_STATUS,
    ERROR_NOT_FOUND,
    ERROR_ORG_MISMATCH,
    ERROR_ROLE_DENIED,
    ERROR_TENANT_ISOLATION_VIOLATION,
    ERROR_UNAUTHENTICATED,
    RBAC,
    SCANNER_USER_ID,
    Action,
    Resource,
    Role,
)

# Verb → action projection per the DOC-API §2.6 matrix. The route layer resolves
# (method, resource) to the capability the RBAC gate checks. "submit"/"create"
# both arise from POST and are disambiguated per resource below.
_POST_ACTION: dict[Resource, Action] = {
    "scans": "submit",
    "snapshots": "submit",
    "codebases": "create",
    "findings": "patch_status",
    "attestations": "read",
}


def _action_for(method: str, resource: Resource) -> Action:
    """Project an HTTP verb + resource onto the capability the role must hold.

    DELETE has no capability cell in the §2.6 matrix for any role on any
    resource, so it is projected onto a capability no role holds, guaranteeing
    a ``role_denied`` (fail-closed: an unmapped verb is never silently allowed).
    """
    verb = method.upper()
    if verb == "GET":
        return "read"
    if verb in ("POST", "PUT"):
        return _POST_ACTION[resource]
    if verb == "PATCH":
        return "patch_status"
    # DELETE / unknown verbs: project onto a non-grantable action. No role has
    # "update_creds" on findings/scans, and the matrix never grants delete, so
    # this always denies (DOC-API §2.6 — delete is not a capability in v3.2).
    return "update_creds"


class TenantIsolationError(RuntimeError):
    """A query was attempted before the RLS session variables were bound.

    Mirrors the DB-side ``current_setting('app.org_id', true) IS NULL`` rejection
    (DOC-CMP-CP-01 §3.1 / §7, CLAR-DEPLOY-16 layer-2 backstop). Raised by
    :class:`OrgScopedStore` when ``query``/``query_one`` runs before
    ``set_session`` — the application maps it to ``403
    tenant_isolation_violation``. It is a programming bug, never an expected
    control-flow path, so it is surfaced loudly rather than swallowed.
    """


@dataclass(frozen=True)
class JWTClaims:
    """Validated Auth0 claims for the request (DOC-CMP-CP-01 §3.1).

    JWT signature / JWKS validation is performed by the (out-of-scope here)
    ``validate_jwt`` middleware; this object is its trusted output. ``user_id``
    is the literal ``"scanner"`` for scanner tokens (DOC-CMP-CP-01 §3.1 step 4).
    """

    user_id: str
    org_id: str
    role: Role
    issued_at: int
    expires_at: int


@dataclass(frozen=True)
class ErrorEnvelope:
    """The shared error shape from DOC-API §6.

    ``http_status`` is derived from ``error_code`` via the §6.1 reserved table so
    callers never have to re-derive it. ``message`` carries no PII (DOC-API §6).
    """

    error_code: str
    message: str
    trace_id: str
    details: dict[str, str] | None = None

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS[self.error_code]


# --- In-memory RLS stand-in ---------------------------------------------------

_Row = TypeVar("_Row")


@dataclass
class _OrgRow(Generic[_Row]):
    org_id: str
    payload: _Row


@dataclass
class OrgScopedStore(Generic[_Row]):
    """In-memory store that simulates PostgreSQL row-level security.

    Models the CLAR-DEPLOY-16 layer-2 backstop without a live database:

      * :meth:`set_session` binds the request's ``app.org_id`` (the value
        ``validate_tenancy_header`` would ``SET LOCAL`` on the PG connection).
      * :meth:`query` / :meth:`query_one` return **only** rows whose ``org_id``
        equals the bound session org — cross-tenant rows are structurally
        unreachable, exactly as an RLS ``USING (org_id = current_setting(...))``
        predicate enforces.
      * A query issued **before** ``set_session`` raises
        :class:`TenantIsolationError` (the ``app.org_id IS NULL`` rejection).

    The store is fail-closed: an unset or cleared session yields zero rows /
    a hard error, never an unscoped read.
    """

    _rows: dict[str, _OrgRow[_Row]] = field(default_factory=dict)
    _session_org_id: str | None = field(default=None)

    def seed(self, row_id: str, org_id: str, payload: _Row) -> None:
        """Insert a row owned by ``org_id`` (test/fixture setup helper)."""
        self._rows[row_id] = _OrgRow(org_id=org_id, payload=payload)

    def set_session(self, org_id: str) -> None:
        """Bind ``app.org_id`` for subsequent queries (CP-01's SET LOCAL)."""
        self._session_org_id = org_id

    def clear_session(self) -> None:
        """Drop the bound session org (connection returned to the pool)."""
        self._session_org_id = None

    def query(self) -> list[_Row]:
        """Return every row visible to the bound session org (RLS USING)."""
        org_id = self._require_session()
        return [r.payload for r in self._rows.values() if r.org_id == org_id]

    def query_one(self, row_id: str) -> _Row | None:
        """Return ``row_id`` iff it exists AND belongs to the session org.

        A row owned by another tenant is indistinguishable from a non-existent
        row (returns ``None``) — the caller surfaces ``404 not_found`` and never
        leaks the foreign row's existence (DOC-CMP-CP-01 §9 layer 2).
        """
        org_id = self._require_session()
        row = self._rows.get(row_id)
        if row is None or row.org_id != org_id:
            return None
        return row.payload

    def _require_session(self) -> str:
        if self._session_org_id is None:
            raise TenantIsolationError(
                "query attempted before app.org_id was set (CLAR-DEPLOY-16 layer-2 RLS backstop)"
            )
        return self._session_org_id


# --- The guard ----------------------------------------------------------------


@dataclass
class CPGuard:
    """Framework-agnostic multi-tenant request guard (CMP-CP-01).

    Composes the tenancy-header check (layer 1) and the RBAC role gate. The
    layer-2/3 data-isolation guarantees live in :class:`OrgScopedStore`; the
    application wires ``set_session`` immediately after :meth:`authorize_request`
    returns ``None`` so the store and the role gate share one tenant identity.
    """

    def check_tenancy_header(
        self,
        claims: JWTClaims,
        headers: dict[str, str],
        *,
        route: str,
        trace_id: str,
    ) -> ErrorEnvelope | None:
        """Layer 1 — header ↔ JWT-claim agreement (DOC-CMP-CP-01 §3.1).

        Returns ``None`` to proceed, or an :class:`ErrorEnvelope`:

          * missing ``X-Scanipy-Org-Id`` / ``X-Scanipy-User-Id`` →
            ``401 unauthenticated``;
          * ``X-Scanipy-Org-Id`` ≠ ``claims.org_id`` → ``403 org_mismatch``
            (the AC-CP-01a observation point; a real deployment also emits a WARN
            OTel event with ``{header_org_id, jwt_org_id, user_id, route}``);
          * dashboard token whose ``X-Scanipy-User-Id`` ≠ ``claims.user_id``, or
            scanner token whose header is not the literal ``"scanner"`` →
            ``403 org_mismatch`` (user-identity disagreement is a cross-tenant
            signal).
        """
        header_org = _ci_get(headers, "X-Scanipy-Org-Id")
        header_user = _ci_get(headers, "X-Scanipy-User-Id")
        if header_org is None or header_user is None:
            return ErrorEnvelope(
                error_code=ERROR_UNAUTHENTICATED,
                message="missing tenancy header",
                trace_id=trace_id,
            )
        if header_org != claims.org_id:
            # AC-CP-01a observation point. details carry only non-PII ids.
            return ErrorEnvelope(
                error_code=ERROR_ORG_MISMATCH,
                message="tenancy header does not match authenticated org",
                trace_id=trace_id,
                details={
                    "header_org_id": header_org,
                    "jwt_org_id": claims.org_id,
                    "user_id": claims.user_id,
                    "route": route,
                },
            )
        expected_user = SCANNER_USER_ID if claims.role == "scanner" else claims.user_id
        if header_user != expected_user:
            return ErrorEnvelope(
                error_code=ERROR_ORG_MISMATCH,
                message="tenancy user header does not match authenticated user",
                trace_id=trace_id,
                details={"route": route, "user_id": claims.user_id},
            )
        return None

    def check_rbac(
        self,
        claims: JWTClaims,
        *,
        method: str,
        resource: Resource,
        trace_id: str,
    ) -> ErrorEnvelope | None:
        """RBAC role gate (DOC-API §2.6, verbatim matrix in ``constants.RBAC``).

        Returns ``None`` when ``claims.role`` holds the capability that
        ``(method, resource)`` projects to, else ``403 role_denied``. Fail-closed:
        an unknown role or unmapped resource denies.
        """
        required = _action_for(method, resource)
        granted = RBAC.get(claims.role, {}).get(resource, frozenset())
        if required not in granted:
            return ErrorEnvelope(
                error_code=ERROR_ROLE_DENIED,
                message="role lacks permission for this endpoint",
                trace_id=trace_id,
                details={
                    "role": claims.role,
                    "resource": resource,
                    "required_action": required,
                },
            )
        return None

    def authorize_request(
        self,
        claims: JWTClaims,
        headers: dict[str, str],
        *,
        method: str,
        resource: Resource,
        route: str,
        trace_id: str,
    ) -> ErrorEnvelope | None:
        """Run layer-1 tenancy then the RBAC gate, in normative order.

        Order matters (DOC-CMP-CP-01 §3.1 "Order is normative"): a cross-tenant
        request is rejected as ``org_mismatch`` before its role is even
        considered. Returns ``None`` only when the request may proceed — at which
        point the caller binds :meth:`OrgScopedStore.set_session` with
        ``claims.org_id`` so data-layer reads are tenant-scoped (layers 2/3).
        """
        tenancy = self.check_tenancy_header(claims, headers, route=route, trace_id=trace_id)
        if tenancy is not None:
            return tenancy
        return self.check_rbac(claims, method=method, resource=resource, trace_id=trace_id)

    def isolation_error_envelope(self, trace_id: str) -> ErrorEnvelope:
        """Map a bubbled :class:`TenantIsolationError` to its envelope (§7).

        A query that reached the DB without ``app.org_id`` set is a CP-01 bug;
        the layer-3 RLS backstop caught it. Surfaced as ``403
        tenant_isolation_violation`` (never as a successful unscoped read).
        """
        return ErrorEnvelope(
            error_code=ERROR_TENANT_ISOLATION_VIOLATION,
            message="query reached the data layer without a bound tenant",
            trace_id=trace_id,
        )

    def not_found_envelope(self, trace_id: str) -> ErrorEnvelope:
        """Envelope for a layer-2 cross-tenant miss (DOC-API §6.1 ``not_found``).

        Returned when :meth:`OrgScopedStore.query_one` yields ``None`` because the
        requested resource belongs to another tenant; the response does not
        distinguish "does not exist" from "not yours" (no existence leak).
        """
        return ErrorEnvelope(
            error_code=ERROR_NOT_FOUND,
            message="resource not found",
            trace_id=trace_id,
        )


def _ci_get(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup (HTTP header names are case-insensitive)."""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


__all__ = [
    "CPGuard",
    "ErrorEnvelope",
    "JWTClaims",
    "OrgScopedStore",
    "TenantIsolationError",
]

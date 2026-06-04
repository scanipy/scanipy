"""CMP-CP-01 — per-request RLS session binding (``acquire_for_request``).

This is the production session-binding seam the RLS migration explicitly defers
to CMP-CP-01:

    db/migrations/versions/20260524_0002_rls_policies.py (≈line 29):
    "The application-side setter contract (db/session.py) is a CMP-CP-01
     follow-up and is out of scope for this migration."

The migration installed the DB-side half of the CLAR-DEPLOY-16 layer-2 backstop:
every multi-tenant table has ``FORCE ROW LEVEL SECURITY`` plus a tenant-isolation
policy keyed on ``current_setting('app.org_id', true)``. A connection that
reaches a query **without** ``app.org_id`` bound evaluates the predicate against
``NULL`` → zero rows on SELECT / RLS violation on write. This module is the
application-side contract that binds those session variables **per request, on a
pooled connection, with no possibility of a stale binding escaping to the next
request**.

The mechanism (DOC-DB §3.2, DOC-CMP-CP-01 §3.1):

  * Each request runs inside its own transaction (``BEGIN`` … ``COMMIT`` /
    ``ROLLBACK``).
  * Inside that transaction we issue ``SET LOCAL app.org_id`` /
    ``app.user_id`` / ``app.role``. ``SET LOCAL`` (NOT plain ``SET``) scopes the
    binding to the transaction; at ``COMMIT`` / ``ROLLBACK`` PostgreSQL discards
    it. The next request that checks out the same pooled connection therefore
    starts with ``app.org_id`` **unbound** and must re-bind, or RLS returns zero
    rows. A stale binding cannot leak across requests because the transaction
    boundary is the binding boundary.
  * Binding is done via ``set_config(name, value, is_local := true)`` — a real
    function call taking a **bind parameter** for the value, so the org id can
    never be string-interpolated into SQL (injection-proof). ``is_local = true``
    is the function-call equivalent of ``SET LOCAL``; ``false`` would be the
    forbidden session-wide ``SET`` (the exact bug this seam exists to prevent).

This module is **framework-light and driver-light by design** (HARD CONSTRAINT
"do not add new heavy deps"): it depends only on DB-API 2.0 / PEP 249 surface
(``connection.cursor()``, ``cursor.execute(sql, params)``, ``connection.commit``
/ ``rollback``), expressed as the structural :class:`Connection` protocol below.
``psycopg2`` connections satisfy it directly; so does any DB-API driver and the
in-test fake. The framework-agnostic seam DOC-CMP-CP-01 §3.1 needs is provided
here: :func:`authorize_request_for_binding` (the tenancy + RBAC decision) and
:func:`acquire_for_request` (the per-request binding + transaction lifecycle).
The §3.1 FastAPI ``Request``/``call_next`` ASGI middleware that *wraps* this seam
is deliberately NOT built here: no test in scope exercises it and FastAPI is not
a pinned dependency. Per RULE-4 (no invented scope), wiring an unpinned web
framework is filed as a CLAR-DEPLOY (FastAPI request-lifecycle adapter for the
CP-01 middleware stack) rather than guessed at here.

Provenance / RULE-6 note: CP-01 is a **non-emitting** component (DOC-CMP-CP-01
§8). It writes no ``findings`` / ``provenance_records`` rows, so the four
provenance fields (``origin``, ``S_version``, ``env_digest``, ``cpg_order_hash``)
are stamped downstream by CMP-ORCH-03 / CMP-FND-01..03, not here. This seam's
threading responsibility is solely to bind ``app.org_id`` / ``app.user_id`` /
``app.role`` so the RLS-scoped downstream writes inherit the correct tenant.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol, runtime_checkable

from services.control_plane.constants import (
    SCANNER_USER_ID,
    SESSION_VAR_ORG_ID,
    SESSION_VAR_ROLE,
    SESSION_VAR_USER_ID,
    Role,
)

# The control-plane guard is the framework-agnostic authorization seam; the thin
# adapter below composes it with this binding seam.
from services.control_plane.guard import CPGuard, ErrorEnvelope, JWTClaims

__all__ = [
    "Connection",
    "Cursor",
    "SessionBindingError",
    "acquire_for_request",
    "authorize_request_for_binding",
    "request_binding_args",
]


# A defensive allow-list for the *names* of the GUCs we bind. Names are never
# user-controlled (they come from the constants module), so this is belt-and-
# suspenders: ``set_config`` takes the name as a bind parameter too, but a custom
# GUC name must be a valid ``namespace.name`` identifier and we refuse anything
# that is not, so a future careless caller cannot smuggle a surprising setting in.
_GUC_NAME = re.compile(r"\A[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*\Z")


class SessionBindingError(RuntimeError):
    """Raised when a request session could not be bound to a tenant.

    Distinct from ``services.control_plane.guard.TenantIsolationError`` (which is
    the DB-side "query ran before any binding" backstop): this is the
    application-side refusal to *establish* a binding at all — e.g. an empty
    ``org_id`` or a malformed GUC name. Fail-closed: if we cannot positively bind
    a tenant, we raise rather than run the request unscoped.
    """


@runtime_checkable
class Cursor(Protocol):
    """Minimal DB-API 2.0 cursor surface this module uses.

    ``execute`` returns ``object`` (DB-API leaves the return unspecified — for
    ``psycopg2`` it is the cursor; we never consume it). ``params`` is an
    optional positional, matching the PEP 249 ``execute(operation[, parameters])``
    signature that ``psycopg2.cursor`` provides.
    """

    def execute(self, sql: str, params: tuple[str, ...] = ..., /) -> object: ...

    def close(self) -> None: ...


@runtime_checkable
class Connection(Protocol):
    """Minimal DB-API 2.0 connection surface (PEP 249).

    ``psycopg2.connection`` satisfies this structurally; so does any other
    DB-API driver and the in-test fake. We require only ``cursor()`` plus
    transaction control, so no concrete driver is imported here.

    DB-API 2.0 connections are **non-autocommit by default**: a transaction is
    implicitly open from the first statement until ``commit()`` / ``rollback()``.
    ``acquire_for_request`` relies on that implicit transaction to scope its
    ``SET LOCAL`` bindings, so it refuses to run on a connection in autocommit
    mode (see :func:`acquire_for_request`). The optional ``autocommit``
    attribute (psycopg2 / psycopg exposes it; pure DB-API does not) is consulted
    defensively when present.
    """

    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _validate_org_id(org_id: str) -> str:
    """Fail closed on an empty / whitespace tenant id (never bind a blank org)."""
    if not isinstance(org_id, str) or not org_id.strip():
        raise SessionBindingError(
            "refusing to bind a request session to an empty org_id "
            "(fail-closed: an unbound app.org_id makes RLS return zero rows)"
        )
    return org_id


def _bind_guc(cur: Cursor, name: str, value: str) -> None:
    """Bind one transaction-local GUC via ``set_config(name, value, true)``.

    ``set_config(setting_name, new_value, is_local)`` is the SQL-function form of
    ``SET``/``SET LOCAL``. ``is_local = true`` makes the assignment **transaction
    local**, exactly like ``SET LOCAL`` — discarded at COMMIT/ROLLBACK so it
    cannot survive on a recycled pooled connection. Both ``name`` and ``value``
    are passed as **bind parameters**, so neither is string-interpolated into the
    statement: the tenant id can never be a SQL-injection vector (contrast the
    naive ``cur.execute(f"SET LOCAL app.org_id = '{org_id}'")``).
    """
    if not _GUC_NAME.match(name):
        raise SessionBindingError(f"refusing to bind a non-identifier GUC name: {name!r}")
    cur.execute("SELECT set_config(%s, %s, true);", (name, value))


@contextmanager
def acquire_for_request(
    conn: Connection,
    *,
    org_id: str,
    user_id: str,
    role: Role,
) -> Iterator[Connection]:
    """Bind ``conn`` to a tenant for exactly one request, then unbind on exit.

    Usage (the per-request RLS binding contract)::

        with pool.connection() as conn:                 # pooled checkout
            with acquire_for_request(conn, org_id=..., user_id=..., role=...):
                # every query on `conn` here is RLS-scoped to `org_id`
                run_request_handler(conn)
            # on exit the transaction is committed (or rolled back on error);
            # SET LOCAL is discarded, so the connection returns to the pool with
            # NO tenant binding. The next request MUST re-bind or RLS denies it.

    Semantics:

      * Relies on the DB-API 2.0 **implicit** transaction (PEP 249: a transaction
        is open from the first statement until ``commit``/``rollback``). It issues
        ``SET LOCAL app.org_id`` / ``app.user_id`` / ``app.role`` via
        :func:`_bind_guc` *before yielding*, so the very first query the handler
        runs is already tenant-scoped (DOC-DB §3.4 "before any query runs"). It
        does **not** issue a raw SQL ``BEGIN`` — mixing a SQL ``BEGIN`` with a
        method-level ``commit()`` is config-dependent (under a driver's
        autocommit mode the ``commit()`` is a no-op and the SQL ``BEGIN`` opens a
        transaction that never closes, so ``SET LOCAL`` would persist and leak
        across requests). The implicit-transaction contract is the portable,
        leak-free one.
      * On clean exit: ``commit()`` — ends the transaction (discarding the
        ``SET LOCAL`` bindings) and durably persists any writes the handler made
        under the bound tenant (RLS ``WITH CHECK`` already enforced the tenant on
        each write).
      * On any exception (including a bubbled RLS / isolation error):
        ``rollback()`` and re-raise — never commit a partially-applied,
        possibly-cross-tenant request. Fail-closed.
      * ``SET LOCAL`` (not ``SET``) guarantees the binding is **transaction
        scoped**: commit/rollback discards it, so no stale ``app.org_id`` escapes
        to the next request that reuses this pooled connection. This is the
        precise property the integration test's discriminating leg falsifies.

    **Autocommit is refused (fail-closed).** If the connection exposes an
    ``autocommit`` attribute that is truthy, there is no enclosing transaction for
    ``SET LOCAL`` to scope to: the binding would either error or leak into the
    next request. Rather than bind into that hole, the seam raises
    :class:`SessionBindingError` before any query runs. A connection pool MUST
    hand out non-autocommit connections to the request path.

    The ``scanner`` role's ``user_id`` is the literal ``"scanner"`` (DOC-CMP-CP-01
    §3.1 step 4); callers pass ``JWTClaims.user_id`` through unchanged — the guard
    already normalised it — so this function does not re-derive it.
    """
    org_id = _validate_org_id(org_id)
    # Fail-closed: SET LOCAL needs an enclosing transaction. Autocommit removes it.
    if getattr(conn, "autocommit", False):
        raise SessionBindingError(
            "refusing to bind a request session on an autocommit connection: "
            "SET LOCAL has no enclosing transaction to scope to and would leak "
            "across requests (the request path must use non-autocommit pooled "
            "connections)"
        )
    cur = conn.cursor()
    try:
        # No raw SQL BEGIN: rely on the DB-API implicit transaction so the binding
        # boundary IS the transaction boundary that conn.commit()/rollback() ends.
        _bind_guc(cur, SESSION_VAR_ORG_ID, org_id)
        _bind_guc(cur, SESSION_VAR_USER_ID, user_id)
        _bind_guc(cur, SESSION_VAR_ROLE, role)
        yield conn
    except BaseException:
        # Roll back on ANY failure (including KeyboardInterrupt/SystemExit, and a
        # binding error before the yield) so a half-applied request never commits
        # and the SET LOCAL bindings are discarded; then re-raise — the seam never
        # swallows a request error.
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        cur.close()


def authorize_request_for_binding(
    guard: CPGuard,
    claims: JWTClaims,
    headers: dict[str, str],
    *,
    method: str,
    resource: str,
    route: str,
    trace_id: str,
) -> ErrorEnvelope | None:
    """Thin adapter: the authorization half of the DOC-CMP-CP-01 §3.1 wiring.

    This is the framework-agnostic composition the §3.1 FastAPI middleware would
    perform per request, expressed without the ASGI ``Request``/``call_next``
    surface (no FastAPI dependency — see module docstring). It runs **only** the
    tenancy-header (layer-1) + RBAC gate; it does **not** open a transaction or
    bind the session. Binding is the caller's responsibility, performed via
    :func:`acquire_for_request` with :func:`request_binding_args` *after* this
    function returns ``None`` — keeping the transaction lifecycle owned by the
    ``with`` block (a function cannot both return an envelope and yield a bound
    connection). Canonical caller shape::

        envelope = authorize_request_for_binding(guard, claims, headers, ...)
        if envelope is not None:
            return error_response(envelope.http_status, envelope)   # short-circuit
        with acquire_for_request(conn, **request_binding_args(claims)):
            return run_route_handler(conn)                          # tenant-bound

    Returns ``None`` exactly when the request passes the tenancy-header / RBAC
    gate (the caller may then bind + run the handler); otherwise returns the
    guard's :class:`ErrorEnvelope`, leaving ``conn`` untouched (no transaction
    opened), so a denied request never reaches the data layer.

    Order is normative (DOC-CMP-CP-01 §3.1): authorize FIRST — a cross-tenant or
    role-denied request is rejected before any binding is attempted, so the
    caller never opens a transaction for a request it is going to deny.
    """
    # ``resource`` is validated against the RBAC matrix inside the guard; we pass
    # it through as the typed ``Resource`` the guard expects. mypy sees ``str``
    # here for adapter ergonomics; the guard's own lookup is fail-closed on an
    # unknown resource (returns role_denied), so an invalid resource cannot pass.
    return guard.authorize_request(
        claims,
        headers,
        method=method,
        resource=resource,  # type: ignore[arg-type]
        route=route,
        trace_id=trace_id,
    )


def request_binding_args(claims: JWTClaims) -> dict[str, str]:
    """Project validated claims onto the ``acquire_for_request`` kwargs.

    Single source of the (org_id, user_id, role) triple a caller binds, so
    authorization (``CPGuard``) and binding (``acquire_for_request``) can never
    drift onto different tenant identities. ``user_id`` is the literal
    ``"scanner"`` for scanner tokens (DOC-CMP-CP-01 §3.1 step 4); for dashboard
    roles it is the JWT ``sub``.
    """
    user_id = SCANNER_USER_ID if claims.role == "scanner" else claims.user_id
    return {"org_id": claims.org_id, "user_id": user_id, "role": claims.role}

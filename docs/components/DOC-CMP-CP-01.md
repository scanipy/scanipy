# DOC-CMP-CP-01 — Multi-tenant scan API guard

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-01` (Purpose, AC-CP-01a)
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`
- `docs/cross-cutting/DOC-API.md` (§2 auth, §2.5 tenancy header, §2.6 RBAC, §6 error envelope, §7 rate limits)
- `docs/cross-cutting/DOC-DB.md` (§3.2 session-variable scheme — CLAR-DB-02 DEFERRED working assumption)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-10 Auth0; CLAR-DEPLOY-12 RBAC roles; CLAR-DEPLOY-14 LLM provider; CLAR-DEPLOY-16 isolation layers)
- `docs/cross-cutting/DOC-INV.md §3, §4, §5` (INV-1 routing, INV-2 versioned parameters, INV-3 ancillary)
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`

This document is the **implementation contract** for `CMP-CP-01`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-01` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | cross-cutting |
| Depends-On (build) | `CMP-CP-03` (`WBS.md §20`) |
| Depends-On (runtime read) | `CMP-CP-02` (KMS handle for downstream cred decryption resolution path), `CMP-CP-04` (JWT verification middleware emits the role claim consumed here). Both are **runtime read coupling**, not build-order Depends-On. |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-1** (routing-only; CP-01 never stamps `origin` but rejects request shapes that would skip it); **INV-2** (validates `S_version` against the registered spec set on every scan submission); **INV-3** ancillary (rejects LLM-tampered specs by allowing only pinned `S_version` values to pass through). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-01`):**

> Require `X-Scanipy-Org-Id` with `X-Scanipy-User-Id`; scope every query to the org; enforce RBAC in the API layer.

**Operational role.** `CMP-CP-01` is the **first hop** for every authenticated request to the Scanipy v3.2 control plane. It is a FastAPI middleware stack that runs before any route handler. It validates the JWT (from Auth0 per CLAR-DEPLOY-10), enforces the tenancy-header / JWT-claim agreement, sets the PostgreSQL session variables that back RLS (`DOC-DB.md §3.2`, CLAR-DB-02 DEFERRED), and enforces RBAC and per-tenant rate quotas. It is the **only** layer in the system permitted to map an inbound HTTP request to an `org_id` for downstream RLS-scoped reads; every downstream component reads `app.org_id` from the connection-level setting that CP-01 wrote, and a missing or mismatched setting causes RLS to return zero rows (the CLAR-DEPLOY-16 layer-2 backstop).

CP-01 does **not** authenticate worker callbacks (HMAC-bearer per `DOC-API.md §2.3`) and does **not** authenticate webhook ingress (per-provider signatures per `DOC-API.md §2.4`). Both are explicitly out of CP-01's authentication path; they enter the application via separate guards documented in `CMP-ORCH-01` and `CMP-SCM-01..03`.

---

## 3. Interface contract

### 3.1 FastAPI middleware surface

`CMP-CP-01` is a stack of four middlewares, applied in order. Each is a callable returning `Awaitable[Response]` that either short-circuits with an error or forwards to the next layer.

```python
class CPGuard:
    async def validate_jwt(request: Request, call_next) -> Response: ...
    async def validate_tenancy_header(request: Request, call_next) -> Response: ...
    async def enforce_rbac_role(request: Request, route: APIRoute, call_next) -> Response: ...
    async def enforce_quota(request: Request, call_next) -> Response: ...
```

Order is normative; reordering changes failure semantics.

#### `validate_jwt`

- Input: `Authorization: Bearer <jwt>` header.
- Behavior: validate signature against Auth0 JWKS (cached, with rotation per Auth0 key-rollover policy); validate `iss`, `aud`, `exp`, `nbf`; extract claims `sub` (user_id), `https://scanipy.io/org_id`, `https://scanipy.io/role ∈ {org-admin, org-viewer, scanner}`.
- Output: attaches `request.state.jwt_claims` (typed object below).
- Failure: `401 unauthenticated` per `DOC-API.md §6.1`.

```python
@dataclass(frozen=True)
class JWTClaims:
    user_id: str                       # uuid; from `sub`
    org_id: str                        # uuid; from custom claim
    role: Literal["org-admin", "org-viewer", "scanner"]
    issued_at: int                     # iat
    expires_at: int                    # exp
```

#### `validate_tenancy_header`

- Input: headers `X-Scanipy-Org-Id`, `X-Scanipy-User-Id`.
- Behavior:
  1. Both headers MUST be present. Missing → `401 unauthenticated`.
  2. `X-Scanipy-Org-Id` MUST equal `request.state.jwt_claims.org_id`. Mismatch → `403 org_mismatch` AND log to OpenTelemetry at `WARN` (CLAR-DEPLOY-07) with attributes `{header_org_id, jwt_org_id, user_id, route}`. This is the AC-CP-01a observation point.
  3. For dashboard tokens (`role ∈ {org-admin, org-viewer}`), `X-Scanipy-User-Id` MUST equal `jwt_claims.user_id`.
  4. For scanner tokens (`role = scanner`), `X-Scanipy-User-Id` is the literal string `"scanner"`.
- Side effect (CRITICAL — INV-2 setup): on the PostgreSQL connection checked out for this request, issue `SET LOCAL app.org_id = '<uuid>'; SET LOCAL app.user_id = '<uuid|scanner>'; SET LOCAL app.role = '<role>';` before any query runs (`DOC-DB.md §3.2`). The DB connection-pool wrapper MUST surface a runtime error if any query is attempted before this setter runs (DB-side: `current_setting('app.org_id', true) IS NULL` makes RLS reject the row).
- Failure: `403 org_mismatch` (cross-tenant attempt; AC-CP-01a) or `403 tenant_isolation_violation` (RLS-rejected query bubbling up).

#### `enforce_rbac_role`

The RBAC enforcement table is taken **verbatim** from `DOC-API.md §2.6` (CLAR-DEPLOY-12 RESOLVED — `org-admin`, `org-viewer`, `scanner`):

| Role | Scans | Snapshots | Codebases | Findings (read) | Findings (PATCH status) | Attestations |
|---|---|---|---|---|---|---|
| `org-admin` | submit, read | submit, read | create, read, update creds | yes | yes | read |
| `org-viewer` | read | read | read (no creds) | yes | no | read |
| `scanner` | submit, read own | submit, read own | no | yes (own scan) | no | read (own) |

A request whose role lacks the right for the matched FastAPI route returns `403 role_denied` per `DOC-API.md §6.1`. The mapping `route → required_role_set` is declared per-route via a `requires_role(...)` decorator and is enforced by `enforce_rbac_role` after the route has been resolved.

`scanner` "own only" scoping (rightmost column) is enforced at the persistence layer via RLS plus an additional WHERE clause on `scans.submitted_by_user_id`; CP-01 verifies the role gate, the DB enforces the data-row gate.

#### `enforce_quota`

Two budget axes per `DOC-API.md §7`:

```python
def enforce_quota(request: Request, claims: JWTClaims) -> None:
    # general API token bucket per org_id (sustained 60 RPS, burst 200 RPS for 5s)
    # see CLAR-SLA-02 DEFERRED — numeric defaults are working-assumption values from DOC-API.md §7.1
    bucket = self._token_bucket(claims.org_id)
    if not bucket.consume(1):
        raise QuotaExceeded(error_code="rate_limited", retry_after_sec=bucket.reset_in())
    # llm-bearing routes: PATCH /findings re-triggers triage if LLM_TRIAGE=on
    if route.is_llm_bearing:
        llm_bucket = self._llm_bucket(claims.org_id)
        if not llm_bucket.consume(1):
            raise QuotaExceeded(error_code="llm_quota_exceeded", retry_after_sec=...)
```

Numeric defaults are **DEFERRED in CLAR-SLA-02**. Working-assumption values from `DOC-API.md §7.1/§7.2`:

- General: sustained 60 RPS per `org_id`, burst 200 RPS for 5 s, drained.
- Per-endpoint caps: `POST /api/v1/scans` 600/hour per org; `POST /snapshots` 1200/hour per org; webhooks uncapped.
- LLM bearing (server-side; per CLAR-DEPLOY-14 vendor is `claude-sonnet-4-6`): RPM and TPD per tenant — exact numbers TBD; budgets must exist and emit `429 llm_quota_exceeded` when crossed.

Headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

### 3.2 INV-2 / INV-3-ancillary spec gate on scan submission

For `POST /api/v1/scans`, CP-01 additionally validates the request body's `S_version` (if supplied) before forwarding to `CMP-ORCH-01`:

```python
def validate_s_version(org_id: str, s_version: str | None) -> str:
    """Return the S_version that this scan will run under, or raise 422."""
    if s_version is None:
        return latest_accepted_S_version(org_id)   # default
    # The submitted S_version MUST exist in `spec_versions` and be visible to this org.
    # `spec_versions` RLS (DOC-DB.md §4.9) already constrains visibility:
    # scope='global' rows are universally readable; scope='customer' follows app.org_id.
    if not spec_version_exists_and_visible(org_id, s_version):
        raise InvariantViolation("invariant_inv2_violation",
                                 "S_version not registered or not visible to org")
    return s_version
```

This is the **INV-3-ancillary discharge**: an LLM-tampered or unauthored spec body that bypasses the e-process gate cannot enter `F` because CP-01 only accepts `S_version` strings that resolve to a row already committed to `spec_versions` via the `CMP-TRI-02` acceptance path. Triage cannot inject specs through the API; the only ingress for new specs is `CMP-TRI-02`'s acceptance gate.

### 3.3 Error envelope

All CP-01 failures use the shared envelope from `DOC-API.md §6`:

```json
{
  "error_code": "<see DOC-API §6.1>",
  "message": "string (no PII)",
  "trace_id": "W3C trace_id (equals X-Scanipy-Trace-Id)",
  "details": { "object | null" }
}
```

Reserved codes CP-01 may emit: `unauthenticated`, `role_denied`, `org_mismatch`, `tenant_isolation_violation`, `invariant_inv2_violation`, `rate_limited`, `llm_quota_exceeded`.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `Authorization: Bearer <jwt>` | Inbound HTTP | Validated against Auth0 JWKS; signature + iss + aud + exp + nbf. |
| `X-Scanipy-Org-Id`, `X-Scanipy-User-Id` | Inbound HTTP | RLS-binding; equality-checked against JWT claims. |
| JWT claims `sub`, `org_id`, `role` | Auth0 custom claims | Per CLAR-DEPLOY-12, role ∈ `{org-admin, org-viewer, scanner}`. |
| Route metadata `requires_role(...)`, `is_llm_bearing` | Declared per-route | Used by `enforce_rbac_role` and `enforce_quota`. |
| `spec_versions` row visibility | RLS-scoped SQL after session vars set | Backs `validate_s_version`. |

### 4.2 Outputs

| Output | Consumer | Contract |
|---|---|---|
| `request.state.jwt_claims: JWTClaims` | Downstream route handlers (ORCH-01, FND-01, etc.) | Single source of `org_id` for the request. |
| `SET LOCAL app.org_id`, `app.user_id`, `app.role` on the request's PG connection | All downstream SQL | Applied at connection-checkout; RLS depends on it (§3.1). |
| `X-RateLimit-*` response headers | Client | Quota visibility. |
| WARN-level OpenTelemetry events for `org_mismatch` | Observability stack | AC-CP-01a — cross-tenant attempts are logged with full context. |
| Error JSON envelope on failure | Client | `DOC-API §6`. |

### 4.3 Persistence touched (read-only)

| Table | Access | Purpose |
|---|---|---|
| `orgs` | SELECT | Org existence + `status` check (no INSERT/UPDATE from CP-01). |
| `memberships` | SELECT | Cross-check `(user_id, org_id, role)` if a stricter than-JWT verification is configured. |
| `spec_versions` | SELECT (RLS-scoped) | `validate_s_version`. |

CP-01 does NOT write any application table. The only state CP-01 manages is the in-memory token-bucket cache (per-process, with optional Redis backing for cross-process consistency — left as an implementation choice; not pinned by SDD).

---

## 5. Invariants touched

| Invariant | How `CMP-CP-01` discharges it | Test |
|---|---|---|
| **INV-1** (routing) | CP-01 does not stamp `origin` — that is `CMP-ORCH-03`. CP-01 enforces that every scan submission carries a body that downstream `CMP-ORCH-03` can correctly route into the partition. Specifically, no API path exposed by CP-01 can produce a finding-emitting flow that lacks a detector lookup (which is what derives `origin`). | (indirect; see `TST-INV-1-ORCH-03`) |
| **INV-2** (versioned parameters) | `validate_s_version` (§3.2) rejects `POST /api/v1/scans` requests whose `S_version` is not registered. Combined with `CMP-SNAP-01`'s `env_digest` stamping, this is the API-layer half of the "no unpinned analysis" invariant: a scan can only enter the pipeline if both `S_version` and `env_digest` are resolvable to pinned values. | `TST-AC-CP-01a [FORTHCOMING]` (negative test: unknown `S_version` rejected); `TST-INV-2-CP-01 [FORTHCOMING]` |
| **INV-3** (ancillary) | The only way a new spec enters `F` is via `CMP-TRI-02`'s e-process acceptance → INSERT into `spec_versions`. CP-01 will not accept `S_version` strings that bypass this path. This means an LLM-generated `proposed_specs` row cannot be invoked by a scan submission until the e-process accepts it as a pinned `spec_versions` row. (`DOC-INV.md §5`.) | (indirect; covered jointly by `TST-INV-3-TRI-02`) |
| **CLAR-DEPLOY-16 layer 2** | The session-variable setter is CP-01's mechanism for the RLS backstop. A connection that fails to receive `SET LOCAL app.org_id` produces zero rows on SELECT and an RLS-rejection on INSERT/UPDATE/DELETE (`DOC-DB.md §3.4`). | `TST-AC-CP-01a [FORTHCOMING]` (cross-org access denial) |

See `DOC-INV.md` for verbatim invariant statements; do not paraphrase them here.

---

## 6. Algorithm / data flow

```
client --HTTPS--> ALB --> FastAPI app
                              |
                              v
                     CPGuard.validate_jwt
                              | claims attached to request.state
                              v
                     CPGuard.validate_tenancy_header
                              | header == claim?  -> 403 org_mismatch (AC-CP-01a)
                              | side effect: SET LOCAL app.{org_id,user_id,role} on
                              |              the PG connection (CLAR-DB-02 working assumption)
                              v
                     FastAPI route resolution
                              |
                              v
                     CPGuard.enforce_rbac_role  (route-declared requires_role set)
                              | role denied?     -> 403 role_denied
                              v
                     CPGuard.enforce_quota (token bucket per org_id)
                              | exceeded?        -> 429 rate_limited / llm_quota_exceeded
                              v
                     (POST /scans only)
                     CPGuard.validate_s_version
                              | unregistered?    -> 422 invariant_inv2_violation
                              v
                     route handler  (ORCH-01, FND-01, ...)
                              | (all SQL runs under RLS predicates keyed on app.org_id)
                              v
                     response  (with X-RateLimit-* headers)
```

The middleware chain is non-bypassable: every authenticated route resolves through it. Worker-callback paths (HMAC-bearer) and webhook paths (provider-signature) attach **different** middleware stacks; their auth surfaces are documented in `DOC-API §2.3, §2.4` and are out of CP-01's scope.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| JWT signature invalid / expired | `validate_jwt` | `401 unauthenticated` | None. |
| Missing `X-Scanipy-Org-Id` | `validate_tenancy_header` | `401 unauthenticated` | None. |
| `X-Scanipy-Org-Id ≠ JWT claim` (cross-tenant attempt) | `validate_tenancy_header` | `403 org_mismatch` | **WARN** OTel event with `{header_org_id, jwt_org_id, user_id, route}`; this is the AC-CP-01a observation. |
| Role lacks endpoint permission | `enforce_rbac_role` | `403 role_denied` | DEBUG OTel event. |
| Rate budget exceeded | `enforce_quota` | `429 rate_limited` + `Retry-After` | Counter incremented. |
| LLM budget exceeded | `enforce_quota` | `429 llm_quota_exceeded` + `Retry-After` | Counter incremented. |
| `S_version` not registered | `validate_s_version` | `422 invariant_inv2_violation` | None. |
| Connection pool returns connection w/o `app.org_id` set | DB layer (RLS) | `403 tenant_isolation_violation` (bubbled) | Hard alarm: this is a programming bug — CP-01's session-variable setter failed to run. |
| Auth0 JWKS endpoint unreachable | `validate_jwt` | `503` service-unavailable; **fail closed** (never accept unverified tokens). | OTel alarm. |

**Fail-closed posture (CLAR-DEPLOY-16 backstop alignment).** Any internal error inside CP-01 results in request rejection (5xx with no downstream call), never in a request that bypasses tenancy enforcement. A bug that causes `SET LOCAL app.org_id` not to execute is caught by the DB-side RLS (zero rows / explicit rejection); CP-01 never trades enforcement for availability.

**CLAR-SLA-02 (DEFERRED) note.** Numeric rate-limit budgets are working-assumption values from `DOC-API §7`. Implementation MUST surface the configured numbers via the response headers and a `GET /internal/quotas` admin endpoint so that the eventual CLAR-SLA-02 resolution can drop in production-grade values without code changes.

---

## 8. Provenance threading

CP-01 itself **does not write provenance rows**. Its threading responsibility is to populate `request.state.jwt_claims.org_id` and to set `app.org_id` on the PG connection, which together cause every downstream emitter (`CMP-ORCH-03`, `CMP-FND-01..03`) to:

- INSERT into multi-tenant tables under the correct `org_id` (RLS `WITH CHECK` enforced).
- SELECT only rows the caller may see (RLS `USING` enforced).

| Field | CP-01 role |
|---|---|
| `org_id` | Sourced from JWT; injected as `app.org_id` session variable. Every persisted Finding row inherits this through RLS-bound writes. |
| `S_version` | Validated by `validate_s_version` for `POST /scans`; passed to `CMP-ORCH-01` body untouched. CP-01 does not generate `S_version`. |
| `env_digest` | Not touched by CP-01. Stamped by `CMP-SNAP-01` from the worker container image digest. |
| `origin` | Not touched by CP-01. Stamped by `CMP-ORCH-03` from `detector.engine`. |
| `cpg_order_hash` (+ annotation) | Not touched by CP-01. Set by `CMP-CORE-03`. |

**Must NOT touch.** CP-01 never writes to `findings`, `triage_scores`, `provenance_records`, `attestations`, `repartition_events`, or `spec_versions`. (The last is a SELECT-only relationship from CP-01; INSERTs are owned by `CMP-TRI-02`.)

---

## 9. Acceptance criteria cross-reference

The following AC is quoted **verbatim** from `SDD.md §10 CMP-CP-01`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CP-01a** | > A cross-org access attempt is denied (parameterized negative test, no IAM cross-bleed). | `TST-AC-CP-01a` `[FORTHCOMING]` |

Invariant tests cross-referenced:

- `TST-INV-2-CP-01 [FORTHCOMING]` — `POST /api/v1/scans` with an unregistered `S_version` rejected with `invariant_inv2_violation`.
- `TST-INV-1-ORCH-03 [FORTHCOMING]` (sibling) — verifies the routing chain that begins at CP-01.

The AC-CP-01a parameterized negative test must verify cross-tenant denial across **at least three layers** (CLAR-DEPLOY-16):

1. Header / JWT mismatch → CP-01 returns `403 org_mismatch`.
2. Forged tenancy header that matches the JWT but the JWT itself is for a different tenant → JWT validation already failed.
3. Connection-pool bug simulation: a route handler that runs SQL without the session-variable setter → RLS returns zero rows / RLS-violation error.

All three negative paths are within the AC-CP-01a falsifier's scope ("no IAM cross-bleed" — every layer of CLAR-DEPLOY-16 is independently exercised).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-01 |
|---|---|---|---|
| `CLAR-DEPLOY-10` | OIDC / SAML IdP integration | **RESOLVED** | Auth0; CP-01's `validate_jwt` validates Auth0 JWTs. |
| `CLAR-DEPLOY-12` | RBAC model surface | **RESOLVED** | Three roles per §3.1; table verbatim from `DOC-API §2.6`. |
| `CLAR-DEPLOY-14` | LLM provider + quota controls | **RESOLVED** (vendor); numeric budgets DEFERRED via `CLAR-SLA-02`. | `claude-sonnet-4-6`; `llm_quota_exceeded` enforced via `enforce_quota`. |
| `CLAR-DEPLOY-16` | Per-tenant isolation backstop | **RESOLVED** | CP-01 implements layer 2 (RLS session variable) of three layers. |
| `CLAR-DB-02` | RLS session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) | **DEFERRED** | Working assumption used here; ratification by SRE/DevOps + Security Analyst still pending. CP-01 implementation should keep the variable names in a single constants module so a rename is trivial. |
| `CLAR-SLA-02` | Numeric per-tenant rate-limit + LLM RPM/TPD budgets | **DEFERRED** | `DOC-API §7` working-assumption values used; production-grade numbers will drop in via configuration only. |
| `CLAR-MIGRATION-01` | v2 → v3.2 data migration | **DEFERRED** | Not blocking CP-01's design; migrated orgs must surface with the same JWT claim shape as new orgs. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |

No new CLAR-CP-01-* are filed by this document; every CP-01 contract is unambiguous given the cross-cutting refs.

---

## 11. References

- `SDD.md §10 CMP-CP-01` — verbatim AC.
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`.
- `docs/cross-cutting/DOC-API.md` — auth, RBAC, error envelope, rate-limit defaults.
- `docs/cross-cutting/DOC-DB.md §3` — RLS session-variable scheme.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-10, 12, 14, 16.
- `docs/cross-cutting/DOC-INV.md` §3, §4, §5 — INV-1/2/3 verbatim statements.
- `docs/components/DOC-CMP-CP-02.md` (sibling) — KMS handle that CP-01 indirectly depends on at runtime.
- `docs/components/DOC-CMP-CP-03.md` (sibling) — schema and RLS policies enforced via the session variable CP-01 sets.
- `.claude/rules/00-global.md` RULE-6 (provenance threading); `.claude/rules/02-provenance.md` (per-component table).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-01`.*

# DOC-CMP-CP-04 — Authentication (OIDC / SAML) + customer dashboard

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-04` (Purpose, AC-CP-04a, AC-CP-04b)
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`
- `docs/cross-cutting/DOC-API.md §2.1` (Auth0 → JWT bearer), §2.5 (tenancy header), §2.6 (RBAC summary)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-10 Auth0; CLAR-DEPLOY-12 three roles)
- `docs/cross-cutting/DOC-PARTITION.md §6` (Attestor pipelines — partition surfaced in the dashboard)
- `docs/cross-cutting/DOC-PROVENANCE.md` (the four threaded fields the dashboard renders)
- `docs/cross-cutting/DOC-INV.md §3 (INV-1)`, `§7 (INV-5)` (partition + conditional-canonicality annotation surfaced in UI)
- `.claude/rules/00-global.md` RULE-6, `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`

This document is the **implementation contract** for `CMP-CP-04`. A code-writing agent given only this file plus the cross-cutting refs above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-04` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | cross-cutting (web tier) |
| Depends-On | `CMP-CP-01` (API guard / RBAC), `CMP-FND-03` (signed provenance the dashboard renders) — per `WBS.md §20` |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched (ancillary) | **INV-1** (the findings view never visually blurs the two partitions — `AC-CP-04b`); **INV-5** (conditional-canonicality annotation surfaced beside `cpg_order_hash`). INV-3 is **not** discharged here — it is owned by `CMP-TRI-01..03` / `CMP-CP-05` (`DOC-INV §5`); CP-04 is at most a perimeter precondition (only authenticated tenants can reach the spec-acceptance API). |

`CMP-CP-04` is **not** an INV-1/INV-5 owner; the partition values and the annotation are produced upstream and the dashboard's responsibility is faithful, non-blurring presentation.

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-04`):**

> OIDC/SAML in `web/auth.ts`/`web/middleware.ts`; dashboard tree orgs → projects → codebases → scans → findings grouped by class; each finding renders its witness, `origin`, `S_version`, `env_digest`, and the conditional-canonicality annotation.

**Operational role.** `CMP-CP-04` ships:

1. The Auth0-backed authentication middleware that validates the dashboard JWT (`web/auth.ts`, `web/middleware.ts`), extracts `org_id` and `role`, and populates the request context that downstream API guards (`CMP-CP-01`) consume.
2. The customer dashboard UI (`web/`) — a TypeScript single-page application that renders the **orgs → projects → codebases → scans → findings** tree, with findings grouped by detection `class`.
3. The provisioning flow that creates an `orgs` row + first-admin `memberships` row when an Auth0 tenant first signs in (`AC-CP-04a`).
4. The findings-view rendering rules that surface, for every finding, its witness, `origin`, `S_version`, `env_digest`, and the conditional-canonicality annotation — and that **never visually blur** `deterministic-core` and `oracle-passthrough` (`AC-CP-04b`).

`CMP-CP-04` does **not** issue JWTs itself (Auth0 does, per `CLAR-DEPLOY-10` resolved decision). It does **not** enforce RBAC at the endpoint level (`CMP-CP-01` does, per `DOC-API §2.6`). It does **not** write to the `findings` table or any provenance table — it is strictly a presentation + auth-handshake layer.

---

## 3. Interface contract

### 3.1 Authentication flow (verbatim from `DOC-API §2.1`)

The customer dashboard uses **OIDC against Auth0** as the primary IdP, with federation to customer IdPs (Okta, Azure AD, Google Workspace) handled by Auth0 connections. Per `CLAR-DEPLOY-10` (RESOLVED 2026-05-23):

- **IdP:** Auth0.
- **Token:** short-lived JWT (default 1 h TTL) bearer in `Authorization: Bearer <jwt>`.
- **Claims required:** `sub` (user_id, uuid), `https://scanipy.io/org_id` (uuid), `https://scanipy.io/role ∈ {org-admin, org-viewer, scanner}`.
- **Role claim source:** Auth0 custom rule that maps the authenticated user's tenant membership in `memberships` to a role string.

SAML federation is achieved by configuring the customer's SAML IdP as an Auth0 connection. `CMP-CP-04` does **not** parse SAML assertions directly; it only consumes Auth0-issued OIDC JWTs.

### 3.2 Middleware signatures

```typescript
// web/middleware.ts
//
// validateJwt — invoked on every dashboard request. Verifies the JWT
// signature against Auth0's JWKS, validates `iss`, `aud`, `exp`, and
// extracts the three required claims. On failure, returns 401 with
// error_code = unauthenticated (see DOC-API §5).
export async function validateJwt(req: Request): Promise<AuthContext> {
  // 1. Extract Bearer token from Authorization header.
  // 2. Verify signature against Auth0 JWKS (cached, refresh every 10 min).
  // 3. Validate `iss === AUTH0_ISSUER`, `aud === AUTH0_AUDIENCE`, `exp > now`.
  // 4. Extract `sub`, `https://scanipy.io/org_id`, `https://scanipy.io/role`.
  // 5. Return { user_id, org_id, role } for downstream consumption.
}

// enforceTenancyHeader — validates that X-Scanipy-Org-Id header matches
// the JWT org_id claim (DOC-API §2.5). Mismatch → 403 org_mismatch +
// WARN log to OTel (cross-tenant attempt signal for CMP-CP-01 AC-CP-01a).
export function enforceTenancyHeader(ctx: AuthContext, req: Request): void;

// AuthContext is propagated to every downstream handler via
// AsyncLocalStorage; CMP-CP-01 reads from it to set app.org_id / app.user_id
// / app.role on the PostgreSQL session variable (DOC-CMP-CP-03 §3.4).
export interface AuthContext {
  user_id: string;  // uuid
  org_id: string;   // uuid
  role: "org-admin" | "org-viewer" | "scanner";
}
```

### 3.3 SSO sign-up provisioning (AC-CP-04a)

When Auth0 issues a JWT for a `sub` that has no corresponding row in `memberships`:

```
1. CMP-CP-04 detects "first sign-in" by looking up (sub) in memberships.
   - Miss → first-sign-in flow.
2. If the JWT's org_id claim is also absent from `orgs`:
   a. Create `orgs` row with id = JWT org_id claim, name = JWT email domain.
   b. Create `memberships` row (user_id = sub, org_id, role = 'org-admin').
   c. This is the first-admin provisioning required by AC-CP-04a.
3. If the JWT's org_id exists but `sub` is absent from `memberships`:
   a. Create `memberships` row (user_id = sub, org_id, role = 'org-viewer').
   b. The org-admin must promote the user explicitly (out of CP-04's scope).
4. Provisioning is a transactional INSERT under the `scanipy_system` DB role
   (BYPASSRLS) — RLS would otherwise reject a write before the membership
   exists. The transaction wraps both inserts so a partial provisioning
   (orgs row without first-admin membership) is impossible.
```

Per `CLAR-DEPLOY-12` (RESOLVED 2026-05-23): "First user in a tenant is auto-provisioned as `org-admin`; subsequent users default to `org-viewer` pending admin promotion."

### 3.4 Dashboard tree (presentation contract)

The dashboard renders five tree levels in order:

```
orgs                     (current tenant only — JWT org_id scoping)
  └─ projects            (CMP-CP-03 `projects` table, RLS-scoped)
       └─ codebases      (CMP-CP-03 `codebases` table, RLS-scoped)
            └─ scans     (CMP-ORCH-01 / `scans` table, RLS-scoped)
                 └─ findings  (CMP-FND-02 / `findings` table, grouped by `class`)
```

Per-finding render block (`AC-CP-04b` discharge):

| Element | Source field | Rendering rule |
|---|---|---|
| Witness | `findings.witness_blob_uri` → S3 GET | Rendered inline (highlighted source slice). NULL → "No witness available (oracle finding)." |
| `origin` | `findings.origin` | Rendered as a **distinct visual badge** (color + icon + label) — never as plain text adjacent to the rule name. `deterministic-core` and `oracle-passthrough` must have visually distinguishable badges that pass WCAG AA contrast. The CSS class names are namespaced (`.origin-core`, `.origin-oracle`) so a stylesheet override cannot collapse them silently. |
| `S_version` | `findings.S_version` | Rendered as a semver string adjacent to the rule id, with a hover tooltip linking to the spec-version detail page. |
| `env_digest` | `findings.env_digest` | Rendered as a short sha256 prefix with full digest on hover/copy. |
| `cpg_order_hash` + annotation | `findings.cpg_order_hash`, `findings.cpg_order_hash_annotation` | Rendered together; the annotation string `canonical iff fingerprint_class = strong` MUST appear in the same UI element as the hash. INV-5 — see `DOC-INV §7`. |

**The findings view never visually blurs** `deterministic-core` and `oracle-passthrough` (AC-CP-04b). Concretely:

- No "All findings" filter is the default; the partition is always visible.
- A grouped view (e.g., "by class") that shows aggregate counts MUST also show per-partition counts (e.g., `injection: 7 core / 2 oracle`).
- Export endpoints (CSV/JSON download) include `origin` as a column; the dashboard does not offer an export that strips it.

### 3.5 RBAC enforcement boundary (CLAR-DEPLOY-12)

`CMP-CP-04` reads the role claim and presents the dashboard accordingly (e.g., the `org-viewer` UI hides the "Promote member" button). **Endpoint-level RBAC enforcement is `CMP-CP-01`'s responsibility, not CP-04's** (per `DOC-API §2.6`). A user with `org-viewer` who crafts a direct PATCH against `/api/v1/findings/{id}` is rejected by CP-01 (403 `role_denied`), not by hiding the UI element.

The role table (verbatim from `DOC-API §2.6`):

| Role | Scans | Snapshots | Codebases | Findings (read) | Findings (PATCH) | Attestations |
|---|---|---|---|---|---|---|
| `org-admin` | submit, read | submit, read | create, read, update creds | yes | yes | read |
| `org-viewer` | read | read | read (no creds) | yes | no | read |
| `scanner` | submit, read own | submit, read own | no | yes (own scan) | no | read (own) |

### 3.6 Tenancy header (DOC-API §2.5)

Every dashboard request MUST carry:

```
X-Scanipy-Org-Id: <uuid>
X-Scanipy-User-Id: <uuid>
```

CP-04 middleware verifies that `X-Scanipy-Org-Id` matches the JWT `https://scanipy.io/org_id` claim. Mismatch → **403 Forbidden** with `error_code = org_mismatch`, logged WARN to OTel as a cross-tenant attempt signal (`CMP-CP-01 AC-CP-01a`, `CLAR-DEPLOY-16`).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Dashboard HTTPS request | Browser / Customer IdP via Auth0 | `Authorization: Bearer <jwt>`, `X-Scanipy-Org-Id`, `X-Scanipy-User-Id`. |
| Auth0 JWKS | `https://<tenant>.auth0.com/.well-known/jwks.json` | Refreshed every 10 minutes; cached in process. |
| `memberships` row lookup | `memberships` table (RLS-bypass via `scanipy_system` role for the first-sign-in path only) | Read-only after first-sign-in provisioning. |
| Findings + provenance rows | `findings`, `provenance_records` (RLS-scoped by `app.org_id`) | Read-only via CMP-CP-01-guarded endpoints; CP-04 never reads them directly from the DB. |

### 4.2 Outputs / Persisted artifacts

| Output | Location | Contract |
|---|---|---|
| `AuthContext` (per request) | AsyncLocalStorage | Consumed by CMP-CP-01 to issue `SET LOCAL app.org_id/user_id/role`. |
| `orgs` row (on first sign-in only) | PostgreSQL `orgs` table | Written under `scanipy_system` role; AC-CP-04a discharge. |
| `memberships` row (on first sign-in only) | PostgreSQL `memberships` table | Written under `scanipy_system` role; role = `org-admin` for the first user. |
| Dashboard HTTPS response | Browser | HTML/JS bundle + JSON payloads from upstream API. Never includes secrets; JWTs are never echoed back. |

CP-04 does **not** write to `findings`, `provenance_records`, `scans`, `snapshots`, `attestations`, or any other application table. The only writes are the two first-sign-in provisioning inserts.

---

## 5. Invariants touched

| Invariant | How `CMP-CP-04` discharges it (ancillary owner) | Test |
|---|---|---|
| **INV-1** (presentation) | The findings view renders `origin` as a distinct visual badge per `§3.4`; the dashboard never offers a grouping/export that collapses the two partitions into a single visual element. AC-CP-04b is the empirical falsifier. | `TST-AC-CP-04b [FORTHCOMING]` (visual-regression snapshot test asserts the two badges differ in color, icon, and CSS class). |
| **INV-5** (presentation) | The `cpg_order_hash` is rendered in the same UI element as `cpg_order_hash_annotation` (literal `canonical iff fingerprint_class = strong`). A `weak`-class finding shows the annotation prominently. | `TST-INV-5-FND-03 [FORTHCOMING]` covers the auditor-export path; CP-04's UI must thread the same. |
| **INV-3** (perimeter precondition; not a discharge) | INV-3 is owned by `CMP-TRI-01..03` and verified by `CMP-CP-05` (`LLM_TRIAGE=off`). CP-04 is at most a perimeter precondition: only authenticated callers (validated JWT) reach the spec-acceptance API surface. This is not an INV-3 discharge. | INV-3 tests (`TST-INV-3-TRI-02 [FORTHCOMING]`, `TST-INV-3-CP-05 [FORTHCOMING]`) operate downstream of CP-04. |
| **CLAR-DEPLOY-16** (tenancy isolation, layer 1) | JWT `org_id` claim is the **first** of three isolation layers (layer 2 = RLS in `CMP-CP-03`; layer 3 = KMS CMK per `CMP-CP-02`). A cross-tenant JWT cannot be forged without breaking Auth0's signing key. | `TST-AC-CP-04a [FORTHCOMING]` (provisioning), `TST-AC-CP-01a [FORTHCOMING]` (org-mismatch denial). |

CP-04 is **not** an INV-1/INV-5 owner — the values are produced upstream by `CMP-ORCH-03`, `CMP-FND-02`, `CMP-CORE-03`. CP-04's role is faithful presentation; corruption of the values at the UI layer would be an AC-CP-04b violation, not an INV-1 owner-side defect.

---

## 6. Algorithm / data flow

```
browser  →  HTTPS GET /dashboard      Authorization: Bearer <jwt>
              │
              ▼
   web/middleware.ts: validateJwt(req)
              │  signature OK, claims extracted
              ▼
   memberships SELECT WHERE user_id=sub, org_id=jwt.org_id
              │
              ├─ miss → first-sign-in flow:
              │     BEGIN; INSERT orgs (if missing); INSERT memberships
              │       (role='org-admin' for first user in this org);
              │     COMMIT.   (AC-CP-04a discharge)
              │
              ▼
   enforceTenancyHeader(): X-Scanipy-Org-Id MUST equal jwt.org_id
              │  mismatch → 403 org_mismatch (+ WARN OTel)
              ▼
   AsyncLocalStorage.run({ user_id, org_id, role }, handler)
              │
              ▼
   CMP-CP-01 endpoint guard checks role for the requested endpoint
              │  fail → 403 role_denied
              ▼
   CMP-CP-01 acquires DB connection with
     SET LOCAL app.org_id, app.user_id, app.role (DOC-CMP-CP-03 §3.4)
              │
              ▼
   Endpoint handler reads findings / provenance under RLS.
              │
              ▼
   Web bundle renders the orgs→projects→codebases→scans→findings tree.
   Per-finding render block (§3.4): witness, origin badge, S_version,
   env_digest, cpg_order_hash + annotation. (AC-CP-04b discharge)
```

Auth0 outage handling: CP-04 fails closed. JWT validation requires the JWKS to be reachable (cache TTL 10 min). On JWKS unreachable + cache expired, dashboard requests return **503 Service Unavailable** with `Retry-After: 60`. The dashboard does **not** serve any data on cached-JWT-only validation past the cache TTL — failing open would risk JWT-revocation bypass. (This is `CLAR-CP-04-01` if a partial-degraded read-only mode is later required; see §10.)

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| JWT signature invalid / `iss` / `aud` / `exp` fail | `validateJwt()` | **401 Unauthenticated** with `error_code = unauthenticated`. | None. |
| JWT lacks required custom claim (org_id or role) | `validateJwt()` | **401 Unauthenticated** with `error_code = unauthenticated_missing_claim`. | Logged WARN to OTel as malformed-Auth0-rule signal. |
| `X-Scanipy-Org-Id` ≠ JWT `org_id` claim | `enforceTenancyHeader()` | **403 Forbidden** with `error_code = org_mismatch`. | WARN-logged to OTel as cross-tenant attempt signal (CMP-CP-01 AC-CP-01a, CLAR-DEPLOY-16). |
| User has no `memberships` row in JWT's `org_id` | First-sign-in flow | Provision (org-admin if no other admin; org-viewer otherwise) and continue. | Transactional INSERT under `scanipy_system` role. |
| Auth0 JWKS unreachable + cache expired | `validateJwt()` | **503 Service Unavailable** with `Retry-After: 60`. | Fail-closed; no degraded read-only fallback in v3.2 (see `CLAR-CP-04-01`). |
| Auth0 SAML federation failure (customer IdP down) | Auth0-side, surfaced as `iss`/`aud` mismatch | **401 Unauthenticated** + customer-facing error page directs to their IdP admin. | Out of CP-04's direct control; Auth0 handles the federation retry. |
| Browser sends expired JWT | `validateJwt()` (exp check) | **401 Unauthenticated**; browser re-redirects to Auth0 login flow. | None. |
| Visual-regression test detects collapsed-partition rendering | CI snapshot test (TST-AC-CP-04b) | **Hard PR block.** | Patch must restore the distinct badges. |

**Fail-closed posture.** A request without a valid JWT cannot reach any handler. A JWT for a different tenant cannot see this tenant's data (three-layer isolation: JWT claim → tenancy header check → RLS). The findings view cannot be configured to collapse the partition badges (CSS classes are namespaced and the snapshot test fences it).

---

## 8. Provenance threading

CP-04 reads four threaded fields per finding and renders them faithfully. It **does not write** any of them.

| Field | CP-04 contribution |
|---|---|
| `origin` | Rendered as a distinct visual badge per `§3.4`; partition counts surfaced in grouped views. |
| `S_version` | Rendered adjacent to the rule id; hover tooltip links to the spec-version detail. |
| `env_digest` | Rendered as a short sha256 prefix with full digest available on hover/copy. |
| `cpg_order_hash` + `cpg_order_hash_annotation` | Rendered together in the same UI element; the literal annotation `canonical iff fingerprint_class = strong` MUST appear adjacent to the hash. INV-5. |

CP-04 propagates the `AuthContext` (`user_id`, `org_id`, `role`) to downstream handlers via AsyncLocalStorage; that context is what CP-01 uses to set `app.org_id` / `app.user_id` / `app.role` on the PostgreSQL session variable (per `DOC-CMP-CP-03 §3.4`).

**Must NOT touch.** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `cpg_order_hash_annotation`, `slice_fingerprint`, `fingerprint_class` — these are upstream-set, read-only at CP-04. Any code path that appears to mutate them is a bug.

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §10 CMP-CP-04`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CP-04a** | > SSO sign-up provisions an org row plus first-admin membership. | `TST-AC-CP-04a` `[FORTHCOMING]` |
| **AC-CP-04b** | > The findings view never visually blurs `deterministic-core` and `oracle-passthrough`. | `TST-AC-CP-04b` `[FORTHCOMING]` |

**AC-CP-04a** falsifier sketch (for QA Agent):

1. Configure a fresh Auth0 tenant and a fresh PostgreSQL database (no `orgs` rows).
2. Sign in via OIDC with a new user; obtain a JWT bearing a new `org_id` claim.
3. Issue a GET against the dashboard.
4. Assert: exactly one new row in `orgs` with that id; exactly one new row in `memberships` with `(user_id=sub, org_id, role='org-admin')`.
5. Sign in a second user against the same `org_id`; assert second `memberships` row is `role='org-viewer'`.

**AC-CP-04b** falsifier sketch:

1. Snapshot test of the findings view with a fixture containing both `deterministic-core` and `oracle-passthrough` rows.
2. Assert: the rendered DOM contains at least two distinct CSS classes for the badges (`.origin-core`, `.origin-oracle`); their computed colors differ; their icons differ; the WCAG AA contrast ratio between them is ≥ 4.5:1.
3. Assert: the per-class aggregate view shows per-partition counts, not a single sum.
4. Assert: the CSV export contains the `origin` column.

Cross-referenced invariant tests:

- `TST-INV-1-FND-01 [FORTHCOMING]` — normalizer preserves `origin` through SARIF serialization; CP-04 inherits the rendered value.
- `TST-INV-5-FND-03 [FORTHCOMING]` — auditor export pairs `cpg_order_hash` with the annotation; CP-04's UI render must thread the same pair.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-04 |
|---|---|---|---|
| `CLAR-DEPLOY-10` | OIDC / SAML IdP integration target | **RESOLVED** 2026-05-23 | Auth0 (primary); customer-IdP federation via Auth0 connections. |
| `CLAR-DEPLOY-12` | RBAC roles + first-admin provisioning | **RESOLVED** 2026-05-23 | Roles `org-admin`, `org-viewer`, `scanner`; first user → `org-admin`. |
| `CLAR-DEPLOY-16` | Tenancy isolation backstop | **RESOLVED** 2026-05-23 | CP-04 implements layer 1 (JWT claim); CP-03 implements layer 2 (RLS); CP-02 implements layer 3 (KMS CMKs). |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |
| **`CLAR-CP-04-01`** *(new — filed by this document)* | Should an Auth0 outage allow a partial degraded read-only mode (cached JWT validation past TTL, no writes), or remain fail-closed (503)? | **FILED** in `WBS.md §17` (OPEN) | Default = fail-closed (§7). A read-only degraded mode would require careful JWT-revocation semantics; needs SRE + Security Analyst sign-off. |

**Note on SCIM provisioning.** Bulk user provisioning via SCIM is **not** in CP-04's scope; the first-sign-in lazy-provisioning flow (§3.3) is sufficient for v3.2. SCIM is filed as `OOS-PROVIDER-01` if requested in future (not yet appended to `WBS.md §18`).

---

## 11. References

- `SDD.md §10 CMP-CP-04` — verbatim ACs.
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`.
- `docs/cross-cutting/DOC-API.md` §2.1 (Auth0 → JWT), §2.5 (tenancy header), §2.6 (RBAC summary).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-10 (Auth0), CLAR-DEPLOY-12 (three roles).
- `docs/cross-cutting/DOC-PARTITION.md` §6 — the partition the dashboard surfaces; the visual-blurring prohibition derives from INV-1.
- `docs/cross-cutting/DOC-INV.md` §3 (INV-1), §7 (INV-5).
- `docs/cross-cutting/DOC-PROVENANCE.md` — the four threaded fields rendered per finding.
- `docs/components/DOC-CMP-CP-01.md` (sibling) — endpoint RBAC enforcement; consumes `AuthContext` from CP-04.
- `docs/components/DOC-CMP-CP-03.md` (sibling) — RLS session-variable setter; consumes `AuthContext` from CP-04 (via CP-01) to set `app.org_id`.
- `docs/components/DOC-CMP-FND-02.md` (sibling, forthcoming) — owns `findings` column shape; CP-04 reads but never writes.
- `docs/components/DOC-CMP-FND-03.md` (sibling, forthcoming) — signed provenance; CP-04 renders the chain in the auditor view.
- `.claude/rules/00-global.md` RULE-6 (provenance threading), `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-04`.*

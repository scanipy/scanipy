# R08/R16 — Legacy Docker application containment and cutover

Status: independently approved narrow design; implementation in progress, not
runtime acceptance.
Owner: root. Date: 2026-09-25. Issue: #396 under #362.
Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
Base: reviewed main `2709177afff1c78f06532e0298dd5ee4d608237f`.

This change intentionally makes new scans unavailable in the legacy application
until the replacement is connected. It is a security containment, not delivery
of the advertised Docker demo, R08/R16, or any Black Hat acceptance gate. Existing
user containers, databases, local configuration and images are untouched.

## 1. Observed gap and exact scope

`deploy/scanipy_oracle/app.py` invokes Git and Semgrep directly, independently of
the generic wrapper, snapshot worker and four SCM providers addressed by #395.
Git inherits configuration/environment, materializes a checkout and can fill a
missing commit with zeroes. Semgrep inherits the environment and captures output
without a retained-stream bound. Startup runs Semgrep to hash its version and
rules, which is not evidence of the full observed analysis environment. Source
is removed after the run. These are read-only code findings: no malicious target,
native Git/Semgrep process or real scan was run to demonstrate them.

The generic/provider containment and this application containment are separate
changes. Neither claims system-wide safe native execution, complete source
coverage, enforced read-only source mounts or pinned runtime closure.

The original five-file runtime/document/test scope is extended to seven files
only for the independently reviewed normal-hook corrections described below:

| File | Permitted change |
|---|---|
| `docs/bhmea/LEGACY-APP-CUTOVER.md` | Contract, scoped review and actual verification record. |
| `deploy/scanipy_oracle/app.py` | Explicit unavailable scan boundary; remove native execution and fabricated current runtime identity; preserve historical reads/schema. |
| `deploy/scanipy_oracle/static/index.html` | Static unavailable-capability shell with no active scan submission or promise of delivered guarantees. |
| `deploy/README.md` | Current containment warning, truthful endpoint/configuration semantics and mandatory cutover requirements. |
| `tests/unit/test_legacy_oracle_containment.py` | Hermetic HTTP, startup, direct-helper, import and historical-read tests; no live DB/native tools. |
| `.pre-commit-config.yaml` | Supply the existing exact HTTP-stack pins to isolated mypy; no type-check exclusion or runtime dependency change. |
| `.secrets.baseline` | Only two audited file/type/password-hash entries for existing public development defaults; no detector/filter/exclusion changes. |

No production code is changed before independent design review. Changes outside
this list require a separate scoped decision. Do not alter Dockerfiles, Compose,
runtime dependencies, migrations, legacy findings/signatures, PLAN/SDD/WBS, source corpus,
or the user's running state. Normal repository hooks/tests remain mandatory.

## 2. New-scan boundary

Every `POST /api/scan` receives HTTP 503 with a closed constant error envelope:

```json
{"code":"native_scan_unavailable","error":"Native scanning is unavailable pending the reviewed capture and worker cutover.","retryable":false}
```

Add `Cache-Control: no-store`; do not invent a Retry-After deadline. The endpoint
does not need to parse a repository URL or request model while disabled. The
same refusal covers missing, malformed and arbitrary bodies, without reflecting
their contents. HTTP method routing remains normal (unsupported methods may
return 405). Refusal precedes DB connection/insertion, UUID allocation, queue or
threadpool submission, source staging, filesystem reads/writes and native work.
This does not claim a server-wide request-size or denial-of-service defense.

Remove the legacy scan-job threadpool and its work submission. Ordinary FastAPI
HTTP handler thread offload is unchanged and is not a scan job. Remove the old clone,
rev-parse, rules/version probing, Semgrep launch, source cleanup and result mapping
implementations rather than retaining dormant unsafe code behind a flag.
For compatibility with direct internal callers, `_run_scan`, `_run_semgrep` and
`_compute_env_digest` may retain their former signatures but must immediately
raise a typed `NativeScanUnavailableError` with the same constant message. They must
not inspect/traverse/format supplied objects, log payloads, stage files, touch the
database or invoke tools. No environment, query, header, CLI or injected-runner
switch can enable this legacy path. Trusted Python monkeypatching is outside
the application boundary, not an authorized runtime profile.

## 3. Startup, health and historical compatibility

Startup retains only the existing database initialization and existing legacy
restart-reaping behavior. It does not call any tool/version/rule probe or claim
a current observed environment. Preserve the existing `oracle.scan` and
`oracle.finding` definitions and the SQL used to read historical rows. This is
not an occurrence-store migration, and no stored origin, fingerprint, digest,
decision or provenance bytes are rewritten by this containment.

Replace deprecated FastAPI startup registration with a normal lifespan context
if required by the repository's warnings-as-errors HTTP stack. That is lifecycle
registration only: run the same initialization/reaping once on entry, propagate
its failure, and add no shutdown mutation. The existing `_startup` helper may
remain as that implementation. Do not catch initialization failure and pretend
the application is ready.

`GET /healthz` remains liveness, HTTP 200 with `status: "ok"`; it must additionally
declare `capabilities.native_scan: "unavailable"` and the constant reason. A
current `env_digest` is JSON null with explicit `env_digest_status: "not-observed"`,
not a zero hash, unknown string or partial rules/version digest. Preserve the
configured `s_version` label only with `s_version_status: "configured-only"`;
configuration is not accepted registry authority. `capabilities.historical_read`
is labeled `legacy`, not authenticated/completely verified or a DB health probe.

`GET /api/scan/{scan_id}` retains its existing response shape, ordering and 404
behavior. The stored rows retain their historic values, including imperfect
legacy metadata; do not upgrade them to new structural/provenance guarantees.
`GET /` serves the static unavailable shell. The shell has no scripts, active
form, automatic request, remote assets or scan example that could suggest a
working submission. It may show a disabled repository input/button and explain
that existing rows remain available through the legacy GET endpoint. This is
not a newly implemented historical browser or the final asynchronous UI.

The old unauthenticated/single-tenant read boundary is unchanged. The README
must not imply that containment secures public exposure, fixes deployment
credentials, bounds historic result size or authenticates an actor. Keep the
localhost/reverse-proxy caution and the data-preservation warning.

## 4. Required evidence before merge

- [ ] Import and lifespan tests prove no native process, executable discovery,
  threadpool, source staging or rule read; only controlled DB doubles are used.
- [ ] POSTs with valid, invalid, absent and hostile-shaped bodies all return
  the same 503/code/message with no new scan row, UUID/task or request reflection.
  Direct handler/helper calls refuse before hostile argument access.
- [ ] Startup calls the existing initialization/reaping once, preserves its
  update fields, propagates DB failures and does not manufacture runtime identity.
- [ ] Health explicitly distinguishes live app, unavailable scanning and
  configured-versus-observed metadata without touching the database.
- [ ] Historical GET/404 retain actual controlled stored fields and ordering;
  no rewrite to strong fingerprints or signed finding claims. These doubles
  verify adapter compatibility, not real PostgreSQL persistence or migration.
- [ ] Static HTML has no execution/submission/remote-resource path and clearly
  states unavailability. The read endpoint remains available independently.
- [ ] All new tests are unit-marked and selected by actual CI/pre-push; scoped
  Ruff/mypy and configured full tests pass with normal hooks and no weakened
  thresholds, skipped checks or warning suppressions.
- [ ] Successful exact-head canonical `claude-review` APPROVE and all required
  GitHub tests precede merge. Independent local review does not replace it.

## 5. Mandatory replacement and acceptance actions

Do not restore the legacy subprocess bodies or add an enable flag. Implement
the reviewed vertical path with real evidence for each prerequisite:

1. Acquire an exact commit through a bounded no-checkout SCM profile, verify its
   commit/tree/blob content, and preserve one immutable source capture. A commit
   assertion or safe local-copy receipt alone is not SCM proof.
2. Resolve actual immutable accepted rule/spec/model contents and durable
   authority. A configured S_version, a YAML path or PR approval is insufficient.
3. Seal source/request/spec and planned inputs in the occurrence store. Observe
   actual tool/helper/image/code/argv/cwd/environment separately from policies.
4. Invoke the closed native engine profile in the resource/network-constrained
   worker, retaining bounded raw output and real coverage/failure evidence.
   Parse every observed result before deduplication or structural identity.
5. Atomically persist detections and identity work; retain them through identity,
   signing and finalization failures. Read-only capture mounts and leases must
   survive restart/retry and prevent unsafe cleanup.
6. Expose versioned processing states and correct origin/CWE/identity classes,
   finalize provenance from actual producers, and measure fresh oracle reruns.
7. Deliver durable human decisions and supported strong continuity after its
   independent policy/fidelity/canonicality gates. Do not auto-suppress oracle,
   weak, ambiguous, failed or incompatible results.
8. Re-enable the new scan endpoint/UI only after its real end-to-end path passes
   review/tests. Verify local Docker start/restart, no-network rehearsal, fresh
   provenance verification and real refactor/rescan. Measure actual stage budgets
   on this development machine, which the owner confirmed as the local Docker
   presentation host. The [stage-machine observation](../evidence/2026-09-25-stage-machine/README.md)
   records its selected capacity sample, not verified performance or offline
   readiness. Recheck available resources before each real rehearsal.

All full R08/R16 and shared G1/G2/G3 criteria remain open. No release, image
publication, organizer message or user-container operation is authorized here.

## 6. Review record

The independent corpus/tooling reviewer read this complete contract and the
legacy application/README on 2026-09-25 and approved the scoped design. The
review specifically required import tests to replace `create_engine` before
module loading, explicit lifespan initialization-failure/once-only-reaping
tests, and distinguishing trusted application static assets from target/rule
reads. This is design approval only; implemented behavior and canonical PR
approval remain separate gates.

Implemented five-file code was independently reviewed and approved, with
27 focused tests passing (zero skips). The configured full suite passed
1,276 tests with 51 existing optional skips on Python 3.11.16. These are adapter
and repository checks, not live PostgreSQL/native/Docker acceptance. The first
Ruff check rejected the proposed exception name; it now uses
`NativeScanUnavailableError`, without suppressing the naming rule. Explicit
strict mypy on the application passes in the declared project environment.

Normal hooks then exposed two setup/baseline gaps, not successful checks:
isolated mypy lacked the already-declared HTTP packages, and two previously
unbaselined public development-default passwords were detected in the preserved
app DSN and README DSN. The independent reviewer approved the narrow two-file
extension: add only fastapi 0.138.2, starlette 1.3.1, anyio 4.14.2 and pydantic
2.13.4 to that hook, and retain two detector-derived file/type/password hashes
in the secret baseline. BasicAuthDetector hashes the password, NOT the whole
DSN; reusing the same public default at another URI in either of those files
would also match that baseline. A changed password must remain detectable.
There is no blanket inline allowlist, new secret, ad-hoc hook-environment install,
runtime-default change or claim that default credentials are secure. The
existing authentication/default-credential limitations remain open.

An isolated trusted regression repository exercised the actual pinned
`detect-secrets-hook` against those two baseline entries: both unchanged public
defaults passed; changing the password in both files to a synthetic test value
failed with one `Basic Auth Credentials` finding per file. This verifies the
narrow password-hash behavior, not credential security. The product baseline
was not regenerated by that test. A later normal hook run passed isolated mypy
and required staging the deliberately edited baseline before its secret check;
that unstaged-baseline refusal is not counted as a passing hook run.

After staging the exact seven files, all applicable normal pre-commit hooks
passed, including the isolated mypy and secret checks. The actual pre-push
script also passed all four stages: project Ruff, formatting, strict mypy
(83 source files), and its configured unit/invariant pytest selection. The
independent reviewer approved the complete seven-file delta. Canonical PR
review, exact-head CI and merge are still required; these local checks do not
restore scan capability or establish full R08/R16 acceptance.

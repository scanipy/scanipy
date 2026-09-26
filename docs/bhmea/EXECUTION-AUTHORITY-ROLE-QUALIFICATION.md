# Execution authority reader: role-only PostgreSQL qualification

Current engineering source allocation, 2026-09-26. Primary owner CMP-ORCH-03,
coordinating the existing CMP-CP-03 database boundary. Root approved this
four-path test slice; that is not separate human approval or executed database
acceptance. The owning [reader contract](EXECUTION-AUTHORITY-READER.md) and
unchanged migrations 0007/0008 remain authoritative for production behavior.
This document specifies only their dedicated-cluster qualification.

## 1. Scope and dependencies

The base is role commit `5c39512311e4fbd926d71bd002d3daf29d9d9bf5`, normally
merged with final-ticket commit `ca51a9bd73de294fee308f8a940c910404390a29` as
`67c41eb02eb977383dd5fa68987d240372a0c4c9`. Exact incoming ten paths and three
role paths were preserved; applicable merge hooks passed. No implementation
commit, push, full suite or PostgreSQL execution is authorized by this note.

Owned paths are this new document, new
`tests/integration/test_execution_authority_role.py`, and the existing
`tests/occurrence_store_postgres.py` / `tests/unit/test_accepted_ledger_repository.py`.
Do not edit the reader contract, migration/SQL bodies, public facade, workflow,
baseline, or the existing 43 SQL / 102 security / 38 historical integration cases.

This is effective-role qualification, **not authenticated-login or role-escape
qualification**. A privileged fixture session deliberately uses fixed
`SET LOCAL ROLE scanipy_accepted_execution_reader`. Tests assert that
`current_user` is the non-superuser NOLOGIN reader while `session_user` remains
the bootstrap administrator. They do not claim that RESET ROLE, changing role,
connection authentication, credentials, filesystem custody or a runtime factory
has been restricted. No login/password/membership is created for this reader.

## 2. Fixed harness additions

Only an explicit accepted-profile, non-administration request may name 0008.
Occurrence default 0005, accepted default 0006, the administration bootstrap,
its ten setup tickets and sole explicit eleventh successful 0007 ticket remain
unchanged. Do not add the reader to ACCEPTED_RESERVED or change existing login
names/counts. Existing caller-selected URLs remain forbidden: use only the
separately explicit accepted test URL and the harness-owned child database.

`_migrate_execution_reader` owns only explicit upgrade0008/downgrade0007 and
admits at most five such calls. Check exact accepted/non-administration mode,
known child OID/owner, current literal revision and reader identity first.
Then set a pending flag before the subprocess may start. Reuse the existing
non-administration Alembic invocation, exact URL routing and 60-second timeout.
This does not upgrade that legacy capture_output path into a bounded transport
or an authenticated installation primitive.

After acknowledged success, re-read exact revision and the one fixed role's
name/OID/restrictive flags; both cursor and connection close must complete
before adding/removing its OID in `owned_roles`. A completed expected refusal
must leave the complete pre-call role/revision snapshot unchanged. Uncertain
process outcome, malformed readback, unexpected exit, or close failure leaves
pending set and blocks further migration and automatic cleanup. Never infer
ownership from a failed migration or adopt a discovered same-named role.
Each completed result or original process exception is retained in the existing
in-memory migration evidence list. No retry/reset refunds a ticket. This is
fixture custody, not a durable catalog
identity anchor against an administrator recreating an indistinguishable role.

Exactly one optional sidecar is permitted by `_create_reader_probe_database`:
an ASCII `scanipy_reader_probe_` plus a full uuid4 hex suffix, admitted against
the real server identifier limit before CREATE. It uses the same explicit
bootstrap connection, template0/UTF8, and no caller-supplied name or connection.
Retain its exact name/OID/owner only after acknowledged creation, bounded
readback and close. A pending flag precedes CREATE; uncertainty blocks cleanup.
There is no second attempt after success or failure.

The test creates one empty schema in that sidecar and grants USAGE to the
reader. Its genuine cross-database dependency must reject downgrade. The test
then revokes that exact grant and removes the owned sidecar. The fixed drop
helper rechecks name/OID/owner, marks pending before DROP, and verifies absence
and close before forgetting it. No FORCE, CASCADE, DROP OWNED, termination,
adoption or cleanup retry is allowed. Before normal fixture cleanup drops
anything, validate both database identities and all owned role OIDs. Close
all test connections and remove the sidecar before the main child/roles.
Retain primary and cleanup failures; ambiguous residue requires root disposition.

## 3. Integration organization and finite schedule

Use the existing session `accepted_ledger_pg` fixture, with administration=False.
One module fixture wraps it and restores literal 0006 before the original
session teardown. No second cluster fixture or ambient app/occurrence URL.
Seven additional actual Alembic process calls are planned, beyond the unchanged
ten setup calls:

1. upgrade0007;
2. upgrade0008;
3. populated downgrade0007;
4. upgrade0008;
5. expected-refused downgrade0007 while the sidecar dependency is committed;
6. successful downgrade0007 after exact sidecar cleanup;
7. downgrade0006 to restore the original accepted fixture.

The five middle reader transitions use the new pending/ownership gate. Other
guard falsifiers execute the **actual generated owning DO statement**, not a
copied SQL validator, inside deliberately rolled-back transactions. Those are
real SQL guard tests when eventually run, but are not additional Alembic process
invocations. Version-row changes needed for a guard scenario are also rolled
back. Never count collect-only or controlled Python doubles as actual SQL.

Test-local `_reader_transaction` installs fixed timeouts and effective role,
uses the actual AcceptedLedgerRepository and closes/rolls back its connection.
Existing SqlLedger produces genuine owner request/publication/seal/execution
rows with its explicitly synthetic fixtures; no operational key is generated.
The six public read methods must return their actual closed owner results.
R6 consumes the exact prior R5 ledger/LIVE/reference tuple; stale policy,
namespace and binding failures remain fatal, not successful ACL tests.

Before and after upgrade/downgrade/refusal, compare original function OIDs,
owners, bodies, signatures/configuration and ACLs; compare tables and retained
material history. Upgrade adds only the seven reader grants. Downgrade removes
only those grants and the new role. Unrelated ACLs/history and old function
bytes must be exact. A successful re-upgrade creates a newly captured role OID;
the old role OID is never silently transferred or reused as proof.

## 4. Required falsifiers and later run gate

- All six read positives; original R5/R6 continuity and stale context rejection.
- No direct table/column/sequence privileges, mutation function execution,
  private helper/bridge execution, schema CREATE, or grant option.
- Actual guard refusal for role collision, predecessor/body/owner/property
  drift, memberships in either direction, role flags/settings/comments,
  foreign ownership/dependencies, extra grants, grant options and PUBLIC access.
- Successful and aborted transaction-local search_path restoration; exact
  upgrade/rollback/populated inverse preservation.
- Real sidecar dependency refusal with no changes to the main child's role,
  ACLs/history or version; exact sidecar removal then successful inverse.
- Controlled harness cases at each subprocess/readback/close boundary: no OID
  promotion/removal before close, pending blocks disposal, fifth/sixth reader
  ticket, failed/ambiguous results, duplicate sidecar and wrong OID/owner.
- Unchanged occurrence/accepted defaults and administration eleven-ticket
  behavior, with original test ASTs and bootstrap bytes retained.

Actual PG execution requires a later root-owned disposable PostgreSQL16 cluster
and separately approved finite command/report plan. No existing app database,
operator identity or A2 authentication fixture may be reused implicitly.
Initial source work permits only controlled unit/static checks and collection.
Full original integration regressions, catalog before/after preservation,
nonzero executed cases, zero unexpected skips, restricted effective-role SQL
results and teardown all remain unexecuted gates until actual reports exist.
This test slice does not reduce the full Black Hat submission or enable native
runtime/provider authority.

## 5. Source-only checkpoint — 2026-09-26

The final controlled selection executed 393 unique cases, zero failures,
errors or skips, 4.637 seconds JUnit: 53 new reader-harness controls, 217 prior
accepted-harness controls, 36 unchanged occurrence-repository controls and 87
unchanged reader-migration/offline-codec controls. Final report SHA256 is
`578494f4b6fc6ab82f852edac583c52c7af1f8fee6c9c536b3c513989d16628f`.
Prior selections of 40, 306 and 87 passes overlap this coverage and are not
additional independent cases. No selected case created a real key, login,
database, process or native fixture. Ruff check/format and diff-check pass.

Collection-only verified 246 unique integration IDs: 63 new role cases and
the exact existing 43 SQL, 102 security and 38 historical cases. Collection
report SHA256 is
`979441b62681b7eadf1360564d8a6455008b200b94b99b777c83845c04ce330c`.
All 246 remain unexecuted in this checkpoint. The first collection attempt
had four import-order errors: the new test imported the shared pytest plugin
before registration. Taking the fixed role name from the actual migration
owner corrected that new test without suppressing warnings or editing the
plugin. The initial diagnostic is retained separately; it is not a SQL failure.
Initial authoring lint findings were likewise corrected before the final checks.

The original 3,317-line repository-unit prefix is byte-exact; all eight existing
top-level harness functions and twenty unaffected class methods are AST-exact.
Only constructor state, explicit migration dispatch and disposal fencing changed,
alongside four new fixed helpers. Original administration setup/transport/login
methods, all bootstrap constants, three old integration modules, migrations,
reader contract and baseline are unchanged. Source and collection review, a
separately bounded real-PG run plan and actual qualification remain pending.

## 6. Coordinated qualification composition and owner boundaries

2026-09-26 clarification under
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
Section1 defines the **four-path role-qualification owner's allocation**, not
the entire later composed qualification PR. Its prohibition on editing the
reader contract, migrations and workflow applies to that owner. Root separately
allocated and reviewed the role owner, final-ticket fixture owner and CI owner.
No author was authorized to overwrite another owner's frozen work.

The actual source commits and their complete per-commit path inventories are:

| Slice | Reviewed source commit | Allocated paths |
| --- | --- | --- |
| Guarded reader role | `5c39512311e4fbd926d71bd002d3daf29d9d9bf5` | `db/migrations/versions/20260926_0008_execution_reader.py`; `tests/unit/test_execution_authority_role.py`; `docs/bhmea/EXECUTION-AUTHORITY-READER.md` |
| Final administration ticket | `ca51a9bd73de294fee308f8a940c910404390a29` | `tests/occurrence_store_postgres.py`; `tests/unit/test_accepted_ledger_repository.py`; `docs/bhmea/ACCEPTED-LEDGER-SQL.md` |
| Role-only qualification | `0bee28339bebffe55840b4131a8add52962e8ca6` | `tests/integration/test_execution_authority_role.py`; `tests/occurrence_store_postgres.py`; `tests/unit/test_accepted_ledger_repository.py`; this document |
| Required CI246 selection | `275b0750aeaf016685b50be9493cddd04f394d06` | `.github/workflows/ci.yml`; `tests/unit/test_accepted_ledger_ci.py`; `docs/workflows/ci.md` |

The role and final-ticket dependencies were ordinarily merged as
`67c41eb02eb977383dd5fa68987d240372a0c4c9`, parents5c395123+ca51a9bd,
tree `9de6def3e1d333ae8e920aefbcb2d51da20e8c7e`, before the four-path
qualification commit. That owner then made only its reviewed role-specific
harness/unit additions, preserving the final-ticket behavior. The two shared
fixture files account for the overlap: 3+3+4+3 allocated path entries form
**11 distinct composed paths**, not an expanded four-path author allocation.

After the CI commit, ordinary merge
`ee1f4e3d56f6ee60e4d7a7ecbd14b9da2df53f6a`, parents275b0750+4041cc3d,
tree `04392b268ecd3f4fca13369dc17bb795a21a5f9a`, incorporated the separately
reviewed historical-read scope clarification. That historical document is
already present in accepted main `b5bff4292892d024a21380eb01b02b528f3e2baa`;
it is not a twelfth role-qualification change against that accepted base.
The composed reader-contract bytes are the role5c395123 version; later private
custody/factory modules and genuine A2 production/71-case fixture additions are
separate allocations, not part of this composition.

This clarification changes no owner permission, SQL/Python/workflow behavior,
test oracle, budget, default or prior evidence. Occurrence0005/accepted0006
defaults, the opt-in administration ten-plus-explicit-eleventh ticket, and this
non-administration lane remain distinct. Its complete planned246 selection is
43 SQL+102 security+38 historical+63 role, with21 healthy migration calls
(10 setup+4 historical+7 role). Section3's rolled-back owning DO guards are
not additional migration-process calls. Existing cleanup/refusal rules remain.

The role cases deliberately use effective SET LOCAL ROLE under privileged
session_user; they do not prove restricted login, RESET ROLE confinement,
SCRAM/root-peer authentication, installed custody, a working reader/composer
or runtime authority. No new login, operator identity or service is authorized.
Source/collection checkpoints above remain dated history. This ownership note
does not report a PostgreSQL result or turn controlled/collected cases into
executed passes. Any later run, cleanup, exact-head CI/canonical, merge and
accepted-artifact result must be recorded separately from its actual evidence.
All original task/claim/shared-gate and release/stage limitations remain.

## 7. Namespace-record ambiguity correction — source allocation

2026-09-26. Root allocated only migration0008, its existing role-unit module,
and this append in a new isolated tree based on `ee1f4e3d`. The original
role/CI tree and this document's first228 lines remain unchanged. This extends
the earlier composed owner allocation only for the correction described here;
it authorizes no migration, fixture disposal, database retry or activation.

The actual single standalone246 campaign started07:51:47 UTC and exited1 at
08:07:38. Its JUnit records183 passing old bodies (43 SQL+102 security+38
historical), followed by setup and teardown errors on the first role case:
184 testcase elements,2 errors,0 failures/skips,948.764 seconds. No new role
body executed. The wrapper preserved pytest failure and a subsequent failed
after-catalog baseline check. This is not246 success or successful cleanup.

Root's retained server record at08:07:36.810, PID6680, identifies ambiguous
`n.nspacl` in the inline DO block at line475. The outer block declares
`n pg_catalog.pg_namespace%ROWTYPE`; its object-snapshot loop uses that record.
The later role guard independently aliases `pg_catalog.pg_namespace` as `n`.
Both meanings are visible in the role guard's ACL expression. PostgreSQL16's
[variable-substitution rules](https://www.postgresql.org/docs/16/plpgsql-implementation.html#PLPGSQL-VAR-SUBST)
explain the default ambiguity refusal and the local-variable rename remedy.
Offline SQLAlchemy/Alembic serialization controls do not parse that PL/pgSQL
expression; their prior passes are not evidence that this SQL executed.

The correction is exactly eight source identifier substitutions: the outer
namespace-record declaration and its seven references in `_objects` become
`v_n`. Keep the ACL kind string/argument `'n'`, `_role_guard` and its SQL aliases,
all six TARGETS, function bodies/signatures, guards, counts, privileges and
DDL unchanged. Do not set `plpgsql.variable_conflict`, qualify away a guard,
rewrite an old owner body or change any migration/harness default.

Preserve the original530-line migration and426-line unit module outside the
tree. Add a controlled two-direction regression which excludes embedded
frozen body literals, derives the outer row-variable names and catalog table
aliases, and refuses their intersection. It must fail on both original
generated statements, then pass after the rename. This source invariant is
not a PostgreSQL compiler or runtime test. Keep all87 existing controls;
only their two namespace-record-specific assertion lines may change by the
same reversible identifier substitution. Prove exact inverse-renamed SQL in
both directions and unchanged other helper/TARGETS ASTs, DDL and predicates.

Original actual evidence remains in the root's local
`/tmp/scanipy-role-pg-wrapper-ETRyLPDw/RESULT-FAILED.md` record and its adjacent
`role-pg-junit.xml`, `catalog-before.json` and `catalog-after.json`. These are
retained local evidence, not a public immutable archive. The report SHA256 is
`64b872b894fffc94ef4e2f6f9d9a9cca019ddd3ca8dad27583b5b7f69632dba5`.
The after-catalog contains the retained child OID34310 and fixture roles;
the new reader role is absent and other_clients is empty. That does not
authorize adoption or cleanup. Any new actual campaign or disposition needs
separate exact-target review and root approval. Source-only corrected results
will be appended after they are observed; all real role/factory/current-
authority, native/operator/restore and full shared-gate claims remain open.

### 7.1. Observed controlled correction checkpoint

The new two-direction source regression failed on the preserved original
migration with2 failures,0 errors/skips,1.099 seconds; both reported the actual
outer-record/catalog-alias intersection `{'n'}`. Its corrected-source run
passes alongside all87 previous cases. Final configured Python3.11.16 result:
89 unique passes,0 failures/errors/skips,1.905 seconds JUnit. Report SHA256:
`dabbd150e9a326712d0ae0e9c88ab5146a740e75b347ab304739918d54eef9a1`.
The earlier corrected89 run overlaps this selection and is not extra coverage.
Its only later test change was formatting of the new regression; its AST and
the original red regression's AST are identical.

Read-only preservation checks prove exactly eight source token substitutions,
exact inverse-renamed original source/AST, and byte-identical `_role_guard`,
`_privileges`, six TARGETS and each function guard. Each rendered direction has
15 uses of the renamed variable; inverse rename restores the full original SQL.
Corrected generated sizes are67,934/72,649 UTF-8 bytes, still below131,072.
The two permitted old assertion lines reverse exactly to the426-line original
unit prefix; all22 original definition ASTs are exact after that reversal.
This document's228-line pre-correction prefix is exact.

Ruff check/format, strict mypy on the single migration and diff-check pass.
The first format check requested only a line-wrap change in the new regression;
it was corrected without changing an old test AST or migration behavior.
Same-settings detect-secrets1.5 API inspection found no findings in the three
allocated paths; no annotation, baseline or scanner-setting change was needed.
No hook, commit, migration, database connection, fixture cleanup or native
operation ran for this correction. Real PG qualification is still pending.

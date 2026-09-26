# Accepted historical-read outcomes — owning contract

2026-09-26. Root engineering approved the exact five-path source and controlled-test
allocation below after reading the 166-line proposal at SHA256
`4ddc5805f587d6b1d846e5c59a193f435700c004e705fe762ae740ba28615d97`.
This is an engineering decision, not separate human/operator approval. Actual
PostgreSQL execution, installation and A2 consumption are not approved here.

This self-contained contract supersedes only the ambiguous absence-versus-error
classification in ACCEPTED-LEDGER-SQL.md §D.2. Public error codes, successful
wire bytes, existing limits, ownership and all other contracts remain unchanged.
Implementation base: accepted `a871c00a9b05299f11b2662dd9bdb3bf841f2afd`, tree
`f071afd0502dc2716bc3ab80e94d7e77460cc294`. Revision0007 was verified unused.

## 1. Evidence and defect

Reviewed owner tree: `/tmp/scanipy-builtin-administration-a2-RJLQcFmW`, base A
`a56c5f7f5c8a74531ad0d45f831efbaaf40630fd`. Frozen B remains unchanged.
The independent final-byte run was 647 passed; the separate 12-case diagnostic
was six failures/six passes. These are controlled Python diagnostics, not PG.
Both reports and original test remain in
`/tmp/scanipy-a2-b-peer-review-fLBhl8kL`; no rerun is proposed here.

Every reachable SQL P0001/ledger-mismatch in R1/R3 is accounted for:

| Owner location | Meaning |
| --- | --- |
| `accepted_v1_reads.sql:180–181`, R1 first selection | No matching approval selector **or** invalid retained record/receipt length. |
| `accepted_v1_reads.sql:160–164`, called by R1:193 | Receipt/approval identity, publication, content, inventory, actor or digest linkage mismatch; not absence. |
| `accepted_v1_reads.sql:216–217`, R3 first selection | No exact row (currently including requested digest) **or** invalid retained record length. |
| `accepted_v1_reads.sql:242`, R3 approval support | Same receipt/approval linkage checks. |
| R3:243 → `accepted_v1_operations.sql:437–449` → :411–435 → :427 | The same linkage checks again during original publication-material validation. |

R3 policy/admission has no further ledger-mismatch branch. Its wrong schema,
event/digest or signature is content-mismatch. Namespace lookup/scope failures
are 42501/scope-mismatch (`accepted_v1_operations.sql:3–34`), never absence.
Other errors in the R3 approval closure include grant/time/checkpoint failures;
none become unavailable. `v1_live`, R2 and R4–R6 are not R1/R3 callees.

`ledger_repository.py:309–331` maps only known genuine P0001/42501 primary
messages, retaining the driver error as cause. It currently ignores DETAIL.
The same ledger-mismatch can also arise after a successful fetch in Python;
those result/link failures have no raw I/O origin and remain fatal.
AL contract §D.2 currently groups missing, wrong requested digest and record
linkage under ledger-mismatch; it permits no absent-as-NULL success.

## 2. Root-approved semantic distinction

Fixed private DETAIL literal: `accepted-historical-row-missing`.
There is one exact literal, not a prefix/pattern, public code or new result field.

R1: keep the exact initial scoped selector and reservation. Immediately after
its SELECT, `IF NOT FOUND` raises P0001/ledger-mismatch with that DETAIL.
The existing length guard follows separately with ordinary unmarked
ledger-mismatch. Every later raw/link/namespace/material check stays unchanged.

R3: keep one initial bounded query keyed by namespace, kind and event ID.
Remove only the requested-digest WHERE predicate; select stored record_digest
alongside the existing three lengths. Raise the marker only if this keyed row
is missing; then independently require exact requested/stored digest equality
and the existing length bound as unmarked ledger-mismatch. The extra fixed
32-byte digest fits the existing 512-byte control reservation. No raw blob,
extra query, alternative-kind search or authority lookup is introduced.

The marker means no matching **typed selector row in the scoped lookup**;
it is not proof of no foreign/other-kind history, a fresh permission, or an
operation acknowledgement. Wrong requested digest must never receive it.
No sentinel on length, link, work, malformed stored material or permission
failures. Public signature, P0001/message, successful bytes and budgets remain.

## 3. Exact genuine-driver classification

Add one private owner helper in `ledger_repository.py`, fixed name
`_historical_read_failure_kind(error: BaseException)` returning only
`Literal["missing", "transport"] | None`. Keep `_driver_code` public behavior
and all existing facade error/result/transaction behavior unchanged.

Read built-in `psycopg2.Error` pgcode/diag descriptors and the actual
`psycopg2.extensions.Diagnostics` field descriptors; never overridden instance
properties, str/repr, diagnostic context text, recursive chains or custom
exception callbacks. Reject custom subclasses and type/state inconsistencies.

- `missing`: exact installed RaiseException class, genuine SQLSTATE P0001,
  exact primary `ledger-mismatch`, exact private DETAIL above. Returned mapped
  VerificationError must itself be exact-type ledger-mismatch whose original
  cause is that same captured driver error.
- `transport`: exact installed `errors.lookup(state)` type for the closed set
  08000, 08001, 08003, 08004, 08006, 08007, 08P01; or exact base
  psycopg2.OperationalError/InterfaceError with genuine pgcode None.
  This applies only when the final exception is that same original error.
- Otherwise None, including 42501, 42P01, 22xxx, 57014, 55P03, 53xxx/57xxx,
  unknown P0001, all unmarked ledger-mismatch and other mapped owner failures.
  OperationalError inheritance alone is insufficient (timeouts inherit it).

The existing A2 marker remains activated only for actual R1/R3 execute/fetch.
Require original/outer exception identities and unchanged cause/context links
after cursor cleanup, rollback and factory close. Connection/catalog/settings,
cursor acquisition, local guard, returned-data and cleanup failures stay fatal.
No descriptor match excuses a cleanup failure or permits a retry/reset/refund.
Status 4 retains unresolved observation with the exact private original failure;
it does not write an ack, declare absence as authority or replay a mutation.

## 4. Forward migration, no historical rewrite

New revision `20260926_0007`, down_revision `20260926_0006`; its absence was
verified before creating the isolated implementation worktree.
Use a new `db/migrations/versions/20260926_0007_accepted_read_outcomes.py` with
frozen literal up/down definitions for exactly the two functions. Preserve
all old 0006/.sql bytes. Do not import a runtime codec/owner or rewrite old SQL.

Upgrade uses CREATE OR REPLACE, never DROP/regrant/new functions/tables/roles.
Before replacement, require both exact existing signatures, predecessor bodies,
expected owner and function properties (language, result/argument metadata,
SECURITY DEFINER, search_path, bytea_output, volatility/strictness/parallel and
other emitted properties). Missing or drifted targets refuse atomically; never
let CREATE OR REPLACE silently create an absent function with default ACLs.
Capture identities/ACLs and check preservation; do not scrub or adopt privileges.
Normal exclusive migration custody is required; no hostile concurrent DB-owner
guarantee is claimed. Literal submission must preserve colons, casts and percent
bytes using the already-reviewed Alembic escaping behavior.

Downgrade checks the exact successor bodies and restores the exact 0006 bodies
with the same replacement discipline, without touching retained history.
Clients on old/downgraded SQL fail closed on unmarked missing ledger-mismatch.
Deploy 0007 before enabling the new missing-outcome behavior; no startup query,
fallback inference or automatic migration is added to A2.

PostgreSQL16 states replacement preserves ownership/permissions but assigns
other properties from the new declaration; all such declarations must remain
exact: https://www.postgresql.org/docs/16/sql-createfunction.html . Psycopg
documents the actual diagnostic fields separately:
https://www.psycopg.org/docs/extensions.html#psycopg2.extensions.Diagnostics .

## 5. Exact non-conflicting allocation and tests

Allocated owner slice, in a separate worktree, exactly these five paths:

1. New migration above (embedded frozen up/down bodies; no extra SQL resource).
2. `services/scan/accepted_inputs/ledger_repository.py`: private classifier only.
3. NEW `tests/unit/test_accepted_historical_reads.py`.
4. NEW `tests/integration/test_accepted_historical_reads.py`.
5. NEW `docs/bhmea/ACCEPTED-HISTORICAL-READ-OUTCOMES.md`: self-contained governing
   correction, precedence over only the older ambiguous read-outcome wording.

Separately canonical owns `tests/occurrence_store_postgres.py`: add only literal
0007 to accepted-profile migrate allowlist. Default accepted0006 and occurrence
0005 and all existing setup/OID/cleanup schedules stay unchanged. The new PG
module/A2 fixture explicitly upgrades its already-owned accepted child to0007;
no `head`, second colliding session fixture, ambient URL or operator DB.
Canonical also owns the existing repository unit module; do not edit it here.

After owning correction is reviewed, separately authorize B author to consume
the private classifier in admission._ReadOrigin and update its controlled
regressions/append-only resolver chronology. No edit to frozen B before that
grant, and no claim owner slice alone fixes the A2 conversion.

Required pure controls: exact genuine descriptors/type rejection, each allowed
state and base-None case, wrong/missing DETAIL/primary/state/type, every excluded
server category, six retained material/work reds, unmarked missing/link mismatch,
origin/link/cleanup gates, no descriptor formatting/properties and no SQL calls.
Test actual Alembic PostgreSQL compilation, no invented binds, and byte/AST
comparison showing only authorized R1/R3 semantic edits versus frozen0006.

Required scheduled real-PG controls: populated0006→0007→0006→0007; same function
OIDs/owners/ACL/config and exact history; actual error descriptors for R1 missing
via both selectors and R3 missing for every supported kind; present event with
wrong requested digest unmarked; stored length/link/syntax/signature/work and
scope failures unmarked/fatal; valid reads byte-exact; existing restricted-role
rights unchanged; drift/missing-target upgrade rollback; no additional query or
raw selection. Controlled corruption must be explicit transaction-local test
setup with rollback, not a claim normal owner writes produce corrupt history.

No real PG/native/keys/UID/production installation is authorized by this plan.

## 6. Source checkpoint and evidence, 2026-09-26

The five-path implementation is now authored for root/independent review, not
accepted or installed. Its only pre-existing source change is the new private
classifier and the necessary Literal import. The public mapper, facade methods,
all historical test bodies, 0006 and its SQL/resources remain unchanged.

Controlled reports live in `/tmp/scanipy-historical-read-evidence-bnD5bINi`:

- `classifier-before.xml`: five failures, no errors/skips, 0.994 seconds;
  SHA256 `1e1edb20f194c1499894953ad3a8eb2fb92417447bcb898cb380902f4bba07a2`.
  All five were absent-helper AttributeErrors: a construction baseline, **not**
  reproduced SQL failures or the separate six B semantic reds.
- `owner-first.xml`: 94 passed, no failures/errors/skips, 1.791 seconds;
  SHA256 `f87cbdbf34f71df38ae5c03151adf8cb846e4487f5b1ce59e45ad1686d06aeb5`.
- `owner-final.xml`: 97 unique passed, no failures/errors/skips, 1.426 seconds;
  SHA256 `2004d2977bd87946f1f6290a712d4dd77cc8c6107785088b3c7df63c46f96857`.
  This overlaps the preceding 94; the counts are not additive.

These Python tests use restored genuine driver objects/native member descriptors
and separately labelled controlled diagnostic-descriptor oracles. Neither is a
server SQLSTATE observation. Actual Alembic/SQLAlchemy offline compilation is
tested; it is not PostgreSQL parsing, execution or migration acceptance.
Ruff, four-file formatting and strict two-source-file Mypy checks passed after
correcting literal-SQL line annotations and tuple-index typing diagnostics.

The new dedicated PG module contains 38 parameterized cases by static inventory;
none has been collected or executed in this checkpoint. It explicitly requires
the separately owned accepted0007 harness allowlist, performs owned-child
upgrade/downgrade, and leaves the default0006/occurrence0005 schedule unchanged.
Signature-length corruption is explicitly a table-constraint refusal before
R3, not a claim that the R3 decoder ran on an impossible ordinary-history row.
Actual missing/link/digest/length/corruption, catalog preservation and restricted
role efficacy remain scheduled PostgreSQL gates.

Frozen A2 B is untouched. Its six previously retained semantic reds remain
unresolved until a separately reviewed consumer change uses this classifier
with the required raw-origin/identity/link/cleanup gates. No source-only result
here establishes installation, a successful read, replay acknowledgement,
current authority, native execution, or complete Black Hat acceptance.

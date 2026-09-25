# Targeted board lookup — corrective issue #377

Scope: repository-workflow prerequisite under #362, not a new analysis gate or
completion of a Black Hat feature. Only `scripts/board.sh`, its dedicated fake-`gh`
tests and this evidence note change. Existing project IDs are resolved live, not
hardcoded. This helper remains the auditable board interface required by RULE-11.

## Contract

The existing `status <issue>`, `check <issue>` and `set <issue> <status>` commands
remain. Defaults are repository `scanipy/scanipy`, project owner `scanipy`, project
number `5`. Existing `SCANIPY_PROJECT_OWNER` and `SCANIPY_PROJECT_NUMBER` overrides
remain; `SCANIPY_REPOSITORY=owner/repository` explicitly selects the repository.
The current checkout/`gh` default repository cannot silently redirect a lookup.
Issue/project numbers must be positive GraphQL Ints; unsupported arguments fail
before any network request.

Every lookup performs at most two bounded GraphQL reads, with no pagination,
retry loop, fallback credential or project-wide item listing:

1. Exact repository issue → first 20 project memberships, issue/content identity,
   project owner/number/ID, archive flag and current Status identity.
2. Selected project ID → first 50 field names/IDs/types and only the named Status
   field's options. The full small field inventory is needed to detect duplicate
   Status names; `field(name:)` alone cannot establish uniqueness.

Both connections must have `hasNextPage=false` and `totalCount` equal to the
returned inventory size. Null, missing, duplicate, ambiguous, truncated, wrong
repository/project/content and GraphQL partial-error responses fail closed.
Each response must contain exactly one JSON document, and an errors field, if
present, must be an empty array. Only the literal `Todo` may authorize work.
Closed projects and archived target items are rejected. No first-match shortcut
or implicit `Todo` is used. Exactly one single-select Status field must exist,
with uniquely identified `Todo`, `In Progress` and `Done` options; its selected
option ID/name and field ID must agree. Unknown workflow columns need an explicit
reviewed contract change, not an automatic authorization to start work.

Exit behavior:

- `status`: exact current status and exit 0.
- `check`: `Todo` permits work (0); `In Progress` or `Done` blocks work (3).
- Errors, including a genuinely unset value for `check`/`status`: exit 2.
- `set`: an explicit allowed target may initialize a verified null Status,
  printing `Unset → <target>`. A missing response field, malformed value or
  unknown option cannot enter this initialization path. Repeating the current
  target is a successful no-op with no mutation request.

Changed `set` operations retain the existing `gh project item-edit` command with
the verified item, project, field and option IDs. A command failure never prints
a successful transition. This read-then-write workflow is **not an atomic lock**:
coordinators must still serialize ownership transitions. No generic helper can
infer which agent owns an already `In Progress` issue from Status alone.

## Evidence and boundary

On 2026-09-25 the previous helper performed project view, full field listing and
up to 250 full project-item reads for every command. It matched only issue number,
which could select another repository's identically numbered issue. Coordinated
use exhausted the shared GraphQL quota; REST rate-limit reporting did not describe
the exhausted GraphQL budget reliably. No alternative credentials were used.

One authorized read-only `BoardIssue` query on 2026-09-25 confirmed the new query
shape against GitHub: reported cost **1**, remaining **7**, reset
`2026-09-25T10:07:38Z`. Issue #377 existed with zero project memberships. No live
mutation or second live metadata query was made during implementation. This is
not a measured total two-query cost or latency claim. Initial board preflight and
claim therefore remain pending, explicitly recorded under the root's exclusive
assignment while the quota-blocked helper is repaired. Required CI and canonical
review approval remain prerequisites for merge/helper replacement.

Hermetic tests use a fake `gh` executable and check exact request arguments,
bounded reads, all status transitions, no-op writes, repository/project overrides,
explicit unset initialization, exit codes, malformed/partial/truncated/ambiguous
records, wrong identities, unique status options and command failures. They never
contact GitHub or mutate a project. Bash syntax, ShellCheck, Ruff and strict mypy
are run in addition; two narrow SC2016 annotations explain intentional GraphQL
`$variable` literals, not ignored safety warnings.

The schema reference is GitHub's own published
[GraphQL schema](https://github.com/github/docs/blob/main/src/graphql/data/ghes-3.20/schema.docs-enterprise.graphql):
`Issue.projectItems`, `ProjectV2Item.fieldValueByName`, `ProjectV2.fields`,
`ProjectV2.field`, and `ProjectV2ItemFieldSingleSelectValue`. Its documented
first-matching-field behavior is why uniqueness is checked independently. The
small live query validates GitHub.com membership-field compatibility; hermetic
tests alone are not a live-service proof.

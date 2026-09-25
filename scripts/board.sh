#!/usr/bin/env bash
# scripts/board.sh — Scanipy v3.2 GitHub Project board helper (project #5).
#
# The single mechanical interface for RULE-11 (board hygiene). Every agent that
# picks up or completes a CMP-* / T-CMP-* / meta issue uses this to read and
# write the board's `Status` field, keeping the board honest about who-is-doing-
# what so concurrent agents do not duplicate work or collide on merges.
#
# Usage:
#   scripts/board.sh check  <issue-number>            Pre-flight gate. Prints status.
#                                                     Exit 3 if NOT safe to start
#                                                     (already In Progress / Done).
#   scripts/board.sh status <issue-number>            Print the current Status only.
#   scripts/board.sh set    <issue-number> <status>   Set Status. <status> is one of:
#                                                     Todo | "In Progress" | Done
#
# Status maps to WBS.md status codes:
#   Todo        ← BLOCKED | READY | STAGE-GATED   (WBS.md carries the nuance)
#   In Progress ← IN-PROGRESS
#   Done        ← DONE
#
# Requires: gh (authenticated), jq. No network fallbacks — a failure is a hard
# error (exit non-zero), never a silent no-op, per the project's CI philosophy.
# Repository defaults to scanipy/scanipy, independent of the current directory;
# SCANIPY_REPOSITORY may explicitly select another owner/repository. Existing
# SCANIPY_PROJECT_OWNER and SCANIPY_PROJECT_NUMBER overrides remain supported.
# Lookup is bounded to 20 issue memberships and 50 selected-project fields.
# Truncation, ambiguity and unknown Status fail closed; no implicit Todo.
# A verified unset value blocks check/status; set can explicitly initialize it.
set -euo pipefail

OWNER="${SCANIPY_PROJECT_OWNER:-scanipy}"
PROJECT_NUMBER="${SCANIPY_PROJECT_NUMBER:-5}"
REPOSITORY="${SCANIPY_REPOSITORY:-scanipy/scanipy}"

die() { echo "board.sh: $*" >&2; exit 2; }

command -v gh >/dev/null 2>&1 || die "gh CLI not found on PATH"
command -v jq >/dev/null 2>&1 || die "jq not found on PATH"

cmd="${1:-}"
issue="${2:-}"
new="${3:-}"
case "$cmd" in
  check|status) [ "$#" -eq 2 ] || die "usage: board.sh $cmd <issue-number>" ;;
  set)
    [ "$#" -eq 3 ] || die 'usage: board.sh set <issue-number> <Todo|"In Progress"|Done>'
    case "$new" in Todo|"In Progress"|Done) ;; *) die "unknown Status option '$new'" ;; esac
    ;;
  *) die 'usage: board.sh {check|status|set} <issue-number> [status]' ;;
esac
if ! [[ "$issue" =~ ^[1-9][0-9]{0,9}$ ]] || ((issue > 2147483647)); then
  die "issue number must be a positive GraphQL Int: '$issue'"
fi
if ! [[ "$PROJECT_NUMBER" =~ ^[1-9][0-9]{0,9}$ ]] || ((PROJECT_NUMBER > 2147483647)); then
  die "project number must be a positive GraphQL Int"
fi
[[ "$OWNER" =~ ^[A-Za-z0-9][A-Za-z0-9-]*$ ]] || die "invalid project owner"
[[ "$REPOSITORY" =~ ^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+$ ]] \
  || die "repository must be owner/repository"

# Start at the exact repository issue, not all items on a board (where issue
# numbers are not unique). Fetch only small membership metadata here; field
# definitions are fetched once, for the selected project, in the second read.
# shellcheck disable=SC2016 # GraphQL variables must not expand in the shell.
items_json=$(gh api graphql \
  -f owner="${REPOSITORY%%/*}" -f repo="${REPOSITORY#*/}" -F number="$issue" \
  -f query='query BoardIssue($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      nameWithOwner
      issue(number: $number) {
        id number
        projectItems(first: 20, includeArchived: true) {
          totalCount pageInfo { hasNextPage }
          nodes {
            id isArchived
            content { __typename ... on Issue { id number repository { nameWithOwner } } }
            project { id number owner { __typename ... on Organization { login } ... on User { login } } }
            fieldValueByName(name: "Status") {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name optionId field { ... on ProjectV2FieldCommon { id name } }
              }
            }
          }
        }
      }
    }
  }') || die "cannot read issue $REPOSITORY#$issue project membership (gh auth/quota?)"

item_json=$(jq -ce --arg repo "$REPOSITORY" --arg owner "$OWNER" \
  --argjson issue "$issue" --argjson project "$PROJECT_NUMBER" '
  def need($condition; $message): if $condition then . else error($message) end;
  def text: type == "string" and test("^[^[:cntrl:][:space:]]+$");
  need(type == "object" and ((.errors // []) == []); "GraphQL errors")
  | .data.repository
  | need((.nameWithOwner | ascii_downcase) == ($repo | ascii_downcase); "wrong repository")
  | .issue
  | need(.number == $issue and (.id | text); "missing/wrong issue")
  | . as $issue_record | .projectItems
  | need((.nodes | type) == "array" and .pageInfo.hasNextPage == false
      and .totalCount == (.nodes | length) and (.nodes | length) <= 20;
      "missing/truncated membership connection")
  | need(all(.nodes[]; (.id | text) and (.project.id | text)
      and (.project.owner.login | text) and (.project.number | type) == "number"
      and (.isArchived | type) == "boolean"); "malformed membership")
  | need(([.nodes[].id] | unique | length) == (.nodes | length); "duplicate item ID")
  | [.nodes[] | select(.project.number == $project
      and (.project.owner.login | ascii_downcase) == ($owner | ascii_downcase))]
  | need(length == 1; "missing/ambiguous target project item") | .[0]
  | need(.isArchived == false; "target item is archived")
  | need((.project.owner.__typename == "Organization" or .project.owner.__typename == "User")
      and .content.__typename == "Issue" and .content.id == $issue_record.id
      and .content.number == $issue
      and (.content.repository.nameWithOwner | ascii_downcase) == ($repo | ascii_downcase);
      "wrong item repository/issue/project owner")
' <<<"$items_json") || die "invalid/incomplete membership for $REPOSITORY#$issue"
project_id=$(jq -er '.project.id' <<<"$item_json") || die "missing project ID"

# shellcheck disable=SC2016 # GraphQL variables must not expand in the shell.
field_json=$(gh api graphql -f id="$project_id" -f query='
  query BoardFields($id: ID!) {
    node(id: $id) {
      __typename
      ... on ProjectV2 {
        id number closed
        owner { __typename ... on Organization { login } ... on User { login } }
        fields(first: 50) {
          totalCount pageInfo { hasNextPage }
          nodes {
            __typename
            ... on ProjectV2FieldCommon { id name }
          }
        }
        statusField: field(name: "Status") {
          __typename
          ... on ProjectV2FieldCommon { id name }
          ... on ProjectV2SingleSelectField { options { id name } }
        }
      }
    }
  }') || die "cannot read fields for selected project #$PROJECT_NUMBER"

metadata=$(jq -ce --arg id "$project_id" --arg owner "$OWNER" \
  --argjson project "$PROJECT_NUMBER" --argjson item "$item_json" '
  def need($condition; $message): if $condition then . else error($message) end;
  def text: type == "string" and test("^[^[:cntrl:][:space:]]+$");
  need(type == "object" and ((.errors // []) == []); "GraphQL errors")
  | .data.node
  | need(.__typename == "ProjectV2" and .id == $id and .number == $project
      and .owner.__typename == $item.project.owner.__typename
      and (.owner.login | ascii_downcase) == ($owner | ascii_downcase)
      and .closed == false; "wrong/closed project")
  | . as $selected_project | .fields
  | need((.nodes | type) == "array" and .pageInfo.hasNextPage == false
      and .totalCount == (.nodes | length) and (.nodes | length) <= 50;
      "missing/truncated field connection")
  | need(all(.nodes[]; (.id | text) and (.name | type) == "string"); "malformed field")
  | need(([.nodes[].id] | unique | length) == (.nodes | length); "duplicate field ID")
  | [.nodes[] | select(.name == "Status")]
  | need(length == 1; "missing/ambiguous Status field") | .[0]
  | . as $selected_field | $selected_project.statusField
  | need(.id == $selected_field.id and .name == "Status"
      and .__typename == $selected_field.__typename; "wrong Status field definition")
  | need(.__typename == "ProjectV2SingleSelectField" and (.options | type) == "array";
      "Status is not single-select")
  | need((.options | map(.name) | sort) == ["Done", "In Progress", "Todo"]
      and all(.options[]; (.id | text))
      and ([.options[].id] | unique | length) == 3; "invalid/ambiguous Status options")
  | . as $field | $item.fieldValueByName as $current
  | need($item | has("fieldValueByName"); "missing Status response field")
  | need($current == null or ($current.__typename == "ProjectV2ItemFieldSingleSelectValue"
      and $current.field.id == $field.id and $current.field.name == "Status"
      and ([.options[] | select(.id == $current.optionId and .name == $current.name)] | length) == 1);
      "invalid Status value")
  | {item_id: $item.id, field_id: $field.id,
      current: (if $current == null then "Unset" else $current.name end), options: .options}
' <<<"$field_json") || die "invalid/incomplete Status metadata for project #$PROJECT_NUMBER"
item_id=$(jq -er '.item_id' <<<"$metadata") || die "missing item ID"
status_field_id=$(jq -er '.field_id' <<<"$metadata") || die "missing Status field ID"
cur_status=$(jq -er '.current' <<<"$metadata") || die "missing Status value"
if [ "$cur_status" = "Unset" ] && [ "$cmd" != "set" ]; then
  die "issue #$issue Status is Unset; initialize explicitly: scripts/board.sh set $issue Todo"
fi

case "$cmd" in
  status)
    echo "$cur_status"
    ;;

  check)
    echo "issue #$issue board status: $cur_status"
    case "$cur_status" in
      "In Progress")
        echo "BLOCKED: #$issue is already In Progress — another agent owns it. Do NOT duplicate work."
        exit 3
        ;;
      "Done")
        echo "BLOCKED: #$issue is already Done. Do NOT re-implement."
        exit 3
        ;;
      *)
        echo "OK to start. On first edit run:  scripts/board.sh set $issue \"In Progress\""
        ;;
    esac
    ;;

  set)
    opt_id=$(jq -er --arg s "$new" '.options[] | select(.name==$s) | .id' <<<"$metadata") \
      || die "missing Status option '$new'"
    if [ "$new" != "$cur_status" ]; then
      gh project item-edit \
        --id "$item_id" \
        --field-id "$status_field_id" \
        --project-id "$project_id" \
        --single-select-option-id "$opt_id" >/dev/null \
        || die "failed to set Status for #$issue"
    fi
    echo "issue #$issue: $cur_status → $new"
    ;;
esac

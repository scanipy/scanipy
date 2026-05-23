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
set -euo pipefail

OWNER="${SCANIPY_PROJECT_OWNER:-scanipy}"
PROJECT_NUMBER="${SCANIPY_PROJECT_NUMBER:-5}"

die() { echo "board.sh: $*" >&2; exit 2; }

command -v gh >/dev/null 2>&1 || die "gh CLI not found on PATH"
command -v jq >/dev/null 2>&1 || die "jq not found on PATH"

cmd="${1:-}"
issue="${2:-}"
[ -z "$cmd" ]  && die "usage: board.sh {check|status|set} <issue-number> [status]"
[ -z "$issue" ] && die "missing <issue-number>"
case "$issue" in (*[!0-9]*) die "issue number must be numeric: '$issue'";; esac

# Resolve project node id + Status field metadata (fetched live so the script
# survives a board re-create; the IDs are not hard-coded).
proj_json=$(gh project view "$PROJECT_NUMBER" --owner "$OWNER" --format json) \
  || die "cannot read project #$PROJECT_NUMBER for owner '$OWNER' (gh auth?)"
project_id=$(jq -r '.id' <<<"$proj_json")
if [ -z "$project_id" ] || [ "$project_id" = "null" ]; then die "could not resolve project node id"; fi

field_json=$(gh project field-list "$PROJECT_NUMBER" --owner "$OWNER" --format json) \
  || die "cannot list fields for project #$PROJECT_NUMBER"
status_field_id=$(jq -r '.fields[] | select(.name=="Status") | .id' <<<"$field_json")
if [ -z "$status_field_id" ] || [ "$status_field_id" = "null" ]; then die "Status field not found"; fi

items_json=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json --limit 250) \
  || die "cannot list items for project #$PROJECT_NUMBER"
item_id=$(jq -r --argjson n "$issue" '.items[] | select(.content.number==$n) | .id' <<<"$items_json")
cur_status=$(jq -r --argjson n "$issue" '.items[] | select(.content.number==$n) | (.status // "Todo")' <<<"$items_json")
[ -z "$item_id" ] && die "issue #$issue is not on project board #$PROJECT_NUMBER"

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
    new="${3:-}"
    [ -z "$new" ] && die "usage: board.sh set <issue-number> <Todo|\"In Progress\"|Done>"
    opt_id=$(jq -r --arg s "$new" \
      '.fields[] | select(.name=="Status") | .options[] | select(.name==$s) | .id' <<<"$field_json")
    [ -z "$opt_id" ] && die "unknown Status option '$new' (valid: Todo, \"In Progress\", Done)"
    gh project item-edit \
      --id "$item_id" \
      --field-id "$status_field_id" \
      --project-id "$project_id" \
      --single-select-option-id "$opt_id" >/dev/null \
      || die "failed to set Status for #$issue"
    echo "issue #$issue: $cur_status → $new"
    ;;

  *)
    die "unknown command '$cmd' (valid: check, status, set)"
    ;;
esac

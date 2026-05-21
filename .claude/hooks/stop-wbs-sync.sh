#!/usr/bin/env bash
# Scanipy v3.2 — stop-time WBS status snapshot
#
# Prints a brief status summary when the Claude Code session ends.
# Helps the next agent pick up without having to re-read the whole WBS.
# Exit 0 always.

set -uo pipefail

WBS="${WBS_PATH:-WBS.md}"
[ ! -f "$WBS" ] && exit 0

# Count status codes appearing in WBS tables.
IN_PROG=$(grep -oE '\bIN-PROGRESS\b' "$WBS" 2>/dev/null | wc -l | tr -d ' ')
READY=$(grep -oE '\bREADY\b' "$WBS" 2>/dev/null | wc -l | tr -d ' ')
DONE_CNT=$(grep -oE '\bDONE\b' "$WBS" 2>/dev/null | wc -l | tr -d ' ')
BLOCKED=$(grep -oE '\bBLOCKED\b' "$WBS" 2>/dev/null | wc -l | tr -d ' ')
OPEN_CLAR=$(grep -cE '^\| *CLAR-' "$WBS" 2>/dev/null || echo 0)

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Scanipy v3.2 — WBS status at session end"
echo "  IN-PROGRESS: $IN_PROG  │  READY: $READY  │  DONE: $DONE_CNT  │  BLOCKED: $BLOCKED"
echo "  Open CLAR-* items (WBS §17): $OPEN_CLAR"
echo ""
echo "  Next: run /sync-wbs to identify work eligible to start."
echo "═══════════════════════════════════════════════════════"

exit 0

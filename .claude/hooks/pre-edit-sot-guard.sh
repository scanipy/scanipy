#!/usr/bin/env bash
# Scanipy v3.2 — pre-edit source-of-truth guard
#
# Blocks any attempted edit to PLAN.md or SDD.md, which are the two highest-
# authority documents in the source-of-truth hierarchy. No agent may modify them.
# WBS.md is allowed for §17 CLAR-*, §18 OOS-*, and status-code flips only.

set -uo pipefail

# Claude Code delivers hook context on stdin as JSON.
HOOK_INPUT="$(cat 2>/dev/null || echo '{}')"
EDITED_PATH="$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"

[ -z "$EDITED_PATH" ] && exit 0

BASE="$(basename "$EDITED_PATH")"

case "$BASE" in
  PLAN.md)
    echo "[sot-guard] BLOCKED: PLAN.md is the highest-authority document. Agents must not edit it." >&2
    echo "[sot-guard] If the architecture appears wrong, file a CLAR-* in WBS.md §17." >&2
    exit 2
    ;;
  SDD.md)
    echo "[sot-guard] BLOCKED: SDD.md is source-of-truth #2. Agents must not edit it." >&2
    echo "[sot-guard] If a component spec is incomplete, file a CLAR-* in WBS.md §17." >&2
    exit 2
    ;;
  WBS.md)
    echo "[sot-guard] NOTICE: WBS.md edit detected." >&2
    echo "[sot-guard] Allowed: §17 CLAR-* appends, §18 OOS-* appends, status-code flips (§1.2)." >&2
    echo "[sot-guard] Not allowed: structural changes, renumbering CMP-* IDs, adding design decisions." >&2
    # Advisory only — do not block.
    exit 0
    ;;
esac

exit 0

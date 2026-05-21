#!/usr/bin/env bash
# Scanipy v3.2 — post-edit invariant check (advisory)
#
# Fires after any Edit or Write. For files in finding-emitting paths
# (services/, analysis/, detectors/) it checks whether the four required
# provenance fields are referenced. This is advisory only — the hard gate
# lives in tests/unit/test_inv_provenance.py and CMP-CI-01.
#
# Exit 0 always (never blocks).

set -uo pipefail

HOOK_INPUT="$(cat 2>/dev/null || echo '{}')"
EDITED_PATH="$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"

[ -z "$EDITED_PATH" ] && exit 0
[ ! -f "$EDITED_PATH" ] && exit 0

# Only check files in finding-emitting subsystems.
case "$EDITED_PATH" in
  services/*|analysis/*|detectors/*) ;;
  *) exit 0 ;;
esac

# Heuristic: file defines or calls something that looks like a Finding constructor.
if grep -qE '(class Finding|emit_finding|new_finding|Finding\(|Finding\{)' "$EDITED_PATH" 2>/dev/null; then
  MISSING=()
  for field in "S_version" "env_digest" "origin" "cpg_order_hash"; do
    grep -q "$field" "$EDITED_PATH" 2>/dev/null || MISSING+=("$field")
  done
  if [ "${#MISSING[@]}" -gt 0 ]; then
    echo "" >&2
    echo "┌─ [provenance-check] WARNING ──────────────────────────────────────────" >&2
    echo "│  File: $EDITED_PATH" >&2
    echo "│  Emits findings but does not reference: ${MISSING[*]}" >&2
    echo "│  INV-1 requires 'origin'; INV-2 requires 'S_version' + 'env_digest'." >&2
    echo "│  INV-5 requires 'cpg_order_hash' with conditional-canonicality annotation." >&2
    echo "│  See: CLAUDE.md §3, docs/cross-cutting/DOC-PROVENANCE.md" >&2
    echo "└───────────────────────────────────────────────────────────────────────" >&2
  fi
fi

exit 0

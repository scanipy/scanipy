#!/usr/bin/env bash
# check-finding-provenance.sh — pre-commit advisory check for Finding provenance fields.
#
# Usage: check-finding-provenance.sh <file1.py> [file2.py ...]
# Exits 0 always (advisory). Prints warnings for files that construct Finding()
# or call emit_finding() but appear to be missing one or more of the four required
# provenance fields: origin, S_version, env_digest, cpg_order_hash.

set -euo pipefail

REQUIRED_FIELDS=("origin" "S_version" "env_digest" "cpg_order_hash")
EXIT_CODE=0

for file in "$@"; do
    # Only check files that actually reference Finding construction patterns
    if ! grep -qE '(Finding\(|emit_finding)' "$file" 2>/dev/null; then
        continue
    fi

    missing=()
    for field in "${REQUIRED_FIELDS[@]}"; do
        if ! grep -qE "${field}\s*=" "$file"; then
            missing+=("$field")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo "WARN [provenance-check] $file: possibly missing field(s): ${missing[*]}"
        echo "  See .claude/rules/02-provenance.md for required threading."
        # Advisory only — do not fail the commit
    fi
done

exit 0

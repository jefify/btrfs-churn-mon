#!/usr/bin/env bash

set -euo pipefail

# ============================================
# verify-bootstrap.sh — Post-bootstrap health check
# Read-only. Run after bootstrap.sh.
# ============================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"

REPORTDIR="${PREFIX}/reports"
STATEDIR="${PREFIX}/state"
ERRORS=0

check() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1
    then
        echo "  ✅ $desc"
    else
        echo "  ❌ $desc"
        ((ERRORS++))
    fi
}

echo "=== Bootstrap Health Check ==="
echo

check "reports directory exists" test -d "$REPORTDIR"
check "state directory exists" test -d "$STATEDIR"

echo
echo "=== State Files ==="
echo

if [[ -d "$STATEDIR" ]]
then
    for LAST in "$STATEDIR"/*.last
    do
        [[ -f "$LAST" ]] || continue
        FAMILY=$(basename "$LAST" .last)
        CONTENT=$(cat "$LAST")
        if [[ -n "$CONTENT" ]]
        then
            echo "  ✅ $FAMILY → $CONTENT"
        else
            echo "  ❌ $FAMILY → EMPTY"
            ((ERRORS++))
        fi
    done

    STATE_COUNT=$(find "$STATEDIR" -name "*.last" | wc -l)
    [[ $STATE_COUNT -gt 0 ]] || {
        echo "  ❌ No state files found"
        ((ERRORS++))
    }
else
    echo "  ❌ State directory missing"
    ((ERRORS++))
fi

echo
echo "=== Reports ==="
echo

if [[ -d "$REPORTDIR" ]]
then
    FAMILIES=$(find "$REPORTDIR" -maxdepth 1 -type d | tail -n +2)
    for FAM_DIR in $FAMILIES
    do
        FAM=$(basename "$FAM_DIR")
        REPORT_COUNT=$(find "$FAM_DIR" -name report.md | wc -l)
        EMPTY_COUNT=$(find "$FAM_DIR" -name detail.tsv -empty | wc -l)

        if (( REPORT_COUNT > 0 ))
        then
            echo "  ✅ $FAM: $REPORT_COUNT reports"
        else
            echo "  ❌ $FAM: no reports"
            ((ERRORS++))
        fi

        if (( EMPTY_COUNT > 0 ))
        then
            echo "  ⚠️  $FAM: $EMPTY_COUNT empty detail.tsv files"
        fi
    done
else
    echo "  ❌ Reports directory missing"
    ((ERRORS++))
fi

echo
if (( ERRORS == 0 ))
then
    echo "✅ Bootstrap looks healthy."
    exit 0
else
    echo "❌ $ERRORS issue(s) found."
    exit 1
fi

#!/usr/bin/env bash

set -euo pipefail

# ============================================
# verify-install.sh — Post-install health check
# Read-only. Run after install-systemd.sh --install.
# ============================================

SERVICE="btrfs-churn-mon"
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

echo "=== Systemd Health Check ==="
echo

check "timer unit exists" systemctl cat "${SERVICE}.timer"
check "service unit exists" systemctl cat "${SERVICE}.service"
check "timer is enabled" systemctl is-enabled "${SERVICE}.timer"
check "timer is active" systemctl is-active "${SERVICE}.timer"

# Check last trigger (timer should fire within 25h)
LAST=$(systemctl show "${SERVICE}.timer" --property=LastTriggerUSec --value 2>/dev/null || echo "")
if [[ -n "$LAST" && "$LAST" != "n/a" ]]
then
    echo "  ℹ️  Last trigger: $LAST"
else
    echo "  ⚠️  Timer has never fired yet"
fi

echo
echo "=== Reports Health Check ==="
echo

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"

REPORTDIR="${PREFIX}/reports"
STATEDIR="${PREFIX}/state"

check "reports directory exists" test -d "$REPORTDIR"
check "state directory exists" test -d "$STATEDIR"

if [[ -d "$REPORTDIR" ]]
then
    REPORT_COUNT=$(find "$REPORTDIR" -name report.md 2>/dev/null | wc -l)
    echo "  ℹ️  Reports found: $REPORT_COUNT"
fi

if [[ -d "$STATEDIR" ]]
then
    STATE_COUNT=$(find "$STATEDIR" -name "*.last" 2>/dev/null | wc -l)
    echo "  ℹ️  State files: $STATE_COUNT"
fi

echo
if (( ERRORS == 0 ))
then
    echo "✅ All checks passed."
    exit 0
else
    echo "❌ $ERRORS check(s) failed."
    exit 1
fi

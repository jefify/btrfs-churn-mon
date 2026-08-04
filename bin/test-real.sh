#!/usr/bin/env bash

set -euo pipefail

# ============================================
# test-real.sh — Privileged tests
# Requires: root + etc/btrfs-churn-mon.conf + btrfs
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

[[ $EUID -eq 0 ]] || {
    echo "ERROR: must run as root (sudo $0)" >&2
    exit 1
}

# Load config (same as runtime scripts)
source "${ROOT}/lib/load-config.rc"

# Override PREFIX for test isolation (don't touch production state)
PREFIX="${PREFIX_TEST:-/tmp/btrfs-churn-test}"
export PREFIX SNAPDIR

# Pre-flight: validate config exists
[[ -f "${ROOT}/etc/btrfs-churn-mon.conf" ]] || {
    echo "ERROR: missing etc/btrfs-churn-mon.conf" >&2
    echo "Copy etc/btrfs-churn-mon.conf.example and customize SNAPDIR." >&2
    exit 1
}

# Pre-flight: validate snapshot directory
[[ -d "$SNAPDIR" ]] || {
    echo "ERROR: SNAPDIR not found: $SNAPDIR" >&2
    exit 1
}

SNAP_COUNT=$(find "$SNAPDIR" -maxdepth 1 -type d | wc -l)
(( SNAP_COUNT > 2 )) || {
    echo "ERROR: need at least 2 snapshots in $SNAPDIR (found $((SNAP_COUNT - 1)))" >&2
    exit 1
}

echo "SNAPDIR=$SNAPDIR ($(( SNAP_COUNT - 1 )) snapshots found)"
echo "PREFIX=$PREFIX (test isolation)"
echo

FAILS=0

run_test() {

    local T="$1"

    echo
    echo "=================================="
    echo "$T"
    echo "=================================="

    if bash "$T"
    then
        :
    else
        echo
        echo "$(basename "$T") FAILED"
        echo

        ((FAILS++))
    fi
}

echo
echo "##################################"
echo "LOCAL (real btrfs snapshots)"
echo "##################################"

for T in test/local/*.sh
do
    run_test "$T"
done

echo
echo "##################################"
echo "ACCEPTANCE REAL (systemd, install)"
echo "##################################"

for T in test/acceptance/real/*.sh
do
    run_test "$T"
done

echo
echo "##################################"
echo "TOTAL FAILS=$FAILS"
echo "##################################"

exit "$FAILS"

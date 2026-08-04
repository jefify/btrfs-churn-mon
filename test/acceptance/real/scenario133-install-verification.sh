#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

# Test install logic WITHOUT touching real systemd.
# Uses SYSTEMD_DIR override to write to tmpdir.

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

export SYSTEMD_DIR="$TMP/systemd"
mkdir -p "$SYSTEMD_DIR"

./bin/install-systemd.sh --install

assert_file_exists "$SYSTEMD_DIR/btrfs-churn-mon.service"
assert_file_exists "$SYSTEMD_DIR/btrfs-churn-mon.timer"

assert_contains \
    "$SYSTEMD_DIR/btrfs-churn-mon.service" \
    "monitor-run.sh"

assert_contains \
    "$SYSTEMD_DIR/btrfs-churn-mon.timer" \
    "OnUnitActiveSec"

pass "install logic verified (isolated)"

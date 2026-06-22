#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=/tmp/btrfs-churn-test-01

rm -rf "$PREFIX"

mkdir -p "$PREFIX/state"

export PREFIX

OUT=$(./lib/monitor-find-pairs.sh raiz)

LINES=$(echo "$OUT" | wc -l)

[[ "$LINES" -ge 1 ]] \
    && pass "returned pair" \
    || fail "no pair returned"

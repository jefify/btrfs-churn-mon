#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=/tmp/btrfs-churn-test-03

rm -rf "$PREFIX"

mkdir -p "$PREFIX/state"

export PREFIX

echo "raiz.19000101T000000-0300" \
    > "$PREFIX/state/raiz.last"

OUT=$(
./lib/monitor-find-pairs.sh raiz \
2>&1
)

echo "$OUT" \
| grep -q "recovery" \
&& pass "recovery mode detected" \
|| fail "recovery mode missing"

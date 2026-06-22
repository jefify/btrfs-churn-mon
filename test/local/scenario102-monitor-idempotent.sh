#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/state" \
    "$PREFIX/reports"

./bin/monitor-run.sh raiz >/dev/null

OUT=$(
./lib/monitor-find-pairs.sh raiz \
2>&1
)

echo "$OUT"

echo "$OUT" \
| grep -q "PAIRS: 0" \
&& pass "already up to date" \
|| fail "expected PAIRS: 0"

REPORTS1=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

./bin/monitor-run.sh raiz >/dev/null

REPORTS2=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

assert_equals \
    "$REPORTS1" \
    "$REPORTS2"

rm -rf "$PREFIX"

#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/reports" \
    "$PREFIX/state"

./bin/bootstrap.sh

STATE_COUNT=$(
find "$PREFIX/state" \
    -name '*.last' \
| wc -l
)

[[ "$STATE_COUNT" -gt 0 ]] \
&& pass "state files=$STATE_COUNT" \
|| fail "no state files"

REPORT_COUNT=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

[[ "$REPORT_COUNT" -gt 0 ]] \
&& pass "reports=$REPORT_COUNT" \
|| fail "no reports"

LATEST_STATE=$(
find "$PREFIX/state" \
    -name '*.last' \
| head -1
)

assert_file_exists \
    "$LATEST_STATE"

assert_not_empty \
    "$LATEST_STATE"

LATEST_REPORT=$(
find "$PREFIX/reports" \
    -name report.md \
| sort \
| tail -1
)

assert_file_exists \
    "$LATEST_REPORT"

assert_contains \
    "$LATEST_REPORT" \
    "Btrfs Churn Report"

rm -rf "$PREFIX"


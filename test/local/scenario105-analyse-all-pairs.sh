#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/reports"

OUT=$(
    ./bin/analyse-all-pairs.sh raiz
)

echo "$OUT"

COUNT=$(
    find "$PREFIX/reports" \
        -name report.md \
    | wc -l
)

[[ "$COUNT" -gt 0 ]] \
    && pass "generated reports=$COUNT" \
    || fail "no reports generated"

LATEST=$(
    find "$PREFIX/reports" \
        -name report.md \
    | sort \
    | tail -1
)

assert_file_exists "$LATEST"

assert_contains \
    "$LATEST" \
    "Btrfs Churn Report"

rm -rf "$PREFIX"


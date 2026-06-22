#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/state" \
    "$PREFIX/reports"

SNAPNAME=raiz

echo
echo "=== monitor-run ==="
echo

./bin/monitor-run.sh \
    "$SNAPNAME"

STATEFILE="$PREFIX/state/${SNAPNAME}.last"

assert_file_exists \
    "$STATEFILE"

STATE_VALUE=$(
cat "$STATEFILE"
)

[[ -n "$STATE_VALUE" ]] \
    && pass "state updated" \
    || fail "empty state"

REPORTROOT="$PREFIX/reports/${SNAPNAME}"

assert_dir_exists \
    "$REPORTROOT"

LATEST_REPORT=$(
find "$REPORTROOT" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
| sort \
| tail -1
)

assert_dir_exists \
    "$LATEST_REPORT"

assert_file_exists \
    "$LATEST_REPORT/detail.tsv"

assert_file_exists \
    "$LATEST_REPORT/report.md"

assert_file_exists \
    "$LATEST_REPORT/report.json"

assert_file_exists \
    "$LATEST_REPORT/metadata.json"

assert_not_empty \
    "$LATEST_REPORT/detail.tsv"

assert_json_key \
    "$LATEST_REPORT/report.json" \
    total_bytes

assert_json_key \
    "$LATEST_REPORT/report.json" \
    top_files

assert_json_value \
    "$LATEST_REPORT/metadata.json" \
    schema_version \
    1

assert_grep_count \
    "$LATEST_REPORT/report.md" \
    "Total Churn" \
    1

pass "monitor pipeline"

rm -rf "$PREFIX"


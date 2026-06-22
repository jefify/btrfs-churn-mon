#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PAIR=$(
./lib/collect-snapshot-pair.sh \
    raiz \
    24h
)

OLD=$(
echo "$PAIR" \
| awk -F'\t' '
$1=="OLD"{
    print $2
}'
)

NEW=$(
echo "$PAIR" \
| awk -F'\t' '
$1=="NEW"{
    print $2
}'
)

DST=$(mktemp -d)

echo
echo "OLD=$OLD"
echo "NEW=$NEW"
echo

./bin/analyse-churn.sh \
    "$OLD" \
    "$NEW" \
    --dst "$DST"

assert_file_exists \
    "$DST/detail.tsv"

assert_file_exists \
    "$DST/report.md"

assert_file_exists \
    "$DST/report.json"

assert_file_exists \
    "$DST/metadata.json"

assert_not_empty \
    "$DST/detail.tsv"

assert_not_empty \
    "$DST/report.md"

assert_json_key \
    "$DST/report.json" \
    total_bytes

assert_json_key \
    "$DST/report.json" \
    top_files

assert_json_value \
    "$DST/metadata.json" \
    schema_version \
    1

assert_grep_count \
    "$DST/report.md" \
    "Total Churn" \
    1

assert_grep_count \
    "$DST/report.md" \
    "Top Files" \
    1

LINES=$(
tail -n +2 \
"$DST/detail.tsv" \
| wc -l
)

[[ "$LINES" -gt 0 ]] \
    && pass "detail rows=$LINES" \
    || fail "detail.tsv empty"

rm -rf "$DST"

pass "end-to-end pipeline"

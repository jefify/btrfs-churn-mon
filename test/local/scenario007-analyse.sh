#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PAIR=$(
./lib/collect-snapshot-pair.sh \
    raiz \
    24h
)

OLD=$(echo "$PAIR" | awk -F'\t' '$1=="OLD"{print $2}')
NEW=$(echo "$PAIR" | awk -F'\t' '$1=="NEW"{print $2}')

DST=/tmp/churn-analysis-test

rm -rf "$DST"

./bin/analyse-churn.sh \
    "$OLD" \
    "$NEW" \
    --dst "$DST"

assert_file_exists "$DST/detail.tsv"

assert_file_exists "$DST/report.md"

assert_file_exists "$DST/report.json"

assert_file_exists "$DST/metadata.json"

assert_not_empty "$DST/detail.tsv"

assert_contains \
    "$DST/report.md" \
    "Btrfs Churn Report"

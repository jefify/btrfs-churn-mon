#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/detail.tsv" <<DATA
100	user/file1
200	user/file2
300	user/file3
DATA

./lib/build-report.py \
    "$TMP/detail.tsv" \
    >/dev/null

assert_file_exists \
    "$TMP/report.json"

assert_json_key \
    "$TMP/report.json" \
    total_bytes

assert_json_value \
    "$TMP/report.json" \
    total_bytes \
    600

pass "report json"

rm -rf "$TMP"


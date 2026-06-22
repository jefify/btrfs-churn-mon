#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/detail.tsv" << TSV
BYTES	PATH
1000	user/file1
2000	user/file2
3000	user/file3
TSV

python3 \
    lib/build-report.py \
    "$TMP/detail.tsv" \
    >/dev/null

assert_file_exists \
    "$TMP/report.md"

assert_contains \
    "$TMP/report.md" \
    "Total Churn"

assert_contains \
    "$TMP/report.md" \
    "Top Files"

assert_contains \
    "$TMP/report.md" \
    "user/file3"

rm -rf "$TMP"

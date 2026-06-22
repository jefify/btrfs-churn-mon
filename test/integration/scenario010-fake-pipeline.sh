#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/send.dump" << DUMP
write ./lin/file1 len=1000
write ./lin/file2 len=2000
clone ./lin/file3 len=3000
DUMP

{
    echo -e "BYTES\tPATH"

    awk \
        -f lib/parse-churn.awk \
        "$TMP/send.dump" \
        | sort -nr

} > "$TMP/detail.tsv"

python3 \
    lib/build-report.py \
    "$TMP/detail.tsv"

assert_file_exists "$TMP/report.md"

assert_file_exists "$TMP/report.json"

assert_contains \
    "$TMP/report.md" \
    "Total Churn"

rm -rf "$TMP"

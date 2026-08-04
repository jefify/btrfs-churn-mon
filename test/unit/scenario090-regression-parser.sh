#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/send.dump" << DUMP
write ./user/file1 len=100
write ./user/file2 len=200
clone ./user/file3 len=300
DUMP

cat > "$TMP/expected.tsv" << TSV
100	user/file1
200	user/file2
300	user/file3
TSV

python3 \
    lib/parse_churn.py \
    "$TMP/send.dump" \
| sort > "$TMP/actual.tsv"

diff -u \
    "$TMP/expected.tsv" \
    "$TMP/actual.tsv" \
>/dev/null \
&& pass "parser regression" \
|| fail "parser output changed"

rm -rf "$TMP"

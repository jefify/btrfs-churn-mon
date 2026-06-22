#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/detail.tsv" << TSV
BYTES	PATH
100	a
200	b
TSV

python3 lib/build-report.py \
    "$TMP/detail.tsv" \
    >/dev/null

jq . \
    "$TMP/report.json" \
    >/dev/null \
&& pass "json valid" \
|| fail "json invalid"

rm -rf "$TMP"

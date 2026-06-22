#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/detail.tsv" << TSV
BYTES	PATH
100	a
TSV

python3 \
    lib/build-report.py \
    "$TMP/detail.tsv" \
    >/dev/null

jq -e '
    has("total_bytes")
    and
    has("top_files")
' \
    "$TMP/report.json" \
    >/dev/null \
&& pass "json schema" \
|| fail "json schema changed"

rm -rf "$TMP"

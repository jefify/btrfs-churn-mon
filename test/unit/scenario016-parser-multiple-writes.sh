#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/send.dump" << DUMP
write ./foo/bar len=100
write ./foo/bar len=200
clone ./foo/bar len=300
DUMP

OUT=$(
python3 \
    lib/parse_churn.py \
    "$TMP/send.dump"
)

echo "$OUT" \
| grep -q '^600[[:space:]]' \
&& pass "aggregated bytes" \
|| fail "aggregation failed"

rm -rf "$TMP"

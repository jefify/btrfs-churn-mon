#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

echo -e "BYTES\tPATH" \
    > "$TMP/detail.tsv"

python3 lib/build-report.py \
    "$TMP/detail.tsv" \
    >/dev/null 2>&1 \
&& fail "should fail" \
|| pass "header only rejected"

rm -rf "$TMP"

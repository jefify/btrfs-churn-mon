#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/detail.tsv" << TSV
BYTES	PATH
TSV

if python3 lib/build-report.py \
    "$TMP/detail.tsv"
then
    fail "expected failure"
else
    pass "empty detail rejected"
fi

rm -rf "$TMP"

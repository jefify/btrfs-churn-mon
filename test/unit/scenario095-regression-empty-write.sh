#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

: > "$TMP/send.dump"

OUT=$(
python3 \
    lib/parse_churn.py \
    "$TMP/send.dump"
)

[[ -z "$OUT" ]] \
&& pass "empty dump handled" \
|| fail "unexpected output"

rm -rf "$TMP"

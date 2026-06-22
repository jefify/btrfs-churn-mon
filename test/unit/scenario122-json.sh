#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/generate-mon-report.sh \
        --json
)

TMP=$(mktemp)

printf '%s\n' "$OUT" > "$TMP"

assert_json_key \
    "$TMP" \
    '.reports'

assert_json_key \
    "$TMP" \
    '.top_by_bytes'

assert_json_key \
    "$TMP" \
    '.top_by_frequency'

rm -f "$TMP"


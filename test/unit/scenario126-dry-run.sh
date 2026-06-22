#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

./bin/generate-mon-report.sh \
    --dry-run \
    --out-dir "$TMP"

assert_not_exists \
    "$TMP/aggregate.md"

assert_not_exists \
    "$TMP/aggregate.json"

rm -rf "$TMP"


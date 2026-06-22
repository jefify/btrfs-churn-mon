#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUTDIR=$(mktemp -d)

./bin/generate-mon-report.sh \
    --out-dir "$OUTDIR"

assert_file_exists \
    "$OUTDIR/aggregate.md"

assert_file_exists \
    "$OUTDIR/aggregate.json"

rm -rf "$OUTDIR"


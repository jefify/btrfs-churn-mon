#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/generate-mon-report.sh \
        --stdout
)

assert_stdout_contains \
    "$OUT" \
    "Aggregate Churn Report"


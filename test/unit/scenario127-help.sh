#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/generate-mon-report.sh \
        --help
)

assert_stdout_contains \
    "$OUT" \
    "--exclude"

assert_stdout_contains \
    "$OUT" \
    "--limit"

assert_stdout_contains \
    "$OUT" \
    "--stdout"

assert_stdout_contains \
    "$OUT" \
    "--json"


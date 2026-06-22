#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/install-systemd.sh \
        --help
)

assert_stdout_contains \
    "$OUT" \
    "Usage"

assert_stdout_contains \
    "$OUT" \
    "--install"

assert_stdout_contains \
    "$OUT" \
    "--dry-run"

assert_stdout_contains \
    "$OUT" \
    "--stdout"

pass "help ok"


#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/install-systemd.sh \
        --stdout
)

assert_stdout_contains \
    "$OUT" \
    ".service"

assert_stdout_contains \
    "$OUT" \
    ".timer"

assert_stdout_contains \
    "$OUT" \
    "daemon-reload"

assert_stdout_contains \
    "$OUT" \
    "enable"

assert_stdout_contains \
    "$OUT" \
    "start"

pass "stdout plan ok"


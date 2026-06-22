#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

OUT=$(
    ./bin/install-systemd.sh \
        --dry-run
)

assert_stdout_contains \
    "$OUT" \
    "DRY RUN"

assert_stdout_contains \
    "$OUT" \
    "daemon-reload"

assert_stdout_contains \
    "$OUT" \
    "enable"

assert_stdout_contains \
    "$OUT" \
    "start"

pass "dry-run ok"


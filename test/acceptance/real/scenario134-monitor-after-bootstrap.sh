#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/reports" \
    "$PREFIX/state"

./bin/bootstrap.sh \
    >/dev/null

REPORTS1=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

./bin/monitor-run.sh \
    >/dev/null

REPORTS2=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

assert_equals \
    "$REPORTS1" \
    "$REPORTS2"

rm -rf "$PREFIX"


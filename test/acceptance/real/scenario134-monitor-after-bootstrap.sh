#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "${ROOT}/lib/load-config.rc"

PREFIX=$(mktemp -d)
export PREFIX

mkdir -p \
    "$PREFIX/reports" \
    "$PREFIX/state"

# Discover first snapshot family
FAMILY=$(
    find "$SNAPDIR" \
        -maxdepth 1 \
        -type d \
    | sed 's#.*/##' \
    | awk -F. 'NF>1 {print $1}' \
    | sort -u \
    | head -1
)

[[ -n "$FAMILY" ]] || {
    echo "SKIP: no snapshot families found"
    rm -rf "$PREFIX"
    exit 0
}

./bin/bootstrap.sh \
    >/dev/null 2>&1

REPORTS1=$(
    find "$PREFIX/reports" \
        -name report.md \
    | wc -l
)

# Run monitor again — should be idempotent (no new reports)
./bin/monitor-run.sh \
    "$FAMILY" \
    >/dev/null 2>&1

REPORTS2=$(
    find "$PREFIX/reports" \
        -name report.md \
    | wc -l
)

assert_equals \
    "$REPORTS1" \
    "$REPORTS2"

rm -rf "$PREFIX"

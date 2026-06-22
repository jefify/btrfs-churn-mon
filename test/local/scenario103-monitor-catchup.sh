#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/state" \
    "$PREFIX/reports"

FIRST=$(
find /mnt/btrfs_pool/btrbk_snapshots \
    -maxdepth 1 \
    -type d \
    -name 'raiz.*' \
| sort \
| head -1 \
| xargs basename
)

echo "$FIRST" \
    > "$PREFIX/state/raiz.last"

./bin/monitor-run.sh \
    raiz \
    --catchup-limit 3

REPORTS=$(
find "$PREFIX/reports" \
    -name report.md \
| wc -l
)

assert_equals \
    "3" \
    "$REPORTS"

rm -rf "$PREFIX"


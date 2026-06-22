#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

export SNAPDIR="$TMP"

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$SNAPDIR" \
    "$PREFIX/state"

mkdir -p \
    "$SNAPDIR/raiz.20260101T010000-0300"

mkdir -p \
    "$SNAPDIR/raiz.20260101T020000-0300"

echo "raiz.20260101T010000-0300" \
    > "$PREFIX/state/raiz.last"

LINES=$(
./lib/monitor-find-pairs.sh raiz \
| wc -l
)

assert_equals \
    "1" \
    "$LINES"

rm -rf "$TMP" "$PREFIX"


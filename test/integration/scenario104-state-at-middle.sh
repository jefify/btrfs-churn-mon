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

for i in {1..5}
do
    mkdir -p \
        "$SNAPDIR/raiz.20260101T0${i}0000-0300"
done

STATE_SNAP="raiz.20260101T030000-0300"

echo "$STATE_SNAP" \
    > "$PREFIX/state/raiz.last"

OUT=$(
    ./lib/monitor-find-pairs.sh raiz
)

LINES=$(
    echo "$OUT" \
    | wc -l
)

assert_equals \
    "2" \
    "$LINES"

FIRST_OLD=$(
    echo "$OUT" \
    | head -1 \
    | cut -f1
)

FIRST_OLD_BASE=$(
    basename "$FIRST_OLD"
)

assert_equals \
    "$STATE_SNAP" \
    "$FIRST_OLD_BASE"

rm -rf "$TMP" "$PREFIX"


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

for i in {1..10}
do
    mkdir -p \
        "$SNAPDIR/raiz.20260101T0${i}0000-0300"
done

echo "raiz.20260101T010000-0300" \
    > "$PREFIX/state/raiz.last"

LINES=$(
./lib/monitor-find-pairs.sh \
    raiz \
    --catchup-limit 3 \
| wc -l
)

assert_equals \
    "3" \
    "$LINES"

rm -rf "$TMP" "$PREFIX"


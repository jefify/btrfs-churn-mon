#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

mkdir -p "$TMP/snaps"

mkdir "$TMP/snaps/raiz.001"
mkdir "$TMP/snaps/raiz.002"
mkdir "$TMP/snaps/raiz.003"
mkdir "$TMP/snaps/raiz.004"

COUNT=$(
find "$TMP/snaps" \
    -maxdepth 1 \
    -type d \
    -name 'raiz.*' \
| wc -l
)

assert_equals \
    "4" \
    "$COUNT"

PAIRS=$((COUNT-1))

assert_equals \
    "3" \
    "$PAIRS"

rm -rf "$TMP"


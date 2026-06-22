#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

./lib/monitor-update-state.sh \
    raiz \
    raiz.TEST

assert_file_exists \
    "$PREFIX/state/raiz.last"

VALUE=$(cat "$PREFIX/state/raiz.last")

assert_equals \
    "raiz.TEST" \
    "$VALUE"

rm -rf "$PREFIX"

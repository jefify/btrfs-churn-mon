#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

./lib/monitor-update-state.sh \
    raiz \
    raiz.TEST123

VALUE=$(
cat "$PREFIX/state/raiz.last"
)

assert_equals \
    "raiz.TEST123" \
    "$VALUE"

rm -rf "$PREFIX"

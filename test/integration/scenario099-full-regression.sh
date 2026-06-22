#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

COUNT=$(
find test \
    -regex '.*/scenario09[0-9].*\.sh' \
| wc -l
)

[[ "$COUNT" -ge 5 ]] \
&& pass "regression suite present" \
|| fail "missing regression tests"

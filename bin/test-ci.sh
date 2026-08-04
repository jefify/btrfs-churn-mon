#!/usr/bin/env bash

set -euo pipefail

# ============================================
# test-ci.sh — All CI-safe tests
# No root, no btrfs, no network required.
# Uses fixtures only.
# ============================================

FAILS=0

run_suite() {

    local NAME="$1"
    local DIR="$2"

    echo
    echo "##################################"
    echo "$NAME"
    echo "##################################"

    local SUITE_FAILS=0

    for T in $DIR
    do
        echo
        echo "=================================="
        echo "$T"
        echo "=================================="

        if bash "$T"
        then
            :
        else
            echo
            echo "$(basename "$T") FAILED"
            echo
            ((SUITE_FAILS++))
        fi
    done

    echo
    echo "=================================="
    echo "$NAME FAILS=$SUITE_FAILS"
    echo "=================================="

    (( SUITE_FAILS > 0 )) && ((FAILS++))

    return 0
}

run_suite UNIT "test/unit/*.sh"
run_suite INTEGRATION "test/integration/*.sh"
run_suite ACCEPTANCE_SAFE "test/acceptance/safe/*.sh"

echo
echo "##################################"
echo "TOTAL FAILS=$FAILS"
echo "##################################"

exit "$FAILS"

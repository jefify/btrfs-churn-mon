#!/usr/bin/env bash

set -euo pipefail

FAILS=0

run_suite() {

    local NAME="$1"
    local CMD="$2"

    echo
    echo
    echo "##################################"
    echo "$NAME"
    echo "##################################"

    if bash "$CMD"
    then
        :
    else
        ((FAILS++))
    fi
}

run_suite \
    UNIT \
    bin/test-unit.sh

run_suite \
    INTEGRATION \
    bin/test-integration.sh

echo
echo "##################################"
echo "TOTAL FAILS=$FAILS"
echo "##################################"

exit "$FAILS"


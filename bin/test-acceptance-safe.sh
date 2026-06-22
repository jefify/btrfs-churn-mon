#!/usr/bin/env bash

set -euo pipefail

FAILS=0

for T in test/acceptance/safe/*.sh
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

        ((FAILS++))
    fi

done

echo
echo "=================================="
echo "ACCEPTANCE SAFE FAILS=$FAILS"
echo "=================================="

exit "$FAILS"


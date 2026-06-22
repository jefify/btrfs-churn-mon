#!/usr/bin/env bash

set -euo pipefail

FAILS=0

for T in test/unit/*.sh
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
echo "UNIT FAILS=$FAILS"
echo "=================================="

exit "$FAILS"


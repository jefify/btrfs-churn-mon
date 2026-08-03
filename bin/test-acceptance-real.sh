#!/usr/bin/env bash

set -euo pipefail

# These tests may modify the system (systemd, real btrfs).
# Requires: root privileges + real btrfs snapshots.
if [[ $EUID -ne 0 ]]
then
    echo "WARNING: running as non-root — tests requiring root will SKIP" >&2
fi

FAILS=0

for T in test/acceptance/real/*.sh
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
echo "ACCEPTANCE REAL FAILS=$FAILS"
echo "=================================="

exit "$FAILS"


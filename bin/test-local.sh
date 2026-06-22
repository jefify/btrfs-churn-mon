#!/usr/bin/env bash

set -euo pipefail

if [[ -f test/settings.conf ]]
then
    source test/settings.conf
else
    echo "Missing test/settings.conf"
    echo "Copy test/settings.conf.example"
    exit 1
fi

for T in test/local/*.sh
do
    echo
    echo "=================================="
    echo "$T"
    echo "=================================="

    bash "$T"
done
#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

if [[ $EUID -ne 0 ]]
then
    echo "SKIP: root required"
    exit 0
fi

./bin/install-systemd.sh \
    --install

assert_rc 0 true

systemctl cat \
    btrfs-churn-mon.service \
    >/dev/null

pass "service installed"

systemctl cat \
    btrfs-churn-mon.timer \
    >/dev/null

pass "timer installed"


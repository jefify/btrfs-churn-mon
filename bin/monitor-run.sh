#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

SNAPNAME="${1:?snapshot name required}"

shift || true



REPORTROOT="${PREFIX}/reports/${SNAPNAME}"
source "${ROOT}/lib/load-config.rc"
mkdir -p "$REPORTROOT"

"${ROOT}/lib/monitor-find-pairs.sh" \
    "$SNAPNAME" \
    "$@" \
|
while IFS=$'\t' read -r OLD NEW
do

    NEWID="$(basename "$NEW")"

    DST="${REPORTROOT}/${NEWID}"

    echo
    echo "======================================"
    echo "OLD: $OLD"
    echo "NEW: $NEW"
    echo "======================================"
    echo

    "${ROOT}/bin/analyse-churn.sh" \
        "$OLD" \
        "$NEW" \
        --dst "$DST"

    "${ROOT}/lib/monitor-update-state.sh" \
        "$SNAPNAME" \
        "$NEWID"

done

#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source "${ROOT}/lib/load-config.rc"

REPORTROOT="${REPORTROOT:-${PREFIX}/reports}"

STATEDIR="${PREFIX}/state"

mkdir -p \
    "$REPORTROOT" \
    "$STATEDIR"

echo
echo "======================================"
echo "SCAN FAMILIES"
echo "======================================"

mapfile -t FAMILIES < <(
    find "$SNAPDIR" \
        -maxdepth 1 \
        -type d \
    | sed 's#.*/##' \
    | awk -F. 'NF>1 {print $1}' \
    | sort -u
)

(( ${#FAMILIES[@]} > 0 )) || {
    echo "ERROR: no snapshot families found" >&2
    exit 1
}

TOTAL_FAMILIES=0

for FAMILY in "${FAMILIES[@]}"
do

    echo
    echo "======================================"
    echo "FAMILY: $FAMILY"
    echo "======================================"

    "${ROOT}/bin/analyse-all-pairs.sh" \
        "$FAMILY"

    LATEST=$(
        find "$SNAPDIR" \
            -maxdepth 1 \
            -type d \
            -name "${FAMILY}.*" \
        | sort \
        | tail -1 \
        | xargs basename
    )

    "${ROOT}/lib/monitor-update-state.sh" \
        "$FAMILY" \
        "$LATEST"

    echo "STATE UPDATED: ${FAMILY} -> ${LATEST}"

    ((TOTAL_FAMILIES++)) || true

done

echo
echo "======================================"
echo "BOOTSTRAP COMPLETE"
echo "======================================"

echo "FAMILIES=${TOTAL_FAMILIES}"
echo "STATEDIR=${STATEDIR}"
echo "REPORTROOT=${REPORTROOT}"


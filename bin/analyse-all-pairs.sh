#!/usr/bin/env bash

set -euo pipefail

SNAPNAME="${1:?snapshot name required}"



REPORTROOT="${REPORTROOT:-${PREFIX}/reports}"


ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"
mapfile -t SNAPS < <(
    find "$SNAPDIR" \
        -maxdepth 1 \
        -type d \
        -name "${SNAPNAME}.*" \
    | sort
)

(( ${#SNAPS[@]} >= 2 )) || {
    echo "ERROR: need at least 2 snapshots" >&2
    exit 1
}

TOTAL=0

for ((i=1; i<${#SNAPS[@]}; i++))
do

    OLD="${SNAPS[$((i-1))]}"
    NEW="${SNAPS[$i]}"

    SNAPID="$(basename "$NEW")"

    DSTDIR="${REPORTROOT}/${SNAPNAME}/${SNAPID}"

    echo
    echo "======================================"
    echo "OLD: $OLD"
    echo "NEW: $NEW"
    echo "======================================"

    "${ROOT}/bin/analyse-churn.sh" \
        "$OLD" \
        "$NEW" \
        --dst "$DSTDIR"

    ((TOTAL++)) || true

done

echo
echo "TOTAL_PAIRS=${TOTAL}"


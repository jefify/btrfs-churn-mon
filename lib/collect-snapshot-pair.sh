#!/usr/bin/env bash

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"

SNAPNAME="${1:?snapshot name required}"
MODE="${2:-24h}"


mapfile -t SNAPS < <(
    find "$SNAPDIR" -maxdepth 1 -type d \
        -name "${SNAPNAME}.*" \
        | sort
)

(( ${#SNAPS[@]} >= 2 )) || {
    echo "ERROR: not enough snapshots" >&2
    exit 1
}

NEW="${SNAPS[-1]}"

case "$MODE" in
    daily) TARGET_HOURS=24 ;;
    weekly) TARGET_HOURS=168 ;;
    *h)
        TARGET_HOURS="${MODE%h}"
        ;;
    *d)
        TARGET_HOURS=$(( ${MODE%d} * 24 ))
        ;;
    *)
        echo "ERROR: invalid mode" >&2
        exit 1
        ;;
esac

new_ts="$(basename "$NEW")"
new_ts="${new_ts#"${SNAPNAME}".}"

new_epoch="$(date -d "${new_ts:0:8} ${new_ts:9:2}:${new_ts:11:2}:${new_ts:13:2}" +%s)"

BEST=""
BEST_DIFF=""

for SNAP in "${SNAPS[@]}"
do
    [[ "$SNAP" == "$NEW" ]] && continue

    ts="$(basename "$SNAP")"
    ts="${ts#"${SNAPNAME}".}"

    epoch="$(date -d "${ts:0:8} ${ts:9:2}:${ts:11:2}:${ts:13:2}" +%s)"

    diff_hours=$(( (new_epoch - epoch) / 3600 ))

    (( diff_hours >= TARGET_HOURS )) || continue

    if [[ -z "$BEST_DIFF" || "$diff_hours" -lt "$BEST_DIFF" ]]
    then
        BEST="$SNAP"
        BEST_DIFF="$diff_hours"
    fi
done

[[ -n "$BEST" ]] || {
    echo "ERROR: no snapshot old enough for $MODE" >&2
    exit 1
}

printf 'MODE\t%s\n' "$MODE"
printf 'TARGET_HOURS\t%s\n' "$TARGET_HOURS"
printf 'ACTUAL_HOURS\t%s\n' "$BEST_DIFF"
printf 'OLD\t%s\n' "$BEST"
printf 'NEW\t%s\n' "$NEW"

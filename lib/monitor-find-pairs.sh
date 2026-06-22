#!/usr/bin/env bash

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"

SNAPNAME="${1:?snapshot name required}"

shift || true

CATCHUP_LIMIT=100

while [[ $# -gt 0 ]]
do
    case "$1" in
        --catchup-limit)
            CATCHUP_LIMIT="${2:?}"
            shift 2
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            exit 1
            ;;
    esac
done


STATEDIR="${PREFIX}/state"


mkdir -p "$STATEDIR"

STATEFILE="${STATEDIR}/${SNAPNAME}.last"

mapfile -t SNAPS < <(
    find "$SNAPDIR" -maxdepth 1 -type d \
        -name "${SNAPNAME}.*" \
        | sort
)

(( ${#SNAPS[@]} >= 2 )) || exit 0

if [[ ! -f "$STATEFILE" ]]
then

    echo "# MODE: first-run" >&2
    echo "# PAIRS: 1" >&2

    OLD="${SNAPS[-2]}"
    NEW="${SNAPS[-1]}"

    printf '%s\t%s\n' "$OLD" "$NEW"

    exit 0
fi

LAST="$(cat "$STATEFILE")"

FOUND=0
RETURNED=0

for ((i=0; i<${#SNAPS[@]}; i++))
do

    CUR="$(basename "${SNAPS[$i]}")"

    echo "CHECK CUR=<$CUR> LAST=<$LAST>" >&2
    if [[ "$CUR" == "$LAST" ]]
    then
        FOUND=1

        for ((j=i+1; j<${#SNAPS[@]}; j++))
        do

            OLD="${SNAPS[$((j-1))]}"
            NEW="${SNAPS[$j]}"

            printf '%s\t%s\n' "$OLD" "$NEW"

            ((RETURNED++)) || true

            if (( RETURNED >= CATCHUP_LIMIT ))
            then
                break
            fi
        done

        break
    fi
done

if (( FOUND == 1 && RETURNED == 0 ))
then
    echo "# MODE: up-to-date" >&2
    echo "# PAIRS: 0" >&2
fi

if (( FOUND == 0 ))
then

    echo "# WARNING: state snapshot not found" >&2
    echo "# STATE: $LAST" >&2
    echo "# MODE: recovery" >&2

    OLD="${SNAPS[-2]}"
    NEW="${SNAPS[-1]}"

    printf '%s\t%s\n' "$OLD" "$NEW"
fi

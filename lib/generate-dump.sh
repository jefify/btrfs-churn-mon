#!/usr/bin/env bash

set -euo pipefail

OLD="${1:?old snapshot required}"
NEW="${2:?new snapshot required}"
DUMPFILE="${3:?dump file required}"

# btrfs send can fail partially but still produce usable output.
# We capture the exit code and warn, but only fail if dump is empty.
if ! btrfs send -p "$OLD" "$NEW" \
    | btrfs receive --dump > "$DUMPFILE" 2>/dev/null
then
    echo "WARNING: btrfs send/receive exited non-zero" >&2
fi

if [[ ! -s "$DUMPFILE" ]]
then
    echo "ERROR: dump file is empty — btrfs send failed completely" >&2
    exit 1
fi

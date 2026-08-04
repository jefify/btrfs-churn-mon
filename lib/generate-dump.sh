#!/usr/bin/env bash

set -euo pipefail

OLD="${1:?old snapshot required}"
NEW="${2:?new snapshot required}"
DUMPFILE="${3:?dump file required}"

# btrfs send | btrfs receive --dump can exit non-zero even when
# producing valid output (e.g. partial streams, pipe signals).
# We disable pipefail temporarily and check the result manually.
set +o pipefail
btrfs send -p "$OLD" "$NEW" 2>/dev/null \
    | btrfs receive --dump > "$DUMPFILE" 2>/dev/null
PIPE_RC=$?
set -o pipefail

if [[ ! -s "$DUMPFILE" ]]
then
    echo "ERROR: dump file is empty — btrfs send failed (rc=$PIPE_RC)" >&2
    exit 1
fi

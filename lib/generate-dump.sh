#!/usr/bin/env bash

set -euo pipefail

OLD="${1:?old snapshot required}"
NEW="${2:?new snapshot required}"
DUMPFILE="${3:?dump file required}"

btrfs send -p "$OLD" "$NEW" \
    | btrfs receive --dump > "$DUMPFILE" \
    || true

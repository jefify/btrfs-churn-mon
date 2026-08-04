#!/usr/bin/env bash

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${ROOT}/lib/load-config.rc"


STATEDIR="${PREFIX}/state"

SNAPNAME="${1:?snapshot name required}"
SNAPID="${2:?snapshot id required}"

mkdir -p "$STATEDIR"

STATEFILE="${STATEDIR}/${SNAPNAME}.last"

TMP="$(mktemp "${STATEFILE}.XXXX")"

printf '%s\n' "$SNAPID" > "$TMP"

chmod 644 "$TMP"

mv "$TMP" "$STATEFILE"

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

OLD="${1:?old snapshot required}"
NEW="${2:?new snapshot required}"

shift 2

DST=""

while [[ $# -gt 0 ]]
do
    case "$1" in

        --dst)
            DST="${2:?}"
            shift 2
            ;;

        *)
            echo "ERROR: unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

NEWNAME="$(basename "$NEW")"

if [[ -z "$DST" ]]
then
    DST="/tmp/btrfs-churn-analysis/${NEWNAME}"
fi

mkdir -p "$DST"

TMPDIR="$(mktemp -d)"

cleanup() {
    rm -rf "$TMPDIR"
}

trap cleanup EXIT

DUMPFILE="${TMPDIR}/send.dump"

echo "[1/4] dump"

"${ROOT}/lib/generate-dump.sh" \
    "$OLD" \
    "$NEW" \
    "$DUMPFILE"

echo "[2/4] parse"

{
    echo -e "BYTES\tPATH"

    python3 \
        "${ROOT}/lib/parse_churn.py" \
        "$DUMPFILE" \
        | sort -nr

} > "${DST}/detail.tsv"

echo "[3/4] metadata"

cat > "${DST}/metadata.json" << JSON
{
  "schema_version": 1,
  "old_snapshot": "$(basename "$OLD")",
  "new_snapshot": "$(basename "$NEW")"
}
JSON

echo "[4/4] report"

python3 \
    "${ROOT}/lib/build-report.py" \
    "${DST}/detail.tsv"

echo
echo "REPORT_DIR=${DST}"

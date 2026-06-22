#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

PREFIX=$(mktemp -d)

export PREFIX

mkdir -p \
    "$PREFIX/reports/raiz/snap1"

cat > \
    "$PREFIX/reports/raiz/snap1/report.json" \
<<JSON
{
  "total_bytes": 1000,
  "total_files": 10,
  "top_by_bytes": [
    {
      "path": "user/file1",
      "bytes": 1000
    }
  ]
}
JSON

./bin/generate-mon-report.sh

assert_file_exists \
    "$PREFIX/reports/aggregate.md"

assert_file_exists \
    "$PREFIX/reports/aggregate.json"

assert_contains \
    "$PREFIX/reports/aggregate.md" \
    "Aggregate"

rm -rf "$PREFIX"


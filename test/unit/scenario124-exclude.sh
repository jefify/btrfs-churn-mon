#!/usr/bin/env bash

set -euo pipefail

source test/lib/assert.sh

TMP=$(mktemp -d)

cat > "$TMP/excludes.txt" <<'EOT'
.bash_history
EOT

./bin/generate-mon-report.sh \
    --out-dir "$TMP" \
    --exclude "$TMP/excludes.txt"

if grep -q '\.bash_history' \
    "$TMP/aggregate.md"
then
    fail ".bash_history found"
fi

pass ".bash_history excluded"

rm -rf "$TMP"


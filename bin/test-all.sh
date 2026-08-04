#!/usr/bin/env bash

set -euo pipefail

# ============================================
# test-all.sh — Run everything (CI + real)
# Requires: root + test/settings.conf + btrfs
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== CI tests (safe) ==="
bash "${SCRIPT_DIR}/test-ci.sh"

echo
echo "=== Real tests (privileged) ==="
bash "${SCRIPT_DIR}/test-real.sh"

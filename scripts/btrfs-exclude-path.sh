#!/usr/bin/env bash
# btrfs-exclude-path.sh — Exclude a directory from btrfs snapshots
#
# Creates a nested subvolume and a systemd .mount unit so the path
# is excluded from parent subvolume snapshots.
#
# Usage:
#   btrfs-exclude-path.sh /var/lib/apt/lists
#   btrfs-exclude-path.sh /var/log/journal --dry-run
#   btrfs-exclude-path.sh /var/crash --device /dev/disk/by-id/dm-uuid-LVM-xxx
#   btrfs-exclude-path.sh /var/tmp --prefix "no_snap/@"
#
# Prefix examples:
#   (empty)           → subvol: var_lib_apt_lists
#   --prefix nosnap   → subvol: nosnap/var_lib_apt_lists
#   --prefix "no_snap/@" → subvol: no_snap/@var_lib_apt_lists
#
# Safety:
#   - Runs btrbk snapshot of parent subvolume before making changes
#   - Does NOT delete original data (mount overlays it)
#   - User must manually remove old data after verifying
#
# Requirements: root, btrfs filesystem, systemd
#
# Config:
#   Reads defaults from /opt/btrfs-churn-mon/etc/btrfs-exclude-path.conf
#   (if exists). Format: KEY=VALUE. Supported: DEVICE, SUBVOL_PREFIX, BTRFS_MOUNT_OPTS.

set -euo pipefail

# --- Defaults (overridable via config or flags) ---
MOUNT_UNIT_DIR="/etc/systemd/system"
BTRFS_MOUNT_OPTS="noatime,compress=zstd"
SUBVOL_PREFIX=""  # e.g. "nosnap" or "no_snap/@"
SYSTEMD_UNIT_PREFIX=""  # e.g. "nosnap-" → unit: nosnap-var-lib-apt-lists.mount
SNAPSHOT=true  # Take btrbk safety snapshot before changes (--no-snapshot to skip)

# BTRBK_MAP: associates mount points to btrbk snapshot_name.
# Used to snapshot only the affected subvolume instead of all.
# Format: associative array. Keys = mount point, Values = btrbk snapshot_name.
# If the target path falls under a key, that snapshot_name is used.
# If empty or unset, falls back to 'btrbk snapshot' (all subvolumes).
declare -A BTRBK_MAP
# Example (set in config file):
#   BTRBK_MAP=( [/]=raiz [/home]=home )

# --- Load config (if exists) ---
CONFIG_FILE="/opt/btrfs-churn-mon/etc/btrfs-exclude-path.conf"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

# --- Args ---
DRY_RUN=false
DEVICE="${DEVICE:-}"
TARGET=""

usage() {
    cat <<EOF
Usage: $(basename "$0") PATH [OPTIONS]

Exclude a directory from btrfs snapshots by creating a nested subvolume.

Arguments:
  PATH            Directory to exclude (e.g. /var/lib/apt/lists)

Options:
  --dry-run       Show plan without modifying system
  --no-snapshot   Skip btrbk safety snapshot (useful when batch-excluding
                  multiple paths — take one snapshot before, then --no-snapshot)
  --device DEV    Btrfs device path (supports /dev/disk/by-id/... for stability)
  --prefix STR    Prefix for subvolume name. Can include '/' for subdirs
                  and '@' as name prefix. Examples:
                    --prefix nosnap        → nosnap/var_cache
                    --prefix "no_snap/@"   → no_snap/@var_cache
  --unit-prefix STR  Prefix for systemd .mount unit filename. Examples:
                    --unit-prefix "nosnap-" → nosnap-var-cache.mount
  --help          Show this help

Config file: $CONFIG_FILE
  DEVICE=              Default btrfs device (supports by-id paths)
  SUBVOL_PREFIX=       Default subvolume prefix
  SYSTEMD_UNIT_PREFIX= Default unit filename prefix (e.g. "nosnap-")
  BTRFS_MOUNT_OPTS=    Mount options (default: noatime,compress=zstd)

Examples:
  $(basename "$0") /var/lib/apt/lists
  $(basename "$0") /var/log/journal --dry-run
  $(basename "$0") /var/crash --prefix "no_snap/@" --device /dev/disk/by-id/dm-uuid-LVM-xxx
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --no-snapshot) SNAPSHOT=false; shift ;;
        --device) DEVICE="$2"; shift 2 ;;
        --prefix) SUBVOL_PREFIX="$2"; shift 2 ;;
        --unit-prefix) SYSTEMD_UNIT_PREFIX="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        -*) echo "ERROR: unknown option: $1" >&2; exit 1 ;;
        *)
            if [[ -z "$TARGET" ]]; then
                TARGET="$1"
            else
                echo "ERROR: unexpected argument: $1" >&2; exit 1
            fi
            shift ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    echo "ERROR: PATH argument required" >&2
    usage >&2
    exit 1
fi

# Normalize path (remove trailing slash)
TARGET="${TARGET%/}"

# Must run as root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: must run as root (sudo)" >&2
    exit 1
fi

# --- Functions ---

detect_device() {
    # Find the btrfs device for the given path.
    # Falls back to df if DEVICE is not set.
    local path="$1"
    local dev
    dev=$(df --output=source "$path" 2>/dev/null | tail -1)
    if [[ -z "$dev" ]] || ! btrfs filesystem show "$dev" &>/dev/null; then
        echo "ERROR: could not detect btrfs device for $path" >&2
        echo "       Specify --device explicitly" >&2
        exit 1
    fi
    echo "$dev"
}

path_to_subvol_name() {
    # Convert /var/lib/apt/lists → var_lib_apt_lists
    # With prefix "nosnap" → nosnap/var_lib_apt_lists
    # With prefix "no_snap/@" → no_snap/@var_lib_apt_lists
    #
    # The prefix is prepended as-is (last char before name can be / or @).
    # If prefix ends with '/' or is empty, name is appended directly.
    # If prefix ends with '@', name is joined without separator.
    local path="$1"
    local name
    name="$(echo "$path" | sed 's|^/||; s|/|_|g')"

    if [[ -z "$SUBVOL_PREFIX" ]]; then
        echo "$name"
    elif [[ "$SUBVOL_PREFIX" == */ ]]; then
        # Prefix ends with slash: prefix/name
        echo "${SUBVOL_PREFIX}${name}"
    else
        # Prefix does not end with slash: prefix/name (add separator)
        # But if prefix ends with @, join directly (no_snap/@name)
        if [[ "$SUBVOL_PREFIX" == *@ ]]; then
            echo "${SUBVOL_PREFIX}${name}"
        else
            echo "${SUBVOL_PREFIX}/${name}"
        fi
    fi
}

subvol_parent_dirs() {
    # Extract directory components from subvol name (everything before last /).
    # e.g. "no_snap/@var_cache" → "no_snap"
    # e.g. "nosnap/deep/name" → "nosnap/deep"
    # e.g. "var_cache" → "" (no parent dirs)
    local name="$1"
    if [[ "$name" == */* ]]; then
        echo "${name%/*}"
    fi
}

path_to_unit_name() {
    # Convert /var/lib/apt/lists → var-lib-apt-lists.mount
    # With SYSTEMD_UNIT_PREFIX="nosnap-" → nosnap-var-lib-apt-lists.mount
    #
    # systemd mount units require the name to match the mount path exactly
    # when Where= is set. However, we use a custom name (prefixed) and
    # specify Where= explicitly in the unit, which systemd handles correctly.
    local path="$1"
    local base
    base="$(echo "$path" | sed 's|^/||; s|/|-|g')"
    echo "${SYSTEMD_UNIT_PREFIX}${base}.mount"
}

subvol_exists() {
    # Check if a subvolume exists (verifies it's actually a subvolume,
    # not just a regular directory, using btrfs subvolume show).
    local toplevel="$1"
    local name="$2"
    local full_path="$toplevel/$name"

    if [[ ! -e "$full_path" ]]; then
        return 1
    fi
    # btrfs subvolume show returns 0 only for actual subvolumes
    btrfs subvolume show "$full_path" &>/dev/null
}

check_open_files() {
    # Check if any process has open files inside the target path.
    # Returns 1 if processes found (caller should warn user).
    local path="$1"
    local pids
    pids=$(lsof +D "$path" 2>/dev/null | tail -n +2 | awk '{print $2}' | sort -u || true)
    if [[ -n "$pids" ]]; then
        echo "⚠️  Processes with open files in $path:"
        lsof +D "$path" 2>/dev/null | head -20
        echo
        return 1
    fi
    return 0
}

resolve_btrbk_name() {
    # Resolve which btrbk snapshot_name to use for a given target path.
    # Looks up BTRBK_MAP for the longest matching mount point prefix.
    # e.g. target=/var/lib/apt/lists, map has [/]=raiz [/home]=home → returns "raiz"
    #
    # Returns empty string if no match (caller falls back to 'btrbk snapshot' all).
    local target="$1"
    local best_match=""
    local best_len=0

    for mount_point in "${!BTRBK_MAP[@]}"; do
        # Check if target starts with this mount point
        if [[ "$target" == "$mount_point"* ]] || [[ "$target" == "$mount_point" ]]; then
            local len=${#mount_point}
            if (( len > best_len )); then
                best_len=$len
                best_match="$mount_point"
            fi
        fi
    done

    if [[ -n "$best_match" ]]; then
        echo "${BTRBK_MAP[$best_match]}"
    fi
}

run_safety_snapshot() {
    # Run btrbk snapshot to preserve current state before making changes.
    # If BTRBK_MAP is configured, only snapshots the affected subvolume.
    # Respects SNAPSHOT flag (caller should check before calling).
    local target="$1"

    if ! command -v btrbk &>/dev/null; then
        echo "  ⚠️  btrbk not found — skipping safety snapshot."
        echo "     Consider: apt install btrbk"
        return
    fi

    local btrbk_name
    btrbk_name=$(resolve_btrbk_name "$target")

    if [[ -n "$btrbk_name" ]]; then
        echo "  Taking safety snapshot: btrbk snapshot $btrbk_name"
        btrbk snapshot "$btrbk_name" 2>&1 | tail -3
    else
        echo "  Taking safety snapshot: btrbk snapshot (all subvolumes)"
        echo "  (Tip: set BTRBK_MAP in config for selective snapshots)"
        btrbk snapshot 2>&1 | tail -3
    fi
    echo "  Safety snapshot complete."
}

# --- Main ---

echo "=== btrfs-exclude-path ==="
echo

# Detect device
if [[ -z "$DEVICE" ]]; then
    DEVICE=$(detect_device "$TARGET")
fi
echo "  Target:     $TARGET"
echo "  Device:     $DEVICE"

# Generate names
SUBVOL_NAME=$(path_to_subvol_name "$TARGET")
UNIT_NAME=$(path_to_unit_name "$TARGET")
PARENT_DIRS=$(subvol_parent_dirs "$SUBVOL_NAME")

echo "  Subvolume:  $SUBVOL_NAME"
echo "  Unit:       $UNIT_NAME"
if [[ -n "$PARENT_DIRS" ]]; then
    echo "  Dirs:       $PARENT_DIRS (will be created if needed)"
fi
echo

# Check if mount unit already exists (idempotent exit)
if [[ -f "$MOUNT_UNIT_DIR/$UNIT_NAME" ]]; then
    echo "  ℹ️  Mount unit $UNIT_NAME already exists — nothing to do."
    exit 0
fi

# Mount top-level (subvolid=5) to manage subvolumes
BTRFS_TOPLEVEL=$(mktemp -d)
mount -o subvolid=5 "$DEVICE" "$BTRFS_TOPLEVEL"
trap 'umount "$BTRFS_TOPLEVEL" 2>/dev/null; rmdir "$BTRFS_TOPLEVEL" 2>/dev/null' EXIT

# Check if subvolume already exists (using btrfs subvolume show)
if subvol_exists "$BTRFS_TOPLEVEL" "$SUBVOL_NAME"; then
    echo "  ℹ️  Subvolume $SUBVOL_NAME already exists (skipping create + copy)"
    SUBVOL_EXISTS=true
else
    SUBVOL_EXISTS=false
fi

# Generate .mount unit content
UNIT_CONTENT="[Unit]
Description=Btrfs subvolume for $TARGET (excluded from snapshots)
DefaultDependencies=no
After=local-fs-pre.target
Before=local-fs.target

[Mount]
What=$DEVICE
Where=$TARGET
Type=btrfs
Options=subvol=$SUBVOL_NAME,$BTRFS_MOUNT_OPTS

[Install]
WantedBy=local-fs.target
"

# --- Show plan ---
echo "--- Plan ---"
echo
STEP=1
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    if [[ "$SNAPSHOT" == "true" ]]; then
        echo "  ${STEP}. Take safety snapshot (btrbk)"
        ((STEP++))
    fi
    echo "  ${STEP}. Create subvolume: $SUBVOL_NAME"
    ((STEP++))
    echo "  ${STEP}. Copy data: $TARGET/* → subvolume (reflink, no extra disk space)"
    ((STEP++))
fi
echo "  ${STEP}. Create mount unit: $MOUNT_UNIT_DIR/$UNIT_NAME"
((STEP++))
echo "  ${STEP}. Enable and start mount (overlays original path)"
echo
echo "  NOTE: Original data remains under the mount (not deleted)."
echo "        After verifying everything works, you can reclaim space"
echo "        by removing the old data — see instructions at the end."
echo
echo "--- Unit content ---"
echo "$UNIT_CONTENT"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "  [DRY-RUN] No changes made."
    exit 0
fi

# Check for open files
if ! check_open_files "$TARGET"; then
    echo
    echo "  The processes listed above have open files in $TARGET."
    echo "  This script does NOT kill or stop them."
    echo "  You should stop them manually in another terminal if you"
    echo "  want a clean data copy. The mount will still work either way,"
    echo "  but in-flight writes during the copy may be inconsistent."
    echo
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Execute
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    # Safety snapshot via btrbk (if enabled)
    if [[ "$SNAPSHOT" == "true" ]]; then
        run_safety_snapshot "$TARGET"
    else
        echo "  ⏭️  Snapshot skipped (--no-snapshot)"
    fi

    # Create parent directories inside btrfs top-level if needed
    if [[ -n "$PARENT_DIRS" ]]; then
        mkdir -p "$BTRFS_TOPLEVEL/$PARENT_DIRS"
    fi

    # Create subvolume
    echo "  Creating subvolume $SUBVOL_NAME..."
    btrfs subvolume create "$BTRFS_TOPLEVEL/$SUBVOL_NAME"

    # Copy data using reflink (btrfs shares blocks — no extra disk space used)
    if [[ -d "$TARGET" ]] && [[ "$(ls -A "$TARGET" 2>/dev/null)" ]]; then
        echo "  Copying data from $TARGET to subvolume (reflink, no extra space)..."
        TEMP_MOUNT=$(mktemp -d)
        mount -o "subvol=$SUBVOL_NAME,$BTRFS_MOUNT_OPTS" "$DEVICE" "$TEMP_MOUNT"

        # cp --reflink=auto: if btrfs supports it (yes), shares blocks without copying
        cp -a --reflink=auto "$TARGET/." "$TEMP_MOUNT/"

        umount "$TEMP_MOUNT"
        rmdir "$TEMP_MOUNT"
        echo "  Data copied (reflink — blocks shared, no extra disk usage)."
    else
        echo "  Target empty or doesn't exist — no data to copy."
        mkdir -p "$TARGET"
    fi
fi

# Install .mount unit
echo "  Installing $UNIT_NAME..."
echo "$UNIT_CONTENT" > "$MOUNT_UNIT_DIR/$UNIT_NAME"

# Activate
systemctl daemon-reload
systemctl enable "$UNIT_NAME"
systemctl start "$UNIT_NAME"

echo
echo "✅ Done. $TARGET is now on subvolume $SUBVOL_NAME (excluded from snapshots)."
echo
echo "--- Verify ---"
echo "  systemctl status $UNIT_NAME"
echo "  findmnt $TARGET"
echo "  btrfs subvolume list /mnt/btrfs_pool | grep ${SUBVOL_NAME##*/}"
echo
echo "--- Cleanup (reclaim space from old data) ---"
echo "  The original data is hidden under the mount. To remove it:"
echo
echo "    # 1. Mount parent subvolume somewhere temporary"
echo "    sudo mount -o subvol=@,noatime /dev/YOUR_DEVICE /mnt/tmp_parent"
echo
echo "    # 2. Verify old data is there"
echo "    ls /mnt/tmp_parent${TARGET}/"
echo
echo "    # 3. Remove it (IRREVERSIBLE — btrbk snapshot was taken for safety)"
echo "    sudo rm -rf /mnt/tmp_parent${TARGET}/*"
echo
echo "    # 4. Unmount"
echo "    sudo umount /mnt/tmp_parent"
echo
echo "  The safety snapshot taken earlier preserves the state before this operation."
echo "  Use 'btrbk list snapshots' to see available recovery points."

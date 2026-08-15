#!/usr/bin/env bash
# btrfs-exclude-path.sh — Exclude a directory from btrfs snapshots
#
# Creates a nested subvolume and a systemd .mount unit so the path
# is excluded from parent subvolume snapshots.
#
# Usage:
#   btrfs-exclude-path.sh /var/lib/apt/lists
#   btrfs-exclude-path.sh /var/log/journal --dry-run
#   btrfs-exclude-path.sh /var/crash --device /dev/dm-0
#   btrfs-exclude-path.sh /var/tmp --prefix nosnap
#
# What it does:
#   1. Detects the btrfs device for the path
#   2. Creates a new subvolume (e.g. var_lib_apt_lists)
#   3. Copies existing data to the new subvolume (reflink, no extra space)
#   4. Generates a systemd .mount unit
#   5. Enables and starts the mount (overlays old path)
#
# Requirements: root, btrfs filesystem, systemd
#
# Config:
#   Reads defaults from /opt/btrfs-churn-mon/etc/btrfs-exclude-path.conf
#   (if exists). Format: KEY=VALUE. Supported: DEVICE, PREFIX, MOUNT_OPTS.

set -euo pipefail

# --- Defaults (overridable via config or flags) ---
MOUNT_UNIT_DIR="/etc/systemd/system"
BTRFS_MOUNT_OPTS="noatime,compress=zstd"
SUBVOL_PREFIX=""  # e.g. "nosnap" → subvol: nosnap/var_lib_apt_lists

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
  --device DEV    Btrfs device (auto-detected if omitted)
  --prefix NAME   Prefix for subvolume name (e.g. nosnap → nosnap/var_cache)
  --help          Show this help

Config file: $CONFIG_FILE
  DEVICE=         Default btrfs device
  SUBVOL_PREFIX=  Default prefix (e.g. nosnap)
  BTRFS_MOUNT_OPTS= Mount options (default: noatime,compress=zstd)

Examples:
  $(basename "$0") /var/lib/apt/lists
  $(basename "$0") /var/log/journal --dry-run
  $(basename "$0") /var/crash --prefix nosnap
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --device) DEVICE="$2"; shift 2 ;;
        --prefix) SUBVOL_PREFIX="$2"; shift 2 ;;
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
    local path="$1"
    local dev
    dev=$(df --output=source "$path" 2>/dev/null | tail -1)
    if [[ -z "$dev" ]] || ! btrfs filesystem show "$dev" &>/dev/null; then
        echo "ERROR: could not detect btrfs device for $path" >&2
        exit 1
    fi
    echo "$dev"
}

path_to_subvol_name() {
    # Convert /var/lib/apt/lists → var_lib_apt_lists
    # With prefix "nosnap" → nosnap/var_lib_apt_lists
    local path="$1"
    local name
    name="$(echo "$path" | sed 's|^/||; s|/|_|g')"
    if [[ -n "$SUBVOL_PREFIX" ]]; then
        echo "${SUBVOL_PREFIX}/${name}"
    else
        echo "$name"
    fi
}

path_to_unit_name() {
    # Convert /var/lib/apt/lists → var-lib-apt-lists.mount
    local path="$1"
    echo "$(echo "$path" | sed 's|^/||; s|/|-|g').mount"
}

subvol_exists() {
    # Check if a subvolume exists (not just a directory)
    local toplevel="$1"
    local name="$2"
    local full_path="$toplevel/$name"

    if [[ ! -e "$full_path" ]]; then
        return 1
    fi
    # Verify it's actually a subvolume (not just a dir)
    btrfs subvolume show "$full_path" &>/dev/null
}

check_open_files() {
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

echo "  Subvolume:  $SUBVOL_NAME"
echo "  Unit:       $UNIT_NAME"
echo

# Check if mount unit already exists
if [[ -f "$MOUNT_UNIT_DIR/$UNIT_NAME" ]]; then
    echo "  ℹ️  Mount unit $UNIT_NAME already exists — nothing to do."
    exit 0
fi

# Mount top-level (subvolid=5) to manage subvolumes
BTRFS_TOPLEVEL=$(mktemp -d)
mount -o subvolid=5 "$DEVICE" "$BTRFS_TOPLEVEL"
trap 'umount "$BTRFS_TOPLEVEL" 2>/dev/null; rmdir "$BTRFS_TOPLEVEL" 2>/dev/null' EXIT

# Check if subvolume already exists (properly, not just directory check)
if subvol_exists "$BTRFS_TOPLEVEL" "$SUBVOL_NAME"; then
    echo "  ℹ️  Subvolume $SUBVOL_NAME already exists"
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

echo "--- Plan ---"
echo
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    echo "  1. Create subvolume: $SUBVOL_NAME"
    echo "  2. Copy data: $TARGET/* → subvolume (reflink, no extra space)"
fi
echo "  3. Create mount unit: $MOUNT_UNIT_DIR/$UNIT_NAME"
echo "  4. Enable and start mount (overlays original path)"
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
    echo "  The script does NOT kill them. You should stop them manually"
    echo "  (in another terminal) if you want a clean move."
    echo
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Create subvolume (with prefix directory if needed)
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    # Create prefix directory if needed
    if [[ -n "$SUBVOL_PREFIX" ]] && [[ ! -d "$BTRFS_TOPLEVEL/$SUBVOL_PREFIX" ]]; then
        mkdir -p "$BTRFS_TOPLEVEL/$SUBVOL_PREFIX"
    fi

    echo "  Creating subvolume $SUBVOL_NAME..."
    btrfs subvolume create "$BTRFS_TOPLEVEL/$SUBVOL_NAME"

    # Copy data using reflink (btrfs shares blocks, no extra space)
    if [[ -d "$TARGET" ]] && [[ "$(ls -A "$TARGET" 2>/dev/null)" ]]; then
        echo "  Copying data from $TARGET to subvolume (reflink)..."
        TEMP_MOUNT=$(mktemp -d)
        mount -o "subvol=$SUBVOL_NAME,$BTRFS_MOUNT_OPTS" "$DEVICE" "$TEMP_MOUNT"

        cp -a --reflink=auto "$TARGET/." "$TEMP_MOUNT/"

        umount "$TEMP_MOUNT"
        rmdir "$TEMP_MOUNT"
        echo "  Data copied (reflink — no extra disk usage)."
    else
        echo "  Target empty or doesn't exist — no data to copy."
        # Ensure the mount point directory exists
        mkdir -p "$TARGET"
    fi
fi

# Install .mount unit
echo "  Installing $UNIT_NAME..."
echo "$UNIT_CONTENT" > "$MOUNT_UNIT_DIR/$UNIT_NAME"

systemctl daemon-reload
systemctl enable "$UNIT_NAME"
systemctl start "$UNIT_NAME"

echo
echo "✅ Done. $TARGET is now on subvolume $SUBVOL_NAME (excluded from snapshots)."
echo "   Original data is hidden under the mount (still exists on parent subvol)."
echo "   To reclaim space, remove old data after verifying mount works:"
echo "     # Mount parent without the overlay, then rm the old dir content"
echo
echo "Verify:"
echo "  systemctl status $UNIT_NAME"
echo "  findmnt $TARGET"
echo "  btrfs subvolume list /mnt/btrfs_pool | grep $SUBVOL_NAME"

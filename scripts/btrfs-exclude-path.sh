#!/usr/bin/env bash
# btrfs-exclude-path.sh — Exclude a directory from btrfs snapshots
#
# Creates a nested subvolume and a systemd .mount unit so the path
# is excluded from parent subvolume snapshots.
#
# Usage:
#   btrfs-exclude-path.sh /var/lib/apt/lists
#   btrfs-exclude-path.sh /var/log/journal --dry-run
#   btrfs-exclude-path.sh /var/crash --device /dev/sda2
#
# What it does:
#   1. Detects the btrfs device and parent subvolume for the path
#   2. Creates a new subvolume (e.g. @var_lib_apt_lists)
#   3. Moves existing data to the new subvolume
#   4. Generates a systemd .mount unit
#   5. Enables and starts the mount
#
# Requirements: root, btrfs filesystem, systemd
#
# Safety:
#   - Checks lsof for open files before moving
#   - --dry-run shows plan without modifying
#   - Backs up existing data (rsync -a) before removing original

set -euo pipefail

# --- Config ---
MOUNT_UNIT_DIR="/etc/systemd/system"
BTRFS_MOUNT_OPTS="noatime,compress=zstd"

# --- Args ---
DRY_RUN=false
DEVICE=""
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
  --help          Show this help

Examples:
  $(basename "$0") /var/lib/apt/lists
  $(basename "$0") /var/log/journal --dry-run
  $(basename "$0") /var/crash --device /dev/sda2
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --device) DEVICE="$2"; shift 2 ;;
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
    # Find the btrfs device for the given path
    local path="$1"
    local dev
    dev=$(df --output=source "$path" 2>/dev/null | tail -1)
    if [[ -z "$dev" ]] || ! btrfs filesystem show "$dev" &>/dev/null; then
        echo "ERROR: could not detect btrfs device for $path" >&2
        exit 1
    fi
    echo "$dev"
}

detect_parent_subvol() {
    # Find the parent subvolume name for a path
    local path="$1"
    local subvol
    subvol=$(btrfs subvolume show "$path" 2>/dev/null | grep -m1 "Name:" | awk '{print $2}' || true)
    if [[ -z "$subvol" ]]; then
        # Path might be inside a subvolume — find the mount point's subvol
        subvol=$(findmnt -n -o FSROOT "$path" 2>/dev/null | sed 's|^/||' || true)
    fi
    echo "${subvol:-@}"
}

path_to_subvol_name() {
    # Convert /var/lib/apt/lists → @var_lib_apt_lists
    local path="$1"
    echo "@$(echo "$path" | sed 's|^/||; s|/|_|g')"
}

path_to_unit_name() {
    # Convert /var/lib/apt/lists → var-lib-apt-lists.mount
    local path="$1"
    echo "$(echo "$path" | sed 's|^/||; s|/|-|g').mount"
}

check_open_files() {
    local path="$1"
    local pids
    pids=$(lsof +D "$path" 2>/dev/null | tail -n +2 | awk '{print $2}' | sort -u || true)
    if [[ -n "$pids" ]]; then
        echo "WARNING: The following processes have open files in $path:"
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
MOUNT_POINT="$TARGET"

echo "  Subvolume:  $SUBVOL_NAME"
echo "  Unit:       $UNIT_NAME"
echo

# Check if subvolume already exists
BTRFS_TOPLEVEL=$(mktemp -d)
mount -o subvolid=5 "$DEVICE" "$BTRFS_TOPLEVEL"
trap 'umount "$BTRFS_TOPLEVEL" 2>/dev/null; rmdir "$BTRFS_TOPLEVEL" 2>/dev/null' EXIT

if [[ -d "$BTRFS_TOPLEVEL/$SUBVOL_NAME" ]]; then
    echo "  ℹ️  Subvolume $SUBVOL_NAME already exists"
    SUBVOL_EXISTS=true
else
    SUBVOL_EXISTS=false
fi

# Check if mount unit already exists
if [[ -f "$MOUNT_UNIT_DIR/$UNIT_NAME" ]]; then
    echo "  ℹ️  Mount unit $UNIT_NAME already exists"
    echo "  Nothing to do."
    exit 0
fi

# Generate .mount unit content
UNIT_CONTENT="[Unit]
Description=Btrfs subvolume for $MOUNT_POINT (excluded from snapshots)
DefaultDependencies=no
After=local-fs-pre.target
Before=local-fs.target

[Mount]
What=$DEVICE
Where=$MOUNT_POINT
Type=btrfs
Options=subvol=$SUBVOL_NAME,$BTRFS_MOUNT_OPTS

[Install]
WantedBy=local-fs.target
"

echo "--- Plan ---"
echo
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    echo "  1. Create subvolume: $SUBVOL_NAME"
    echo "  2. Move data: $TARGET/* → subvolume"
fi
echo "  3. Create mount unit: $MOUNT_UNIT_DIR/$UNIT_NAME"
echo "  4. Enable and start mount"
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
    read -p "Processes are using $TARGET. Stop them and continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Create subvolume
if [[ "$SUBVOL_EXISTS" == "false" ]]; then
    echo "  Creating subvolume $SUBVOL_NAME..."
    btrfs subvolume create "$BTRFS_TOPLEVEL/$SUBVOL_NAME"

    # Move data
    if [[ -d "$TARGET" ]] && [[ "$(ls -A "$TARGET" 2>/dev/null)" ]]; then
        echo "  Moving data from $TARGET to subvolume..."
        # Mount new subvol temporarily
        TEMP_MOUNT=$(mktemp -d)
        mount -o "subvol=$SUBVOL_NAME,$BTRFS_MOUNT_OPTS" "$DEVICE" "$TEMP_MOUNT"

        rsync -a --remove-source-files "$TARGET/" "$TEMP_MOUNT/"
        # Remove empty dirs left by rsync
        find "$TARGET" -depth -type d -empty -delete 2>/dev/null || true

        umount "$TEMP_MOUNT"
        rmdir "$TEMP_MOUNT"
        echo "  Data moved."
    else
        echo "  Target empty or doesn't exist — no data to move."
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
echo
echo "Verify:"
echo "  systemctl status $UNIT_NAME"
echo "  findmnt $TARGET"

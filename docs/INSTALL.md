# Installation

## Requirements

- Linux with Btrfs filesystem
- Python 3.10+
- `python3-typer` (Ubuntu 24.04: `apt install python3-typer`)
- `btrfs-progs` (`apt install btrfs-progs`)
- systemd
- btrbk (recommended — for snapshot management and safety snapshots)

---

## Clone

```bash
sudo git clone <repo-url> /opt/btrfs-churn-mon
cd /opt/btrfs-churn-mon
```

---

## Install

```bash
# Install all system components
sudo python3 bin/btrfs-churn-mon install
```

This creates:
1. System user `btrfs-churn` (UID < 1000, no-home, nologin)
2. Sudoers rule `/etc/sudoers.d/btrfs-churn-mon` (NOPASSWD for btrfs send/receive)
3. Systemd service + timer (24h cycle)
4. Data directories: `PREFIX/{reports,state}` (owned by btrfs-churn)
5. Environment file: `/etc/default/btrfs-churn-mon` (SNAPSHOT_FAMILIES)
6. Log file: `/var/log/btrfs-churn-mon.log` (owned by btrfs-churn)

Preview without changes:

```bash
sudo python3 bin/btrfs-churn-mon install --dry-run
```

---

## Verify

```bash
python3 bin/btrfs-churn-mon verify
```

Expected:
```
✅ All checks passed.
```

Check timer status:
```bash
systemctl status btrfs-churn-mon.timer
```

---

## Configuration

### Runtime config

Edit `PREFIX/etc/btrfs-churn-mon.conf`:

```bash
PREFIX=/opt/btrfs-churn-mon
SNAPDIR=/mnt/btrfs_pool/btrbk_snapshots
DEFAULT_CATCHUP_LIMIT=100
```

### Systemd environment

Edit `/etc/default/btrfs-churn-mon`:

```bash
# Comma-separated list of families to monitor
# Remove this line to auto-discover all families
SNAPSHOT_FAMILIES=home,raiz
```

### Exclude paths config

Copy `etc/btrfs-exclude-path.conf.example` to `etc/btrfs-exclude-path.conf` and edit:

```bash
DEVICE=/dev/disk/by-id/dm-uuid-LVM-xxx
SUBVOL_PREFIX=
SYSTEMD_UNIT_PREFIX=
BTRFS_MOUNT_OPTS="noatime,compress=zstd"
SNAPSHOT=true
declare -A BTRBK_MAP=( [/]=raiz [/home]=home )
```

---

## Bootstrap

Process all historical snapshot pairs:

```bash
python3 bin/btrfs-churn-mon bootstrap
```

Bootstrap a single family:

```bash
python3 bin/btrfs-churn-mon bootstrap --family home
```

---

## Logging

Two outputs configured automatically:
- **stderr** → journald (visible via `journalctl -u btrfs-churn-mon.service`)
- **/var/log/btrfs-churn-mon.log** → persistent (INFO/WARNING/ERROR only)

```bash
# Recent logs
journalctl -u btrfs-churn-mon.service -n 50

# Follow real-time
journalctl -u btrfs-churn-mon.service -f

# Only warnings/errors
journalctl -u btrfs-churn-mon.service -p warning

# Persistent log file
tail -f /var/log/btrfs-churn-mon.log
```

Verbose mode (adds DEBUG to stderr):
```bash
python3 bin/btrfs-churn-mon -v monitor
```

---

## Exclude Paths from Snapshots

Reduce churn by excluding volatile directories from snapshots:

```bash
# Preview what would be done
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists --dry-run

# Execute
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists

# Batch (one snapshot before, skip for each exclusion)
sudo btrbk snapshot raiz
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists --no-snapshot
sudo scripts/btrfs-exclude-path.sh /var/crash --no-snapshot
sudo scripts/btrfs-exclude-path.sh /var/log/journal --no-snapshot
```

The script:
1. Creates a btrfs subvolume (excluded from parent snapshots automatically)
2. Copies existing data via reflink (no extra disk space)
3. Creates a systemd `.mount` unit (replaces fstab entries)
4. Enables and starts the mount

---

## Upgrade

```bash
cd /opt/btrfs-churn-mon
git pull
sudo python3 bin/btrfs-churn-mon install   # re-installs if units changed
python3 bin/btrfs-churn-mon verify
```

---

## Uninstall

```bash
# Preserves config and data
sudo python3 bin/btrfs-churn-mon uninstall --yes

# Remove everything including reports/state
sudo python3 bin/btrfs-churn-mon uninstall --yes --purge-data
```

Config files (`/etc/default/btrfs-churn-mon`, `etc/btrfs-churn-mon.conf`) are **never** removed.

---

## Tests

```bash
python3 -m pytest
```

170 unit tests — no root, no btrfs required.

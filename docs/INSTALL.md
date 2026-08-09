# Installation

## Requirements

- Linux with Btrfs filesystem
- Python 3.10+
- `python3-typer` (Ubuntu 24.04: `apt install python3-typer`)
- `btrfs-progs` (`apt install btrfs-progs`)
- systemd
- btrbk (recommended — for snapshot management)

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
1. System user `btrfs-churn` (no-home, nologin)
2. Sudoers rule `/etc/sudoers.d/btrfs-churn-mon`
3. Systemd service + timer (24h cycle)
4. Data directories: `PREFIX/{reports,state}`
5. Environment file: `/etc/default/btrfs-churn-mon`

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

Edit `/etc/default/btrfs-churn-mon`:

```bash
# Comma-separated list of families to monitor
SNAPSHOT_FAMILIES=home,raiz
```

Runtime config at `PREFIX/etc/btrfs-churn-mon.conf`:

```bash
PREFIX=/opt/btrfs-churn-mon
SNAPDIR=/mnt/btrfs_pool/btrbk_snapshots
DEFAULT_CATCHUP_LIMIT=100
```

---

## Bootstrap

Process all historical snapshot pairs:

```bash
python3 bin/btrfs-churn-mon bootstrap
```

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

---

## Tests

```bash
python3 -m pytest
```

152 unit tests — no root, no btrfs required.

# btrfs-churn-mon

Analyze Btrfs snapshot churn — find what changes between snapshots.

Answers:
- Why are my snapshots growing?
- Which files change the most between snapshots?
- What's the biggest source of churn over time?

---

## Requirements

- Python 3.10+
- `typer` (via `apt install python3-typer` on Ubuntu 24.04+)
- `btrfs-progs` (btrfs CLI tools)
- sudo access for `btrfs send` / `btrfs receive --dump`
- btrbk (recommended — snapshot management)

---

## Quick Start

```bash
# Install system components (user, sudoers, systemd, directories)
sudo python3 bin/btrfs-churn-mon install

# Verify installation
python3 bin/btrfs-churn-mon verify

# Run monitoring manually (all families)
python3 bin/btrfs-churn-mon monitor

# Check status
python3 bin/btrfs-churn-mon status
```

---

## CLI Commands

```
btrfs-churn-mon monitor     Run monitoring cycle (find pairs, dump, parse, report)
btrfs-churn-mon report      Generate churn report from a detail.tsv
btrfs-churn-mon analyse     Aggregate churn report across all pairs
btrfs-churn-mon status      Show configuration and tracked families
btrfs-churn-mon bootstrap   Full historical bootstrap (all pairs)
btrfs-churn-mon install     Install system components
btrfs-churn-mon verify      Verify installation (alias: install --check)
btrfs-churn-mon uninstall   Remove system components
```

### Monitor

```bash
# Process all discovered families
btrfs-churn-mon monitor

# Process specific families
btrfs-churn-mon monitor --families home,raiz

# Dry-run (show what would be processed)
btrfs-churn-mon monitor --dry-run

# Verbose logging (debug level)
btrfs-churn-mon -v monitor
```

Without `--families`, reads `SNAPSHOT_FAMILIES` env var. Without either, discovers all families in snapdir.

### Install / Uninstall

```bash
# Install (creates user, sudoers, systemd timer, directories, env file, log file)
sudo btrfs-churn-mon install

# Dry-run
sudo btrfs-churn-mon install --dry-run

# Uninstall (preserves config and data)
sudo btrfs-churn-mon uninstall --yes

# Uninstall and remove reports/state
sudo btrfs-churn-mon uninstall --yes --purge-data
```

---

## Logging

Two outputs:
- **stderr** → captured by journald (visible via `journalctl`)
- **/var/log/btrfs-churn-mon.log** → persistent file (INFO/WARNING/ERROR)

```bash
# View logs from systemd timer
journalctl -u btrfs-churn-mon.service -n 50

# Follow in real-time
journalctl -u btrfs-churn-mon.service -f

# Persistent log file
tail -f /var/log/btrfs-churn-mon.log
```

Each pair processed logs: snapshot names, dump lines, unique paths, total churn bytes, elapsed time.

---

## Exclude Paths from Snapshots

Utility script to exclude directories from btrfs snapshots (reduces churn):

```bash
# Preview
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists --dry-run

# Execute (creates subvolume + systemd .mount unit)
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists

# Batch (one snapshot, then skip for each)
sudo btrbk snapshot raiz
sudo scripts/btrfs-exclude-path.sh /var/lib/apt/lists --no-snapshot
sudo scripts/btrfs-exclude-path.sh /var/crash --no-snapshot
sudo scripts/btrfs-exclude-path.sh /var/log/journal --no-snapshot
```

Config: `etc/btrfs-exclude-path.conf` (see `.example` for all options).

---

## Project Layout

```
bin/
    btrfs-churn-mon              # CLI entry point

src/
    __init__.py                  # Root guard (assert_not_root)
    cli.py                       # Typer app (dispatch)
    config.py                    # Configuration (ENV > file > defaults)
    btrfs.py                     # BtrfsClient class (subprocess interface)
    parser.py                    # Parse btrfs send dump → churn data
    report.py                    # Per-pair report (markdown + JSON)
    aggregate.py                 # Multi-pair aggregate report
    monitor.py                   # State machine (find pairs, update state)
    install.py                   # Installer/uninstaller
    log.py                       # Logging config (stderr + file)

scripts/
    btrfs-exclude-path.sh       # Exclude directories from snapshots

install_data/
    btrfs-churn-mon.service     # Systemd service template
    btrfs-churn-mon.timer       # Systemd timer template
    sudoers-btrfs-churn-mon     # Sudoers drop-in template

etc/
    btrfs-churn-mon.conf            # Runtime config
    btrfs-churn-mon.conf.example    # Config example
    btrfs-exclude-path.conf.example # Exclude script config example

tests/
    unit/                        # pytest (170 tests)

docs/
    ENGINEERING_PLAN.md          # Development roadmap and decisions
    INSTALL.md                   # Detailed installation guide
```

---

## Configuration

Precedence: **ENV > config file > defaults**

| Variable | Default | Description |
|----------|---------|-------------|
| `PREFIX` | `/opt/btrfs-churn-mon` | Installation prefix |
| `SNAPDIR` | `/mnt/btrfs_pool/btrbk_snapshots` | Snapshot directory |
| `DEFAULT_CATCHUP_LIMIT` | `100` | Max pairs per monitor run |

Config file: `${PREFIX}/etc/btrfs-churn-mon.conf` or `$CONFIG` env var.

---

## Systemd Timer

After install, the timer runs every 24h:

```bash
systemctl status btrfs-churn-mon.timer
```

The service reads `/etc/default/btrfs-churn-mon`:
```bash
SNAPSHOT_FAMILIES=home,raiz
```

---

## Security Model

- Service runs as unprivileged user `btrfs-churn` (system user, UID < 1000)
- Only `btrfs send` / `btrfs receive --dump` escalate via sudoers
- Root guard: process aborts if run as root (euid == 0)
- Config and data preserved on uninstall

---

## Tests

```bash
python3 -m pytest
```

170 tests covering all modules (unit tests, mocked subprocess).

---

## Upgrade

```bash
cd /opt/btrfs-churn-mon
git pull
sudo python3 bin/btrfs-churn-mon install   # re-installs units if changed
python3 bin/btrfs-churn-mon verify
```

---

## Documentation

- [Engineering Plan](docs/ENGINEERING_PLAN.md) — roadmap, decisions, architecture
- [Installation](docs/INSTALL.md) — detailed setup guide

---

## License

MIT

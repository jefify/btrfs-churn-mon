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
```

Without `--families`, reads `SNAPSHOT_FAMILIES` env var. Without either, discovers all families in snapdir.

### Install / Uninstall

```bash
# Install (creates user, sudoers, systemd timer, directories, env file)
sudo btrfs-churn-mon install

# Dry-run
sudo btrfs-churn-mon install --dry-run

# Uninstall (preserves config and data)
sudo btrfs-churn-mon uninstall --yes

# Uninstall and remove reports/state
sudo btrfs-churn-mon uninstall --yes --purge-data
```

---

## Project Layout

```
bin/
    btrfs-churn-mon          # CLI entry point

src/
    __init__.py              # Root guard (assert_not_root)
    cli.py                   # Typer app (dispatch)
    config.py                # Configuration (ENV > file > defaults)
    btrfs.py                 # BtrfsClient class (subprocess interface)
    parser.py                # Parse btrfs send dump → churn data
    report.py                # Per-pair report (markdown + JSON)
    aggregate.py             # Multi-pair aggregate report
    monitor.py               # State machine (find pairs, update state)
    install.py               # Installer/uninstaller (systemd, user, sudoers)

install_data/
    btrfs-churn-mon.service  # Systemd service template
    btrfs-churn-mon.timer    # Systemd timer template
    sudoers-btrfs-churn-mon  # Sudoers drop-in template

etc/
    btrfs-churn-mon.conf         # Runtime config (not installed — stays in repo)
    btrfs-churn-mon.conf.example # Config example

tests/
    unit/                    # pytest (152 tests)

docs/
    ENGINEERING_PLAN.md      # Development roadmap and decisions
    INSTALL.md               # Detailed installation guide
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

- Service runs as unprivileged user `btrfs-churn`
- Only `btrfs send` / `btrfs receive --dump` escalate via sudoers
- Root guard: process aborts if run as root (euid == 0)

---

## Tests

```bash
python3 -m pytest
```

152 tests covering all modules (unit tests, mocked subprocess).

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

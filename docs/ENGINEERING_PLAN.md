# Engineering Plan — btrfs-churn-mon

Status: Active  
Last updated: 2026-08-04

---

## Context

Project built iteratively with AI assistance. Phases 0-3 completed:
security audit, test stabilization, timer active in production.

Current state: hybrid bash+python. Decision: **migrate fully to Python**
with Typer CLI. Bash stays only for legacy tests (to be removed).

---

## Completed Phases

### Phase 0 — Cleanup ✅

- Removed dead files (.bak, PROJECT_STATE, ROADMAP)
- ENGINEERING_PLAN.md as single planning document

### Phase 1 — Security Audit ✅

- Fixed source ordering bugs (PREFIX used before config load)
- Fixed generate-dump.sh error handling
- ShellCheck pass, SYSTEMD_DIR override for safe testing
- Systemd service with EnvironmentFile

### Phase 2 — Test Stabilization ✅

- All CI tests green (unit + integration + acceptance-safe)
- Test runners consolidated (test-ci.sh, test-real.sh, test-all.sh)

### Phase 3 — Real Testing ✅

- Timer installed and active (24h cycle, 2 families)
- verify-install.sh + verify-bootstrap.sh health checks
- 108 reports generated, monitoring operational

---

## Phase 4 — Full Python Migration

Goal: single-language project (Python + Typer CLI). Bash removed.

### Architecture

```
bin/
└── btrfs-churn-mon              # Entry point (#!/usr/bin/env python3)

src/
├── __init__.py
├── cli.py                       # Typer app (dispatch)
├── config.py                    # Load config (ENV > file > defaults)
├── btrfs.py                     # Btrfs CLI interface (class, reusable)
├── parser.py                    # Parse dump output → churn data
├── report.py                    # Build per-pair report (md + json)
├── aggregate.py                 # Aggregate multi-pair report
├── monitor.py                   # Find pairs, update state, orchestrate
├── bootstrap.py                 # Full historical bootstrap
└── install.py                   # Systemd install/verify

tests/
├── conftest.py                  # Shared fixtures
├── test_parser.py               # (exists — migrate from tests/python/)
├── test_btrfs.py                # Mock subprocess for btrfs interface
├── test_report.py
├── test_aggregate.py
├── test_monitor.py
├── test_bootstrap.py
├── test_install.py
└── test_cli.py                  # Typer CliRunner

etc/
├── btrfs-churn-mon.conf.example
└── systemd/                     # (moved from systemd/)
    ├── btrfs-churn-mon.service
    └── btrfs-churn-mon.timer

docs/
├── ENGINEERING_PLAN.md          # This file
├── INSTALL.md
└── archived/
```

### 4.1 — Btrfs interface class (foundation)

Design a reusable class for btrfs CLI interaction:

```python
class BtrfsClient:
    """Interface with btrfs CLI tools via subprocess."""

    def send_dump(self, old: Path, new: Path) -> str:
        """Generate incremental send dump between two snapshots.
        Uses sudo for privilege escalation (only operation requiring root)."""

    def list_subvolumes(self, path: Path) -> list[Subvolume]:
        """List subvolumes under a path."""

    def show_subvolume(self, path: Path) -> SubvolumeInfo:
        """Get metadata for a subvolume/snapshot."""

    def discover_families(self, snapdir: Path) -> list[str]:
        """Discover snapshot families from naming convention."""

    def find_snapshots(self, snapdir: Path, family: str) -> list[Path]:
        """Find all snapshots of a family, sorted chronologically."""
```

**Privilege model:**
- Service runs as unprivileged user (`btrfs-churn` or current user)
- Only `send_dump()` escalates via `sudo btrfs send` / `sudo btrfs receive --dump`
- Everything else (reports, state, aggregation) runs without privilege
- sudoers rule created by installer:
  ```
  # /etc/sudoers.d/btrfs-churn-mon
  btrfs-churn ALL=(root) NOPASSWD: /usr/bin/btrfs send *, /usr/bin/btrfs receive --dump *
  ```

Design:
- Subprocess calls isolated behind methods
- `use_sudo: bool` parameter (default True, disable for testing)
- Easy to mock in tests (inject fake BtrfsClient)
- Handles non-zero exit codes gracefully (btrfs send quirks)

Steps:
- [ ] Create `src/btrfs.py` with BtrfsClient class
- [ ] Create `tests/test_btrfs.py` (mocked subprocess)
- [ ] Create `etc/sudoers.d/btrfs-churn-mon` template
- [ ] Test with real btrfs (manual validation)

### 4.2 — Config module

```python
class Config:
    prefix: Path         # /opt/btrfs-churn-mon
    snapdir: Path        # /mnt/btrfs_pool/btrbk_snapshots
    catchup_limit: int   # 100
```

- Precedence: ENV > config file > defaults
- Config file path: `{prefix}/etc/btrfs-churn-mon.conf` or `$CONFIG`

Steps:
- [ ] Create `src/config.py`
- [ ] Create `tests/test_config.py`
- [ ] Remove `lib/load-config.rc` (replaced)

### 4.3 — Parser module (already done, move)

- [ ] Move `lib/parse_churn.py` → `src/parser.py`
- [ ] Move `tests/python/test_parse_churn.py` → `tests/test_parser.py`
- [ ] Adapt imports

### 4.4 — Report modules (migrate existing Python)

- [ ] Move `lib/build-report.py` → `src/report.py` (refactor as importable module)
- [ ] Move `lib/generate-mon-report.py` → `src/aggregate.py` (refactor)
- [ ] Create `tests/test_report.py`
- [ ] Create `tests/test_aggregate.py`

### 4.5 — Monitor + Bootstrap (migrate from bash)

- [ ] Create `src/monitor.py` (find-pairs, update-state, orchestration)
- [ ] Create `src/bootstrap.py` (discover families, process all)
- [ ] Create `tests/test_monitor.py`
- [ ] Create `tests/test_bootstrap.py`

### 4.6 — Install module (migrate from bash)

- [ ] Create `src/install.py` (systemd install/verify/health-check)
- [ ] Install creates:
  - System user `btrfs-churn` (verify if exists, create if not — `useradd --system --no-create-home`)
  - `/etc/sudoers.d/btrfs-churn-mon` (privilege escalation for btrfs send)
  - systemd service (runs as `User=btrfs-churn`)
  - systemd timer
  - Directories with correct ownership: `PREFIX/{reports,state}` owned by `btrfs-churn`
- [ ] `btrfs-churn-mon install --check` validates: user exists + sudoers + systemd + permissions
- [ ] Create `tests/test_install.py`
- [ ] Move `systemd/` → `etc/systemd/`

### 4.7 — Typer CLI (final assembly)

- [ ] Create `src/cli.py` with Typer app
- [ ] Subcommands: report, analyse, monitor, status, bootstrap, install, verify
- [ ] Create `bin/btrfs-churn-mon` (entry point → `src.cli:app`)
- [ ] Create `tests/test_cli.py` (CliRunner)
- [ ] `--install-completion` for bash/zsh/fish
- [ ] Update systemd service ExecStart

### 4.8 — Cleanup

- [ ] Remove all `bin/*.sh` (old scripts)
- [ ] Remove `lib/` directory (absorbed into src/)
- [ ] Remove `cmd/` if created
- [ ] Remove `test/` (legacy bash tests)
- [ ] Remove `tests/python/` (merged into `tests/`)
- [ ] Update README, INSTALL.md
- [ ] Update pyproject.toml (dependencies: typer)
- [ ] Final: `pytest` green + `btrfs-churn-mon --help` works

---

## Phase 5 — Features (post-migration)

| Feature | Priority | Notes |
|---------|----------|-------|
| Retention/rotation | High | `btrfs-churn-mon report --keep-days 30` |
| GitHub Actions CI | Medium | pytest only (no btrfs needed for unit/integration) |
| Trend analysis | Low | ASCII graphs, path history |
| Exclude management | Low | Config-based exclude patterns |
| Health check | Low | `btrfs-churn-mon status --health` |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-07-17 | Replace ROADMAP.md with ENGINEERING_PLAN.md | Single doc for both vision and execution |
| 2025-07-17 | Replace AWK with Python | Unify stack, easier maintenance |
| 2025-07-17 | pytest for Python logic | Test functions directly, better assertions |
| 2025-07-17 | Privileged tests in separate runner | Prevent accidental root execution in CI |
| 2025-07-17 | SYSTEMD_DIR override for install tests | Test without touching real systemd |
| 2026-08-04 | Full Python migration (drop bash) | Single language, Typer CLI, no bats-core needed |
| 2026-08-04 | BtrfsClient class for CLI interface | Reusable, mockable, handles quirks centrally |
| 2026-08-04 | Typer for CLI dispatch | Single declaration → parsing + help + completion |
| 2026-08-04 | sudoers for privilege escalation | Only btrfs send needs root; service runs unprivileged |

---

## Guiding Principles

- MVP first — working code over architecture discussion
- Tests are the spec — failing test > design debate
- TDD: document → contract → tests → implement
- Security before features — audit before activating timer
- Single language — Python for everything, subprocess for btrfs CLI
- Gradual migration — bash tests stay until Python equivalents exist

---

## Design Docs

- [Phase 4.1/4.3 — Parser design](archived/plan-python-parse-churn.md)

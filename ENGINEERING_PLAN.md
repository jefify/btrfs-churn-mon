# Engineering Plan — btrfs-churn-mon

Status: Active  
Last updated: 2025-07-17

---

## Context

Project built iteratively with AI assistance (web-based, patch-by-patch).
Most features work but some loose ends remain from the back-and-forth process.
Goal: reach a clean state where all tests pass, code is safe, and the timer can be activated with confidence.

---

## Phase 0 — Cleanup

Remove dead weight before any real work.

- [ ] Remove `bin/setup-systemd-timer.sh.bak` (replaced by `install-systemd.sh`)
- [ ] Remove `PROJECT_STATE.md` (redundant with this plan + README)
- [ ] Remove `ROADMAP.md` (superseded by this file)
- [ ] Review for any other dead/orphan files

---

## Phase 1 — Security Audit

Ensure nothing dangerous before activating the timer.

- [x] Audit `generate-dump.sh` — runs `btrfs send` (requires root or CAP_SYS_ADMIN)
  - Fixed: now warns on partial failure, exits on empty dump
- [x] Audit `install-systemd.sh` — writes to `/etc/systemd/` (requires sudo, documented)
- [x] Check all scripts for unquoted variables (injection risk) — all clean
- [x] Check file permissions on generated reports/state — inherits umask, acceptable
- [x] Fix `|| true` in generate-dump.sh — replaced with proper error handling
- [x] Fix `monitor-run.sh`: PREFIX used before source (could write to wrong path)
- [x] Fix `analyse-all-pairs.sh`: same source ordering bug
- [x] Systemd service: added EnvironmentFile for configurable snapshot family
- [ ] Run ShellCheck on all `.sh` files (shellcheck not installed — deferred to Phase 4)

---

## Phase 2 — Test Stabilization

Goal: `bin/test-ci.sh` = PASS (without root).

- [x] Run full suite, map failures — **ALL GREEN** (unit=20, integration=5, acceptance-safe=3)
- [x] Fix broken tests — none broken
- [x] Reorganize misplaced tests — already well-organized:
  - `test-ci.sh` = unit + integration (CI-safe, no root)
  - `test-all.sh` = + acceptance-safe
  - `test-acceptance-real.sh` = needs root (added warning guard)
  - `test-local.sh` = needs settings.conf + btrfs + root
- [x] Mark privileged tests clearly — scenario133 has EUID guard, runner has warning
- [ ] Improve `test/lib/assert.sh`:
  - [ ] Add `assert_exit_code` (run command, check rc without `set +e` dance)
  - [ ] Add `assert_file_contains_lines` (ordered multi-line check)
  - [ ] Add test summary at end (TOTAL / PASS / FAIL count)
  - [ ] Consider: trap-based cleanup (auto rm tmpdir on exit)
- [x] Verify all unit tests are truly CI-safe — confirmed (no root, no real btrfs, no network)

---

## Phase 3 — Real Testing (manual)

After CI green, activate monitoring on real system.

### 3.1 — Consolidate test runners

Reduce from 8 runners to 3:

- [x] Create `bin/test-real.sh` (root guard + settings.conf guard + local + acceptance-real)
- [x] Update `bin/test-ci.sh` to include acceptance-safe (was only unit + integration)
- [x] Simplify `bin/test-all.sh` to: `test-ci.sh` + `test-real.sh`
- [x] Remove redundant runners: `test-unit.sh`, `test-integration.sh`, `test-acceptance-safe.sh`, `test-acceptance-real.sh`, `test-local.sh`

Final structure:
| Runner | CI-safe | Requires |
|--------|:---:|---|
| `test-ci.sh` | ✅ | Nothing (fixtures only) |
| `test-real.sh` | ❌ | root + test/settings.conf + btrfs |
| `test-all.sh` | ❌ | root + test/settings.conf + btrfs |

### 3.2 — Isolate install tests (SYSTEMD_DIR override)

The install scenario (133) currently installs to real `/etc/systemd/system/`.
This is unsafe for automated testing on a desktop machine.

Strategy: split into "install logic works" (automated) vs "my system is healthy" (manual).

- [x] Modify `scenario133` to use `SYSTEMD_DIR=/tmp/systemd-test-$$`:
  - Validates files are correctly copied
  - Validates install script exits 0
  - Does NOT touch real systemd
  - Skip `systemctl` commands when SYSTEMD_DIR is not `/etc/systemd/system`
- [x] Modify `scenario134` (monitor-after-bootstrap) — already uses mktemp, safe as-is
- [x] Create `bin/verify-install.sh` — post-install health check (read-only, manual):
  - Checks timer exists and is enabled
  - Checks timer has fired recently
  - Checks reports/state directories exist
  - Exit 0 = healthy, Exit 1 = problem found
- [x] Create `bin/verify-bootstrap.sh` — post-bootstrap health check (read-only, manual):
  - Checks state directory has .last files for each family
  - Checks reports directory has at least one report per family
  - Checks no empty reports

### 3.3 — Manual validation

- [ ] Create `etc/btrfs-churn-mon.conf` from example
- [ ] Run `sudo bash bin/test-real.sh`
- [ ] Run `sudo bin/bootstrap.sh` against real snapshots
- [ ] Run `sudo bin/monitor-run.sh home`
- [ ] Install timer (`sudo bin/install-systemd.sh --install`)
- [ ] Run `bin/verify-install.sh` to confirm health
- [ ] Validate aggregate report (`bin/generate-mon-report.sh --stdout`)

---

## Phase 4 — Refactoring

Post-stabilization improvements. Each item is independent.

### 4.1 — Replace AWK with Python

- [ ] Create `lib/parse_churn.py` (equivalent to `parse-churn.awk`)
- [ ] Add pytest tests for the new parser
- [ ] Update `analyse-churn.sh` to call Python instead of AWK
- [ ] Remove `lib/parse-churn.awk`
- [ ] Benefit: single language for data processing, easier to extend

### 4.2 — Migrate Python tests to pytest

- [ ] Create `tests/` directory (pytest convention)
- [ ] Migrate scenario120-127 (generate-mon-report tests) to pytest
- [ ] Test Python functions directly (not just CLI invocation)
- [ ] Add pytest for `build-report.py` internals (load_detail, build_tree, expand)
- [ ] Keep bash tests for script-level integration
- [ ] Add `pytest.ini` or `pyproject.toml` with test config

### 4.3 — Config centralization

- [ ] Fix `monitor-run.sh`: move `source load-config.rc` before REPORTROOT usage
- [ ] Single source of truth for all defaults
- [ ] Document config precedence: ENV > conf file > defaults

### 4.4 — Code style

- [ ] ShellCheck clean on all scripts
- [ ] PEP8/ruff on Python files
- [ ] Consistent quoting in bash (double-quote all variables)

### 4.5 — Migrate to bats-core

- [ ] Install bats-core (git submodule in `test/bats-core/` or system package)
- [ ] Create `test/bats/` directory for new bats tests
- [ ] Write first bats tests for new Python parser (Phase 4.1)
- [ ] Gradually migrate existing scenarios to bats `@test` format
- [ ] Leverage `setup_file` / `teardown_file` for tmpdir management
- [ ] Use `skip` for root/btrfs guards (replaces `exit 0` pattern)
- [ ] Add `--jobs` for parallel execution in CI
- [ ] When 100% migrated, remove `test/lib/assert.sh`
- [ ] TAP output for CI integration (GitHub Actions)

Rationale: bats-core is the de facto standard for bash testing (10+ years, 5k+ stars).
Migration is gradual — old assert.sh tests stay until individually rewritten.

---

## Phase 5 — Features (post-refactor)

| Feature | Priority | Notes |
|---------|----------|-------|
| Retention/rotation | High | Reports grow indefinitely — needs `--keep-days N` |
| GitHub Actions CI | Medium | After tests are stable |
| Health check command | Low | Verify timer/state/reports |
| Trend analysis / ASCII graphs | Low | Nice to have |
| Path history | Low | Analyse single path over time |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-07-17 | Replace ROADMAP.md with ENGINEERING_PLAN.md | Single doc for both vision and execution |
| 2025-07-17 | Keep bash tests for script integration | pytest adds no value for subprocess-level tests |
| 2025-07-17 | pytest for Python logic only | Test functions directly, better assertions |
| 2025-07-17 | Replace AWK with Python | Unify stack, easier maintenance |
| 2025-07-17 | Privileged tests in separate dir | Prevent accidental root execution in CI |
| 2025-07-17 | Adopt bats-core (gradual migration) | De facto standard, TAP output, setup/teardown, skip, parallel |
| 2025-07-17 | SYSTEMD_DIR override for install tests | Test install logic without touching real systemd; verify-* scripts for post-install health check |

---

## Guiding Principles

- MVP first — working code over architecture discussion
- Tests are the spec — failing test > design debate
- Security before features — audit before activating timer
- Gradual migration — no big-bang rewrites

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

- [ ] Run full suite, map failures
- [ ] Fix broken tests
- [ ] Reorganize misplaced tests:
  - Unit tests that need filesystem/tmpdir tricks → keep (they use mktemp, that's fine)
  - Tests that need real btrfs/root → move to `test/privileged/` with runner `bin/test-privileged.sh`
- [ ] Mark privileged tests clearly (require sudo)
- [ ] Improve `test/lib/assert.sh`:
  - [ ] Add `assert_exit_code` (run command, check rc without `set +e` dance)
  - [ ] Add `assert_file_contains_lines` (ordered multi-line check)
  - [ ] Add test summary at end (TOTAL / PASS / FAIL count)
  - [ ] Consider: trap-based cleanup (auto rm tmpdir on exit)
- [ ] Verify all unit tests are truly CI-safe (no root, no real btrfs, no network)

---

## Phase 3 — Real Testing (manual)

After CI green, activate monitoring on real system.

- [ ] Run `bin/bootstrap.sh` against real snapshots
- [ ] Run `bin/monitor-run.sh` for one family
- [ ] Install timer (`install-systemd.sh --install`)
- [ ] Verify timer fires and produces reports
- [ ] Validate aggregate report (`generate-mon-report.sh --stdout`)

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

### 4.5 — Bash test lib improvement

- [ ] Evaluate adopting bats-core (Bash Automated Testing System) vs improving assert.sh
- [ ] If staying with assert.sh: add structured output (TAP format or similar)
- [ ] Add setup/teardown helpers (tmpdir auto-management)
- [ ] Document test writing conventions

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

---

## Guiding Principles

- MVP first — working code over architecture discussion
- Tests are the spec — failing test > design debate
- Security before features — audit before activating timer
- Gradual migration — no big-bang rewrites

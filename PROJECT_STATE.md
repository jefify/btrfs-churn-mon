# PROJECT_STATE.md

## Project

btrfs-churn-mon

Analyze Btrfs snapshot churn and identify directories/files responsible for snapshot growth.

---

## Current Status

State: Active Development

Development Mode: MVP-first

Primary Workflow:

1. Implement
2. Run tests
3. Fix failures
4. Refactor later

Architecture discussion is secondary to producing a runnable version.

---

## Repository Layout

bin/
user-facing commands

lib/
internal implementation

systemd/
service/timer units

test/
unit/
integration/
acceptance/
safe/
real/
local/

---

## Main Commands

analyse-churn.sh

analyse-all-pairs.sh

bootstrap.sh

monitor-run.sh

generate-mon-report.sh

install-systemd.sh

---

## Monitoring

State stored under:

PREFIX/state

Reports stored under:

PREFIX/reports

Current monitoring model:

bootstrap.sh
-> historical analysis

monitor-run.sh
-> future analysis

install-systemd.sh
-> systemd deployment

---

## Testing Strategy

### Unit

No Btrfs required.

Expected CI-safe.

Examples:

011
012
013
014
016
017

090
091
093
094
095

120-127

205

---

### Integration

Uses fake snapshots and temporary directories.

Examples:

010
015
092
099

100
101
102
104
105

110
111

---

### Local

Depends on real snapshot environment.

Ignored by CI.

Examples:

001
003
007
103

---

### Acceptance Safe

No system modification.

130
131
132

---

### Acceptance Real

Touches systemd and/or real installation.

133
134

---

## Known Design Decisions

### Full Script Preference

When modifying files:

Prefer complete file output.

Avoid diffs unless explicitly requested.

---

### Test Driven Context

Tests are considered the authoritative project description.

A failing test is preferred over architectural discussion.

---

### MVP MODE

When MVP MODE is active:

Priority order:

1. Runnable implementation
2. Tests
3. User validation
4. Architecture discussion

---

## Future Work

* Config centralization
* GitHub Actions
* Aggregate reporting improvements
* Path history analysis
* Trend visualization
* Exclude management
* Time-window reporting

---

## Current Goal

Reach:

git clone

bash bin/test-ci.sh

FAILS=0

on a clean Linux machine.

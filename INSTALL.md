# Installation

## Requirements

Required:

- Linux
- Btrfs
- Python 3
- awk
- systemd (optional)

Recommended:

- btrbk
- jq

---

## Clone

```bash
git clone <repo-url>

cd btrfs-churn-mon
````

---

## Verify

Run unit tests:

```bash
./bin/test-unit.sh
```

Run integration tests:

```bash
./bin/test-integration.sh
```

Expected:

```text
FAILS=0
```

---

## Bootstrap Existing Snapshots

Analyze all existing snapshot pairs:

```bash
./bin/bootstrap.sh
```

Expected output:

```text
reports/
state/
```

---

## Generate Reports

Markdown:

```bash
./bin/generate-mon-report.sh --stdout
```

JSON:

```bash
./bin/generate-mon-report.sh --json
```

---

## Install Monitoring

Preview:

```bash
./bin/install-systemd.sh --stdout
```

Dry run:

```bash
./bin/install-systemd.sh --dry-run
```

Install:

```bash
sudo ./bin/install-systemd.sh --install
```

Verify:

```bash
systemctl status \
    btrfs-churn-mon.timer
```

---

## Directory Structure

```text
reports/
    generated reports

state/
    monitoring state

systemd/
    unit files
```

---

## Test Categories

### Unit

No Btrfs required.

```bash
./bin/test-unit.sh
```

---

### Integration

Uses temporary directories and fake data.

```bash
./bin/test-integration.sh
```

---

### Acceptance Safe

Does not modify the system.

```bash
./bin/test-acceptance-safe.sh
```

---

### Acceptance Real

May modify the system.

```bash
./bin/test-acceptance-real.sh
```

---

### Local

Uses real snapshot environments.

These tests are intentionally excluded from CI.


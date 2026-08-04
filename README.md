# btrfs-churn-mon

Analyze Btrfs snapshot churn and identify which files and directories are responsible for snapshot growth.

The project helps answer:

- Why are my snapshots growing?
- Which files change the most?
- Which paths generate the most churn?
- What changed between snapshots?

---

## Features

- Analyze a single snapshot pair
- Analyze all snapshot pairs
- Bootstrap historical reports
- Continuous monitoring with systemd timer
- Aggregate reporting
- JSON output
- Markdown reporting
- Exclude patterns
- Time-range filtering

---

## Quick Start

Bootstrap all existing snapshots:

```bash
./bin/bootstrap.sh
````

Generate aggregate report:

```bash
./bin/generate-mon-report.sh --stdout
```

Generate JSON:

```bash
./bin/generate-mon-report.sh --json
```

Recent reports only:

```bash
./bin/generate-mon-report.sh \
    --limit 7d \
    --stdout
```

---

## Project Layout

```text
bin/
    user-facing commands

lib/
    internal implementation

systemd/
    service and timer

test/
    unit, integration, acceptance (legacy bash tests)

tests/
    python/     (pytest)
```

---

## Test Suites

Run CI-safe tests (no root, no btrfs):

```bash
./bin/test-ci.sh
```

Run privileged tests (root + real btrfs):

```bash
sudo ./bin/test-real.sh
```

Run everything:

```bash
sudo ./bin/test-all.sh
```

Run Python tests:

```bash
python3 -m pytest
```

---

## Bootstrap

Generate reports for all existing snapshots:

```bash
./bin/bootstrap.sh
```

This creates:

```text
reports/
state/
```

and initializes monitoring state.

---

## Monitoring

Install systemd timer:

```bash
sudo ./bin/install-systemd.sh --install
```

View installation plan:

```bash
./bin/install-systemd.sh --stdout
```

Dry run:

```bash
./bin/install-systemd.sh --dry-run
```

---

## Aggregate Reports

Markdown:

```bash
./bin/generate-mon-report.sh --stdout
```

JSON:

```bash
./bin/generate-mon-report.sh --json
```

Custom output directory:

```bash
./bin/generate-mon-report.sh \
    --out-dir /tmp/report
```

Exclude patterns:

```bash
./bin/generate-mon-report.sh \
    --exclude excludes.txt
```

Recent reports only:

```bash
./bin/generate-mon-report.sh \
    --limit 24h
```

---

## Documentation

- [Installation](docs/INSTALL.md) — requirements, setup, verification
- [Engineering Plan](docs/ENGINEERING_PLAN.md) — development roadmap and decisions

---

## License

MIT


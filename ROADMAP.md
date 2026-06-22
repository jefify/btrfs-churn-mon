# btrfs-churn-mon Roadmap

## Current Status (v0.1.0)

Completed:

* Snapshot pair discovery
* Btrfs send-stream analysis
* Churn report generation
* Bootstrap workflow
* Monitoring workflow
* Systemd integration
* Aggregate report generation
* Unit / Integration / Local / Acceptance test separation
* CI-safe test suite
* Public GitHub repository
* Initial documentation

Repository state:

* test-ci.sh = PASS
* Integration tests do not require real snapshots
* Real snapshot tests moved to test/local
* Acceptance tests separated into safe/real

---

# v0.2 - Better Analysis

Goal:

Make reports more useful for finding churn sources.

## Features

### Path Exclusion

Support:

```bash
generate-mon-report.sh \
    --exclude exclude.txt
```

Patterns similar to:

```text
.cache/
node_modules/
.snapshots/
```

---

### Time Window Filtering

Support:

```bash
generate-mon-report.sh \
    --limit 24h

generate-mon-report.sh \
    --limit 7d

generate-mon-report.sh \
    --limit 4w
```

Show only recent churn activity.

---

### Report Output Improvements

Support:

```bash
--stdout

--out-file report.md

--json
```

Consistent behavior across commands.

---

### Historical Aggregation

Generate:

```text
Top paths by total churn
Top paths by frequency
Top paths by growth trend
```

Across many reports.

---

# v0.3 - Trend Analysis

Goal:

Identify churn trends over time.

## Features

### Churn Timeline

Example:

```text
Path                    Churn

~/.cache                ██████████
~/.local/share          ██████
~/Downloads             ██
```

---

### ASCII Graphs

Example:

```text
2026-06-01  ##
2026-06-02  #####
2026-06-03  #########
2026-06-04  ###
```

Terminal friendly.

---

### Path History

Example:

```bash
analyse-path-history.sh \
    ~/.cache
```

Show churn history for a specific path.

---

# v0.4 - Operational Mode

Goal:

Run continuously with minimal maintenance.

## Features

### Retention

Automatically clean old reports.

Example:

```bash
--keep-days 30
```

---

### Report Rotation

Prevent report directory growth.

---

### Health Check

Example:

```bash
btrfs-churn-mon health
```

Verify:

* timer installed
* service installed
* state files valid
* reports generated recently

---

# v0.5 - GitHub Automation

Goal:

Make project easier for contributors.

## Features

### GitHub Actions

Run:

```bash
bin/test-ci.sh
```

Automatically.

---

### ShellCheck

Static analysis.

---

### Markdown Lint

Documentation validation.

---

### Release Workflow

Automatically publish tagged releases.

---

# Future Ideas

Not committed yet.

## Interactive TUI

Browse reports from terminal.

---

## HTML Dashboard

Generate static dashboard.

---

## Path Recommendation Engine

Suggest:

```text
Move to separate subvolume
Exclude from snapshots
High churn detected
```

---

## Multi-host Comparison

Compare churn across systems.

---

# Guiding Principle

MVP first.

Working code and tests are preferred over architecture discussions.

Feature flow:

Idea
→ MVP
→ Test
→ Fix
→ Release
→ Improve

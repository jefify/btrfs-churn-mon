"""Multi-pair aggregate churn report.

Aggregates all detail.tsv files across families and snapshot pairs.
"""

import fnmatch
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .report import human


def load_excludes(path: Optional[Path]) -> list:
    """Load exclude patterns from file.

    Args:
        path: Path to excludes file, or None.

    Returns:
        List of pattern strings (comments and empty lines stripped).
    """
    if path is None:
        return []
    if not Path(path).is_file():
        return []

    patterns = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def excluded(path: str, patterns: list) -> bool:
    """Check if a path matches any exclude pattern.

    Matching rules:
    - fnmatch (glob-style)
    - prefix match (path starts with pattern)
    - suffix match (path ends with /pattern)
    """
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        if path.startswith(pat.rstrip("/")):
            return True
        if path.endswith("/" + pat.rstrip("/")):
            return True
    return False


def parse_limit(spec: Optional[str]) -> Optional[float]:
    """Parse time limit string into cutoff timestamp.

    Args:
        spec: String like '24h', '7d', '4w' or None.

    Returns:
        Cutoff timestamp (epoch) or None.

    Raises:
        SystemExit: If spec is invalid.
    """
    if not spec:
        return None

    m = re.match(r"^(\d+)([hdw])$", spec)
    if not m:
        raise SystemExit(f"invalid limit: {spec}")

    n = int(m.group(1))
    u = m.group(2)
    seconds = {"h": 3600, "d": 86400, "w": 86400 * 7}[u]

    return time.time() - n * seconds


def _report_timestamp(path: Path) -> float:
    """Extract timestamp from snapshot path name."""
    m = re.search(r"(\d{8}T\d{6})", str(path))
    if not m:
        return 0
    return time.mktime(time.strptime(m.group(1), "%Y%m%dT%H%M%S"))


def generate_aggregate(
    reports_dir: Path,
    exclude_patterns: Optional[list] = None,
    limit: Optional[str] = None,
    top_n: int = 50,
) -> tuple:
    """Generate aggregate report from all detail.tsv files.

    Args:
        reports_dir: Root directory containing family/snapshot/detail.tsv
        exclude_patterns: List of patterns to exclude
        limit: Time limit string (e.g. '7d')
        top_n: Number of top entries to include

    Returns:
        Tuple of (markdown_string, json_data_dict)
    """
    if exclude_patterns is None:
        exclude_patterns = []

    cutoff = parse_limit(limit)

    bytes_by_path = defaultdict(int)
    count_by_path = defaultdict(int)
    reports = 0

    for detail in reports_dir.glob("*/*/detail.tsv"):
        if cutoff:
            ts = _report_timestamp(detail)
            if ts < cutoff:
                continue

        reports += 1

        for line in detail.read_text(encoding="utf-8").splitlines():
            line = line.rstrip()
            if not line or line.startswith("BYTES"):
                continue

            try:
                size_str, path = line.split("\t", 1)
            except ValueError:
                continue

            if excluded(path, exclude_patterns):
                continue

            size = int(size_str)
            bytes_by_path[path] += size
            count_by_path[path] += 1

    top_bytes = sorted(bytes_by_path.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top_freq = sorted(count_by_path.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Build markdown
    md = []
    md.append("# Aggregate Churn Report\n")
    md.append(f"\nReports analysed: {reports}\n")
    md.append("\n## Top By Bytes\n\n")
    for path, size in top_bytes:
        md.append(f"- {human(size)} {path}\n")
    md.append("\n## Top By Frequency\n\n")
    for path, count in top_freq:
        md.append(f"- {count} {path}\n")

    markdown = "".join(md)

    json_data = {
        "reports": reports,
        "top_by_bytes": [{"path": p, "bytes": b} for p, b in top_bytes],
        "top_by_frequency": [{"path": p, "count": c} for p, c in top_freq],
    }

    return (markdown, json_data)

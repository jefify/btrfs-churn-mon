"""Per-pair churn report generation.

Generates markdown + JSON report from a detail.tsv file produced by the parser.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

TOP_N = 20
DEFAULT_MIN_PERCENT = 5.0
DEFAULT_MIN_SIZE_MIB = 30.0


def human(n: float) -> str:
    """Convert bytes to human-readable string."""
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    n = float(n)
    for unit in units:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def load_detail(path: Path) -> list:
    """Load detail.tsv file into list of (bytes, path) tuples.

    Skips header (BYTES\\tPATH), empty lines, and malformed lines.
    """
    rows = []
    if not path.is_file():
        return rows

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        bytes_str, file_path = parts
        if bytes_str == "BYTES":
            continue
        try:
            size = int(bytes_str)
        except ValueError:
            continue
        rows.append((size, file_path))

    return rows


def build_tree(rows: list) -> dict:
    """Build hierarchical byte aggregation tree.

    Each path component accumulates bytes from its children.
    """
    tree = defaultdict(int)
    for size, path in rows:
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            node = "/".join(parts[:depth])
            tree[node] += size
    return dict(tree)


def _children(tree: dict, parent: str) -> list:
    """Get direct children of a node in the tree."""
    prefix = parent + "/"
    parent_depth = parent.count("/")
    result = []
    for path, size in tree.items():
        if not path.startswith(prefix):
            continue
        if path.count("/") != parent_depth + 1:
            continue
        result.append((size, path))
    result.sort(reverse=True)
    return result


def _should_show(size: int, total: int, min_percent: float, min_bytes: int) -> bool:
    if size >= min_bytes:
        return True
    if total > 0 and (size / total * 100) >= min_percent:
        return True
    return False


def _expand(tree, node, total, min_percent, min_bytes, lines, indent=0):
    size = tree[node]
    pct = size / total * 100 if total else 0
    lines.append(f'{"  " * indent}- {node} ({human(size)}, {pct:.1f}%)')

    for child_size, child_path in _children(tree, node):
        if not _should_show(child_size, total, min_percent, min_bytes):
            continue
        _expand(tree, child_path, total, min_percent, min_bytes, lines, indent + 1)


def generate_report(
    detail_path: Path,
    min_percent: float = DEFAULT_MIN_PERCENT,
    min_size_mib: float = DEFAULT_MIN_SIZE_MIB,
) -> Optional[tuple]:
    """Generate markdown + JSON report from a detail.tsv file.

    Args:
        detail_path: Path to detail.tsv
        min_percent: Minimum percentage to show in smart expansion
        min_size_mib: Minimum size in MiB to show in smart expansion

    Returns:
        Tuple of (markdown_string, json_data_dict) or None if no data.
    """
    rows = load_detail(detail_path)
    if not rows:
        return None

    total = sum(x[0] for x in rows)
    tree = build_tree(rows)
    min_bytes = int(min_size_mib * 1024 * 1024)

    # Build markdown
    md = []
    md.append("# Btrfs Churn Report")
    md.append("")
    md.append("## Total Churn")
    md.append("")
    md.append(human(total))
    md.append("")
    md.append("## Top Files")
    md.append("")

    top_files = sorted(rows, reverse=True)[:TOP_N]
    for size, path in top_files:
        pct = size / total * 100
        md.append(f"- {path} ({human(size)}, {pct:.1f}%)")

    md.append("")
    md.append("## Smart Expansion")
    md.append("")

    # Find roots (paths without /)
    roots = [(size, path) for path, size in tree.items() if "/" not in path]
    roots.sort(reverse=True)

    for size, root in roots:
        if not _should_show(size, total, min_percent, min_bytes):
            continue
        _expand(tree, root, total, min_percent, min_bytes, md)
        md.append("")

    markdown = "\n".join(md)

    json_data = {
        "total_bytes": total,
        "top_files": top_files,
    }

    return (markdown, json_data)

#!/usr/bin/env python3
"""Parse btrfs receive --dump output and aggregate churn per path.

Replaces lib/parse-churn.awk. Drop-in CLI replacement:
    python3 lib/parse_churn.py DUMPFILE
    cat DUMPFILE | python3 lib/parse_churn.py -

Library usage:
    from parse_churn import parse_line, aggregate, format_output
"""

import re
import sys
from collections import defaultdict
from typing import Optional, Tuple

# Match len=DIGITS anywhere in the line
_LEN_RE = re.compile(r"len=(\d+)")

# Operations we capture
_OPS = frozenset(("write", "clone"))


def parse_line(line: str) -> Optional[Tuple[str, str, int]]:
    """Parse a single dump line.

    Returns (operation, path, bytes) or None if line is not relevant.
    """
    if not line:
        return None

    parts = line.split()
    if len(parts) < 2:
        return None

    op = parts[0]
    if op not in _OPS:
        return None

    path = parts[1]

    # Strip ./ prefix
    if path.startswith("./"):
        path = path[2:]

    # Extract len=N
    m = _LEN_RE.search(line)
    if not m:
        return None

    bytes_val = int(m.group(1))
    return (op, path, bytes_val)


def aggregate(lines) -> dict:
    """Aggregate bytes per path from an iterable of dump lines.

    Args:
        lines: iterable of strings (file lines or list)

    Returns:
        dict mapping path -> total_bytes
    """
    churn = defaultdict(int)

    for line in lines:
        if isinstance(line, str):
            line = line.rstrip("\n")
        result = parse_line(line)
        if result is not None:
            _, path, bytes_val = result
            churn[path] += bytes_val

    return dict(churn)


def format_output(data: dict) -> str:
    """Format aggregated data as bytes\\tpath lines.

    Args:
        data: dict mapping path -> total_bytes

    Returns:
        String with one line per entry (no trailing newline if empty)
    """
    if not data:
        return ""

    lines = []
    for path, total in data.items():
        lines.append(f"{total}\t{path}")

    return "\n".join(lines) + "\n"


def main():
    """CLI entry point — drop-in replacement for parse-churn.awk."""
    if len(sys.argv) < 2:
        print("Usage: parse_churn.py DUMPFILE", file=sys.stderr)
        print("       parse_churn.py -  (read from stdin)", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1]

    if source == "-":
        lines = sys.stdin
    else:
        lines = open(source, "r", encoding="utf-8")

    try:
        data = aggregate(lines)
    finally:
        if source != "-":
            lines.close()

    output = format_output(data)
    if output:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()

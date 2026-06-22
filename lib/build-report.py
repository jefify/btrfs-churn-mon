#!/usr/bin/env python3

import argparse
import json

from collections import defaultdict
from pathlib import Path

TOP_N = 20

DEFAULT_MIN_PERCENT = 5.0
DEFAULT_MIN_SIZE_MIB = 30.0


def human(n):

    units = [
        "B",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
    ]

    n = float(n)

    for unit in units:

        if n < 1024:
            return f"{n:.1f} {unit}"

        n /= 1024

    return f"{n:.1f} PiB"


def load_detail(path):

    rows = []

    with open(path, "r", encoding="utf-8") as f:

        for line in f:

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

            rows.append(
                (
                    size,
                    file_path
                )
            )

    return rows


def build_tree(rows):

    tree = defaultdict(int)

    for size, path in rows:

        parts = path.split("/")

        for depth in range(
            1,
            len(parts) + 1
        ):

            node = "/".join(
                parts[:depth]
            )

            tree[node] += size

    return tree


def children(tree, parent):

    prefix = parent + "/"

    parent_depth = parent.count("/")

    result = []

    for path, size in tree.items():

        if not path.startswith(prefix):
            continue

        if path.count("/") != parent_depth + 1:
            continue

        result.append(
            (
                size,
                path
            )
        )

    result.sort(
        reverse=True
    )

    return result


def should_show(
    size,
    total,
    min_percent,
    min_bytes
):

    if size >= min_bytes:
        return True

    if total > 0:

        pct = (
            size
            / total
            * 100
        )

        if pct >= min_percent:
            return True

    return False


def expand(
    tree,
    node,
    total,
    min_percent,
    min_bytes,
    lines,
    indent=0
):

    size = tree[node]

    pct = (
        size / total * 100
        if total
        else 0
    )

    lines.append(
        f'{"  " * indent}- {node} '
        f'({human(size)}, {pct:.1f}%)'
    )

    for child_size, child_path in children(
        tree,
        node
    ):

        if not should_show(
            child_size,
            total,
            min_percent,
            min_bytes
        ):
            continue

        expand(
            tree,
            child_path,
            total,
            min_percent,
            min_bytes,
            lines,
            indent + 1
        )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "detail_tsv"
    )

    parser.add_argument(
        "--min-percent",
        type=float,
        default=DEFAULT_MIN_PERCENT
    )

    parser.add_argument(
        "--min-size-mib",
        type=float,
        default=DEFAULT_MIN_SIZE_MIB
    )

    args = parser.parse_args()

    detail = Path(
        args.detail_tsv
    )

    rows = load_detail(
        detail
    )

    if not rows:
        raise SystemExit(
            "No rows found"
        )

    total = sum(
        x[0]
        for x in rows
    )

    tree = build_tree(
        rows
    )

    min_bytes = int(
        args.min_size_mib
        * 1024
        * 1024
    )

    report_md = (
        detail.parent
        / "report.md"
    )

    report_json = (
        detail.parent
        / "report.json"
    )

    md = []

    md.append(
        "# Btrfs Churn Report"
    )

    md.append("")

    md.append(
        "## Total Churn"
    )

    md.append("")

    md.append(
        human(total)
    )

    md.append("")

    md.append(
        "## Top Files"
    )

    md.append("")

    top_files = sorted(
        rows,
        reverse=True
    )[:TOP_N]

    for size, path in top_files:

        pct = (
            size
            / total
            * 100
        )

        md.append(
            f"- {path} "
            f"({human(size)}, "
            f"{pct:.1f}%)"
        )

    md.append("")
    md.append(
        "## Smart Expansion"
    )
    md.append("")

    roots = []

    for path, size in tree.items():

        if "/" not in path:

            roots.append(
                (
                    size,
                    path
                )
            )

    roots.sort(
        reverse=True
    )

    for size, root in roots:

        if not should_show(
            size,
            total,
            args.min_percent,
            min_bytes
        ):
            continue

        expand(
            tree,
            root,
            total,
            args.min_percent,
            min_bytes,
            md
        )

        md.append("")

    report_md.write_text(
        "\n".join(md),
        encoding="utf-8"
    )

    report_json.write_text(
        json.dumps(
            {
                "total_bytes": total,
                "top_files": top_files
            },
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        report_md
    )


if __name__ == "__main__":
    main()


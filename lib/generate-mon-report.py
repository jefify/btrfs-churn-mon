#!/usr/bin/env python3

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PREFIX=os.environ.get(
    "PREFIX",
    "/opt/btrfs-churn-mon"
)

REPORTROOT=Path(
    os.environ.get(
        "REPORTROOT",
        f"{PREFIX}/reports"
    )
)


def human(n):

    units=["B","KiB","MiB","GiB","TiB"]

    value=float(n)

    for unit in units:

        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} PiB"


def load_excludes(path):

    if not path:
        return []

    patterns=[]

    with open(path) as fh:

        for line in fh:

            line=line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            patterns.append(line)

    return patterns


def excluded(path, patterns):

    for pat in patterns:

        if fnmatch.fnmatch(path, pat):
            return True

        if path.startswith(
            pat.rstrip("/")
        ):
            return True

        if path.endswith(
            "/" + pat
        ):
            return True

    return False


def parse_limit(spec):

    if not spec:
        return None

    m=re.match(
        r"^(\d+)([hdw])$",
        spec
    )

    if not m:
        raise SystemExit(
            f"invalid limit: {spec}"
        )

    n=int(m.group(1))
    u=m.group(2)

    seconds={
        "h":3600,
        "d":86400,
        "w":86400*7,
    }[u]

    return time.time() - n*seconds


def report_timestamp(path):

    m=re.search(
        r'(\d{8}T\d{6})',
        str(path)
    )

    if not m:
        return 0

    return time.mktime(
        time.strptime(
            m.group(1),
            "%Y%m%dT%H%M%S"
        )
    )


def main():

    ap=argparse.ArgumentParser(
        description="Aggregate Btrfs churn reports"
    )

    ap.add_argument(
        "--exclude"
    )

    ap.add_argument(
        "--limit"
    )

    ap.add_argument(
        "--top",
        type=int,
        default=50
    )

    ap.add_argument(
        "--stdout",
        action="store_true"
    )

    ap.add_argument(
        "--json",
        dest="json_stdout",
        action="store_true"
    )

    ap.add_argument(
        "--out-dir"
    )

    ap.add_argument(
        "--dry-run",
        action="store_true"
    )

    args=ap.parse_args()

    cutoff=parse_limit(
        args.limit
    )

    excludes=load_excludes(
        args.exclude
    )

    bytes_by_path=defaultdict(int)
    count_by_path=defaultdict(int)

    reports=0

    selected=[]

    for detail in REPORTROOT.glob(
        "*/*/detail.tsv"
    ):

        if cutoff:

            ts=report_timestamp(
                detail
            )

            if ts < cutoff:
                continue

        reports += 1

        selected.append(
            str(detail)
        )

        with open(detail) as fh:

            for line in fh:

                line=line.rstrip()

                if not line:
                    continue

                if line.startswith(
                    "BYTES"
                ):
                    continue

                try:

                    size,path=\
                        line.split(
                            "\t",
                            1
                        )

                except ValueError:
                    continue

                if excluded(
                    path,
                    excludes
                ):
                    continue

                size=int(size)

                bytes_by_path[path] += size
                count_by_path[path] += 1

    top_bytes=sorted(
        bytes_by_path.items(),
        key=lambda x:x[1],
        reverse=True
    )[:args.top]

    top_freq=sorted(
        count_by_path.items(),
        key=lambda x:x[1],
        reverse=True
    )[:args.top]

    md=[]

    md.append(
        "# Aggregate Churn Report\n"
    )

    md.append(
        f"\nReports analysed: {reports}\n"
    )

    md.append(
        "\n## Top By Bytes\n\n"
    )

    for path,size in top_bytes:

        md.append(
            f"- {human(size)} {path}\n"
        )

    md.append(
        "\n## Top By Frequency\n\n"
    )

    for path,count in top_freq:

        md.append(
            f"- {count} {path}\n"
        )

    markdown="".join(md)

    json_data={
        "reports":reports,
        "top_by_bytes":[
            {
                "path":p,
                "bytes":b
            }
            for p,b in top_bytes
        ],
        "top_by_frequency":[
            {
                "path":p,
                "count":c
            }
            for p,c in top_freq
        ]
    }

    if args.dry_run:

        print(
            f"Reports analysed: {reports}"
        )

        return

    if args.stdout:

        print(markdown)

        return

    if args.json_stdout:

        print(
            json.dumps(
                json_data,
                indent=2
            )
        )

        return

    outdir=Path(
        args.out_dir
        or REPORTROOT
    )

    outdir.mkdir(
        parents=True,
        exist_ok=True
    )

    aggregate_md=\
        outdir / "aggregate.md"

    aggregate_json=\
        outdir / "aggregate.json"

    with open(
        aggregate_md,
        "w"
    ) as fh:

        fh.write(
            markdown
        )

    with open(
        aggregate_json,
        "w"
    ) as fh:

        json.dump(
            json_data,
            fh,
            indent=2
        )

    print(
        aggregate_md
    )


if __name__ == "__main__":
    main()


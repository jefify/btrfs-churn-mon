"""Btrfs CLI interface — reusable class for btrfs operations.

Isolates all subprocess calls to btrfs CLI tools behind a clean interface.
Privilege escalation (sudo) is configurable and only used for send_dump.
"""

import subprocess
from pathlib import Path


class BtrfsSendError(Exception):
    """Raised when btrfs send fails completely (no output produced)."""


class BtrfsClient:
    """Interface with btrfs CLI tools via subprocess.

    Args:
        use_sudo: If True, prefix btrfs send/receive commands with sudo.
                  Set to False for testing without privileges.
    """

    def __init__(self, use_sudo: bool = True):
        self.use_sudo = use_sudo

    def send_dump(self, old: Path, new: Path) -> str:
        """Generate incremental send dump between two snapshots.

        Runs: btrfs send -p OLD NEW | btrfs receive --dump

        Args:
            old: Path to parent (older) snapshot
            new: Path to child (newer) snapshot

        Returns:
            Dump text content (btrfs receive --dump output)

        Raises:
            BtrfsSendError: If dump is empty (btrfs send failed completely)
        """
        send_cmd = ["btrfs", "send", "-p", str(old), str(new)]
        recv_cmd = ["btrfs", "receive", "--dump"]

        if self.use_sudo:
            send_cmd = ["sudo"] + send_cmd
            recv_cmd = ["sudo"] + recv_cmd

        # Run as a shell pipe: send | receive --dump
        full_cmd = send_cmd + ["|"] + recv_cmd
        shell_cmd = " ".join(full_cmd)

        result = subprocess.run(
            shell_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        output = result.stdout.decode("utf-8", errors="replace")

        if not output.strip():
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise BtrfsSendError(
                f"Dump is empty — btrfs send failed (rc={result.returncode}). "
                f"stderr: {stderr[:200]}"
            )

        return output

    def discover_families(self, snapdir: Path) -> list:
        """Discover snapshot families from naming convention.

        Families are identified by the prefix before the first dot in
        directory names (e.g. 'home' from 'home.20260101T090000-0300').

        Args:
            snapdir: Path to snapshot directory

        Returns:
            Sorted list of unique family names
        """
        families = set()

        if not snapdir.is_dir():
            return []

        for entry in snapdir.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if "." in name:
                family = name.split(".")[0]
                families.add(family)

        return sorted(families)

    def find_snapshots(self, snapdir: Path, family: str) -> list:
        """Find all snapshots of a family, sorted chronologically.

        Args:
            snapdir: Path to snapshot directory
            family: Family name prefix (e.g. 'home')

        Returns:
            Sorted list of Path objects for matching snapshot directories
        """
        snapshots = []

        if not snapdir.is_dir():
            return []

        for entry in snapdir.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.startswith(f"{family}."):
                snapshots.append(entry)

        snapshots.sort(key=lambda p: p.name)
        return snapshots

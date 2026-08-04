"""Tests for src/btrfs.py — BtrfsClient class.

Contract:
- send_dump(old, new) → dump text (uses sudo btrfs send | btrfs receive --dump)
- discover_families(snapdir) → list of family names
- find_snapshots(snapdir, family) → sorted list of snapshot Paths
- Privilege escalation via sudo (configurable, disable for tests)
- Graceful handling of non-zero exit from btrfs send
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.btrfs import BtrfsClient, BtrfsSendError


# --- send_dump tests ---


class TestSendDump:
    """Test send_dump method."""

    def test_send_dump_returns_dump_content(self):
        """Successful btrfs send produces dump text."""
        client = BtrfsClient(use_sudo=False)
        fake_dump = "write ./file1 offset=0 len=1024\nclone ./file2 offset=0 len=2048\n"

        with patch("subprocess.run") as mock_run:
            # btrfs send piped to btrfs receive --dump
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=fake_dump.encode(),
                stderr=b"",
            )
            result = client.send_dump(Path("/snap/old"), Path("/snap/new"))

        assert result == fake_dump

    def test_send_dump_uses_sudo_when_enabled(self):
        """With use_sudo=True, command is prefixed with sudo."""
        client = BtrfsClient(use_sudo=True)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=b"write ./f len=100\n",
                stderr=b"",
            )
            client.send_dump(Path("/snap/old"), Path("/snap/new"))

        cmd = mock_run.call_args[0][0]
        assert "sudo" in cmd

    def test_send_dump_no_sudo_when_disabled(self):
        """With use_sudo=False, no sudo prefix."""
        client = BtrfsClient(use_sudo=False)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=b"write ./f len=100\n",
                stderr=b"",
            )
            client.send_dump(Path("/snap/old"), Path("/snap/new"))

        cmd = mock_run.call_args[0][0]
        assert "sudo" not in cmd

    def test_send_dump_nonzero_but_has_output(self):
        """btrfs send returns non-zero but dump has content — return content with warning."""
        client = BtrfsClient(use_sudo=False)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout=b"write ./f len=100\n",
                stderr=b"some warning",
            )
            result = client.send_dump(Path("/snap/old"), Path("/snap/new"))

        # Should still return content (btrfs send quirk)
        assert result == "write ./f len=100\n"

    def test_send_dump_nonzero_empty_output_raises(self):
        """btrfs send fails completely (no output) — raise BtrfsSendError."""
        client = BtrfsClient(use_sudo=False)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout=b"",
                stderr=b"ERROR: cannot send",
            )
            with pytest.raises(BtrfsSendError, match="empty"):
                client.send_dump(Path("/snap/old"), Path("/snap/new"))

    def test_send_dump_passes_correct_paths(self):
        """Paths are passed correctly to btrfs send -p OLD NEW."""
        client = BtrfsClient(use_sudo=False)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=b"write ./f len=1\n",
                stderr=b"",
            )
            client.send_dump(Path("/mnt/snaps/home.20260101"), Path("/mnt/snaps/home.20260102"))

        cmd = mock_run.call_args[0][0]
        assert "/mnt/snaps/home.20260101" in cmd
        assert "/mnt/snaps/home.20260102" in cmd


# --- discover_families tests ---


class TestDiscoverFamilies:
    """Test family discovery from snapshot directory."""

    def test_discover_families_from_directory(self, tmp_path):
        """Discovers families from snapshot naming convention (family.TIMESTAMP)."""
        (tmp_path / "home.20260101T090000-0300").mkdir()
        (tmp_path / "home.20260102T090000-0300").mkdir()
        (tmp_path / "raiz.20260101T090000-0300").mkdir()
        (tmp_path / "raiz.20260102T090000-0300").mkdir()
        (tmp_path / "random_file.txt").touch()

        client = BtrfsClient(use_sudo=False)
        families = client.discover_families(tmp_path)

        assert sorted(families) == ["home", "raiz"]

    def test_discover_families_empty_dir(self, tmp_path):
        """Empty directory returns empty list."""
        client = BtrfsClient(use_sudo=False)
        families = client.discover_families(tmp_path)
        assert families == []

    def test_discover_families_no_dot_in_names(self, tmp_path):
        """Directories without dots are not families."""
        (tmp_path / "nodot").mkdir()
        (tmp_path / "also_no_dot").mkdir()

        client = BtrfsClient(use_sudo=False)
        families = client.discover_families(tmp_path)
        assert families == []

    def test_discover_families_single_snapshot_still_detected(self, tmp_path):
        """Even a single snapshot detects the family."""
        (tmp_path / "data.20260801T120000-0300").mkdir()

        client = BtrfsClient(use_sudo=False)
        families = client.discover_families(tmp_path)
        assert families == ["data"]


# --- find_snapshots tests ---


class TestFindSnapshots:
    """Test finding snapshots of a family, sorted chronologically."""

    def test_find_snapshots_sorted(self, tmp_path):
        """Returns snapshots sorted by name (chronological)."""
        (tmp_path / "home.20260103T090000-0300").mkdir()
        (tmp_path / "home.20260101T090000-0300").mkdir()
        (tmp_path / "home.20260102T090000-0300").mkdir()
        (tmp_path / "raiz.20260101T090000-0300").mkdir()

        client = BtrfsClient(use_sudo=False)
        snaps = client.find_snapshots(tmp_path, "home")

        assert len(snaps) == 3
        assert snaps[0].name == "home.20260101T090000-0300"
        assert snaps[1].name == "home.20260102T090000-0300"
        assert snaps[2].name == "home.20260103T090000-0300"

    def test_find_snapshots_no_match(self, tmp_path):
        """No snapshots of requested family → empty list."""
        (tmp_path / "raiz.20260101T090000-0300").mkdir()

        client = BtrfsClient(use_sudo=False)
        snaps = client.find_snapshots(tmp_path, "home")
        assert snaps == []

    def test_find_snapshots_ignores_files(self, tmp_path):
        """Files matching pattern are ignored (only dirs)."""
        (tmp_path / "home.20260101T090000-0300").touch()  # file, not dir
        (tmp_path / "home.20260102T090000-0300").mkdir()  # dir

        client = BtrfsClient(use_sudo=False)
        snaps = client.find_snapshots(tmp_path, "home")
        assert len(snaps) == 1
        assert snaps[0].name == "home.20260102T090000-0300"

"""Tests for src/monitor.py — Monitor state machine + orchestration.

Contract:
- find_pairs(family, snapshots, state_dir, catchup_limit) → list[(old, new)]
  Modes: first-run, catchup, up-to-date, recovery
- read_state(state_dir, family) → last_snapshot_name or None
- write_state(state_dir, family, snapshot_name) → None (atomic write)
"""

from pathlib import Path

import pytest

from src.monitor import find_pairs, read_state, write_state


class TestReadState:
    """Test reading state files."""

    def test_read_existing_state(self, tmp_path):
        state_file = tmp_path / "home.last"
        state_file.write_text("home.20260803T090000-0300\n")

        result = read_state(tmp_path, "home")
        assert result == "home.20260803T090000-0300"

    def test_read_missing_state(self, tmp_path):
        result = read_state(tmp_path, "home")
        assert result is None

    def test_read_empty_state(self, tmp_path):
        state_file = tmp_path / "home.last"
        state_file.write_text("")

        result = read_state(tmp_path, "home")
        assert result is None


class TestWriteState:
    """Test atomic state writing."""

    def test_write_creates_file(self, tmp_path):
        write_state(tmp_path, "home", "home.20260804T090000-0300")

        state_file = tmp_path / "home.last"
        assert state_file.exists()
        assert state_file.read_text().strip() == "home.20260804T090000-0300"

    def test_write_overwrites_existing(self, tmp_path):
        (tmp_path / "home.last").write_text("old_value\n")

        write_state(tmp_path, "home", "new_value")
        assert (tmp_path / "home.last").read_text().strip() == "new_value"

    def test_write_permissions(self, tmp_path):
        write_state(tmp_path, "home", "test")

        import stat
        mode = (tmp_path / "home.last").stat().st_mode
        # Should be readable by all (0644)
        assert mode & stat.S_IROTH


class TestFindPairs:
    """Test pair discovery state machine."""

    def _make_snaps(self, tmp_path, names):
        """Helper: create fake snapshot dirs."""
        paths = []
        for name in names:
            p = tmp_path / name
            p.mkdir()
            paths.append(p)
        return sorted(paths, key=lambda p: p.name)

    def test_first_run_returns_last_pair(self, tmp_path):
        """No state file → first-run mode → return last 2 snapshots."""
        snaps = self._make_snaps(tmp_path, [
            "home.20260801T090000-0300",
            "home.20260802T090000-0300",
            "home.20260803T090000-0300",
        ])
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        pairs = find_pairs("home", snaps, state_dir)
        assert len(pairs) == 1
        assert pairs[0] == (snaps[-2], snaps[-1])

    def test_catchup_returns_new_pairs(self, tmp_path):
        """State points to middle → catchup mode → return pairs after state."""
        snaps = self._make_snaps(tmp_path, [
            "home.20260801T090000-0300",
            "home.20260802T090000-0300",
            "home.20260803T090000-0300",
            "home.20260804T090000-0300",
        ])
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "home.last").write_text("home.20260802T090000-0300\n")

        pairs = find_pairs("home", snaps, state_dir)
        assert len(pairs) == 2
        assert pairs[0] == (snaps[1], snaps[2])
        assert pairs[1] == (snaps[2], snaps[3])

    def test_up_to_date_returns_empty(self, tmp_path):
        """State points to last snapshot → up-to-date → empty list."""
        snaps = self._make_snaps(tmp_path, [
            "home.20260801T090000-0300",
            "home.20260802T090000-0300",
        ])
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "home.last").write_text("home.20260802T090000-0300\n")

        pairs = find_pairs("home", snaps, state_dir)
        assert pairs == []

    def test_recovery_when_state_not_found(self, tmp_path):
        """State points to non-existent snapshot → recovery → last pair."""
        snaps = self._make_snaps(tmp_path, [
            "home.20260801T090000-0300",
            "home.20260802T090000-0300",
            "home.20260803T090000-0300",
        ])
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "home.last").write_text("home.20260799T090000-0300\n")  # doesn't exist

        pairs = find_pairs("home", snaps, state_dir)
        assert len(pairs) == 1
        assert pairs[0] == (snaps[-2], snaps[-1])

    def test_less_than_2_snapshots_returns_empty(self, tmp_path):
        """Only 1 snapshot → nothing to compare."""
        snaps = self._make_snaps(tmp_path, ["home.20260801T090000-0300"])
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        pairs = find_pairs("home", snaps, state_dir)
        assert pairs == []

    def test_catchup_limit(self, tmp_path):
        """Catchup limit caps number of returned pairs."""
        names = [f"home.2026080{i}T090000-0300" for i in range(1, 8)]
        snaps = self._make_snaps(tmp_path, names)
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "home.last").write_text("home.20260801T090000-0300\n")

        pairs = find_pairs("home", snaps, state_dir, catchup_limit=3)
        assert len(pairs) == 3

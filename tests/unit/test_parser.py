"""Tests for lib/parse_churn.py — TDD Red Phase.

Contract:
- Parse btrfs receive --dump output
- Capture write and clone operations
- Extract path (strip ./ prefix) and bytes (from len=N)
- Aggregate bytes per path
- Output: bytes\tpath (unsorted)
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from src.parser import parse_line, aggregate, format_output


# --- parse_line tests ---


class TestParseLine:
    """Test individual line parsing."""

    def test_parse_write_line(self):
        line = "write ./home/user/file.txt offset=0 len=1024"
        result = parse_line(line)
        assert result == ("write", "home/user/file.txt", 1024)

    def test_parse_clone_line(self):
        line = "clone ./var/log/syslog offset=0 len=2048 from=./var/log/syslog.1 clone_offset=0 clone_len=2048"
        result = parse_line(line)
        assert result == ("clone", "var/log/syslog", 2048)

    def test_skip_unknown_operation(self):
        lines = [
            "mkfile ./new_file",
            "rename ./old ./new",
            "mkdir ./new_dir",
            "unlink ./deleted",
            "truncate ./file size=0",
            "link ./src ./dst",
        ]
        for line in lines:
            assert parse_line(line) is None

    def test_skip_line_without_len(self):
        line = "write ./file offset=0"
        assert parse_line(line) is None

    def test_strip_dot_slash_prefix(self):
        line = "write ./deep/path/file.bin offset=100 len=500"
        result = parse_line(line)
        assert result[1] == "deep/path/file.bin"

    def test_path_without_dot_slash(self):
        """If path doesn't have ./ prefix, use as-is."""
        line = "write path/no/dot/slash offset=0 len=100"
        result = parse_line(line)
        assert result[1] == "path/no/dot/slash"

    def test_len_anywhere_in_line(self):
        """len= can appear at different positions."""
        line = "write ./file offset=500 len=999 extra=data"
        result = parse_line(line)
        assert result[2] == 999

    def test_empty_line(self):
        assert parse_line("") is None

    def test_comment_or_header_line(self):
        assert parse_line("# comment") is None
        assert parse_line("snapshot ./snap1") is None


# --- aggregate tests ---


class TestAggregate:
    """Test aggregation of parsed lines."""

    def test_aggregate_multiple_writes_same_path(self):
        lines = [
            "write ./user/file1 len=1000",
            "write ./user/file1 len=2000",
            "write ./user/file1 len=500",
        ]
        result = aggregate(lines)
        assert result == {"user/file1": 3500}

    def test_aggregate_mixed_ops(self):
        """write + clone on same path should sum."""
        lines = [
            "write ./data/db.sqlite len=4096",
            "clone ./data/db.sqlite len=2048 from=./data/db.sqlite.old clone_offset=0 clone_len=2048",
        ]
        result = aggregate(lines)
        assert result == {"data/db.sqlite": 6144}

    def test_aggregate_different_paths(self):
        lines = [
            "write ./file_a len=100",
            "write ./file_b len=200",
            "clone ./file_c len=300 from=./x clone_offset=0 clone_len=300",
        ]
        result = aggregate(lines)
        assert result == {"file_a": 100, "file_b": 200, "file_c": 300}

    def test_aggregate_skips_irrelevant_lines(self):
        lines = [
            "mkfile ./ignored",
            "write ./real len=100",
            "rename ./old ./new",
            "clone ./real len=50 from=./x clone_offset=0 clone_len=50",
        ]
        result = aggregate(lines)
        assert result == {"real": 150}

    def test_empty_input(self):
        result = aggregate([])
        assert result == {}

    def test_all_lines_irrelevant(self):
        lines = [
            "mkfile ./a",
            "mkdir ./b",
            "rename ./c ./d",
        ]
        result = aggregate(lines)
        assert result == {}


# --- format_output tests ---


class TestFormatOutput:
    """Test output formatting (bytes\tpath)."""

    def test_format_single_entry(self):
        data = {"home/user/file.txt": 1024}
        output = format_output(data)
        assert output.strip() == "1024\thome/user/file.txt"

    def test_format_multiple_entries(self):
        data = {"file_a": 100, "file_b": 200}
        output = format_output(data)
        lines = output.strip().split("\n")
        assert len(lines) == 2
        # Check that both entries are present (order not guaranteed)
        assert "100\tfile_a" in lines
        assert "200\tfile_b" in lines

    def test_format_empty(self):
        output = format_output({})
        assert output == ""


# --- CLI integration test ---


class TestCLI:
    """Test CLI invocation matches contract."""

    def test_cli_invocation(self):
        """CLI should produce same output as AWK on same input."""
        dump_content = (
            "write ./lin/file1 offset=0 len=1000\n"
            "write ./lin/file2 offset=0 len=2000\n"
            "clone ./lin/file3 offset=0 len=3000 from=./x clone_offset=0 clone_len=3000\n"
            "mkfile ./ignored\n"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".dump", delete=False) as f:
            f.write(dump_content)
            dump_path = f.name

        try:
            result = subprocess.run(
                ["python3", "lib/parse_churn.py", dump_path],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
            assert result.returncode == 0

            lines = [l for l in result.stdout.strip().split("\n") if l]
            parsed = {}
            for line in lines:
                parts = line.split("\t", 1)
                parsed[parts[1]] = int(parts[0])

            assert parsed == {"lin/file1": 1000, "lin/file2": 2000, "lin/file3": 3000}
        finally:
            Path(dump_path).unlink()

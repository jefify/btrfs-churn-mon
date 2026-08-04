"""Tests for src/aggregate.py — Multi-pair aggregate report.

Contract:
- load_excludes(path) → list of patterns
- excluded(path, patterns) → bool
- parse_limit(spec) → cutoff timestamp or None
- generate_aggregate(reports_dir, ...) → (md_str, json_data)
"""

import time
from pathlib import Path

import pytest

from src.aggregate import load_excludes, excluded, parse_limit, generate_aggregate


class TestLoadExcludes:
    """Test exclude pattern loading."""

    def test_load_patterns(self, tmp_path):
        f = tmp_path / "excludes.txt"
        f.write_text(".cache/\nnode_modules/\n.snapshots/\n")

        patterns = load_excludes(f)
        assert patterns == [".cache/", "node_modules/", ".snapshots/"]

    def test_skip_comments_and_empty(self, tmp_path):
        f = tmp_path / "excludes.txt"
        f.write_text("# comment\n\n.cache/\n  \n")

        patterns = load_excludes(f)
        assert patterns == [".cache/"]

    def test_none_path_returns_empty(self):
        patterns = load_excludes(None)
        assert patterns == []


class TestExcluded:
    """Test path exclusion matching."""

    def test_fnmatch(self):
        assert excluded(".cache/something", [".cache/*"]) is True

    def test_prefix_match(self):
        assert excluded(".cache/deep/path", [".cache/"]) is True

    def test_suffix_match(self):
        assert excluded("home/user/.cache", [".cache"]) is True

    def test_no_match(self):
        assert excluded("home/user/docs/file.txt", [".cache/"]) is False

    def test_empty_patterns(self):
        assert excluded("anything", []) is False


class TestParseLimit:
    """Test time limit parsing."""

    def test_hours(self):
        cutoff = parse_limit("24h")
        # Should be approximately 24 hours ago
        expected = time.time() - 24 * 3600
        assert abs(cutoff - expected) < 2

    def test_days(self):
        cutoff = parse_limit("7d")
        expected = time.time() - 7 * 86400
        assert abs(cutoff - expected) < 2

    def test_weeks(self):
        cutoff = parse_limit("4w")
        expected = time.time() - 4 * 7 * 86400
        assert abs(cutoff - expected) < 2

    def test_none_returns_none(self):
        assert parse_limit(None) is None

    def test_invalid_raises(self):
        with pytest.raises(SystemExit):
            parse_limit("invalid")


class TestGenerateAggregate:
    """Test aggregate report generation."""

    def test_aggregates_multiple_reports(self, tmp_path):
        # Create fake report structure: reports_dir/family/snap/detail.tsv
        fam = tmp_path / "raiz" / "raiz.20260801T090000-0300"
        fam.mkdir(parents=True)
        (fam / "detail.tsv").write_text("BYTES\tPATH\n1000\tfile_a\n2000\tfile_b\n")

        fam2 = tmp_path / "raiz" / "raiz.20260802T090000-0300"
        fam2.mkdir(parents=True)
        (fam2 / "detail.tsv").write_text("BYTES\tPATH\n500\tfile_a\n3000\tfile_c\n")

        md, json_data = generate_aggregate(tmp_path)

        assert json_data["reports"] == 2
        # file_a appears in both → aggregated
        bytes_map = {e["path"]: e["bytes"] for e in json_data["top_by_bytes"]}
        assert bytes_map["file_a"] == 1500
        assert bytes_map["file_b"] == 2000
        assert bytes_map["file_c"] == 3000

    def test_empty_reports_dir(self, tmp_path):
        md, json_data = generate_aggregate(tmp_path)
        assert json_data["reports"] == 0
        assert json_data["top_by_bytes"] == []

    def test_exclude_patterns(self, tmp_path):
        fam = tmp_path / "home" / "home.20260801T090000-0300"
        fam.mkdir(parents=True)
        (fam / "detail.tsv").write_text(
            "BYTES\tPATH\n1000\t.cache/junk\n2000\timportant/data\n"
        )

        md, json_data = generate_aggregate(tmp_path, exclude_patterns=[".cache/"])

        bytes_map = {e["path"]: e["bytes"] for e in json_data["top_by_bytes"]}
        assert ".cache/junk" not in bytes_map
        assert "important/data" in bytes_map

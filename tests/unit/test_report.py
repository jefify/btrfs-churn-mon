"""Tests for src/report.py — Per-pair report generation.

Contract:
- load_detail(path) → list[(bytes, path)]
- build_tree(rows) → dict[path, total_bytes] (hierarchical aggregation)
- human(n) → human-readable size string
- generate_report(detail_path, min_percent, min_size_mib) → (md_str, json_data)
"""

import json
from pathlib import Path

import pytest

from src.report import load_detail, build_tree, human, generate_report


class TestHuman:
    """Test human-readable size formatting."""

    def test_bytes(self):
        assert human(500) == "500.0 B"

    def test_kib(self):
        assert human(1024) == "1.0 KiB"

    def test_mib(self):
        assert human(1024 * 1024) == "1.0 MiB"

    def test_gib(self):
        assert human(1024 ** 3) == "1.0 GiB"

    def test_fractional(self):
        assert human(1536) == "1.5 KiB"


class TestLoadDetail:
    """Test loading detail.tsv files."""

    def test_load_valid_tsv(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("BYTES\tPATH\n1000\tfile_a\n2000\tfile_b\n")

        rows = load_detail(tsv)
        assert rows == [(1000, "file_a"), (2000, "file_b")]

    def test_skip_header(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("BYTES\tPATH\n500\tonly_file\n")

        rows = load_detail(tsv)
        assert len(rows) == 1

    def test_skip_empty_lines(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("BYTES\tPATH\n\n100\tfile\n\n")

        rows = load_detail(tsv)
        assert rows == [(100, "file")]

    def test_empty_file(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("")

        rows = load_detail(tsv)
        assert rows == []


class TestBuildTree:
    """Test hierarchical aggregation."""

    def test_single_file(self):
        rows = [(1000, "dir/file.txt")]
        tree = build_tree(rows)
        assert tree["dir/file.txt"] == 1000
        assert tree["dir"] == 1000

    def test_multiple_files_same_dir(self):
        rows = [(100, "dir/a"), (200, "dir/b")]
        tree = build_tree(rows)
        assert tree["dir"] == 300

    def test_nested_paths(self):
        rows = [(500, "a/b/c")]
        tree = build_tree(rows)
        assert tree["a"] == 500
        assert tree["a/b"] == 500
        assert tree["a/b/c"] == 500


class TestGenerateReport:
    """Test full report generation."""

    def test_generates_md_and_json(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("BYTES\tPATH\n3000\tdir/big_file\n1000\tdir/small_file\n")

        md, json_data = generate_report(tsv)

        assert "Total Churn" in md
        assert "Top Files" in md
        assert "dir/big_file" in md
        assert json_data["total_bytes"] == 4000
        assert len(json_data["top_files"]) == 2

    def test_empty_detail_returns_none(self, tmp_path):
        tsv = tmp_path / "detail.tsv"
        tsv.write_text("BYTES\tPATH\n")

        result = generate_report(tsv)
        assert result is None

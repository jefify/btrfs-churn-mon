"""Tests for src/config.py — Configuration loading.

Contract:
- Precedence: ENV > config file > defaults
- Config file format: bash-style (KEY=VALUE, with optional : "${KEY:=default}")
- Defaults: PREFIX=/opt/btrfs-churn-mon, SNAPDIR=/mnt/btrfs_pool/btrbk_snapshots, catchup_limit=100
- Config file path: CONFIG env var > {prefix}/etc/btrfs-churn-mon.conf > defaults
"""

import os
from pathlib import Path

import pytest

from src.config import Config, load_config


class TestDefaults:
    """Test default values when no config file or ENV."""

    def test_default_prefix(self, monkeypatch):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.prefix == Path("/opt/btrfs-churn-mon")

    def test_default_snapdir(self, monkeypatch):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.snapdir == Path("/mnt/btrfs_pool/btrbk_snapshots")

    def test_default_catchup_limit(self, monkeypatch):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.catchup_limit == 100


class TestEnvOverride:
    """Test that environment variables take highest precedence."""

    def test_env_prefix_overrides_default(self, monkeypatch):
        monkeypatch.setenv("PREFIX", "/tmp/custom-prefix")
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.prefix == Path("/tmp/custom-prefix")

    def test_env_snapdir_overrides_default(self, monkeypatch):
        monkeypatch.setenv("SNAPDIR", "/mnt/custom/snaps")
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.snapdir == Path("/mnt/custom/snaps")

    def test_env_overrides_config_file(self, monkeypatch, tmp_path):
        # Config file sets PREFIX=/from/file
        conf = tmp_path / "test.conf"
        conf.write_text("PREFIX=/from/file\nSNAPDIR=/from/file/snaps\n")

        # ENV overrides
        monkeypatch.setenv("PREFIX", "/from/env")
        cfg = load_config(config_file=conf)
        assert cfg.prefix == Path("/from/env")


class TestConfigFile:
    """Test loading from config file."""

    def test_load_simple_key_value(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)

        conf = tmp_path / "test.conf"
        conf.write_text("PREFIX=/custom/path\nSNAPDIR=/custom/snaps\n")

        cfg = load_config(config_file=conf)
        assert cfg.prefix == Path("/custom/path")
        assert cfg.snapdir == Path("/custom/snaps")

    def test_load_bash_style_defaults(self, monkeypatch, tmp_path):
        """Handles bash-style : '${VAR:=default}' lines (extracts value)."""
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)

        conf = tmp_path / "test.conf"
        conf.write_text(': "${PREFIX:=/opt/btrfs-churn-mon}"\n: "${SNAPDIR:=/mnt/pool/snaps}"\n')

        cfg = load_config(config_file=conf)
        assert cfg.prefix == Path("/opt/btrfs-churn-mon")
        assert cfg.snapdir == Path("/mnt/pool/snaps")

    def test_load_catchup_limit(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)

        conf = tmp_path / "test.conf"
        conf.write_text("DEFAULT_CATCHUP_LIMIT=50\n")

        cfg = load_config(config_file=conf)
        assert cfg.catchup_limit == 50

    def test_comments_and_empty_lines_ignored(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)

        conf = tmp_path / "test.conf"
        conf.write_text("# comment\n\n  \nPREFIX=/valid\n")

        cfg = load_config(config_file=conf)
        assert cfg.prefix == Path("/valid")

    def test_missing_config_file_uses_defaults(self, monkeypatch):
        monkeypatch.delenv("PREFIX", raising=False)
        monkeypatch.delenv("SNAPDIR", raising=False)
        monkeypatch.delenv("CONFIG", raising=False)

        cfg = load_config(config_file=Path("/nonexistent/file.conf"))
        assert cfg.prefix == Path("/opt/btrfs-churn-mon")


class TestDerivedPaths:
    """Test computed paths from config."""

    def test_reports_dir(self, monkeypatch):
        monkeypatch.setenv("PREFIX", "/opt/test")
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.reports_dir == Path("/opt/test/reports")

    def test_state_dir(self, monkeypatch):
        monkeypatch.setenv("PREFIX", "/opt/test")
        monkeypatch.delenv("CONFIG", raising=False)
        cfg = load_config(config_file=None)
        assert cfg.state_dir == Path("/opt/test/state")

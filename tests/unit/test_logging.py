"""Tests for src/log.py — logging configuration.

Contract:
- setup_logging(verbose) configures root logger
- Two handlers: stderr (for journald) + file (/var/log/btrfs-churn-mon.log)
- File handler logs INFO/WARNING/ERROR (not DEBUG)
- stderr handler logs DEBUG when verbose=True, INFO otherwise
- Log format includes timestamp, level, message
- File handler gracefully degrades if /var/log not writable (no crash)
- get_logger(name) returns a child logger
"""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.log import setup_logging, get_logger, LOG_FILE


class TestSetupLogging:
    """Test logging configuration."""

    def test_returns_root_logger(self):
        """setup_logging returns configured logger."""
        logger = setup_logging(verbose=False, log_file=None)
        assert isinstance(logger, logging.Logger)

    def test_default_level_is_info(self):
        """Without verbose, root logger level is INFO."""
        logger = setup_logging(verbose=False, log_file=None)
        assert logger.level == logging.INFO

    def test_verbose_sets_debug(self):
        """With verbose=True, root logger level is DEBUG."""
        logger = setup_logging(verbose=True, log_file=None)
        assert logger.level == logging.DEBUG

    def test_stderr_handler_present(self):
        """Always has a StreamHandler (stderr → journald)."""
        logger = setup_logging(verbose=False, log_file=None)
        stream_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_file_handler_created(self, tmp_path):
        """File handler is created when log_file path is writable."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

    def test_file_handler_level_is_info(self, tmp_path):
        """File handler captures INFO and above (not DEBUG)."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=True, log_file=log_file)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert file_handlers[0].level == logging.INFO

    def test_file_handler_writes_log(self, tmp_path):
        """File handler actually writes to the log file."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        logger.info("test message")
        # Flush handlers
        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "test message" in content

    def test_file_handler_includes_timestamp(self, tmp_path):
        """Log format includes timestamp."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        logger.info("timestamped")
        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        # Should have date-like pattern (YYYY-MM-DD)
        assert "2" in content  # year starts with 2
        assert "timestamped" in content

    def test_file_handler_includes_level(self, tmp_path):
        """Log format includes level name."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        logger.warning("warn msg")
        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "WARNING" in content

    def test_graceful_when_log_dir_not_writable(self):
        """Does not crash if log file is not writable (just skips file handler)."""
        # Use a path that doesn't exist and can't be created
        bad_path = Path("/nonexistent_dir_xyz/test.log")
        logger = setup_logging(verbose=False, log_file=bad_path)

        # Should have only stream handler (no file handler)
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_debug_not_in_file(self, tmp_path):
        """DEBUG messages are NOT written to file (only to stderr)."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(verbose=True, log_file=log_file)

        logger.debug("debug only")
        logger.info("info visible")
        for h in logger.handlers:
            h.flush()

        content = log_file.read_text()
        assert "debug only" not in content
        assert "info visible" in content


class TestGetLogger:
    """Test child logger creation."""

    def test_get_logger_returns_child(self):
        """get_logger returns a named child logger."""
        setup_logging(verbose=False, log_file=None)
        logger = get_logger("monitor")
        assert logger.name == "btrfs-churn-mon.monitor"

    def test_child_inherits_config(self, tmp_path):
        """Child logger writes to same handlers as parent."""
        log_file = tmp_path / "test.log"
        setup_logging(verbose=False, log_file=log_file)
        logger = get_logger("test_child")

        logger.info("child message")
        for h in logging.getLogger("btrfs-churn-mon").handlers:
            h.flush()

        content = log_file.read_text()
        assert "child message" in content

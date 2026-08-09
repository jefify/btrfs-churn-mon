"""Logging configuration for btrfs-churn-mon.

Two outputs:
- stderr (captured by journald when running via systemd)
- /var/log/btrfs-churn-mon.log (persistent file, INFO+ only)

Usage:
    from src.log import setup_logging, get_logger
    setup_logging(verbose=True)
    log = get_logger("monitor")
    log.info("Processing pair: %s → %s", old, new)
"""

import logging
import sys
from pathlib import Path
from typing import Optional

LOG_FILE = Path("/var/log/btrfs-churn-mon.log")
LOGGER_NAME = "btrfs-churn-mon"

# Format: 2026-08-09 14:30:00 [INFO] monitor: Processing pair
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    verbose: bool = False,
    log_file: Optional[Path] = LOG_FILE,
) -> logging.Logger:
    """Configure application logging.

    Args:
        verbose: If True, stderr shows DEBUG level. Otherwise INFO.
        log_file: Path to log file (INFO+ only). None to disable file logging.
                  Gracefully skips if path is not writable.

    Returns:
        Configured root logger for the application.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Clear any existing handlers (idempotent)
    logger.handlers.clear()

    # Set root level to lowest needed
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Handler 1: stderr (journald captures this)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Handler 2: file (INFO+ only, persistent)
    if log_file is not None:
        try:
            # Ensure parent directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError):
            # Cannot write to log file — skip silently (stderr still works)
            pass

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a named child logger.

    Args:
        name: Module/component name (e.g. 'monitor', 'install').

    Returns:
        Child logger that inherits parent handlers.
    """
    return logging.getLogger(f"{LOGGER_NAME}.{name}")

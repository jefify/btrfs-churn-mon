"""Configuration loading for btrfs-churn-mon.

Precedence: ENV > config file > defaults.
Config file format: bash-style KEY=VALUE or : "${KEY:=default}".
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Defaults
DEFAULT_PREFIX = "/opt/btrfs-churn-mon"
DEFAULT_SNAPDIR = "/mnt/btrfs_pool/btrbk_snapshots"
DEFAULT_CATCHUP_LIMIT = 100

# Regex for bash-style default: : "${KEY:=VALUE}"
_BASH_DEFAULT_RE = re.compile(r'^:\s*"\$\{(\w+):=(.+?)\}"')
# Regex for simple KEY=VALUE
_SIMPLE_KV_RE = re.compile(r"^(\w+)=(.*)")


@dataclass
class Config:
    """Application configuration."""

    prefix: Path = field(default_factory=lambda: Path(DEFAULT_PREFIX))
    snapdir: Path = field(default_factory=lambda: Path(DEFAULT_SNAPDIR))
    catchup_limit: int = DEFAULT_CATCHUP_LIMIT

    @property
    def reports_dir(self) -> Path:
        return self.prefix / "reports"

    @property
    def state_dir(self) -> Path:
        return self.prefix / "state"


def _parse_config_file(path: Path) -> dict:
    """Parse a bash-style config file into a dict.

    Supports:
    - KEY=VALUE
    - : "${KEY:=DEFAULT}"
    - Comments (#) and empty lines
    """
    values = {}

    if not path.is_file():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        # Skip empty/comments
        if not line or line.startswith("#"):
            continue

        # Try bash-style: : "${KEY:=value}"
        m = _BASH_DEFAULT_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
            values[key] = value
            continue

        # Try simple KEY=VALUE
        m = _SIMPLE_KV_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
            # Strip surrounding quotes if present
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            values[key] = value
            continue

    return values


def load_config(config_file: Optional[Path] = None) -> Config:
    """Load configuration with precedence: ENV > file > defaults.

    Args:
        config_file: Explicit path to config file. If None, uses CONFIG env
                     var or skips file loading.

    Returns:
        Config dataclass with resolved values.
    """
    # Start with defaults
    prefix = DEFAULT_PREFIX
    snapdir = DEFAULT_SNAPDIR
    catchup_limit = DEFAULT_CATCHUP_LIMIT

    # Layer 2: config file
    if config_file is None:
        config_file_path = os.environ.get("CONFIG")
        if config_file_path:
            config_file = Path(config_file_path)

    if config_file is not None:
        file_values = _parse_config_file(config_file)
        if "PREFIX" in file_values:
            prefix = file_values["PREFIX"]
        if "SNAPDIR" in file_values:
            snapdir = file_values["SNAPDIR"]
        if "DEFAULT_CATCHUP_LIMIT" in file_values:
            catchup_limit = int(file_values["DEFAULT_CATCHUP_LIMIT"])

    # Layer 3: ENV (highest precedence)
    env_prefix = os.environ.get("PREFIX")
    if env_prefix:
        prefix = env_prefix

    env_snapdir = os.environ.get("SNAPDIR")
    if env_snapdir:
        snapdir = env_snapdir

    return Config(
        prefix=Path(prefix),
        snapdir=Path(snapdir),
        catchup_limit=catchup_limit,
    )

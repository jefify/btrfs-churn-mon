"""Install module for btrfs-churn-mon.

Handles:
- System user creation (btrfs-churn)
- Sudoers rule installation (privilege escalation for btrfs send)
- Systemd unit installation (service + timer)
- Directory creation with correct ownership
- Health-check (validate installation state)
"""

import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.config import Config


class InstallError(Exception):
    """Raised when an installation step fails."""


class CheckStatus(Enum):
    """Status of a single check component."""

    OK = "ok"
    MISSING = "missing"


@dataclass
class CheckResult:
    """Result of installation health-check."""

    user: CheckStatus = CheckStatus.MISSING
    sudoers: CheckStatus = CheckStatus.MISSING
    systemd_service: CheckStatus = CheckStatus.MISSING
    systemd_timer: CheckStatus = CheckStatus.MISSING
    directories: CheckStatus = CheckStatus.MISSING
    log_file: CheckStatus = CheckStatus.MISSING

    @property
    def ok(self) -> bool:
        """True if all components are OK."""
        return all(
            v == CheckStatus.OK
            for v in (
                self.user,
                self.sudoers,
                self.systemd_service,
                self.systemd_timer,
                self.directories,
                self.log_file,
            )
        )

    def summary(self) -> list:
        """Return list of human-readable issues (empty if all OK)."""
        issues = []
        if self.user != CheckStatus.OK:
            issues.append("User 'btrfs-churn' does not exist")
        if self.sudoers != CheckStatus.OK:
            issues.append("Sudoers file missing")
        if self.systemd_service != CheckStatus.OK:
            issues.append("Systemd service unit missing")
        if self.systemd_timer != CheckStatus.OK:
            issues.append("Systemd timer unit missing")
        if self.directories != CheckStatus.OK:
            issues.append("Data directories (reports/state) missing")
        if self.log_file != CheckStatus.OK:
            issues.append("Log file /var/log/btrfs-churn-mon.log missing")
        return issues


class Installer:
    """Manages installation of btrfs-churn-mon system components.

    Args:
        config: Application config (provides prefix path).
        systemd_dir: Target directory for systemd units.
        sudoers_dir: Target directory for sudoers drop-in.
        user: System user name for the service.
        project_root: Root of the project (where etc/, systemd/ live).
        manage_systemd: If True, run systemctl commands after install.
                        Set to False for non-standard systemd_dir (testing).
    """

    SERVICE_NAME = "btrfs-churn-mon"

    def __init__(
        self,
        config: Config,
        systemd_dir: Path,
        sudoers_dir: Path,
        user: str = "btrfs-churn",
        project_root: Path | None = None,
        manage_systemd: bool = True,
        log_file: Path | None = None,
    ):
        self.config = config
        self.systemd_dir = systemd_dir
        self.sudoers_dir = sudoers_dir
        self.user = user
        self.manage_systemd = manage_systemd
        self.log_file = log_file if log_file is not None else Path("/var/log/btrfs-churn-mon.log")

        if project_root is None:
            # Default: assume src/install.py is at <root>/src/install.py
            project_root = Path(__file__).resolve().parents[1]
        self.project_root = project_root

    def _user_exists(self) -> bool:
        """Check if the service user already exists."""
        result = subprocess.run(
            ["id", "-u", self.user],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0

    def ensure_user(self) -> None:
        """Create system user if it does not exist.

        Uses sudo for privilege escalation (installer may not run as root).

        Raises:
            InstallError: If useradd fails.
        """
        if self._user_exists():
            return  # User already exists, nothing to do

        # Create system user via sudo
        cmd = [
            "sudo", "useradd",
            "--system",
            "--no-create-home",
            "--shell", "/usr/sbin/nologin",
            self.user,
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise InstallError(
                f"useradd failed (rc={result.returncode}): {stderr}"
            )

    def install_sudoers(self) -> None:
        """Install sudoers drop-in file with correct permissions (0440)."""
        src = self.project_root / "install_data" / f"sudoers-{self.SERVICE_NAME}"
        dst = self.sudoers_dir / self.SERVICE_NAME

        shutil.copy2(src, dst)
        dst.chmod(0o440)

    def install_systemd(self) -> None:
        """Install systemd service and timer units.

        Copies .service and .timer files. If manage_systemd is True,
        also runs daemon-reload, enable, and start.
        """
        src_dir = self.project_root / "install_data"

        for unit in (f"{self.SERVICE_NAME}.service", f"{self.SERVICE_NAME}.timer"):
            src = src_dir / unit
            dst = self.systemd_dir / unit
            shutil.copy2(src, dst)

        if not self.manage_systemd:
            return

        # daemon-reload
        subprocess.run(
            ["systemctl", "daemon-reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        # enable timer
        subprocess.run(
            ["systemctl", "enable", f"{self.SERVICE_NAME}.timer"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        # start timer
        subprocess.run(
            ["systemctl", "start", f"{self.SERVICE_NAME}.timer"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def ensure_directories(self) -> None:
        """Create data directories with correct ownership.

        Creates:
            PREFIX/reports
            PREFIX/state
            /var/log/btrfs-churn-mon.log (owned by service user)
        """
        prefix = self.config.prefix
        prefix.mkdir(parents=True, exist_ok=True)

        for subdir in ("reports", "state"):
            path = prefix / subdir
            path.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["chown", f"{self.user}:{self.user}", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        # Log file (needs to be writable by service user)
        if not self.log_file.exists():
            self.log_file.touch()
        subprocess.run(
            ["chown", f"{self.user}:{self.user}", str(self.log_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def check(self) -> CheckResult:
        """Run health-check on installation state.

        Returns:
            CheckResult with per-component status.
        """
        result = CheckResult()

        # Check user
        proc = subprocess.run(
            ["id", "-u", self.user],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode == 0:
            result.user = CheckStatus.OK

        # Check sudoers
        if (self.sudoers_dir / self.SERVICE_NAME).is_file():
            result.sudoers = CheckStatus.OK

        # Check systemd units
        if (self.systemd_dir / f"{self.SERVICE_NAME}.service").is_file():
            result.systemd_service = CheckStatus.OK
        if (self.systemd_dir / f"{self.SERVICE_NAME}.timer").is_file():
            result.systemd_timer = CheckStatus.OK

        # Check directories
        prefix = self.config.prefix
        if (prefix / "reports").is_dir() and (prefix / "state").is_dir():
            result.directories = CheckStatus.OK

        # Check log file
        if self.log_file.exists():
            result.log_file = CheckStatus.OK

        return result

    def install_all(self) -> None:
        """Run full installation (user + sudoers + dirs + systemd).

        Order matters:
        1. User (needed for ownership)
        2. Sudoers (needs user name)
        3. Directories (needs user for chown)
        4. Systemd (service references user and directories)
        """
        self.ensure_user()
        self.install_sudoers()
        self.ensure_directories()
        self.install_systemd()

    def _generate_environment_content(self, families: list) -> str:
        """Generate content for /etc/default/btrfs-churn-mon.

        Args:
            families: List of discovered snapshot families.

        Returns:
            File content string.
        """
        families_str = ",".join(families)
        lines = [
            "# /etc/default/btrfs-churn-mon",
            "# Environment variables for the systemd service.",
            "# Managed by: btrfs-churn-mon install",
            "#",
            f"# Discovered families: {', '.join(families)}",
            "# Comma-separated list. Remove to process ALL discovered families.",
            "#",
            f"SNAPSHOT_FAMILIES={families_str}",
            "",
        ]
        return "\n".join(lines)

    def install_environment_file(
        self,
        target: Path,
        families: list,
        force: bool = False,
    ) -> str:
        """Install /etc/default/btrfs-churn-mon (EnvironmentFile for systemd).

        Logic:
        - If target does not exist → create, return 'created'
        - If target exists with same content → return 'unchanged'
        - If target exists with different content:
          - force=True → overwrite, return 'updated'
          - force=False → do NOT overwrite, return 'conflict'

        Args:
            target: Path to the environment file.
            families: List of discovered snapshot families.
            force: If True, overwrite on conflict.

        Returns:
            Status string: 'created', 'unchanged', 'updated', or 'conflict'.
        """
        new_content = self._generate_environment_content(families)

        if not target.exists():
            target.write_text(new_content, encoding="utf-8")
            return "created"

        existing = target.read_text(encoding="utf-8")
        if existing == new_content:
            return "unchanged"

        # Content differs
        if force:
            target.write_text(new_content, encoding="utf-8")
            return "updated"

        return "conflict"

    def uninstall(
        self,
        purge_data: bool = False,
        keep_user: bool = False,
    ) -> None:
        """Remove installed system components.

        Order (reverse of install):
        1. Stop and disable systemd timer
        2. Remove systemd units + daemon-reload
        3. Remove sudoers
        4. Remove data directories (only if purge_data=True)
        5. Remove user (unless keep_user=True)

        Config files are NEVER removed (preserved always).

        Args:
            purge_data: If True, remove PREFIX/reports and PREFIX/state.
            keep_user: If True, do not delete the service user.
        """
        # 1. Stop and disable systemd
        if self.manage_systemd:
            subprocess.run(
                ["systemctl", "stop", f"{self.SERVICE_NAME}.timer"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(
                ["systemctl", "disable", f"{self.SERVICE_NAME}.timer"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        # 2. Remove systemd units
        for unit in (f"{self.SERVICE_NAME}.service", f"{self.SERVICE_NAME}.timer"):
            unit_path = self.systemd_dir / unit
            if unit_path.is_file():
                unit_path.unlink()

        if self.manage_systemd:
            subprocess.run(
                ["systemctl", "daemon-reload"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        # 3. Remove sudoers
        sudoers_path = self.sudoers_dir / self.SERVICE_NAME
        if sudoers_path.is_file():
            sudoers_path.unlink()

        # 4. Remove data directories (preserves config always)
        if purge_data:
            prefix = self.config.prefix
            for subdir in ("reports", "state"):
                path = prefix / subdir
                if path.is_dir():
                    shutil.rmtree(path)

        # 5. Remove user
        if not keep_user:
            subprocess.run(
                ["sudo", "userdel", self.user],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

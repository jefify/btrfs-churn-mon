"""Tests for src/install.py — Installer class.

Contract:
- Installer(config, systemd_dir, sudoers_dir, user) — parametrized for testing
- ensure_user() → creates system user if not exists (sudo useradd --system --no-create-home)
- install_sudoers() → installs sudoers template to sudoers_dir
- install_systemd() → copies .service/.timer to systemd_dir, daemon-reload, enable, start
- ensure_directories() → creates PREFIX/{reports,state} with correct ownership
- check() → health-check returning CheckResult with per-component status
- uninstall() → stops timer, removes units/sudoers, optionally user/data (preserves config)
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.config import Config
from src.install import (
    CheckResult,
    CheckStatus,
    Installer,
    InstallError,
)


# --- Fixtures ---


@pytest.fixture
def tmp_prefix(tmp_path):
    """Temporary prefix directory (simulates /opt/btrfs-churn-mon)."""
    return tmp_path / "prefix"


@pytest.fixture
def tmp_systemd(tmp_path):
    """Temporary systemd directory."""
    d = tmp_path / "systemd"
    d.mkdir()
    return d


@pytest.fixture
def tmp_sudoers(tmp_path):
    """Temporary sudoers.d directory."""
    d = tmp_path / "sudoers.d"
    d.mkdir()
    return d


@pytest.fixture
def config(tmp_prefix):
    """Config pointing to tmp_prefix."""
    return Config(prefix=tmp_prefix)


@pytest.fixture
def installer(config, tmp_systemd, tmp_sudoers):
    """Installer with all paths pointing to tmp dirs."""
    return Installer(
        config=config,
        systemd_dir=tmp_systemd,
        sudoers_dir=tmp_sudoers,
        user="btrfs-churn",
        project_root=Path(__file__).resolve().parents[2],
    )


# --- ensure_user tests ---


class TestEnsureUser:
    """Test system user creation."""

    def test_creates_user_when_not_exists(self, installer):
        """Calls sudo useradd when user does not exist."""
        with patch("subprocess.run") as mock_run:
            # id command fails → user does not exist
            mock_run.side_effect = [
                subprocess.CompletedProcess([], returncode=1),  # id -u fails
                subprocess.CompletedProcess([], returncode=0),  # useradd succeeds
            ]
            installer.ensure_user()

        calls = mock_run.call_args_list
        assert calls[0][0][0] == ["id", "-u", "btrfs-churn"]
        useradd_cmd = calls[1][0][0]
        assert useradd_cmd[0] == "sudo"
        assert "useradd" in useradd_cmd
        assert "--system" in useradd_cmd
        assert "--no-create-home" in useradd_cmd
        assert "btrfs-churn" in useradd_cmd

    def test_skips_creation_when_user_exists(self, installer):
        """Does NOT call useradd when user already exists."""
        with patch("subprocess.run") as mock_run:
            # id command succeeds → user exists
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.ensure_user()

        # Only one call (id -u), no useradd
        assert mock_run.call_count == 1

    def test_raises_on_useradd_failure(self, installer):
        """Raises InstallError if useradd fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], returncode=1),  # id fails
                subprocess.CompletedProcess(
                    [], returncode=9, stderr=b"user already in group"
                ),  # useradd fails
            ]
            with pytest.raises(InstallError, match="useradd"):
                installer.ensure_user()


# --- install_sudoers tests ---


class TestInstallSudoers:
    """Test sudoers file installation."""

    def test_installs_sudoers_file(self, installer, tmp_sudoers):
        """Copies sudoers template to sudoers_dir with mode 0440."""
        installer.install_sudoers()

        sudoers_file = tmp_sudoers / "btrfs-churn-mon"
        assert sudoers_file.exists()
        content = sudoers_file.read_text()
        assert "btrfs-churn" in content
        assert "NOPASSWD" in content
        assert "btrfs send" in content

    def test_sudoers_file_permissions(self, installer, tmp_sudoers):
        """Sudoers file must have restrictive permissions (0440)."""
        installer.install_sudoers()

        sudoers_file = tmp_sudoers / "btrfs-churn-mon"
        mode = oct(sudoers_file.stat().st_mode & 0o777)
        assert mode == "0o440"

    def test_overwrites_existing_sudoers(self, installer, tmp_sudoers):
        """Overwrites existing sudoers file (idempotent)."""
        existing = tmp_sudoers / "btrfs-churn-mon"
        existing.write_text("old content")

        installer.install_sudoers()

        content = existing.read_text()
        assert "old content" not in content
        assert "NOPASSWD" in content


# --- install_systemd tests ---


class TestInstallSystemd:
    """Test systemd unit installation."""

    def test_copies_service_and_timer(self, installer, tmp_systemd):
        """Copies .service and .timer to systemd_dir."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.install_systemd()

        assert (tmp_systemd / "btrfs-churn-mon.service").exists()
        assert (tmp_systemd / "btrfs-churn-mon.timer").exists()

    def test_service_file_has_correct_content(self, installer, tmp_systemd):
        """Service file content comes from project source with User/Group."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.install_systemd()

        content = (tmp_systemd / "btrfs-churn-mon.service").read_text()
        assert "[Service]" in content
        assert "Type=oneshot" in content
        assert "User=btrfs-churn" in content
        assert "Group=btrfs-churn" in content

    def test_calls_daemon_reload(self, installer, tmp_systemd):
        """Calls systemctl daemon-reload after installing units."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.install_systemd()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        daemon_reload = ["systemctl", "daemon-reload"]
        assert daemon_reload in cmds

    def test_enables_and_starts_timer(self, installer, tmp_systemd):
        """Enables and starts the timer after install."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.install_systemd()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        assert ["systemctl", "enable", "btrfs-churn-mon.timer"] in cmds
        assert ["systemctl", "start", "btrfs-churn-mon.timer"] in cmds

    def test_skips_systemctl_for_non_standard_dir(self, config, tmp_systemd, tmp_sudoers):
        """When systemd_dir is not /etc/systemd/system, skip systemctl calls."""
        inst = Installer(
            config=config,
            systemd_dir=tmp_systemd,
            sudoers_dir=tmp_sudoers,
            user="btrfs-churn",
            project_root=Path(__file__).resolve().parents[2],
            manage_systemd=False,
        )
        with patch("subprocess.run") as mock_run:
            inst.install_systemd()

        # No subprocess calls (no systemctl)
        mock_run.assert_not_called()
        # But files are still copied
        assert (tmp_systemd / "btrfs-churn-mon.service").exists()
        assert (tmp_systemd / "btrfs-churn-mon.timer").exists()


# --- ensure_directories tests ---


class TestEnsureDirectories:
    """Test directory creation with correct ownership."""

    def test_creates_reports_and_state_dirs(self, installer, tmp_prefix):
        """Creates PREFIX/reports and PREFIX/state."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.ensure_directories()

        assert (tmp_prefix / "reports").is_dir()
        assert (tmp_prefix / "state").is_dir()

    def test_calls_chown_on_directories(self, installer, tmp_prefix):
        """Calls chown to set ownership to service user."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.ensure_directories()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        # Should chown both reports and state
        chown_cmds = [c for c in cmds if c[0] == "chown"]
        assert len(chown_cmds) == 2
        for cmd in chown_cmds:
            assert "btrfs-churn" in cmd[1]  # user:user

    def test_creates_prefix_if_not_exists(self, installer, tmp_prefix):
        """Creates prefix directory itself if needed."""
        assert not tmp_prefix.exists()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.ensure_directories()

        assert tmp_prefix.is_dir()

    def test_idempotent_on_existing_dirs(self, installer, tmp_prefix):
        """Does not fail if directories already exist."""
        tmp_prefix.mkdir(parents=True)
        (tmp_prefix / "reports").mkdir()
        (tmp_prefix / "state").mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.ensure_directories()

        assert (tmp_prefix / "reports").is_dir()
        assert (tmp_prefix / "state").is_dir()


# --- check tests ---


class TestCheck:
    """Test health-check (install --check)."""

    def test_all_pass_returns_ok(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """When everything is installed, check returns all OK."""
        # Setup: create expected files/dirs
        tmp_prefix.mkdir(parents=True, exist_ok=True)
        (tmp_prefix / "reports").mkdir()
        (tmp_prefix / "state").mkdir()
        (tmp_sudoers / "btrfs-churn-mon").write_text("sudoers content")
        (tmp_systemd / "btrfs-churn-mon.service").write_text("[Service]")
        (tmp_systemd / "btrfs-churn-mon.timer").write_text("[Timer]")

        with patch("subprocess.run") as mock_run:
            # id -u succeeds (user exists)
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            result = installer.check()

        assert result.ok is True
        assert result.user == CheckStatus.OK
        assert result.sudoers == CheckStatus.OK
        assert result.systemd_service == CheckStatus.OK
        assert result.systemd_timer == CheckStatus.OK
        assert result.directories == CheckStatus.OK

    def test_missing_user_returns_fail(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """When user doesn't exist, check.user is MISSING."""
        tmp_prefix.mkdir(parents=True, exist_ok=True)
        (tmp_prefix / "reports").mkdir()
        (tmp_prefix / "state").mkdir()
        (tmp_sudoers / "btrfs-churn-mon").write_text("sudoers")
        (tmp_systemd / "btrfs-churn-mon.service").write_text("[Service]")
        (tmp_systemd / "btrfs-churn-mon.timer").write_text("[Timer]")

        with patch("subprocess.run") as mock_run:
            # id -u fails (user does not exist)
            mock_run.return_value = subprocess.CompletedProcess([], returncode=1)
            result = installer.check()

        assert result.ok is False
        assert result.user == CheckStatus.MISSING

    def test_missing_sudoers_returns_fail(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """When sudoers file missing, check.sudoers is MISSING."""
        tmp_prefix.mkdir(parents=True, exist_ok=True)
        (tmp_prefix / "reports").mkdir()
        (tmp_prefix / "state").mkdir()
        (tmp_systemd / "btrfs-churn-mon.service").write_text("[Service]")
        (tmp_systemd / "btrfs-churn-mon.timer").write_text("[Timer]")
        # No sudoers file

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            result = installer.check()

        assert result.ok is False
        assert result.sudoers == CheckStatus.MISSING

    def test_missing_directories_returns_fail(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """When reports/state dirs missing, check.directories is MISSING."""
        # prefix exists but no subdirs
        tmp_prefix.mkdir(parents=True, exist_ok=True)
        (tmp_sudoers / "btrfs-churn-mon").write_text("sudoers")
        (tmp_systemd / "btrfs-churn-mon.service").write_text("[Service]")
        (tmp_systemd / "btrfs-churn-mon.timer").write_text("[Timer]")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            result = installer.check()

        assert result.ok is False
        assert result.directories == CheckStatus.MISSING

    def test_check_summary_lists_issues(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """summary() returns human-readable list of issues."""
        # Nothing installed
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=1)
            result = installer.check()

        summary = result.summary()
        assert isinstance(summary, list)
        assert len(summary) > 0
        # Each item is a string describing a failing check
        assert all(isinstance(s, str) for s in summary)


# --- Uninstall tests ---


class TestUninstall:
    """Test uninstall method."""

    def _setup_installed(self, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Helper: simulate a complete installation."""
        tmp_prefix.mkdir(parents=True, exist_ok=True)
        (tmp_prefix / "reports").mkdir()
        (tmp_prefix / "state").mkdir()
        (tmp_prefix / "reports" / "home").mkdir()
        (tmp_prefix / "state" / "home.last").write_text("snap.20260101")
        (tmp_sudoers / "btrfs-churn-mon").write_text("sudoers content")
        (tmp_systemd / "btrfs-churn-mon.service").write_text("[Service]")
        (tmp_systemd / "btrfs-churn-mon.timer").write_text("[Timer]")

    def test_removes_systemd_units(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall removes .service and .timer files."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()

        assert not (tmp_systemd / "btrfs-churn-mon.service").exists()
        assert not (tmp_systemd / "btrfs-churn-mon.timer").exists()

    def test_removes_sudoers(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall removes sudoers file."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()

        assert not (tmp_sudoers / "btrfs-churn-mon").exists()

    def test_preserves_data_by_default(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall preserves reports/ and state/ by default."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()

        assert (tmp_prefix / "reports").is_dir()
        assert (tmp_prefix / "state").is_dir()

    def test_purge_data_removes_reports_and_state(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall with purge_data=True removes reports/ and state/."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall(purge_data=True)

        assert not (tmp_prefix / "reports").exists()
        assert not (tmp_prefix / "state").exists()

    def test_preserves_config_always(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall NEVER removes config files (even with purge_data)."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)
        # Create config files that must survive
        etc_dir = tmp_prefix / "etc"
        etc_dir.mkdir()
        (etc_dir / "btrfs-churn-mon.conf").write_text("PREFIX=/opt/btrfs-churn-mon")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall(purge_data=True)

        assert (etc_dir / "btrfs-churn-mon.conf").exists()

    def test_removes_user_by_default(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall removes the service user by default."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        userdel_cmds = [c for c in cmds if "userdel" in c]
        assert len(userdel_cmds) == 1
        assert "btrfs-churn" in userdel_cmds[0]

    def test_keep_user_preserves_user(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall with keep_user=True does NOT call userdel."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall(keep_user=True)

        cmds = [c[0][0] for c in mock_run.call_args_list]
        userdel_cmds = [c for c in cmds if "userdel" in c]
        assert len(userdel_cmds) == 0

    def test_calls_systemctl_stop_and_disable(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall stops and disables the timer via systemctl."""
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        assert ["systemctl", "stop", "btrfs-churn-mon.timer"] in cmds
        assert ["systemctl", "disable", "btrfs-churn-mon.timer"] in cmds
        assert ["systemctl", "daemon-reload"] in cmds

    def test_skips_systemctl_when_manage_systemd_false(self, config, tmp_systemd, tmp_sudoers, tmp_prefix):
        """When manage_systemd=False, no systemctl calls."""
        inst = Installer(
            config=config,
            systemd_dir=tmp_systemd,
            sudoers_dir=tmp_sudoers,
            user="btrfs-churn",
            project_root=Path(__file__).resolve().parents[2],
            manage_systemd=False,
        )
        self._setup_installed(tmp_prefix, tmp_systemd, tmp_sudoers)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            inst.uninstall()

        # Only userdel call, no systemctl
        cmds = [c[0][0] for c in mock_run.call_args_list]
        systemctl_cmds = [c for c in cmds if c[0] == "systemctl"]
        assert len(systemctl_cmds) == 0

    def test_idempotent_on_already_uninstalled(self, installer, tmp_prefix, tmp_systemd, tmp_sudoers):
        """Uninstall does not fail if components are already removed."""
        # Nothing installed — should not raise
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
            installer.uninstall()



# --- install_environment_file tests ---


class TestInstallEnvironmentFile:
    """Test /etc/default/btrfs-churn-mon management."""

    def test_creates_file_when_not_exists(self, installer, tmp_path):
        """Creates environment file when target does not exist."""
        target = tmp_path / "btrfs-churn-mon"
        result = installer.install_environment_file(target, families=["home"])

        assert target.exists()
        content = target.read_text()
        assert "SNAPSHOT_FAMILIES" in content
        assert result == "created"

    def test_content_has_snapshot_family(self, installer, tmp_path):
        """Generated content includes SNAPSHOT_FAMILIES variable."""
        target = tmp_path / "btrfs-churn-mon"
        installer.install_environment_file(target, families=["home", "raiz"])

        content = target.read_text()
        assert "SNAPSHOT_FAMILIES=home,raiz" in content

    def test_content_has_header_comment(self, installer, tmp_path):
        """Generated content has a descriptive header."""
        target = tmp_path / "btrfs-churn-mon"
        installer.install_environment_file(target, families=["home"])

        content = target.read_text()
        assert "# " in content  # Has comments

    def test_unchanged_returns_unchanged(self, installer, tmp_path):
        """When file exists with same content, returns 'unchanged'."""
        target = tmp_path / "btrfs-churn-mon"
        # First install
        installer.install_environment_file(target, families=["home"])
        # Second install — same content
        result = installer.install_environment_file(target, families=["home"])

        assert result == "unchanged"

    def test_different_content_with_force_overwrites(self, installer, tmp_path):
        """When file differs and force=True, overwrites and returns 'updated'."""
        target = tmp_path / "btrfs-churn-mon"
        target.write_text("SNAPSHOT_FAMILIES=old_value\n")

        result = installer.install_environment_file(
            target, families=["home"], force=True
        )

        assert result == "updated"
        content = target.read_text()
        assert "SNAPSHOT_FAMILIES=home" in content

    def test_different_content_without_force_returns_conflict(self, installer, tmp_path):
        """When file differs and force=False, does NOT overwrite, returns 'conflict'."""
        target = tmp_path / "btrfs-churn-mon"
        target.write_text("SNAPSHOT_FAMILIES=custom_value\n")

        result = installer.install_environment_file(
            target, families=["home"], force=False
        )

        assert result == "conflict"
        # File NOT overwritten
        content = target.read_text()
        assert "custom_value" in content

    def test_multiple_families_documented(self, installer, tmp_path):
        """Available families are listed in comments."""
        target = tmp_path / "btrfs-churn-mon"
        installer.install_environment_file(target, families=["home", "raiz", "data"])

        content = target.read_text()
        # Available families should be mentioned
        assert "home" in content
        assert "raiz" in content
        assert "data" in content

    def test_default_family_is_first(self, installer, tmp_path):
        """The SNAPSHOT_FAMILIES includes all families in order."""
        target = tmp_path / "btrfs-churn-mon"
        installer.install_environment_file(target, families=["raiz", "home"])

        content = target.read_text()
        assert "SNAPSHOT_FAMILIES=raiz,home" in content

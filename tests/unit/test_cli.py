"""Tests for src/cli.py — Typer CLI application.

Contract:
- Entry point calls assert_not_root() before any command (except install)
- Subcommands: monitor, report, analyse, status, bootstrap, install, verify
- --help works for app and each subcommand
- install --check runs health-check (does not modify system)
- Root guard abort is testable via mock
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli import app


runner = CliRunner()


# --- App-level tests ---


class TestAppHelp:
    """Test top-level CLI behavior."""

    def test_help_shows_all_commands(self):
        """--help lists all available subcommands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "monitor" in result.output
        assert "report" in result.output
        assert "analyse" in result.output
        assert "status" in result.output
        assert "bootstrap" in result.output
        assert "install" in result.output
        assert "verify" in result.output

    def test_no_args_shows_help(self):
        """No arguments shows help (not an error)."""
        result = runner.invoke(app, [])
        # Typer shows help with exit code 0 or 2 (click convention)
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or "btrfs-churn-mon" in result.output


# --- Root guard tests ---


class TestRootGuard:
    """Test that commands refuse to run as root."""

    def test_monitor_aborts_as_root(self):
        """monitor command aborts if running as root."""
        with patch("src.cli.assert_not_root") as mock_guard:
            from src import RootGuardError

            mock_guard.side_effect = RootGuardError()
            result = runner.invoke(app, ["monitor"])
        assert result.exit_code != 0

    def test_status_aborts_as_root(self):
        """status command aborts if running as root."""
        with patch("src.cli.assert_not_root") as mock_guard:
            from src import RootGuardError

            mock_guard.side_effect = RootGuardError()
            result = runner.invoke(app, ["status"])
        assert result.exit_code != 0

    def test_install_skips_root_guard(self):
        """install command does NOT check root guard (needs sudo)."""
        with patch("src.cli.assert_not_root") as mock_guard:
            # install --check should not call assert_not_root
            with patch("src.cli._run_install_check") as mock_check:
                mock_check.return_value = None
                result = runner.invoke(app, ["install", "--check"])
        mock_guard.assert_not_called()


# --- Monitor command ---


class TestMonitorCommand:
    """Test monitor subcommand."""

    def test_monitor_help(self):
        """monitor --help shows usage."""
        result = runner.invoke(app, ["monitor", "--help"])
        assert result.exit_code == 0
        assert "family" in result.output.lower() or "monitor" in result.output.lower()

    @patch("src.cli.assert_not_root")
    @patch("src.cli.load_config")
    @patch("src.cli.BtrfsClient")
    @patch("src.cli.find_pairs")
    def test_monitor_up_to_date(self, mock_pairs, mock_btrfs, mock_config, mock_guard):
        """When no pairs to process, shows up-to-date message."""
        mock_config.return_value = MagicMock(
            prefix=Path("/tmp/test"),
            snapdir=Path("/tmp/snaps"),
            state_dir=Path("/tmp/test/state"),
            catchup_limit=100,
        )
        mock_client = MagicMock()
        mock_client.discover_families.return_value = ["home"]
        mock_client.find_snapshots.return_value = []
        mock_btrfs.return_value = mock_client
        mock_pairs.return_value = []

        result = runner.invoke(app, ["monitor", "--families", "home"])
        assert result.exit_code == 0
        assert "up-to-date" in result.output.lower() or "no pairs" in result.output.lower()


# --- Report command ---


class TestReportCommand:
    """Test report subcommand."""

    def test_report_help(self):
        """report --help shows usage."""
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0

    @patch("src.cli.assert_not_root")
    @patch("src.cli.generate_report")
    def test_report_no_data(self, mock_gen, mock_guard):
        """report with no data shows message."""
        mock_gen.return_value = None
        result = runner.invoke(app, ["report", "--detail", "/tmp/nonexist.tsv"])
        assert result.exit_code == 0
        assert "no data" in result.output.lower() or "empty" in result.output.lower()


# --- Analyse command ---


class TestAnalyseCommand:
    """Test analyse subcommand."""

    def test_analyse_help(self):
        """analyse --help shows usage."""
        result = runner.invoke(app, ["analyse", "--help"])
        assert result.exit_code == 0

    @patch("src.cli.assert_not_root")
    @patch("src.cli.load_config")
    @patch("src.cli.generate_aggregate")
    def test_analyse_outputs_markdown(self, mock_agg, mock_config, mock_guard):
        """analyse prints markdown aggregate report."""
        mock_config.return_value = MagicMock(prefix=Path("/tmp/test"))
        mock_agg.return_value = ("# Report\n\ndata", {"reports": 5})
        result = runner.invoke(app, ["analyse"])
        assert result.exit_code == 0
        assert "Report" in result.output


# --- Status command ---


class TestStatusCommand:
    """Test status subcommand."""

    def test_status_help(self):
        """status --help shows usage."""
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    @patch("src.cli.assert_not_root")
    @patch("src.cli.load_config")
    def test_status_shows_config(self, mock_config, mock_guard, tmp_path):
        """status shows current configuration."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        mock_config.return_value = MagicMock(
            prefix=Path("/opt/btrfs-churn-mon"),
            snapdir=Path("/mnt/btrfs_pool/btrbk_snapshots"),
            state_dir=state_dir,
            reports_dir=Path("/opt/btrfs-churn-mon/reports"),
            catchup_limit=100,
        )
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "/opt/btrfs-churn-mon" in result.output


# --- Bootstrap command ---


class TestBootstrapCommand:
    """Test bootstrap subcommand."""

    def test_bootstrap_help(self):
        """bootstrap --help shows usage."""
        result = runner.invoke(app, ["bootstrap", "--help"])
        assert result.exit_code == 0


# --- Install command ---


class TestInstallCommand:
    """Test install subcommand."""

    def test_install_help(self):
        """install --help shows usage."""
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output.lower()

    @patch("src.cli._run_install_check")
    def test_install_check_runs_health_check(self, mock_check):
        """install --check runs health-check without modifying system."""
        mock_check.return_value = None
        result = runner.invoke(app, ["install", "--check"])
        assert result.exit_code == 0
        mock_check.assert_called_once()


# --- Verify command ---


class TestVerifyCommand:
    """Test verify subcommand (alias for install --check)."""

    def test_verify_help(self):
        """verify --help shows usage."""
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0

    @patch("src.cli._run_install_check")
    def test_verify_runs_health_check(self, mock_check):
        """verify runs the same health-check as install --check."""
        mock_check.return_value = None
        result = runner.invoke(app, ["verify"])
        assert result.exit_code == 0
        mock_check.assert_called_once()



# --- Uninstall command ---


class TestUninstallCommand:
    """Test uninstall subcommand."""

    def test_uninstall_help(self):
        """uninstall --help shows usage with options."""
        result = runner.invoke(app, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "purge-data" in result.output
        assert "keep-user" in result.output
        assert "dry-run" in result.output

    @patch("src.cli.load_config")
    def test_uninstall_dry_run(self, mock_config):
        """uninstall --dry-run shows plan without modifying."""
        mock_config.return_value = MagicMock(prefix=Path("/opt/btrfs-churn-mon"))
        result = runner.invoke(app, ["uninstall", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry-run" in result.output
        assert "Preserve data" in result.output

    @patch("src.cli.load_config")
    def test_uninstall_dry_run_purge(self, mock_config):
        """uninstall --dry-run --purge-data shows removal plan."""
        mock_config.return_value = MagicMock(prefix=Path("/opt/btrfs-churn-mon"))
        result = runner.invoke(app, ["uninstall", "--dry-run", "--purge-data"])
        assert result.exit_code == 0
        assert "Remove data" in result.output

    @patch("src.cli.Installer")
    @patch("src.cli.load_config")
    def test_uninstall_yes_skips_confirmation(self, mock_config, mock_installer_cls):
        """uninstall --yes executes without prompt."""
        mock_config.return_value = MagicMock(prefix=Path("/opt/btrfs-churn-mon"))
        mock_inst = MagicMock()
        mock_installer_cls.return_value = mock_inst

        result = runner.invoke(app, ["uninstall", "--yes"])
        assert result.exit_code == 0
        assert "Uninstall complete" in result.output
        mock_inst.uninstall.assert_called_once_with(purge_data=False, keep_user=False)

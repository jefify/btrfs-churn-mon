"""Tests for root guard — assert_not_root().

Contract:
- assert_not_root() → does nothing if euid != 0
- assert_not_root() → raises RootGuardError (SystemExit) if euid == 0
- RootGuardError message explains what to do
"""

from unittest.mock import patch

import pytest

from src import RootGuardError, assert_not_root


class TestAssertNotRoot:
    """Test privilege guard."""

    def test_passes_when_not_root(self):
        """Normal user (euid != 0) — no error."""
        with patch("os.geteuid", return_value=1000):
            # Should not raise
            assert_not_root()

    def test_aborts_when_root(self):
        """Running as root (euid == 0) — raises RootGuardError."""
        with patch("os.geteuid", return_value=0):
            with pytest.raises(RootGuardError):
                assert_not_root()

    def test_error_is_system_exit(self):
        """RootGuardError is a SystemExit (process terminates)."""
        with patch("os.geteuid", return_value=0):
            with pytest.raises(SystemExit):
                assert_not_root()

    def test_error_message_is_informative(self):
        """Error message tells user what to do instead."""
        with patch("os.geteuid", return_value=0):
            with pytest.raises(RootGuardError) as exc_info:
                assert_not_root()

        msg = str(exc_info.value)
        assert "root" in msg.lower()
        assert "btrfs-churn" in msg

    def test_uses_effective_uid(self):
        """Uses geteuid (effective), not getuid (real)."""
        # Simulates setuid scenario: real uid=1000, effective uid=0
        with patch("os.geteuid", return_value=0):
            with pytest.raises(RootGuardError):
                assert_not_root()

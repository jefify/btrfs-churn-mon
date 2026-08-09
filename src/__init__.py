"""btrfs-churn-mon — Analyze Btrfs snapshot churn."""

import os
import sys


class RootGuardError(SystemExit):
    """Raised when process is running as root (UID 0)."""

    def __init__(self):
        super().__init__(
            "ERROR: btrfs-churn-mon must NOT run as root. "
            "Use the 'btrfs-churn' service user instead. "
            "Only btrfs send/receive escalate via sudoers."
        )


def assert_not_root() -> None:
    """Abort if running as root (UID 0).

    The service runs as unprivileged user 'btrfs-churn'.
    Only btrfs send/receive commands escalate via sudoers.
    Running the whole process as root is a security risk.

    Raises:
        RootGuardError: If effective UID is 0.
    """
    if os.geteuid() == 0:
        raise RootGuardError()

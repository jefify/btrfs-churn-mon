"""Monitor state machine — find pairs, update state, orchestrate analysis.

State machine modes:
- first-run: no state file → analyse last pair
- catchup: state exists, newer snapshots available → analyse from state forward
- up-to-date: state points to latest → nothing to do
- recovery: state points to non-existent snapshot → analyse last pair
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple


def read_state(state_dir: Path, family: str) -> Optional[str]:
    """Read last processed snapshot name from state file.

    Args:
        state_dir: Directory containing state files
        family: Snapshot family name

    Returns:
        Last snapshot name, or None if no state.
    """
    state_file = state_dir / f"{family}.last"
    if not state_file.is_file():
        return None

    content = state_file.read_text(encoding="utf-8").strip()
    return content if content else None


def write_state(state_dir: Path, family: str, snapshot_name: str) -> None:
    """Atomically write last processed snapshot name to state file.

    Uses tmpfile + rename for atomicity. Sets permissions to 0644.

    Args:
        state_dir: Directory containing state files
        family: Snapshot family name
        snapshot_name: Name of the last processed snapshot
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{family}.last"

    # Atomic write: write to temp, then rename
    fd, tmp_path = tempfile.mkstemp(
        prefix=f"{family}.last.",
        dir=str(state_dir),
    )
    try:
        os.write(fd, f"{snapshot_name}\n".encode())
        os.fchmod(fd, 0o644)
        os.close(fd)
        os.rename(tmp_path, str(state_file))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def find_pairs(
    family: str,
    snapshots: List[Path],
    state_dir: Path,
    catchup_limit: int = 100,
) -> List[Tuple[Path, Path]]:
    """Find snapshot pairs to process based on state machine.

    Args:
        family: Snapshot family name
        snapshots: Sorted list of snapshot paths (chronological)
        state_dir: Directory containing state files
        catchup_limit: Max pairs to return in catchup mode

    Returns:
        List of (old, new) Path tuples to process.
    """
    if len(snapshots) < 2:
        return []

    last = read_state(state_dir, family)

    # Mode: first-run
    if last is None:
        return [(snapshots[-2], snapshots[-1])]

    # Find state position in snapshot list
    found_idx = None
    for i, snap in enumerate(snapshots):
        if snap.name == last:
            found_idx = i
            break

    # Mode: recovery (state not found in snapshots)
    if found_idx is None:
        return [(snapshots[-2], snapshots[-1])]

    # Mode: up-to-date or catchup
    pairs = []
    for j in range(found_idx + 1, len(snapshots)):
        old = snapshots[j - 1]
        new = snapshots[j]
        pairs.append((old, new))
        if len(pairs) >= catchup_limit:
            break

    return pairs

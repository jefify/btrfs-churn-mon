#!/usr/bin/env python3
"""CLI wrapper — delegates to src.parser.

This file exists for backward compatibility with analyse-churn.sh.
Will be removed when full Python migration is complete (Phase 4.8).
"""

import sys
from pathlib import Path

# Add project root to path for src imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser import main

if __name__ == "__main__":
    main()

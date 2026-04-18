#!/usr/bin/env python3
"""MBuild CLI entry point for direct execution."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mbuild.cli import cli

if __name__ == '__main__':
    cli()

"""Utilities for running carrus commands safely in tests."""

import shutil
import subprocess
from pathlib import Path
from typing import List


def get_carrus_path() -> Path:
    """Find carrus executable in PATH."""
    carrus_path = shutil.which("carrus")
    if not carrus_path:
        raise RuntimeError("carrus executable not found in PATH")
    return Path(carrus_path)


def run_carrus(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run carrus command safely."""
    carrus_path = get_carrus_path()

    # Validate arguments are strings
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("All arguments must be strings")

    # Only allow execution of carrus binary
    if not carrus_path.is_file():
        raise RuntimeError("carrus path is not a file")

    # Execute with validated inputs and clean environment
    cmd = [str(carrus_path), *args]
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}  # Use clean PATH

    return subprocess.run(cmd, check=check, capture_output=True, text=True, env=env)

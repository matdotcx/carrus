#!/usr/bin/env python3
"""Quick fix for critical syntax errors."""

from pathlib import Path

FIXES = {
    "builder.py": {
        "subprocess": (
            "result = subprocess.run(cmd, capture_output=True, check=True, check=True, check=True, text=True)",
            "result = subprocess.run(cmd, capture_output=True, check=True, text=True)",
        ),
    },
    "types.py": {
        "post_init": (
            """    def __post_init__(self):
        if self.errors is None:
            self.""",
            """    def __post_init__(self):
        if self.errors is None:
            self.errors = []""",
        ),
    },
    "test_codesign.py": {
        "broken_imports": (
            """from carrus.core.codesign import (
from pathlib import Path
from unittest.mock import patch
import logging
""",
            """from pathlib import Path
from unittest.mock import patch
import logging
from carrus.core.codesign import (
    DMGMount,
    SigningInfo,
    verify_codesign,
    verify_signature_requirements,
)""",
        ),
    },
}


def fix_syntax_errors():
    """Apply quick syntax fixes."""
    root = Path(__file__).parent.parent

    for filename, fixes in FIXES.items():
        # Find matching files (could be in src/carrus/core or tests)
        matching_files = list(root.rglob(filename))
        for file_path in matching_files:
            print(f"Processing {file_path}")
            content = file_path.read_text()
            modified = False

            for fix_name, (old, new) in fixes.items():
                if old in content:
                    content = content.replace(old, new)
                    modified = True
                    print(f"✅ Applied {fix_name} fix")

            if modified:
                file_path.write_text(content)


if __name__ == "__main__":
    fix_syntax_errors()

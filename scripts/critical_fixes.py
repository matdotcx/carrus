#!/usr/bin/env python3
"""Fix critical syntax errors."""

from pathlib import Path

FIXES = {
    "src/carrus/core/builder.py": [
        (
            "validation_",
            "validation_errors = []"
        ),
        (
            "validation_errors.append(f\"Source file not found: {source_path}\")",
            """validation_errors = []
            validation_errors.append(f\"Source file not found: {source_path}\")"""
        ),
    ],
    "src/carrus/core/types.py": [
        (
            """    def __post_init__(self):
        if self.errors is None:
            self.""",
            """    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []"""
        ),
    ],
    "tests/test_codesign.py": [
        (
            """from carrus.core.codesign import (
from pathlib import Path
from unittest.mock import patch
import logging""",
            """from pathlib import Path
import logging
import tempfile
from unittest.mock import patch

from carrus.core.codesign import (
    DMGMount,
    SigningInfo,
    verify_codesign,
    verify_signature_requirements,
)"""
        ),
    ]
}

def fix_file(file_path: Path):
    """Apply fixes to a single file."""
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
        
    content = file_path.read_text()
    modified = False
    
    for old, new in FIXES.get(str(file_path).replace(str(Path.cwd()) + "/", ""), []):
        if old in content:
            content = content.replace(old, new)
            modified = True
            print(f"✅ Fixed in {file_path}")
    
    if modified:
        file_path.write_text(content)
        return True
        
    return False


def main():
    """Fix critical syntax errors."""
    root = Path(__file__).parent.parent
    fixed_files = []
    
    for file_path in FIXES.keys():
        target = root / file_path
        if fix_file(target):
            fixed_files.append(file_path)
    
    if fixed_files:
        print("\n✅ Fixed files:")
        for file in fixed_files:
            print(f"  - {file}")
    else:
        print("\n⚠️ No fixes needed")


if __name__ == "__main__":
    main()
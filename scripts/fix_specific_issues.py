#!/usr/bin/env python3
"""Fix specific linting issues that were identified."""

from pathlib import Path


def fix_files():
    """Fix specific files with known issues."""
    root = Path(__file__).parent.parent

    # Fix test_codesign.py path issues
    test_codesign = root / "tests" / "test_codesign.py"
    if test_codesign.exists():
        content = test_codesign.read_text()
        content = content.replace(
            "mount/TestApp.app')",
            "TestApp.app"
        )
        test_codesign.write_text(content)

    # Fix DatabaseError not being imported
    database = root / "src" / "carrus" / "core" / "database.py"
    if database.exists():
        content = database.read_text()
        if "from typing import Any, List, Optional" in content:
            content = content.replace(
                "from typing import Any, List, Optional",
                "from typing import Any, Dict, List, Optional"
            )
        database.write_text(content)

    # Fix double error chaining
    cli = root / "src" / "carrus" / "cli.py"
    if cli.exists():
        content = cli.read_text()
        content = content.replace(" from e from e", " from e")
        cli.write_text(content)

    print("✅ Fixed specific issues")


if __name__ == "__main__":
    fix_files()
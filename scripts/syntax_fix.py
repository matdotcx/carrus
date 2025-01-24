#!/usr/bin/env python3
"""Fix syntax issues in Python files."""

import re
from pathlib import Path

FIXES = {
    "src/carrus/cli.py": {
        "error_chaining": {
            "find": r"raise typer\.Exit\(1\) from e from e",
            "replace": "raise typer.Exit(1) from e",
        }
    },
    "src/carrus/core/types.py": {
        "post_init": {
            "find": r"def __post_init__\(self\):\s+if self\.errors is None:\s+self\.",
            "replace": """def __post_init__(self):
        if self.errors is None:
            self.errors = []""",
        }
    },
    "tests/test_codesign.py": {
        "temp_path": {
            "find": r"Path\(tempfile\.mkdtemp\(prefix='carrus_'\)\)\/TestApp\.app",
            "replace": "Path(tempfile.mkdtemp(prefix='carrus_test_')) / 'app.app'",
        }
    },
}


def fix_syntax():
    """Apply syntax fixes to files."""
    root = Path(__file__).parent.parent

    for file_path, fixes in FIXES.items():
        target = root / file_path
        if not target.exists():
            print(f"❌ File not found: {file_path}")
            continue

        content = target.read_text()
        modified = False

        for fix_name, fix in fixes.items():
            new_content = re.sub(fix["find"], fix["replace"], content)
            if new_content != content:
                content = new_content
                modified = True
                print(f"✅ Applied {fix_name} fix to {file_path}")

        if modified:
            target.write_text(content)
        else:
            print(f"⚠️ No fixes needed for {file_path}")


if __name__ == "__main__":
    fix_syntax()

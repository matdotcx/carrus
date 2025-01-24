#!/usr/bin/env python3
"""Fix critical syntax issues."""

from pathlib import Path

FIXES = {
    "src/carrus/core/builder.py": {
        "incomplete_validation": {
            "old": "        validation_",
            "new": "        validation_errors = []",
        }
    },
    "src/carrus/core/types.py": {
        "post_init": {
            "old": """    def __post_init__(self):
        if self.errors is None:
            self.""",
            "new": """    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []""",
        }
    },
    "src/carrus/core/codesign.py": {
        "post_init": {
            "old": """    def __post_init__(self):
        if self.errors is None:
            self.""",
            "new": """    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []""",
        }
    },
    "src/carrus/cli.py": {
        "error_chaining": {
            "old": "raise typer.Exit(1) from e from e",
            "new": "raise typer.Exit(1) from e",
        }
    },
    "src/carrus/core/database.py": {
        "error_chaining": {
            "old": 'raise DatabaseError(f"Failed to initialize database: {e}") from e from e',
            "new": 'raise DatabaseError(f"Failed to initialize database: {e}") from e',
        }
    },
}


def fix_critical_errors():
    """Apply critical syntax fixes."""
    root = Path(__file__).parent.parent

    for filepath, fixes in FIXES.items():
        target = root / filepath
        if not target.exists():
            print(f"❌ File not found: {filepath}")
            continue

        content = target.read_text()
        modified = False

        for fix_name, fix in fixes.items():
            if fix["old"] in content:
                content = content.replace(fix["old"], fix["new"])
                modified = True
                print(f"✅ Applied {fix_name} fix to {filepath}")

        if modified:
            target.write_text(content)
        else:
            print(f"⚠️  No fixes needed for {filepath}")


if __name__ == "__main__":
    fix_critical_errors()

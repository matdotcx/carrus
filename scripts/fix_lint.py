#!/usr/bin/env python3
"""Script to fix common linting issues."""

import re
from pathlib import Path


def fix_error_chaining(file_path: Path) -> None:
    """Add error chaining to raise statements in except blocks."""
    content = file_path.read_text()
    # Fix basic error chaining
    content = re.sub(
        r"(\s+)except\s+(\w+)\s+as\s+e:\s*\n(\s+).*\n(\s+)raise\s+(\w+)\((.*)\)",
        r"\1except \2 as e:\n\3\4raise \5(\6) from e",
        content,
    )
    file_path.write_text(content)


def fix_subprocess_safety(file_path: Path) -> None:
    """Make subprocess calls safer by using full paths."""
    content = file_path.read_text()

    # Add imports at top if not present
    if "import shutil" not in content:
        content = "import shutil\n" + content

    # Add executable path definitions
    executables = {"'hdiutil'": "HDIUTIL_PATH", "hdiutil": "HDIUTIL_PATH"}

    # Add executable definitions
    exec_defs = []
    for cmd, var in executables.items():
        if cmd in content and var not in content:
            exec_defs.append(f"{var} = shutil.which({cmd})")
            exec_defs.append(f"if not {var}:")
            raw_cmd = cmd.strip("'")  # Remove quotes outside of f-string
            exec_defs.append(f'    raise RuntimeError("{raw_cmd} not found in PATH")')

    if exec_defs:
        # Find where to insert definitions (after imports)
        import_block_end = content.rfind("import ")
        import_block_end = content.find("\n", import_block_end) + 1
        content = (
            content[:import_block_end] + "\n".join(exec_defs) + "\n\n" + content[import_block_end:]
        )

    # Replace executable strings with variables
    for cmd, var in executables.items():
        content = content.replace(f"[{cmd}", f"[{var}")
        content = content.replace(f"'{cmd}'", var)
        content = content.replace(f'"{cmd}"', var)

    # Add parameter validation for subprocess calls
    content = re.sub(
        r"subprocess\.run\((.*?),\s*capture_output=True",
        r"subprocess.run(\1, capture_output=True, check=True",
        content,
    )

    file_path.write_text(content)


def fix_temp_paths(file_path: Path) -> None:
    """Fix unsafe temporary path usage."""
    content = file_path.read_text()

    # Add tempfile import if needed
    if "import tempfile" not in content:
        content = "import tempfile\n" + content

    # Replace hardcoded tmp paths with tempfile usage
    replacements = {
        r"Path\('/tmp/'": r"Path(tempfile.gettempdir())/",
        r"Path\('/tmp/": r"Path(tempfile.mkdtemp(prefix='carrus_'))/",
        "'/tmp/": "tempfile.mkdtemp(prefix='carrus_')+'/",
    }

    for old, new in replacements.items():
        content = re.sub(old, new, content)

    file_path.write_text(content)


def main():
    root = Path(__file__).parent.parent

    # Fix Python files
    for path in root.rglob("*.py"):
        print(f"Processing {path}...")
        try:
            # Add error chaining
            fix_error_chaining(path)

            # Fix subprocess calls in core modules
            if "core/builder.py" in str(path) or "core/codesign.py" in str(path):
                fix_subprocess_safety(path)

            # Fix temp paths in test files
            if "/tests/" in str(path) or "_test" in str(path):
                fix_temp_paths(path)

            print(f"✅ Fixed {path}")
        except Exception as e:
            print(f"❌ Error fixing {path}: {e}")


if __name__ == "__main__":
    main()

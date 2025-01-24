#!/usr/bin/env python3
"""Sort and organize imports in Python files."""

import re
from pathlib import Path
from typing import Set


def get_third_party_modules() -> Set[str]:
    """Return set of known third-party module names."""
    return {
        "typer",
        "rich",
        "yaml",
        "pydantic",
        "aiohttp",
        "pytest",
        "sqlalchemy",
        "aiosqlite",
        "packaging",
    }


def sort_imports(content: str) -> str:
    """Sort imports into standard library, third party, and local."""
    # First, find the import block
    import_match = re.search(r"(?s)((?:import|from)[^\n]+\n\s*)+", content)
    if not import_match:
        return content

    import_block = import_match.group(0)
    if not import_block.strip():
        return content

    # Split into lines and remove blanks
    imports = [line.strip() for line in import_block.split("\n") if line.strip()]

    # Categorize imports
    stdlib = []
    third_party = []
    local = []
    third_party_modules = get_third_party_modules()

    for imp in imports:
        # Get the module name
        if imp.startswith("from"):
            module = imp.split()[1].split(".")[0]
        else:
            module = imp.split()[1].split(".")[0]

        # Categorize
        if module in third_party_modules:
            third_party.append(imp)
        elif module.startswith("."):
            local.append(imp)
        else:
            stdlib.append(imp)

    # Sort each section
    stdlib.sort()
    third_party.sort()
    local.sort()

    # Combine with proper spacing
    new_imports = []

    if stdlib:
        new_imports.extend(stdlib)
        if third_party or local:
            new_imports.append("")

    if third_party:
        new_imports.extend(third_party)
        if local:
            new_imports.append("")

    if local:
        new_imports.extend(local)
        new_imports.append("")

    # Replace in content
    new_import_block = "\n".join(new_imports) + "\n"
    return content.replace(import_block, new_import_block)


def process_file(file_path: Path) -> None:
    """Process a single Python file."""
    try:
        content = file_path.read_text()

        # Skip if no imports
        if not re.search(r"(?:import|from)\s+\w+", content):
            return

        # Sort imports
        new_content = sort_imports(content)

        # Write back if changed
        if new_content != content:
            file_path.write_text(new_content)
            print(f"✅ Fixed imports in {file_path}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")


def main():
    """Process all Python files in the project."""
    root = Path(__file__).parent.parent

    for py_file in root.rglob("*.py"):
        if py_file.is_file():
            process_file(py_file)


if __name__ == "__main__":
    main()

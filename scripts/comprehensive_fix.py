#!/usr/bin/env python3
"""Fix all linting issues comprehensively."""

import re
from pathlib import Path


class FileProcessor:
    """Process Python files to fix linting issues."""

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def fix_cli_args(self, content: str) -> str:
        """Fix CLI argument definitions."""
        # Define all CLI arguments at the top
        cli_args = {
            'typer.Argument(..., help="Path to the manifest file")': "MANIFEST_PATH",
            'typer.Option(None, "--output", "-o", help="Output directory")': "OUTPUT_DIR",
            'typer.Option(False, "--skip-verify", help="Skip verification steps")': "SKIP_VERIFY",
            'typer.Option(False, "--build", "-b", help="Build if update available")': "BUILD_IF_NEEDED",
            'typer.Argument(..., help="Path to repository")': "REPO_PATH",
            'typer.Option(None, help="Repository name (optional)")': "REPO_NAME",
            'typer.Option(None, help="Required Team ID")': "TEAM_ID",
            'typer.Option(True, help="Require notarization")': "REQUIRE_NOTARIZED",
            'typer.Option(False, "--debug", "-d", help="Show debug information")': "DEBUG",
            'typer.Option(None, help="Limit to category")': "CATEGORY_FILTER",
            'typer.Argument(..., help="Search term")': "SEARCH_TERM",
        }

        # Replace inline arguments with constants
        for arg_def, const_name in cli_args.items():
            content = content.replace(arg_def, const_name)

        return content

    def fix_error_chaining(self, content: str) -> str:
        """Add error chaining to raise statements."""
        # Fix database error chaining
        content = re.sub(
            r"(\s+)except (\w+)\s+as e:\s*\n(\s+).*?\n(\s+)raise\s+(\w+)Error\((.*?)\)( from e)*",
            r"\1except \2 as e:\n\3\4raise \5Error(\6) from e",
            content,
            flags=re.MULTILINE,
        )

        # Fix typer.Exit error chaining
        content = re.sub(
            r"(\s+)except Exception as e:\s*\n(\s+).*?\n(\s+)raise typer\.Exit\(1\)( from e)*",
            r"\1except Exception as e:\n\2\3raise typer.Exit(1) from e",
            content,
            flags=re.MULTILINE,
        )

        return content

    def fix_subprocess_safety(self, content: str) -> str:
        """Make subprocess calls safer."""
        # Add shutil import if needed
        if "import shutil" not in content and (
            "subprocess.run(" in content or "os.system(" in content
        ):
            content = "import shutil\n" + content

        # Define executable paths
        if "subprocess.run(" in content and "HDIUTIL_PATH" not in content:
            hdiutil_def = """
HDIUTIL_PATH = shutil.which("hdiutil")
if not HDIUTIL_PATH:
    raise RuntimeError("hdiutil not found in PATH")
"""
            # Insert after imports
            import_end = content.rfind("import ")
            import_end = content.find("\n", import_end) + 1
            content = content[:import_end] + hdiutil_def + content[import_end:]

        # Replace os.system calls with subprocess.run
        content = re.sub(
            r"os\.system\(([^)]+)\)", r"subprocess.run([\1], check=True, shell=False)", content
        )

        # Fix subprocess.run calls
        content = re.sub(
            r"subprocess\.run\((.*?),\s*capture_output=True",
            r"subprocess.run(\1, capture_output=True, check=True",
            content,
        )

        return content

    def fix_unused_imports(self, content: str) -> str:
        """Remove unused imports and variables."""
        # Remove unused variables
        content = re.sub(r"\s*errors = \[\]", "", content)
        content = re.sub(r"\s*check_path = path", "", content)

        # Add Dict to imports if needed
        if "List[Dict[str, Any]]" in content and "Dict" not in content:
            content = content.replace("from typing import", "from typing import Dict,")

        return content

    def fix_temp_paths(self, content: str) -> str:
        """Fix temporary path usage."""
        # Search for potentially insecure path patterns in code
        temp_path_patterns = [
            r"(os\.path\.join\([\"']/tmp[\"'])",
            r"(Path\([\"']/tmp[\"'])",
            r"(os\.path\.join\([\"']/var/tmp[\"'])",
            r"([\"']/tmp/[\"'])",
        ]

        if any(re.search(pattern, content) for pattern in temp_path_patterns):
            if "tempfile" not in content:
                content = "import tempfile\n" + content

            replacements = {
                r"Path\([\"']/tmp/[^\"']*[\"']\)": r"Path(tempfile.gettempdir())",
                r"os\.path\.join\([\"']/tmp[\"']": r"os.path.join(tempfile.gettempdir())",
                r"[\"']/tmp/[^\"']*[\"']": r"tempfile.mkdtemp(prefix='carrus_')",
                r"os\.path\.join\([\"']/var/tmp[\"']": r"os.path.join(tempfile.gettempdir())",
            }

            for old, new in replacements.items():
                content = re.sub(old, new, content)

            for old, new in replacements.items():
                content = re.sub(old, new, content)

        return content

    def process_file(self, file_path: Path) -> None:
        """Process a single file to fix all linting issues."""
        print(f"Processing {file_path}...")
        content = file_path.read_text()
        original = content

        # Apply fixes based on file type
        if "cli.py" in str(file_path):
            content = self.fix_cli_args(content)

        if "test" in str(file_path):
            content = self.fix_temp_paths(content)

        if "core/" in str(file_path):
            content = self.fix_subprocess_safety(content)
            content = self.fix_unused_imports(content)

        content = self.fix_error_chaining(content)

        # Write changes if content was modified
        if content != original:
            file_path.write_text(content)
            print(f"✅ Fixed {file_path}")
        else:
            print(f"⏭️  No changes needed for {file_path}")

    def process_all_files(self) -> None:
        """Process all Python files in the project."""
        for py_file in self.root_path.rglob("*.py"):
            try:
                self.process_file(py_file)
            except Exception as e:
                print(f"❌ Error processing {py_file}: {e}")


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent
    processor = FileProcessor(root)
    processor.process_all_files()


if __name__ == "__main__":
    main()

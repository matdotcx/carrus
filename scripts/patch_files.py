#!/usr/bin/env python3
"""Apply patches to fix linting issues."""

from pathlib import Path

PATCHES = {
    "src/carrus/cli.py": {
        "constants": {
            "old": """# CLI argument/option definitions
MANIFEST_PATH = MANIFEST_PATH
OUTPUT_DIR = OUTPUT_DIR
SKIP_VERIFY = SKIP_VERIFY
BUILD_IF_NEEDED = BUILD_IF_NEEDED
REPO_PATH = REPO_PATH
REPO_NAME = REPO_NAME
TEAM_ID = TEAM_ID
REQUIRE_NOTARIZED = REQUIRE_NOTARIZED
DEBUG = DEBUG""",
            "new": """# CLI argument/option definitions
MANIFEST_PATH = typer.Argument(..., help="Path to the manifest file")
OUTPUT_DIR = typer.Option(None, "--output", "-o", help="Output directory")
SKIP_VERIFY = typer.Option(False, "--skip-verify", help="Skip verification steps")
BUILD_IF_NEEDED = typer.Option(False, "--build", "-b", help="Build if update available")
REPO_PATH = typer.Argument(..., help="Path to repository")
REPO_NAME = typer.Option(None, help="Repository name (optional)")
TEAM_ID = typer.Option(None, help="Required Team ID")
REQUIRE_NOTARIZED = typer.Option(True, help="Require notarization")
DEBUG = typer.Option(False, "--debug", "-d", help="Show debug information")
CATEGORY_FILTER = typer.Option(None, help="Limit to category")
SEARCH_TERM = typer.Argument(..., help="Search term")"""
        }
    },
    "src/carrus/core/builder.py": {
        "subprocess": {
            "old": "result = subprocess.run(cmd, capture_output=True, check=True, check=True, check=True, check=True, text=True)",
            "new": "result = subprocess.run(cmd, capture_output=True, check=True, text=True)"
        }
    },
    "src/carrus/core/types.py": {
        "post_init": {
            "old": """def __post_init__(self):
        if self.errors is None:
            self.""",
            "new": """def __post_init__(self):
        if self.errors is None:
            self.errors = []"""
        }
    },
}

def apply_patches():
    """Apply all patches to files."""
    root = Path(__file__).parent.parent
    
    for file_path, patches in PATCHES.items():
        target = root / file_path
        if not target.exists():
            print(f"❌ File not found: {file_path}")
            continue
            
        content = target.read_text()
        modified = False
        
        for patch_name, patch in patches.items():
            if patch["old"] in content:
                content = content.replace(patch["old"], patch["new"])
                modified = True
                print(f"✅ Applied {patch_name} patch to {file_path}")
                
        if modified:
            target.write_text(content)
        else:
            print(f"⚠️ No patches applied to {file_path}")

if __name__ == "__main__":
    apply_patches()
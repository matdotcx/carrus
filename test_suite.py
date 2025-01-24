#!/usr/bin/env python3
# test_suite.py

import asyncio
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from tests.command_runner import run_carrus

console = Console()
app = typer.Typer()

class TestFailure(Exception):
    """Test failure with details."""
    pass

class TestSuite:
    def __init__(self):
        self.temp_dir = None
        self.test_repo = None
        self.passed = 0
        self.failed = 0
        self.results = []
        self.downloaded_files = set()

    def setup(self):
        """Set up test environment."""
        console.print("[bold]Creating test environment...[/bold]")
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_repo = self.temp_dir / "test-repo"
        self.create_test_files()

    def cleanup(self):
        """Clean up test environment."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                # Clean up any downloaded files
                for file in self.downloaded_files:
                    if Path(file).exists():
                        os.remove(file)

                # Remove temp directory
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                console.print(f"[yellow]Warning during cleanup: {e}[/yellow]")

    def create_test_files(self):
        """Create test repository and manifests."""
        # Create repository structure
        os.makedirs(self.test_repo / "manifests" / "browsers", exist_ok=True)

        # Create repository metadata
        repo_yaml = {
            "name": "test-repo",
            "description": "Test repository for Carrus",
            "maintainer": "Test Suite",
            "url": "https://example.com/test-repo",
        }

        with open(self.test_repo / "repo.yaml", "w") as f:
            yaml.dump(repo_yaml, f)

        # Create Firefox manifest
        firefox_manifest = {
            "name": "Firefox",
            "version": "123.0",
            "type": "firefox",
            "url": "https://download-installer.cdn.mozilla.net/pub/firefox/releases/123.0/mac/en-US/Firefox%20123.0.dmg",
            "filename": "Firefox-123.0.dmg",
            "checksum": "80321c06df972dcf7d346d1137ca0d31be8988fdcf892702da77a43f4bb8a8f1",
            "code_sign": {
                "team_id": "43AQ936H96",
                "require_notarized": True
            },
            "build": {
                "type": "app_dmg",
                "destination": "/Applications"
            },
            "mdm": {
                "kandji": {
                    "display_name": "Mozilla Firefox",
                    "description": "Firefox web browser",
                    "category": "Browsers",
                    "developer": "Mozilla",
                    "minimum_os_version": "11.0",
                    "uninstallable": True
                }
            }
        }

        with open(self.test_repo / "manifests" / "browsers" / "firefox.yaml", "w") as f:
            yaml.dump(firefox_manifest, f)

        console.print(f"Created test repository at: {self.test_repo}")

    async def run_test(self, name: str, func):
        """Run a single test with proper error handling."""
        try:
            console.print(f"\n[bold blue]Running test: {name}[/bold blue]")
            await func()
            self.passed += 1
            self.results.append({"name": name, "result": "passed"})
            console.print(f"[green]✓ Test passed: {name}[/green]")
        except TestFailure as e:
            self.failed += 1
            self.results.append({"name": name, "result": "failed", "error": str(e)})
            console.print(f"[red]✗ Test failed: {name}[/red]")
            console.print(f"[red]  Error: {str(e)}[/red]")
        except Exception as e:
            self.failed += 1
            self.results.append({"name": name, "result": "error", "error": str(e)})
            console.print(f"[red]✗ Test error: {name}[/red]")
            console.print(f"[red]  Unexpected error: {str(e)}[/red]")

    async def test_help_command(self):
        """Test the help command."""
        try:
            run_carrus(["--help"])
        except Exception as e:
            raise TestFailure("Help command failed") from e

    async def test_download_command(self):
        """Test downloading a package."""
        manifest_path = self.test_repo / "manifests" / "browsers" / "firefox.yaml"
        dest_file = Path("Firefox-123.0.dmg")

        # Remove existing file if any
        if dest_file.exists():
            dest_file.unlink()

        try:
            run_carrus(["download", "--skip-verify", str(manifest_path)])
        except Exception as e:
            raise TestFailure("Download command failed") from e

        # Verify file exists
        if not dest_file.exists():
            raise TestFailure("Downloaded file not found")

        # Track for cleanup
        self.downloaded_files.add(str(dest_file))

    async def test_verify_command(self):
        """Test verifying a package."""
        # Ensure we have the file
        if not Path("Firefox-123.0.dmg").exists():
            await self.test_download_command()

        try:
            run_carrus(["verify", "Firefox-123.0.dmg"])
        except Exception as e:
            raise TestFailure("Verify command failed") from e

    async def test_repo_commands(self):
        """Test repository management commands."""
        # Add repository
        try:
            run_carrus(["repo-add", str(self.test_repo)])
        except Exception as e:
            raise TestFailure("repo-add command failed") from e

        # List repositories
        try:
            run_carrus(["repo-list"])
        except Exception as e:
            raise TestFailure("repo-list command failed") from e

        # Search repositories
        try:
            run_carrus(["search", "browsers"])
        except Exception as e:
            raise TestFailure("search command failed") from e

    async def test_check_updates(self):
        """Test update checking."""
        manifest_path = self.test_repo / "manifests" / "browsers" / "firefox.yaml"
        try:
            run_carrus(["check-updates", str(manifest_path)])
        except Exception as e:
            raise TestFailure("check-updates command failed") from e

    async def test_build_commands(self):
        """Test build commands."""
        manifest_path = self.test_repo / "manifests" / "browsers" / "firefox.yaml"

        # Ensure we have the downloaded file
        if not Path("Firefox-123.0.dmg").exists():
            await self.test_download_command()

        # Wait a moment to ensure file is fully written
        await asyncio.sleep(1)

        # Create build directories
        build_dir = self.temp_dir / "Applications"
        mdm_dir = self.temp_dir / "mdm"
        build_dir.mkdir(parents=True, exist_ok=True)
        mdm_dir.mkdir(parents=True, exist_ok=True)

        # Test regular build
        try:
            run_carrus(["build", "--output", str(build_dir), str(manifest_path)])
        except Exception as e:
            raise TestFailure("build command failed") from e

        # Verify the app exists
        if not (build_dir / "Firefox.app").exists():
            raise TestFailure("Built application not found")

        # Test MDM build
        try:
            run_carrus(["build-mdm", "--output", str(mdm_dir), str(manifest_path)])
        except Exception as e:
            raise TestFailure("build-mdm command failed") from e

    async def run_all_tests(self):
        """Run all test cases."""
        tests = [
            ("Help Command", self.test_help_command),
            ("Download Command", self.test_download_command),
            ("Verify Command", self.test_verify_command),
            ("Repository Commands", self.test_repo_commands),
            ("Update Checking", self.test_check_updates),
            ("Build Commands", self.test_build_commands),
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running tests...", total=None)

            for name, func in tests:
                await self.run_test(name, func)

            progress.update(task, completed=True)

    def generate_report(self):
        """Generate test report."""
        console.print("\n[bold]Test Results Summary[/bold]")
        console.print(f"Tests passed: [green]{self.passed}[/green]")
        console.print(f"Tests failed: [red]{self.failed}[/red]")
        console.print(f"Total tests: {self.passed + self.failed}")

        if self.failed > 0:
            console.print("\n[bold red]Failed Tests:[/bold red]")
            for result in self.results:
                if result["result"] != "passed":
                    console.print(f"[red]✗ {result['name']}[/red]")
                    console.print(f"  Error: {result['error']}")

        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(f"test_report_{timestamp}.txt")

        with open(report_file, "w") as f:
            f.write(f"Carrus Test Report - {datetime.now()}\n")
            f.write("-" * 50 + "\n\n")
            f.write(f"Tests passed: {self.passed}\n")
            f.write(f"Tests failed: {self.failed}\n")
            f.write(f"Total tests: {self.passed + self.failed}\n\n")

            for result in self.results:
                f.write(f"Test: {result['name']}\n")
                f.write(f"Result: {result['result']}\n")
                if result.get('error'):
                    f.write(f"Error: {result['error']}\n")
                f.write("-" * 30 + "\n")

        console.print(f"\nTest report saved to: {report_file}")

@app.command()
def run_tests(
    skip_cleanup: bool = typer.Option(False, "--skip-cleanup", help="Don't clean up test files")
):
    """Run all tests."""
    suite = TestSuite()

    try:
        # Set up test environment
        suite.setup()

        # Run all tests
        asyncio.run(suite.run_all_tests())

    finally:
        # Generate report
        suite.generate_report()

        # Clean up unless skipped
        if not skip_cleanup:
            console.print("\n[bold]Cleaning up test environment...[/bold]")
            suite.cleanup()
        else:
            console.print("\n[yellow]Skipping cleanup as requested[/yellow]")

        # Exit with appropriate code
        sys.exit(1 if suite.failed > 0 else 0)

if __name__ == "__main__":
    app()
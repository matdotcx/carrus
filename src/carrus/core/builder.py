# src/carrus/core/builder.py

import subprocess
from pathlib import Path
import tempfile
import shutil
import os
import asyncio
from rich.console import Console
from rich.progress import Progress
from .types import BuildType, BuildConfig, BuildResult

console = Console()

# Update AppDmgBuilder in builder.py

class AppDmgBuilder:
    """Builds application packages from DMGs."""

    @staticmethod
    async def build(
        source_path: Path,
        destination: Path,
        progress: Progress,
        task_id: int
    ) -> BuildResult:
        """Build package from DMG."""
        temp_dir = None
        mount_point = None

        # Update progress display
        progress.update(task_id, description="Starting build...")
        console.print(f"\n[blue]Starting DMG build[/blue]")
        console.print(f"Source: {source_path}")
        console.print(f"Destination: {destination}")

        try:
            # Verify source file
            if not source_path.exists():
                return BuildResult(
                    success=False,
                    errors=[f"Source file not found: {source_path}"]
                )

            console.print(f"Source file size: {source_path.stat().st_size}")

            # Mount DMG using context manager
            progress.update(task_id, description="Mounting DMG...")
            with DMGMount(source_path) as mount:
                console.print("[blue]DMG mounted successfully[/blue]")

                # Prepare destination
                app_name = mount.app_path.name
                dest_path = Path(destination) / app_name
                console.print(f"Copying to: {dest_path}")

                # Remove existing app if present
                if dest_path.exists():
                    progress.update(task_id, description="Removing existing application...")
                    console.print("[blue]Removing existing application[/blue]")
                    shutil.rmtree(dest_path)

                # Copy the application
                progress.update(task_id, description=f"Copying {app_name}...")
                console.print("[blue]Copying application...[/blue]")
                shutil.copytree(mount.app_path, dest_path, symlinks=True)

                progress.update(task_id, description="Build complete!")
                console.print("[green]Application copied successfully[/green]")

                return BuildResult(
                    success=True,
                    output_path=dest_path
                )

        except Exception as e:
            progress.update(task_id, description=f"Error: {str(e)}")
            console.print(f"[red]Build error: {str(e)}[/red]")
            return BuildResult(
                success=False,
                errors=[str(e)]
            )

class DMGMount:
    """Context manager for mounting DMG files."""
    def __init__(self, dmg_path: Path):
        self.dmg_path = dmg_path
        self.mount_point = None
        self.app_path = None

    def __enter__(self):
        # Create temporary mount point
        self.mount_point = Path(tempfile.mkdtemp())

        console.print(f"\n[yellow]Mount Process:[/yellow]")
        console.print(f"1. Creating mount point at {self.mount_point}")
        console.print(f"2. Attempting to mount {self.dmg_path}")

        mount_cmd = [
            'hdiutil', 'attach',
            str(self.dmg_path),
            '-mountpoint', str(self.mount_point),
            '-nobrowse', '-verbose'
        ]

        console.print("3. Running mount command...")
        result = subprocess.run(
            mount_cmd,
            capture_output=True,
            text=True
        )

        console.print("\n[yellow]Mount Results:[/yellow]")
        if result.stdout:
            console.print("[blue]Standard output:[/blue]")
            for line in result.stdout.splitlines():
                console.print(f"  {line}")

        if result.stderr:
            console.print("[blue]Standard error:[/blue]")
            for line in result.stderr.splitlines():
                console.print(f"  {line}")

        console.print(f"Return code: {result.returncode}")

        if result.returncode != 0:
            raise RuntimeError(f"Failed to mount DMG: {result.stderr}")

        console.print("\n[yellow]Finding Application:[/yellow]")
        console.print(f"1. Searching in {self.mount_point}")
        app_paths = list(Path(self.mount_point).glob("*.app"))
        if not app_paths:
            console.print("2. Not found in root, searching subdirectories...")
            app_paths = list(Path(self.mount_point).rglob("*.app"))

        if app_paths:
            self.app_path = app_paths[0]
            console.print(f"✓ Found app at: {self.app_path}")
        else:
            raise RuntimeError("No .app bundle found in DMG")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.mount_point:
            console.print("\n[yellow]Cleanup Process:[/yellow]")
            console.print(f"1. Unmounting {self.mount_point}")
            detach_cmd = ['hdiutil', 'detach', str(self.mount_point), '-force', '-verbose']
            result = subprocess.run(
                detach_cmd,
                capture_output=True,
                text=True
            )

            if result.stdout or result.stderr:
                console.print("[blue]Unmount output:[/blue]")
                if result.stdout:
                    console.print(result.stdout)
                if result.stderr:
                    console.print(result.stderr)

            try:
                console.print("2. Removing mount point directory")
                os.rmdir(self.mount_point)
                console.print("✓ Cleanup complete")
            except OSError as e:
                console.print(f"[yellow]Warning: Could not remove mount point: {e}[/yellow]")

async def build_package(
    source_path: Path,
    build_config: BuildConfig,
    progress: Progress,
) -> BuildResult:
    """Build a package based on configuration."""

    console.print("[blue]Starting package build[/blue]")
    console.print(f"Source path: {source_path}")
    console.print(f"Build type: {build_config.type}")
    console.print(f"Destination: {build_config.destination}")

    task_id = progress.add_task("Building package...", total=None)

    try:
        destination = Path(build_config.destination)
        destination.mkdir(parents=True, exist_ok=True)

        # Convert string to BuildType
        try:
            build_type = BuildType(build_config.type)
            console.print(f"[blue]Build type resolved to: {build_type}[/blue]")
        except ValueError:
            return BuildResult(
                success=False,
                errors=[f"Invalid build type: {build_config.type}"]
            )

        if build_type == BuildType.APP_DMG:
            console.print("[blue]Using AppDmgBuilder[/blue]")
            return await AppDmgBuilder.build(source_path, destination, progress, task_id)

        return BuildResult(
            success=False,
            errors=[f"Unsupported build type: {build_type}"]
        )

    except Exception as e:
        console.print(f"[red]Build error: {str(e)}[/red]")
        return BuildResult(
            success=False,
            errors=[str(e)]
        )
    finally:
        progress.update(task_id, completed=True)

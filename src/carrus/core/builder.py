# src/carrus/core/builder.py

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.progress import Progress

from .types import BuildConfig, BuildResult, BuildState, BuildStep, BuildType

HDIUTIL_PATH = shutil.which("hdiutil")
if not HDIUTIL_PATH:
    raise RuntimeError("hdiutil not found in PATH")


console = Console()

class BuildError(Exception):
    """Base class for build errors."""
    pass

class DMGMountError(BuildError):
    """Error mounting DMG file."""
    pass

class AppExtractionError(BuildError):
    """Error extracting application."""
    pass

def _validate_cmd(cmd: List[str], executable: str) -> None:
    """Validate a command is safe to execute."""
    if not isinstance(cmd, list) or not cmd:
        raise BuildError("Invalid command format")
        
    if cmd[0] != executable:
        raise BuildError("Invalid command")
        
    if not all(isinstance(arg, str) for arg in cmd):
        raise BuildError("Invalid command arguments")

    exe_path = Path(executable)
    if not (exe_path.is_file() and os.access(exe_path, os.X_OK)):
        raise BuildError(f"{executable} is not an executable file")

def _run_cmd(cmd: List[str], description: str) -> Tuple[str, str, int]:
    """Run a command with validation and safe execution."""
    console.print(f"[blue]{description}[/blue]")
    
    _validate_cmd(cmd, HDIUTIL_PATH)
    
    # Use secure PATH
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}

    # Execute with validated inputs and cleaned environment    
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        text=True,
        env=env
    )

    if result.stdout:
        console.print("[dim]Command output:[/dim]")
        console.print(result.stdout)
    return result.stdout, result.stderr, result.returncode

class AppDmgBuilder:
    """Builds application packages from DMGs."""

    @staticmethod
    async def build(
        source_path: Path,
        destination: Path,
        progress: Progress,
        task_id: int,
        build_state: BuildState
    ) -> BuildResult:
        """Build package from DMG."""
        console.print("\n[blue]Starting DMG build[/blue]")
        console.print(f"Source: {source_path}")
        console.print(f"Destination: {destination}")

        try:
            # Verify source file
            if not source_path.exists():
                raise BuildError(f"Source file not found: {source_path}")

            console.print(f"Source file size: {source_path.stat().st_size}")

            # Mount DMG using context manager
            progress.update(task_id, description="Mounting DMG...")
            with DMGMount(source_path, build_state) as mount:
                console.print("[blue]DMG mounted successfully[/blue]")

                build_state.current_step = BuildStep.COPYING
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

                build_state.current_step = BuildStep.CLEANUP
                progress.update(task_id, description="Build complete!")
                console.print("[green]Application copied successfully[/green]")

                return BuildResult(
                    success=True,
                    output_path=dest_path,
                    build_state=build_state
                )

        except BuildError as e:
            build_state.add_error(str(e))
            return BuildResult(
                success=False,
                build_state=build_state,
                errors=[str(e)]
            )
        except Exception as e:
            build_state.add_error(f"Unexpected error: {str(e)}")
            return BuildResult(
                success=False,
                build_state=build_state,
                errors=[f"Unexpected error: {str(e)}"]
            )

class DMGMount:
    """Context manager for mounting DMG files."""
    def __init__(self, dmg_path: Path, build_state: BuildState):
        self.dmg_path = dmg_path
        self.build_state = build_state
        self.mount_point = None
        self.app_path = None
        self._mounted = False

    def __enter__(self):
        try:
            self.build_state.current_step = BuildStep.MOUNTING
            # Create temporary mount point
            self.mount_point = tempfile.mkdtemp()
            self.build_state.add_temp_file(Path(self.mount_point))
            console.print(f"Created mount point at {self.mount_point}")

            # Mount DMG
            stdout, stderr, returncode = _run_cmd(
                [
                    HDIUTIL_PATH, 'attach',
                    str(self.dmg_path),
                    '-mountpoint', str(self.mount_point),
                    '-nobrowse', '-quiet'
                ],
                "Mounting DMG"
            )

            if returncode != 0:
                raise DMGMountError(f"Failed to mount DMG: {stderr}")

            self._mounted = True
            
            # Find the .app bundle
            self.build_state.current_step = BuildStep.EXTRACTION
            app_paths = list(Path(self.mount_point).glob("*.app"))
            if not app_paths:
                console.print("[yellow]No .app found in root, searching subdirectories...[/yellow]")
                app_paths = list(Path(self.mount_point).rglob("*.app"))

            if app_paths:
                self.app_path = app_paths[0]
                console.print(f"[green]Found app at: {self.app_path}[/green]")
            else:
                raise AppExtractionError("No .app bundle found in DMG")

            return self

        except Exception as e:
            self.cleanup()
            if isinstance(e, (DMGMountError, AppExtractionError)):
                raise
            raise BuildError(f"DMG mount failed: {str(e)}") from e

    def cleanup(self):
        """Clean up mount point and mounted DMG."""
        if self._mounted:
            try:
                _run_cmd(
                    [HDIUTIL_PATH, 'detach', self.mount_point, '-force'],
                    "Unmounting DMG"
                )
                self._mounted = False
            except Exception as e:
                self.build_state.add_warning(f"Failed to unmount DMG: {e}")

        if self.mount_point and Path(self.mount_point).exists():
            try:
                shutil.rmtree(self.mount_point)
                self.mount_point = None
            except Exception as e:
                self.build_state.add_warning(f"Failed to remove mount point: {e}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

async def build_package(
    source_path: Path,
    build_config: BuildConfig,
    progress: Progress,
) -> BuildResult:
    """Build a package based on configuration."""

    build_state = BuildState(
        started_at=datetime.now(),
        build_type=build_config.type,
        source_path=source_path,
        destination=Path(build_config.destination)
    )

    console.print("[blue]Starting package build[/blue]")
    console.print(f"Source path: {source_path}")
    console.print(f"Build type: {build_config.type}")
    console.print(f"Destination: {build_config.destination}")

    task_id = progress.add_task("Building package...", total=None)

    try:
        build_state.current_step = BuildStep.VALIDATION
        # Validate inputs
        validation_errors = []
        
        if not source_path.exists():
            validation_errors.append(f"Source file not found: {source_path}")
        elif not source_path.is_file():
            validation_errors.append(f"Source path is not a file: {source_path}")
            
        if validation_errors:
            build_state.errors.extend(validation_errors)
            return BuildResult(
                success=False,
                build_state=build_state,
                errors=validation_errors
            )

        # Create destination directory
        destination = Path(build_config.destination)
        try:
            destination.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            error = f"Failed to create destination directory: {e}"
            build_state.add_error(error)
            return BuildResult(
                success=False,
                build_state=build_state,
                errors=[error]
            )

        # Convert string to BuildType
        try:
            build_type = BuildType(build_config.type)
        except ValueError:
            error = f"Invalid build type: {build_config.type}"
            build_state.add_error(error)
            return BuildResult(
                success=False,
                build_state=build_state,
                errors=[error]
            )

        if build_type == BuildType.APP_DMG:
            return await AppDmgBuilder.build(
                source_path,
                destination,
                progress,
                task_id,
                build_state
            )

        error = f"Unsupported build type: {build_type}"
        build_state.add_error(error)
        return BuildResult(
            success=False,
            build_state=build_state,
            errors=[error]
        )

    except Exception as e:
        error = f"Unexpected build error: {str(e)}"
        build_state.add_error(error)
        console.print(f"[red]{error}[/red]")
        return BuildResult(
            success=False,
            build_state=build_state,
            errors=[error]
        )
    finally:
        if not build_config.preserve_temp:
            cleanup_errors = build_state.cleanup()
            if cleanup_errors:
                build_state.warnings.extend(cleanup_errors)
        progress.update(task_id, completed=True)
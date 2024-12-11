# src/carrus/core/codesign.py

import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import json
from rich.console import Console
import tempfile
import os

console = Console()

@dataclass
class SigningInfo:
    """Container for code signing information."""
    signed: bool
    team_id: Optional[str] = None
    authority: Optional[List[str]] = None
    notarized: bool = False
    timestamp: Optional[str] = None
    errors: List[str] = None
    raw_output: Optional[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class DMGMount:
    """Context manager for mounting DMG files."""
    def __init__(self, dmg_path: Path):
        self.dmg_path = dmg_path
        self.mount_point = None
        self.app_path = None

    def __enter__(self):
        # Create a temporary mount point
        self.mount_point = tempfile.mkdtemp()

        # Mount DMG
        result = subprocess.run([
            'hdiutil', 'attach', str(self.dmg_path),
            '-mountpoint', str(self.mount_point),
            '-nobrowse', '-quiet'
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to mount DMG: {result.stderr}")

        # Find the .app bundle
        app_paths = list(Path(self.mount_point).glob("*.app"))
        if not app_paths:
            app_paths = list(Path(self.mount_point).rglob("*.app"))  # Search recursively

        if app_paths:
            self.app_path = app_paths[0]
        else:
            raise RuntimeError("No .app bundle found in DMG")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unmount DMG
        if self.mount_point:
            subprocess.run(
                ['hdiutil', 'detach', self.mount_point, '-force'],
                capture_output=True
            )
            try:
                os.rmdir(self.mount_point)
            except OSError:
                pass

def run_command(cmd: List[str], description: str) -> Tuple[str, str, int]:
    """Run a command and return stdout, stderr, and return code."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        return "", str(e), e.returncode
    except Exception as e:
        return "", str(e), -1

def verify_codesign(path: Path, debug: bool = True) -> SigningInfo:
    """Verify code signing of a file."""
    errors = []
    debug_output = []

    is_dmg = path.suffix.lower() == '.dmg'

    if debug:
        debug_output.append(f"File type: {'DMG' if is_dmg else 'Other'}")

    check_path = path
    if is_dmg:
        try:
            with DMGMount(path) as mount:
                if debug:
                    debug_output.append(f"Mounted DMG, found app: {mount.app_path}")
                return verify_codesign_internal(mount.app_path, debug, debug_output)
        except Exception as e:
            return SigningInfo(
                signed=False,
                errors=[f"Failed to process DMG: {str(e)}"],
                raw_output="\n".join(debug_output)
            )
    else:
        return verify_codesign_internal(path, debug, debug_output)

def verify_codesign_internal(path: Path, debug: bool, debug_output: List[str]) -> SigningInfo:
    """Internal verification logic."""
    # Basic codesign verification
    stdout, stderr, returncode = run_command(
        ['codesign', '--verify', '--verbose=2', str(path)],
        "codesign verify"
    )
    is_signed = returncode == 0

    if debug:
        debug_output.append("\nCodesign verify output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")
        debug_output.append(f"return code: {returncode}")

    # Get detailed signing info
    stdout, stderr, returncode = run_command(
        ['codesign', '-dvv', str(path)],
        "codesign details"
    )

    if debug:
        debug_output.append("\nCodesign details output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")

    # Parse team ID and authority
    team_id = None
    authority = []
    for line in (stderr or "").splitlines():
        if 'TeamIdentifier=' in line:
            team_id = line.split('=')[1]
        if 'Authority=' in line:
            authority.append(line.split('=')[1])

    # Check notarization
    stdout, stderr, returncode = run_command(
        ['spctl', '--assess', '--verbose=2', '--type', 'execute', str(path)],
        "notarization check"
    )
    is_notarized = returncode == 0

    if debug:
        debug_output.append("\nNotarization check output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")
        debug_output.append(f"return code: {returncode}")

    return SigningInfo(
        signed=is_signed,
        team_id=team_id,
        authority=authority,
        notarized=is_notarized,
        errors=[],
        raw_output="\n".join(debug_output)
    )

def verify_signature_requirements(
    path: Path,
    required_team_id: Optional[str] = None,
    require_notarized: bool = True,
    debug: bool = True
) -> Tuple[bool, List[str]]:
    """Verify signature matches requirements."""
    info = verify_codesign(path, debug=debug)
    errors = info.errors.copy()

    if debug:
        console.print("\n[bold blue]Debug Information:[/bold blue]")
        console.print(info.raw_output)

    if not info.signed:
        errors.append("File is not signed")
        return False, errors

    if required_team_id and info.team_id != required_team_id:
        errors.append(
            f"Team ID mismatch: found {info.team_id}, "
            f"expected {required_team_id}"
        )
        return False, errors

    if require_notarized and not info.notarized:
        errors.append("File is not notarized")
        return False, errors

    return True, []

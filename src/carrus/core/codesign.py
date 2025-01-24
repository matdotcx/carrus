"""Code signing verification utilities."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console

from .logging import get_audit_logger, get_debug_logger


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


HDIUTIL_PATH = shutil.which("hdiutil")
if not HDIUTIL_PATH:
    raise RuntimeError("hdiutil not found in PATH")

ALLOWED_COMMANDS = {"codesign", "spctl", HDIUTIL_PATH}

console = Console()
audit_log = get_audit_logger()
debug_log = get_debug_logger()


def _validate_command(cmd: List[str]) -> None:
    """Validate command is safe to execute."""
    if not isinstance(cmd, list) or not cmd:
        raise RuntimeError("Invalid command format")

    if cmd[0] not in ALLOWED_COMMANDS:
        raise RuntimeError("Invalid command")

    # Validate all arguments are strings
    if not all(isinstance(arg, str) for arg in cmd):
        raise RuntimeError("Invalid command arguments")


def run_command(cmd: List[str], description: str) -> Tuple[str, str, int]:
    """Run a command and return stdout, stderr, and return code."""
    try:
        _validate_command(cmd)
        # Use clean environment
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        return "", str(e), e.returncode
    except Exception as e:
        return "", str(e), -1


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
        cmd = [
            HDIUTIL_PATH,
            "attach",
            str(self.dmg_path),
            "-mountpoint",
            str(self.mount_point),
            "-nobrowse",
            "-quiet",
        ]

        _validate_command(cmd)
        # Use clean environment
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to mount DMG: {result.stderr}")

        # Find the .app bundle
        app_paths = list(Path(self.mount_point).glob("*.app"))
        if not app_paths:
            app_paths = list(Path(self.mount_point).rglob("*.app"))

        if app_paths:
            self.app_path = app_paths[0]
        else:
            raise RuntimeError("No .app bundle found in DMG")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up mounted DMG."""
        if self.mount_point:
            cmd = [HDIUTIL_PATH, "detach", self.mount_point, "-force"]
            try:
                _validate_command(cmd)
                # Use clean environment
                env = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
                subprocess.run(cmd, capture_output=True, check=True, env=env)
                os.rmdir(self.mount_point)
            except Exception as e:
                # Log the error but don't raise since this is cleanup
                debug_log.error(f"Error during DMG cleanup: {e}")


def verify_codesign_internal(path: Path, debug: bool, debug_output: List[str]) -> SigningInfo:
    """Internal implementation of code sign verification."""
    debug_log.info(f"Starting internal code sign verification for {path}")

    # Basic codesign verification
    debug_log.debug("Running basic codesign verification")
    stdout, stderr, returncode = run_command(
        ["codesign", "--verify", "--verbose=2", str(path)], "codesign verify"
    )
    is_signed = returncode == 0
    debug_log.info(f"Basic verification result: {'signed' if is_signed else 'unsigned'}")

    if debug:
        debug_output.append("\nCodesign verify output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")
        debug_output.append(f"return code: {returncode}")

    # Get detailed signing info
    debug_log.debug("Getting detailed signing information")
    stdout, stderr, returncode = run_command(["codesign", "-dvv", str(path)], "codesign details")

    if debug:
        debug_output.append("\nCodesign details output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")

    # Parse team ID and authority
    team_id = None
    authority = []
    for line in (stderr or "").splitlines():
        if "TeamIdentifier=" in line:
            team_id = line.split("=")[1]
            debug_log.info(f"Found Team ID: {team_id}")
        if "Authority=" in line:
            auth = line.split("=")[1]
            authority.append(auth)
            debug_log.debug(f"Found Authority: {auth}")

    # Check notarization
    debug_log.debug("Checking notarization status")
    stdout, stderr, returncode = run_command(
        ["spctl", "--assess", "--verbose=2", "--type", "execute", str(path)], "notarization check"
    )
    is_notarized = returncode == 0
    debug_log.info(f"Notarization check result: {'notarized' if is_notarized else 'not notarized'}")

    if debug:
        debug_output.append("\nNotarization check output:")
        debug_output.append(f"stdout: {stdout}")
        debug_output.append(f"stderr: {stderr}")
        debug_output.append(f"return code: {returncode}")

    # Log verification summary
    audit_log.info(
        f"Code sign verification completed for {path}: "
        f"signed={is_signed}, "
        f"team_id={team_id}, "
        f"notarized={is_notarized}"
    )

    return SigningInfo(
        signed=is_signed,
        team_id=team_id,
        authority=authority,
        notarized=is_notarized,
        errors=[],
        raw_output="\n".join(debug_output),
    )


def verify_codesign(path: Path, debug: bool = True) -> SigningInfo:
    """Verify code signing of a file."""
    debug_output = []

    is_dmg = path.suffix.lower() == ".dmg"
    debug_log.info(f"Starting code sign verification for {path}")
    debug_log.debug(f"File type: {'DMG' if is_dmg else 'Other'}")

    if debug:
        debug_output.append(f"File type: {'DMG' if is_dmg else 'Other'}")

    if is_dmg:
        try:
            debug_log.info(f"Mounting DMG file: {path}")
            with DMGMount(path) as mount:
                if debug:
                    debug_output.append(f"Mounted DMG, found app: {mount.app_path}")
                debug_log.info(f"Successfully mounted DMG, found app: {mount.app_path}")
                return verify_codesign_internal(mount.app_path, debug, debug_output)
        except Exception as e:
            error_msg = f"Failed to process DMG: {str(e)}"
            debug_log.error(error_msg)
            audit_log.error(f"Code sign verification failed for DMG {path}: {error_msg}")
            return SigningInfo(signed=False, errors=[error_msg], raw_output="\n".join(debug_output))
    else:
        return verify_codesign_internal(path, debug, debug_output)


def verify_signature_requirements(
    path: Path,
    required_team_id: Optional[str] = None,
    require_notarized: bool = True,
    debug: bool = True,
) -> Tuple[bool, List[str]]:
    """Verify signature matches requirements."""
    debug_log.info(
        f"Verifying signature requirements for {path} "
        f"(team_id={required_team_id}, require_notarized={require_notarized})"
    )

    info = verify_codesign(path, debug=debug)
    errors = info.errors.copy()

    if debug:
        console.print("\n[bold blue]Debug Information:[/bold blue]")
        console.print(info.raw_output)

    if not info.signed:
        error_msg = "File is not signed"
        debug_log.error(error_msg)
        audit_log.error(f"Signature verification failed for {path}: {error_msg}")
        errors.append(error_msg)
        return False, errors

    if required_team_id and info.team_id != required_team_id:
        error_msg = f"Team ID mismatch: found {info.team_id}, expected {required_team_id}"
        debug_log.error(error_msg)
        audit_log.error(f"Signature verification failed for {path}: {error_msg}")
        errors.append(error_msg)
        return False, errors

    if require_notarized and not info.notarized:
        error_msg = "File is not notarized"
        debug_log.error(error_msg)
        audit_log.error(f"Signature verification failed for {path}: {error_msg}")
        errors.append(error_msg)
        return False, errors

    debug_log.info(f"Signature requirements verified successfully for {path}")
    audit_log.info(
        f"Signature verification passed for {path} "
        f"(team_id={info.team_id}, notarized={info.notarized})"
    )
    return True, []

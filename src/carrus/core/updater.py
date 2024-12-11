# src/carrus/core/updater.py

import aiohttp
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import json
import re
from datetime import datetime
import logging
from packaging import version

logger = logging.getLogger(__name__)

@dataclass
class UpdateInfo:
    """Information about an available update."""
    current_version: str
    latest_version: str
    download_url: str
    release_date: Optional[datetime] = None
    release_notes: Optional[str] = None
    requires_rebuild: bool = False

class UpdateChecker:
    """Base class for update checkers."""

    @staticmethod
    async def create_checker(recipe_type: str) -> 'UpdateChecker':
        """Factory method to create appropriate checker."""
        checkers = {
            "firefox": FirefoxUpdateChecker(),
            # Add more checkers as needed
        }
        return checkers.get(recipe_type, GenericUpdateChecker())

    async def check_update(self, current_version: str) -> Optional[UpdateInfo]:
        """Check for updates. Override in subclasses."""
        raise NotImplementedError

class GenericUpdateChecker(UpdateChecker):
    """Generic update checker that assumes no updates."""

    async def check_update(self, current_version: str) -> Optional[UpdateInfo]:
        """Generic checker always returns None (no updates)."""
        return None

class FirefoxUpdateChecker(UpdateChecker):
    """Firefox-specific update checker."""

    async def check_update(self, current_version: str) -> Optional[UpdateInfo]:
        try:
            async with aiohttp.ClientSession() as session:
                # Check Mozilla's update API
                url = "https://product-details.mozilla.org/1.0/firefox_versions.json"
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch Firefox versions: {response.status}")
                        return None

                    data = await response.json()
                    latest = data.get("LATEST_FIREFOX_VERSION")

                    if not latest:
                        logger.error("No latest version found in Firefox API response")
                        return None

                    try:
                        if version.parse(latest) > version.parse(current_version):
                            download_url = (
                                f"https://download-installer.cdn.mozilla.net/pub/firefox/"
                                f"releases/{latest}/mac/en-US/Firefox%20{latest}.dmg"
                            )
                            return UpdateInfo(
                                current_version=current_version,
                                latest_version=latest,
                                download_url=download_url,
                                requires_rebuild=True
                            )
                    except version.InvalidVersion:
                        logger.error(f"Invalid version comparison: {current_version} vs {latest}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Network error checking Firefox update: {e}")
        except Exception as e:
            logger.error(f"Error checking Firefox update: {e}")

        return None

class MDMPackageBuilder:
    """Creates MDM-ready packages."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.output_dir = self.base_path / "mdm_packages"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def build_kandji_package(
        self,
        app_path: Path,
        recipe_name: str,
        version: str,
        options: Dict[str, Any]
    ) -> Path:
        """Build a Kandji-ready package."""
        # Create package directory
        pkg_name = f"{recipe_name}-{version}"
        pkg_dir = self.output_dir / pkg_name
        pkg_dir.mkdir(exist_ok=True)

        # Create pkginfo
        pkginfo = {
            "name": recipe_name,
            "version": version,
            "display_name": options.get("display_name", recipe_name),
            "description": options.get("description", ""),
            "category": options.get("category", "Applications"),
            "developer": options.get("developer", ""),
            "uninstallable": options.get("uninstallable", True),
            "minimum_os_version": options.get("minimum_os_version", "11.0"),
            "install_check_script": (
                f'#!/bin/zsh\n'
                f'if [[ -e "/Applications/{app_path.name}" ]] ; then\n'
                f'    exit 0\n'
                f'else\n'
                f'    exit 1\n'
                f'fi'
            ),
            "preinstall_script": options.get("preinstall_script", ""),
            "postinstall_script": options.get("postinstall_script", "")
        }

        # Write pkginfo
        with open(pkg_dir / "pkginfo.json", "w") as f:
            json.dump(pkginfo, f, indent=2)

        # Create installcheck script
        install_check = pkg_dir / "installcheck.sh"
        install_check.write_text(pkginfo["install_check_script"])
        install_check.chmod(0o755)

        # Create scripts if provided
        if pkginfo["preinstall_script"]:
            pre = pkg_dir / "preinstall.sh"
            pre.write_text(pkginfo["preinstall_script"])
            pre.chmod(0o755)

        if pkginfo["postinstall_script"]:
            post = pkg_dir / "postinstall.sh"
            post.write_text(pkginfo["postinstall_script"])
            post.chmod(0o755)

        # Create .pkg
        pkg_path = pkg_dir / f"{pkg_name}.pkg"
        result = await asyncio.create_subprocess_exec(
            "pkgbuild",
            "--root", str(app_path.parent),
            "--component-plist", "/dev/null",
            "--install-location", "/Applications",
            str(pkg_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()

        # Create zip for Kandji
        final_path = self.output_dir / f"{pkg_name}.zip"
        zip_proc = await asyncio.create_subprocess_exec(
            "zip", "-r", str(final_path), ".",
            cwd=pkg_dir
        )
        await zip_proc.communicate()

        return final_path

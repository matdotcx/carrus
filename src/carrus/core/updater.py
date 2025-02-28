# src/carrus/core/updater.py

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from packaging import version

from carrus.core.database import Database

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
    async def create_checker(recipe_type: str) -> "UpdateChecker":
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
                                requires_rebuild=True,
                            )
                    except version.InvalidVersion:
                        logger.error(f"Invalid version comparison: {current_version} vs {latest}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Network error checking Firefox update: {e}")
        except Exception as e:
            logger.error(f"Error checking Firefox update: {e}")

        return None


class VersionTracker:
    """Tracks software versions and manages updates."""

    def __init__(self, db: Database):
        """Initialize with database connection."""
        self.db = db

    async def check_for_updates(self, recipe_type: str, package_name: str) -> Optional[UpdateInfo]:
        """Check if updates are available for a specific package."""
        # Get package from database
        package = self.db.get_package_by_name(package_name)
        if not package:
            logger.warning(
                f"Cannot check for updates: Package {package_name} not found in database"
            )
            return None

        # Get current installed version
        current_version = package.get("version", "0.0.0")

        # Get an appropriate checker for the recipe type
        checker = await UpdateChecker.create_checker(recipe_type)

        # Check for updates
        update_info = await checker.check_update(current_version)

        if update_info:
            # Record the new version in the database if it doesn't exist
            if self._compare_versions(update_info.latest_version, current_version) > 0:
                self.db.add_package_version(
                    package_id=package["id"],
                    version=update_info.latest_version,
                    url=update_info.download_url,
                    release_date=update_info.release_date.isoformat()
                    if update_info.release_date
                    else None,
                )

            return update_info

        return None

    def record_version(
        self,
        package_name: str,
        version: str,
        download_url: str,
        checksum: Optional[str] = None,
        release_date: Optional[datetime] = None,
    ) -> bool:
        """Record a new version for a package."""
        # Get package from database
        package = self.db.get_package_by_name(package_name)
        if not package:
            logger.warning(f"Cannot record version: Package {package_name} not found in database")
            return False

        # Add the version
        release_date_str = release_date.isoformat() if release_date else None
        self.db.add_package_version(
            package_id=package["id"],
            version=version,
            url=download_url,
            checksum=checksum,
            release_date=release_date_str,
        )

        return True

    def get_version_history(self, package_name: str) -> List[Dict[str, Any]]:
        """Get version history for a package."""
        package = self.db.get_package_by_name(package_name)
        if not package:
            logger.warning(
                f"Cannot get version history: Package {package_name} not found in database"
            )
            return []

        return self.db.get_package_versions(package["id"])

    def get_available_updates(self) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Get all packages with available updates."""
        updates = []

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Get all packages
            cursor.execute("SELECT * FROM packages")
            packages = [dict(row) for row in cursor.fetchall()]

            for package in packages:
                # Get installed version
                installed_version = self.db.get_installed_version(package["id"])

                # If no installed version, continue
                if not installed_version:
                    continue

                # Get latest available version
                latest_version = self.db.get_latest_version(package["id"])

                # If latest version is newer than installed, add to updates
                if (
                    latest_version
                    and self._compare_versions(
                        latest_version["version"], installed_version["version"]
                    )
                    > 0
                ):
                    updates.append((package, latest_version))

        return updates

    def mark_version_installed(self, package_name: str, version: str) -> bool:
        """Mark a specific version as installed."""
        package = self.db.get_package_by_name(package_name)
        if not package:
            logger.warning(
                f"Cannot mark version installed: Package {package_name} not found in database"
            )
            return False

        # Find the version
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM versions 
                WHERE package_id = ? AND version = ?
                """,
                (package["id"], version),
            )
            result = cursor.fetchone()
            if not result:
                logger.warning(
                    f"Cannot mark version installed: Version {version} not found for {package_name}"
                )
                return False

            version_id = result[0]

        # Mark as installed
        self.db.update_version_installed_status(version_id, installed=True)

        # Update package record
        self.db.update_package_status(package["id"], "installed")

        # Record in history
        self.db.add_install_history(
            package_id=package["id"],
            version=version,
            action="install",
            status="success",
        )

        return True

    @staticmethod
    def _compare_versions(version1: str, version2: str) -> int:
        """
        Compare two version strings.

        Returns:
            1 if version1 > version2
            0 if version1 == version2
            -1 if version1 < version2
        """
        try:
            v1 = version.parse(version1)
            v2 = version.parse(version2)

            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
            else:
                return 0
        except version.InvalidVersion:
            # Fall back to simple string comparison if parsing fails
            if version1 > version2:
                return 1
            elif version1 < version2:
                return -1
            else:
                return 0


class MDMPackageBuilder:
    """Creates MDM-ready packages."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.output_dir = self.base_path / "mdm_packages"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def build_kandji_package(
        self, app_path: Path, recipe_name: str, version: str, options: Dict[str, Any]
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
            "display_name": getattr(options, "display_name", recipe_name),
            "description": getattr(options, "description", ""),
            "category": getattr(options, "category", "Applications"),
            "developer": getattr(options, "developer", ""),
            "uninstallable": getattr(options, "uninstallable", True),
            "minimum_os_version": getattr(options, "minimum_os_version", "11.0"),
            "install_check_script": (
                f"#!/bin/zsh\n"
                f'if [[ -e "/Applications/{app_path.name}" ]] ; then\n'
                f"    exit 0\n"
                f"else\n"
                f"    exit 1\n"
                f"fi"
            ),
            "preinstall_script": getattr(options, "preinstall_script", ""),
            "postinstall_script": getattr(options, "postinstall_script", ""),
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
            "--root",
            str(app_path.parent),
            "--component-plist",
            "/dev/null",
            "--install-location",
            "/Applications",
            str(pkg_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await result.communicate()

        # Create zip for Kandji
        final_path = self.output_dir / f"{pkg_name}.zip"
        zip_proc = await asyncio.create_subprocess_exec(
            "zip", "-r", str(final_path), ".", cwd=pkg_dir
        )
        await zip_proc.communicate()

        return final_path

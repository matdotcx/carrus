"""Tests for the Carrus database implementation."""

import shutil
import tempfile
from pathlib import Path

import pytest

from carrus.core.database import Database, DatabaseError


@pytest.fixture
def db():
    """Provide a test database instance."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    db = Database(db_path)
    yield db
    shutil.rmtree(temp_dir)


class TestDatabaseSetup:
    def test_creates_schema_version(self, db):
        """Test schema version table is created and populated."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version")
            version = cursor.fetchone()[0]
            assert version == 1  # Current schema version

    def test_creates_all_tables(self, db):
        """Test all required tables are created."""
        expected_tables = {
            "schema_version",
            "packages",
            "versions",
            "metadata",
            "install_history",
            "repositories",
            "manifests",
        }

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = {row[0] for row in cursor.fetchall()}
            assert tables == expected_tables


class TestPackageManagement:
    def test_add_package(self, db):
        """Test adding a new package."""
        pkg_id = db.add_package(
            name="Firefox",
            version="123.0",
            install_path="/Applications/Firefox.app",
            checksum="abc123",
        )

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages WHERE id = ?", (pkg_id,))
            package = dict(cursor.fetchone())

            assert package["name"] == "Firefox"
            assert package["version"] == "123.0"
            assert package["install_path"] == "/Applications/Firefox.app"
            assert package["checksum"] == "abc123"
            assert package["status"] == "not_installed"

    def test_update_package_status(self, db):
        """Test updating package status."""
        pkg_id = db.add_package(name="Firefox", version="123.0")

        db.update_package_status(pkg_id, "installed")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM packages WHERE id = ?", (pkg_id,))
            status = cursor.fetchone()[0]
            assert status == "installed"


class TestInstallHistory:
    def test_add_and_retrieve_history(self, db):
        """Test adding and retrieving installation history."""
        # Add a package
        pkg_id = db.add_package(name="Firefox", version="123.0")

        # Add installation history
        db.add_install_history(
            package_id=pkg_id, version="123.0", action="install", status="success"
        )

        # Add another history entry
        db.add_install_history(
            package_id=pkg_id, version="123.0", action="uninstall", status="success"
        )

        # Retrieve history
        history = db.get_package_history(pkg_id)
        assert len(history) == 2
        assert history[0]["action"] == "uninstall"  # Most recent first
        assert history[1]["action"] == "install"


class TestErrorHandling:
    def test_invalid_package_id(self, db):
        """Test error handling for invalid package ID."""
        with pytest.raises(DatabaseError):
            db.update_package_status(999, "installed")

    def test_duplicate_package(self, db):
        """Test error handling for duplicate package."""
        db.add_package("Firefox", "123.0")
        with pytest.raises(DatabaseError):
            db.add_package("Firefox", "123.0")


class TestBackupRestore:
    def test_backup_and_restore(self, db):
        """Test database backup and restore functionality."""
        # Add initial data
        pkg_id = db.add_package(name="Firefox", version="123.0", status="not_installed")

        # Create backup
        backup_path = Path(tempfile.mkdtemp()) / "backup.db"
        db.backup_database(backup_path)

        # Modify database
        db.update_package_status(pkg_id, "installed")

        # Restore from backup
        db.restore_database(backup_path)

        # Verify restored data
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM packages WHERE id = ?", (pkg_id,))
            status = cursor.fetchone()[0]
            assert status == "not_installed"

        # Cleanup backup
        shutil.rmtree(backup_path.parent)


def test_triggers(db):
    """Test that update triggers are working correctly."""
    # Add a package and get its initial timestamps
    pkg_id = db.add_package("Firefox", "123.0")

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, updated_at FROM packages WHERE id = ?", (pkg_id,))
        created_at, updated_at = cursor.fetchone()

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.1)

        # Update the package
        db.update_package_status(pkg_id, "installed")

        # Check timestamps
        cursor.execute("SELECT created_at, updated_at FROM packages WHERE id = ?", (pkg_id,))
        new_created_at, new_updated_at = cursor.fetchone()

        # Created timestamp should not change
        assert created_at == new_created_at
        # Updated timestamp should be newer
        assert new_updated_at > updated_at


class TestVersionTracking:
    """Test the version tracking functionality."""

    def test_add_package_version(self, db):
        """Test adding a new version for a package."""
        # Create a package first
        pkg_id = db.add_package("Firefox", "123.0")

        # Add a version
        version_id = db.add_package_version(
            package_id=pkg_id,
            version="124.0",
            url="https://example.com/firefox-124.0.dmg",
            checksum="abc123",
            release_date="2025-01-15",
        )

        # Get the version and verify
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM versions WHERE id = ?", (version_id,))
            version = dict(cursor.fetchone())

            assert version["package_id"] == pkg_id
            assert version["version"] == "124.0"
            assert version["url"] == "https://example.com/firefox-124.0.dmg"
            assert version["checksum"] == "abc123"
            assert version["release_date"] == "2025-01-15"
            assert version["is_installed"] == 0  # Default is not installed

    def test_update_existing_version(self, db):
        """Test updating an existing version."""
        # Create a package and version
        pkg_id = db.add_package("Firefox", "123.0")
        version_id = db.add_package_version(
            package_id=pkg_id,
            version="124.0",
            url="https://example.com/firefox-124.0.dmg",
            checksum="abc123",
        )

        # Update the version with new info
        updated_id = db.add_package_version(
            package_id=pkg_id,
            version="124.0",  # Same version, should update not create
            url="https://updated.example.com/firefox-124.0.dmg",
            checksum="updated123",
            is_installed=True,
        )

        # Should return the same ID
        assert version_id == updated_id

        # Verify the update
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM versions WHERE id = ?", (version_id,))
            version = dict(cursor.fetchone())

            assert version["url"] == "https://updated.example.com/firefox-124.0.dmg"
            assert version["checksum"] == "updated123"
            assert version["is_installed"] == 1

    def test_get_package_versions(self, db):
        """Test retrieving all versions for a package."""
        # Create a package
        pkg_id = db.add_package("Firefox", "123.0")

        # Add multiple versions
        db.add_package_version(
            package_id=pkg_id,
            version="123.0",
            url="https://example.com/firefox-123.0.dmg",
        )

        db.add_package_version(
            package_id=pkg_id,
            version="124.0",
            url="https://example.com/firefox-124.0.dmg",
        )

        db.add_package_version(
            package_id=pkg_id,
            version="125.0",
            url="https://example.com/firefox-125.0.dmg",
        )

        # Get all versions
        versions = db.get_package_versions(pkg_id)

        # Should have 3 versions, ordered by created_at DESC
        assert len(versions) == 3
        assert versions[0]["version"] == "125.0"  # Latest created
        assert versions[1]["version"] == "124.0"
        assert versions[2]["version"] == "123.0"

    def test_get_latest_version(self, db):
        """Test retrieving the latest version."""
        # Create a package
        pkg_id = db.add_package("Firefox", "123.0")

        # Add multiple versions
        db.add_package_version(
            package_id=pkg_id,
            version="123.0",
            url="https://example.com/firefox-123.0.dmg",
        )

        db.add_package_version(
            package_id=pkg_id,
            version="124.0",
            url="https://example.com/firefox-124.0.dmg",
        )

        # Get the latest version
        latest = db.get_latest_version(pkg_id)

        # Latest should be the most recently added
        assert latest["version"] == "124.0"

    def test_get_installed_version(self, db):
        """Test retrieving the installed version."""
        # Create a package
        pkg_id = db.add_package("Firefox", "123.0")

        # Add multiple versions
        v1_id = db.add_package_version(
            package_id=pkg_id,
            version="123.0",
            url="https://example.com/firefox-123.0.dmg",
        )

        v2_id = db.add_package_version(
            package_id=pkg_id,
            version="124.0",
            url="https://example.com/firefox-124.0.dmg",
        )

        # Mark version 2 as installed
        db.update_version_installed_status(v2_id, installed=True)

        # Get the installed version
        installed = db.get_installed_version(pkg_id)

        # Should be version 2
        assert installed["version"] == "124.0"
        assert installed["is_installed"] == 1

        # Now mark version 1 as installed
        db.update_version_installed_status(v1_id, installed=True)

        # Version 2 should no longer be installed
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_installed FROM versions WHERE id = ?", (v2_id,))
            is_installed = cursor.fetchone()[0]
            assert is_installed == 0

        # Get the installed version again
        installed = db.get_installed_version(pkg_id)

        # Should be version 1 now
        assert installed["version"] == "123.0"

    def test_get_package_by_name(self, db):
        """Test retrieving a package by name."""
        # Add a package
        db.add_package("Firefox", "123.0", status="installed")

        # Retrieve by name
        package = db.get_package_by_name("Firefox")

        assert package is not None
        assert package["name"] == "Firefox"
        assert package["version"] == "123.0"
        assert package["status"] == "installed"

        # Try with a non-existent package
        package = db.get_package_by_name("Chrome")
        assert package is None

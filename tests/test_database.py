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
            'schema_version',
            'packages',
            'versions',
            'metadata',
            'install_history',
            'repositories',
            'manifests'
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
            checksum="abc123"
        )
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages WHERE id = ?", (pkg_id,))
            package = dict(cursor.fetchone())
            
            assert package['name'] == "Firefox"
            assert package['version'] == "123.0"
            assert package['install_path'] == "/Applications/Firefox.app"
            assert package['checksum'] == "abc123"
            assert package['status'] == "not_installed"

    def test_update_package_status(self, db):
        """Test updating package status."""
        pkg_id = db.add_package(
            name="Firefox",
            version="123.0"
        )
        
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
        pkg_id = db.add_package(
            name="Firefox",
            version="123.0"
        )
        
        # Add installation history
        db.add_install_history(
            package_id=pkg_id,
            version="123.0",
            action="install",
            status="success"
        )
        
        # Add another history entry
        db.add_install_history(
            package_id=pkg_id,
            version="123.0",
            action="uninstall",
            status="success"
        )
        
        # Retrieve history
        history = db.get_package_history(pkg_id)
        assert len(history) == 2
        assert history[0]['action'] == "uninstall"  # Most recent first
        assert history[1]['action'] == "install"

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
        pkg_id = db.add_package(
            name="Firefox",
            version="123.0",
            status="not_installed"
        )
        
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

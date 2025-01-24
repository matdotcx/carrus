"""Database management and schema for Carrus."""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

class DatabaseError(Exception):
    """Base exception for database errors."""
    pass

class MigrationError(DatabaseError):
    """Raised when database migration fails."""
    pass

class Database:
    """Core database management class."""
    
    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic closing."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        try:
            with self.get_connection() as conn:
                # Check schema version
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                result = cursor.fetchone()
                current_version = result[0] if result else 0

                if current_version < SCHEMA_VERSION:
                    self._apply_migrations(conn, current_version)
                
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to initialize database: {e}") from e

    def _apply_migrations(self, conn: sqlite3.Connection, current_version: int):
        """Apply necessary database migrations."""
        try:
            cursor = conn.cursor()
            
            # Core tables
            if current_version < 1:
                # Packages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS packages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        install_path TEXT,
                        install_date TIMESTAMP,
                        checksum TEXT,
                        status TEXT DEFAULT 'not_installed',
                        created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                        updated_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                        UNIQUE(name, version)
                    )
                """)

                # Package versions
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        package_id INTEGER NOT NULL,
                        version TEXT NOT NULL,
                        url TEXT NOT NULL,
                        checksum TEXT,
                        release_date TIMESTAMP,
                        is_installed BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE
                    )
                """)

                # Package metadata
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        package_id INTEGER NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE,
                        UNIQUE(package_id, key)
                    )
                """)

                # Installation history
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS install_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        package_id INTEGER NOT NULL,
                        version TEXT NOT NULL,
                        action TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE
                    )
                """)

                # Repositories (enhanced)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS repositories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        url TEXT,
                        path TEXT NOT NULL,
                        branch TEXT,
                        last_sync TIMESTAMP,
                        active BOOLEAN DEFAULT 1,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Manifests (enhanced)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS manifests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        repo_id INTEGER NOT NULL,
                        category TEXT,
                        path TEXT NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
                        UNIQUE(name, repo_id)
                    )
                """)

                # Update triggers
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_package_timestamp 
                    AFTER UPDATE ON packages
                    BEGIN
                        UPDATE packages SET updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                        WHERE id = NEW.id;
                    END;
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_metadata_timestamp
                    AFTER UPDATE ON metadata
                    BEGIN
                        UPDATE metadata SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = NEW.id;
                    END;
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_repository_timestamp
                    AFTER UPDATE ON repositories
                    BEGIN
                        UPDATE repositories SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = NEW.id;
                    END;
                """)

                # Record schema version
                cursor.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,)
                )

                conn.commit()

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Migration failed: {e}")
            raise MigrationError(f"Failed to apply migrations: {e}") from e

    def add_package(self, name: str, version: str, install_path: Optional[str] = None,
                   checksum: Optional[str] = None, status: str = "not_installed") -> int:
        """Add a new package to the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO packages (name, version, install_path, checksum, status)
                    VALUES (?, ?, ?, ?, ?)
                    """, (name, version, install_path, checksum, status))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to add package: {e}") from e

    def update_package_status(self, package_id: int, status: str):
        """Update package installation status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM packages WHERE id = ?", (package_id,))
                if not cursor.fetchone():
                    raise DatabaseError(f"Package with ID {package_id} not found")
                
                cursor.execute("""
                    UPDATE packages 
                    SET status = ? 
                    WHERE id = ?
                    """, (status, package_id))
                conn.commit()
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to update package status: {e}") from e

    def add_install_history(self, package_id: int, version: str, action: str,
                          status: str, error_message: Optional[str] = None):
        """Record package installation history."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO install_history 
                    (package_id, version, action, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                    """, (package_id, version, action, status, error_message))
                conn.commit()
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to add install history: {e}") from e

    def get_package_history(self, package_id: int) -> List[Dict[str, Any]]:
        """Get installation history for a package."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM install_history
                    WHERE package_id = ?
                    ORDER BY id DESC
                    """, (package_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to get package history: {e}") from e

    def backup_database(self, backup_path: Path):
        """Create a backup of the database."""
        try:
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to create database backup: {e}") from e

    def restore_database(self, backup_path: Path):
        """Restore database from backup."""
        if not backup_path.exists():
            raise DatabaseError(f"Backup file not found: {backup_path}")
        
        try:
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(backup_path)
                backup_conn.backup(conn)
                backup_conn.close()
        except sqlite3.Error as e:
                        raise DatabaseError(f"Failed to restore database: {e}") from e

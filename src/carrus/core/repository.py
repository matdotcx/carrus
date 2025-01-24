# src/carrus/core/repository.py

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml
from rich.table import Table


@dataclass
class RepoMetadata:
    """Repository metadata."""
    name: str
    description: str
    maintainer: str
    url: Optional[str] = None
    branch: Optional[str] = None

class RepositoryManager:
    """Manages manifest repositories."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "repos.db"
        self._init_db()

    def _init_db(self):
        """Initialize the repository database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS repositories (
                    name TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    url TEXT,
                    metadata TEXT,
                    active BOOLEAN DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS manifests (
                    name TEXT,
                    repo_name TEXT,
                    category TEXT,
                    path TEXT,
                    metadata TEXT,
                    UNIQUE(name, repo_name)
                )
            """)

    def add_repository(self, path: Path, name: Optional[str] = None) -> RepoMetadata:
        """Add a repository to the system."""
        path = Path(path).resolve()

        if not path.exists():
            raise ValueError(f"Repository path does not exist: {path}")

        # Read repository metadata
        repo_yaml = path / "repo.yaml"
        if not repo_yaml.exists():
            raise ValueError(f"No repo.yaml found in {path}")

        with open(repo_yaml) as f:
            repo_data = yaml.safe_load(f)
            metadata = RepoMetadata(
                name=name or repo_data.get('name'),
                description=repo_data.get('description', ''),
                maintainer=repo_data.get('maintainer', ''),
                url=repo_data.get('url'),
                branch=repo_data.get('branch')
            )

        # Check for manifests directory
        manifests_dir = path / "manifests"
        if not manifests_dir.exists():
            raise ValueError(f"No manifests directory found in {path}")

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO repositories (name, path, url, metadata) VALUES (?, ?, ?, ?)",
                (metadata.name, str(path), metadata.url, json.dumps(repo_data))
            )

            # Index manifests
            for manifest_path in manifests_dir.rglob("*.yaml"):
                if manifest_path.name == "repo.yaml":
                    continue

                category = manifest_path.parent.relative_to(manifests_dir).as_posix()
                if category == ".":
                    category = "uncategorized"

                conn.execute(
                    "INSERT OR REPLACE INTO manifests (name, repo_name, category, path) VALUES (?, ?, ?, ?)",
                    (manifest_path.stem, metadata.name, category, str(manifest_path))
                )

        return metadata

    def list_manifests(self, category: Optional[str] = None) -> Table:
        """List all manifests in a rich table."""
        table = Table(title="Available Packages")
        table.add_column("Name", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Repository", style="yellow")
        table.add_column("Description", style="white")

        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT
                    manifests.name,
                    manifests.category,
                    repositories.name as repo_name,
                    manifests.metadata
                FROM manifests
                JOIN repositories ON manifests.repo_name = repositories.name
                WHERE repositories.active = 1
            """

            if category:
                query += " AND manifests.category = ?"
                params = (category,)
            else:
                params = ()

            query += " ORDER BY manifests.category, manifests.name"

            for row in conn.execute(query, params):
                metadata = json.loads(row[3] or '{}')
                table.add_row(
                    row[0],
                    row[1],
                    row[2],
                    metadata.get('description', '')
                )

        return table

    def search_manifests(self, term: str, category: Optional[str] = None) -> List[dict]:
        """Search for manifests."""
        results = []
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT
                    manifests.name,
                    manifests.category,
                    repositories.name as repo_name,
                    manifests.metadata
                FROM manifests
                JOIN repositories ON manifests.repo_name = repositories.name
                WHERE repositories.active = 1
            """

            params = []
            if category:
                query += " AND manifests.category = ?"
                params.append(category)

            if term:
                query += " AND (manifests.name LIKE ? OR manifests.metadata LIKE ?)"
                params.extend([f"%{term}%", f"%{term}%"])

            query += " ORDER BY manifests.category, manifests.name"

            for row in conn.execute(query, params):
                metadata = json.loads(row[3] or '{}')
                results.append({
                    'name': row[0],
                    'category': row[1],
                    'repo_name': row[2],
                    'description': metadata.get('description', '')
                })

        return results

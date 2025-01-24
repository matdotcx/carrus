"""Tests for repository management."""
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from carrus.core.repository import (
    clone_repository,
    sync_repository,
    load_recipes,
)

@pytest.fixture
def mock_repo_dir():
    """Create a mock repository directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)

def test_repository_cloning(mock_repo_dir):
    """Test Git repository cloning."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        clone_repository(
            "https://github.com/example/repo.git",
            mock_repo_dir
        )
        assert mock_run.call_count == 1

def test_repository_sync(mock_repo_dir):
    """Test repository synchronization."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        sync_repository(mock_repo_dir)
        assert mock_run.call_count >= 1

def test_recipe_discovery(mock_repo_dir):
    """Test finding recipes in repository."""
    # Create mock recipe files
    recipe_dir = mock_repo_dir / "recipes"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "firefox.yaml").touch()
    (recipe_dir / "chrome.yaml").touch()
    
    recipes = load_recipes(mock_repo_dir)
    assert len(recipes) == 2

def test_recipe_inheritance_chain():
    """Test recipe inheritance resolution."""
    recipes = {
        "base": {"team_id": "ABC123"},
        "firefox": {"parent": "base", "version": "115.0"}
    }
    # Test inheritance resolution
    resolved = resolve_inheritance(recipes)
    assert resolved["firefox"]["team_id"] == "ABC123"
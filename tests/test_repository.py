"""Tests for repository management."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from carrus.core.manifests import Manifest
from carrus.core.config import get_repo_dir


@pytest.fixture
def mock_repo_dir():
    """Create a mock repository directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def test_repo_structure(mock_repo_dir):
    """Test repository directory structure."""
    manifests_dir = mock_repo_dir / "manifests"
    manifests_dir.mkdir(parents=True)
    
    # Create mock recipe files
    (manifests_dir / "browsers").mkdir()
    (manifests_dir / "browsers/firefox.yaml").touch()
    (manifests_dir / "utilities").mkdir()
    (manifests_dir / "utilities/rectangle.yaml").touch()

    assert (manifests_dir / "browsers/firefox.yaml").exists()
    assert (manifests_dir / "utilities/rectangle.yaml").exists()


def test_manifest_loading(mock_repo_dir):
    """Test loading manifests from repository."""
    manifests_dir = mock_repo_dir / "manifests"
    manifests_dir.mkdir(parents=True)
    
    manifest_data = """
    name: Firefox
    version: "115.0"
    type: "app"
    url: "https://download.mozilla.org/?product=firefox-{version}"
    """
    
    firefox_yaml = manifests_dir / "firefox.yaml"
    firefox_yaml.write_text(manifest_data)

    manifest = Manifest.from_yaml(firefox_yaml)
    assert manifest.name == "Firefox"
    assert manifest.version == "115.0"


def test_repo_dir_config():
    """Test repository directory configuration."""
    with patch("carrus.core.config.get_config_dir") as mock_config_dir:
        mock_config_dir.return_value = Path("/test/config/carrus")
        repo_dir = get_repo_dir()
        assert repo_dir == Path("/test/config/carrus/repos")
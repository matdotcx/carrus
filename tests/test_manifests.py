"""Tests for recipe manifest handling."""
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from carrus.core.manifests import (
    Recipe,  # Assuming dataclass
    construct_url,
    load_manifest,
    parse_version,
)


@pytest.fixture
def mock_recipe_file():
    """Create a mock recipe file."""
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmp:
        yield Path(tmp.name)

def test_recipe_loading(mock_recipe_file):
    """Test loading recipe from YAML."""
    recipe_data = """
    name: Firefox
    version: "115.0"
    url: "https://download.mozilla.org/?product=firefox-{version}"
    team_id: "43AQ936H96"
    """
    with patch("builtins.open", mock_open(read_data=recipe_data)):
        recipe = load_manifest(mock_recipe_file)
        assert recipe.name == "Firefox"
        assert recipe.version == "115.0"

def test_version_extraction():
    """Test version string parsing."""
    assert parse_version("Firefox 115.0.dmg") == "115.0"
    assert parse_version("Chrome 120.0.6099.129.pkg") == "120.0.6099.129"

def test_url_construction():
    """Test download URL construction."""
    recipe = Recipe(
        name="Firefox",
        version="115.0",
        url="https://download.mozilla.org/?product=firefox-{version}"
    )
    url = construct_url(recipe)
    assert url == "https://download.mozilla.org/?product=firefox-115.0"

def test_parent_recipe_inheritance():
    """Test recipe inheritance chain."""
    parent_data = """
    name: BrowserBase
    team_id: "43AQ936H96"
    """
    child_data = """
    parent: BrowserBase
    name: Firefox
    version: "115.0"
    """
    with patch("builtins.open") as mock_file:
        mock_file.side_effect = [
            mock_open(read_data=child_data).return_value,
            mock_open(read_data=parent_data).return_value
        ]
        recipe = load_manifest(Path("firefox.yaml"))
        assert recipe.team_id == "43AQ936H96"  # Inherited
        assert recipe.name == "Firefox"  # Overridden

def test_version_validation():
    """Test version format validation."""
    with pytest.raises(ValueError):
        Recipe(name="Test", version="invalid")
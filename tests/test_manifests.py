"""Tests for recipe manifest handling."""
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from carrus.core.manifests import (
    Manifest,
    CodeSignRequirements,
    BuildOptions,
    KandjiOptions,
    MDMOptions,
)


@pytest.fixture
def mock_recipe_file():
    """Create a mock recipe file."""
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmp:
        yield Path(tmp.name)


def test_manifest_loading(mock_recipe_file):
    """Test loading manifest from YAML."""
    recipe_data = """
    name: Firefox
    version: "115.0"
    type: app
    url: "https://download.mozilla.org/?product=firefox-{version}"
    code_sign:
        team_id: "43AQ936H96"
        require_notarized: true
    """
    with patch("builtins.open", mock_open(read_data=recipe_data)):
        manifest = Manifest.from_yaml(mock_recipe_file)
        assert manifest.name == "Firefox"
        assert manifest.version == "115.0"
        assert manifest.code_sign.team_id == "43AQ936H96"


def test_build_options():
    """Test build options configuration."""
    build_opts = BuildOptions(
        type="pkg",
        destination="/Applications",
        customize=[{"action": "set_ownership", "user": "root", "group": "wheel"}]
    )
    assert build_opts.type == "pkg"
    assert build_opts.destination == "/Applications"
    assert build_opts.customize[0]["action"] == "set_ownership"


def test_kandji_options():
    """Test Kandji MDM options."""
    kandji_opts = KandjiOptions(
        display_name="Firefox Browser",
        category="Web Browsers",
        minimum_os_version="12.0"
    )
    assert kandji_opts.display_name == "Firefox Browser"
    assert kandji_opts.category == "Web Browsers"
    assert kandji_opts.minimum_os_version == "12.0"


def test_manifest_build_config():
    """Test build configuration extraction."""
    manifest = Manifest(
        name="Firefox",
        version="115.0",
        type="app",
        url="https://example.com/firefox.dmg",
        build=BuildOptions(
            type="pkg",
            destination="/Applications"
        )
    )
    build_config = manifest.get_build_config()
    assert build_config is not None
    assert build_config.type == "pkg"
    assert build_config.destination == "/Applications"
"""Tests for package building."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from carrus.core.builder import (
    build_package,
    inject_scripts,
    create_dmg,
)

@pytest.fixture
def mock_build_dir():
    """Create a mock build directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)

@pytest.fixture
def mock_app():
    """Create a mock app bundle."""
    with tempfile.NamedTemporaryFile(suffix=".app") as tmp:
        yield Path(tmp.name)

def test_package_building(mock_build_dir, mock_app):
    """Test converting app to pkg."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        pkg_path = build_package(mock_app, mock_build_dir)
        assert pkg_path.suffix == ".pkg"
        assert mock_run.call_count >= 1

def test_script_injection(mock_build_dir):
    """Test adding pre/post install scripts."""
    scripts = {
        "preinstall": "echo 'Installing...'",
        "postinstall": "echo 'Done!'"
    }
    script_paths = inject_scripts(scripts, mock_build_dir)
    assert len(script_paths) == 2
    for path in script_paths.values():
        assert path.exists()
        assert path.stat().st_mode & 0o111  # Check executable

def test_dmg_creation(mock_build_dir, mock_app):
    """Test creating DMG from app."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        dmg_path = create_dmg(mock_app, mock_build_dir)
        assert dmg_path.suffix == ".dmg"
        assert mock_run.call_count >= 1

def test_failed_build(mock_build_dir, mock_app):
    """Test handling build failures."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        with pytest.raises(Exception):
            build_package(mock_app, mock_build_dir)
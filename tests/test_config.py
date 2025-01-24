"""Tests for configuration handling."""
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from carrus.core.config import (
    load_config,
    save_config,
    get_default_config,
    Config,  # Assuming dataclass
)

@pytest.fixture
def mock_config_file():
    """Create a mock config file."""
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmp:
        yield Path(tmp.name)

def test_config_creation():
    """Test Config dataclass creation."""
    config = Config(
        db_path="test.db",
        log_dir="logs",
        repo_url="https://example.com/repo.git"
    )
    assert config.db_path == "test.db"
    assert config.log_dir == "logs"
    assert config.repo_url == "https://example.com/repo.git"

def test_load_config(mock_config_file):
    """Test loading configuration from file."""
    config_data = """
    db_path: test.db
    log_dir: logs
    repo_url: https://example.com/repo.git
    """
    with patch("builtins.open", mock_open(read_data=config_data)):
        config = load_config(mock_config_file)
        assert config.db_path == "test.db"
        assert config.log_dir == "logs"

def test_save_config(mock_config_file):
    """Test saving configuration to file."""
    config = Config(
        db_path="test.db",
        log_dir="logs"
    )
    with patch("builtins.open", mock_open()) as mock_file:
        save_config(config, mock_config_file)
        mock_file().write.assert_called_once()

def test_get_default_config():
    """Test default configuration values."""
    config = get_default_config()
    assert config.db_path is not None
    assert config.log_dir is not None

def test_env_override():
    """Test environment variable overrides."""
    with patch.dict('os.environ', {'CARRUS_DB_PATH': 'env.db'}):
        config = get_default_config()
        assert config.db_path == "env.db"
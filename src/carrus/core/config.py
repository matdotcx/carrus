# src/carrus/core/config.py
import os
from pathlib import Path


def get_config_dir() -> Path:
    """Get the carrus configuration directory."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return Path(xdg_config_home).expanduser() / "carrus"

def get_repo_dir() -> Path:
    """Get the repository storage directory."""
    return get_config_dir() / "repos"

def ensure_dirs() -> tuple[Path, Path]:
    """Ensure all required directories exist."""
    config_dir = get_config_dir()
    repo_dir = get_repo_dir()
    
    config_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir, repo_dir

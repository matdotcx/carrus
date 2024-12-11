# src/carrus/core/types.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from pathlib import Path

class BuildType(Enum):
    """Types of builds we support."""
    APP_DMG = "app_dmg"      # Application in DMG format
    APP_PKG = "app_pkg"      # Application in PKG format
    APP_ZIP = "app_zip"      # Application in ZIP format
    PKG = "pkg"             # Generic PKG
    MANUAL = "manual"       # Custom build steps

@dataclass
class BuildConfig:
    """Build configuration."""
    type: str
    destination: str = "/Applications"
    preserve_temp: bool = False
    sign: Optional[Dict[str, str]] = None
    customize: Optional[List[Dict[str, Any]]] = None

@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    output_path: Optional[Path] = None
    temp_dir: Optional[Path] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

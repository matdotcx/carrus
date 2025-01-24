# src/carrus/core/types.py

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class BuildType(Enum):
    """Types of builds we support."""
    APP_DMG = "app_dmg"      # Application in DMG format
    APP_PKG = "app_pkg"      # Application in PKG format
    APP_ZIP = "app_zip"      # Application in ZIP format
    PKG = "pkg"             # Generic PKG
    MANUAL = "manual"       # Custom build steps

class BuildStep(Enum):
    """Steps in the build process."""
    INIT = "initialization"
    VALIDATION = "validation"
    MOUNTING = "mounting"
    EXTRACTION = "extraction"
    COPYING = "copying"
    CUSTOMIZATION = "customization"
    PACKAGING = "packaging"
    CLEANUP = "cleanup"

@dataclass
class BuildConfig:
    """Build configuration."""
    type: str
    destination: str = "/Applications"
    preserve_temp: bool = False
    sign: Optional[Dict[str, str]] = None
    customize: Optional[List[Dict[str, Any]]] = None

@dataclass
class BuildState:
    """Tracks the state of a build operation."""
    started_at: datetime
    build_type: str
    source_path: Path
    destination: Path
    temp_files: List[Path] = field(default_factory=list)
    current_step: BuildStep = BuildStep.INIT
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_temp_file(self, path: Path):
        """Track a temporary file for cleanup."""
        self.temp_files.append(path)

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)

    def cleanup(self) -> List[str]:
        """Clean up temporary files and return any cleanup errors."""
        cleanup_errors = []
        for path in self.temp_files:
            try:
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except Exception as e:
                cleanup_errors.append(f"Failed to clean up {path}: {e}")
        return cleanup_errors

@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    output_path: Optional[Path] = None
    temp_dir: Optional[Path] = None
    build_state: Optional[BuildState] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

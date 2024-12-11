# src/carrus/core/manifests.py

from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import yaml
from .types import BuildType, BuildConfig

class CodeSignRequirements(BaseModel):
    """Code signing requirements for a package."""
    team_id: Optional[str] = None
    require_notarized: bool = True
    authorities: Optional[List[str]] = None

class BuildOptions(BaseModel):
    """Build options for a package."""
    type: str
    destination: Optional[str] = "/Applications"
    preserve_temp: bool = False
    sign: Optional[Dict[str, str]] = None
    customize: Optional[List[Dict[str, Any]]] = None

class KandjiOptions(BaseModel):
    """Kandji-specific MDM options."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: str = "Applications"
    developer: Optional[str] = None
    minimum_os_version: str = "11.0"
    uninstallable: bool = True
    preinstall_script: Optional[str] = None
    postinstall_script: Optional[str] = None

class MDMOptions(BaseModel):
    """MDM-specific options."""
    kandji: Optional[KandjiOptions] = None

class Manifest(BaseModel):
    """Manifest definition."""
    name: str
    version: str
    type: str
    url: str
    checksum: Optional[str] = None
    filename: Optional[str] = None
    code_sign: Optional[CodeSignRequirements] = None
    build: Optional[BuildOptions] = None
    mdm: Optional[MDMOptions] = None

    @classmethod
    def from_yaml(cls, path: Path) -> "Manifest":
        """Load a manifest from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
            return cls(**data)

    def get_build_config(self) -> Optional[BuildConfig]:
        """Get build configuration from manifest."""
        if not self.build:
            return None

        return BuildConfig(
            type=self.build.type,
            destination=self.build.destination,
            preserve_temp=self.build.preserve_temp,
            sign=self.build.sign,
            customize=self.build.customize
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to a dictionary."""
        return self.dict(exclude_none=True)

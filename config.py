"""
Configuration paths, security guards, and data models.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

HOME = Path.home()
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local" / "share"))
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
XDG_CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache"))
XDG_STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local" / "state"))

ADOPT_HOME = XDG_DATA_HOME / "adopt"
APPS_DIR = ADOPT_HOME / "apps"
BIN_DIR = HOME / ".local" / "bin"
APPLICATIONS_DIR = XDG_DATA_HOME / "applications"
ICONS_DIR = XDG_DATA_HOME / "icons"
PIXMAPS_DIR = XDG_DATA_HOME / "pixmaps"

# Absolute protected paths that must never be deleted
PROTECTED_PATHS: Set[Path] = {
    HOME.resolve(),
    XDG_DATA_HOME.resolve(),
    XDG_CONFIG_HOME.resolve(),
    XDG_CACHE_HOME.resolve(),
    XDG_STATE_HOME.resolve(),
    BIN_DIR.resolve(),
    APPLICATIONS_DIR.resolve(),
    ICONS_DIR.resolve(),
    PIXMAPS_DIR.resolve(),
    ADOPT_HOME.resolve(),
    APPS_DIR.resolve(),
    Path("/").resolve(),
    Path("/home").resolve(),
    Path("/usr").resolve(),
    Path("/etc").resolve(),
    Path("/var").resolve(),
    Path("/tmp").resolve(),
    (HOME / ".pki").resolve(),
    (HOME / ".bashrc").resolve(),
    (HOME / ".zshrc").resolve(),
    (HOME / ".profile").resolve(),
}

# Generic words that cannot be used as blind trace search keys
BLACKLISTED_KEYS: Set[str] = {
    "app", "application", "desktop", "linux", "bin", "share", "data",
    "cache", "config", "state", "system", "local", "root", "usr",
    "var", "etc", "tmp", "home", "opt", "org", "com", "net", "io",
    "main", "ui", "gui", "client", "player", "node", "electron", "java",
    "x86_64", "amd64", "i386", "arm64", "aarch64", "appimage", "run"
}


@dataclasses.dataclass
class AppManifest:
    id: str
    name: str
    version: str
    exec_name: str
    wm_class: str
    comment: str
    categories: List[str]
    installed_at: str
    updated_at: str
    appimage_path: str
    original_filename: str
    binary_sha256: str
    binary_size: int
    desktop_file: str
    icon_files: List[str]
    wrapper_file: str
    portable: bool
    trace_identifiers: List[str]
    source_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AppManifest:
        fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in fields}
        if "trace_identifiers" not in filtered:
            filtered["trace_identifiers"] = [filtered.get("id", "")]
        if "source_url" not in filtered:
            filtered["source_url"] = None
        return cls(**filtered)

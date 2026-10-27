"""
AppImage ELF inspection and asset extraction without FUSE.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from adopt.utils import calculate_sha256
except ImportError:
    from utils import calculate_sha256


def make_executable(path: Path) -> None:
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


class AppImageInspector:
    def __init__(self, appimage_path: Path):
        self.path = appimage_path.resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"AppImage not found: {self.path}")

    def inspect_binary(self) -> Dict[str, Any]:
        file_size = self.path.stat().st_size
        sha256 = calculate_sha256(self.path)

        app_type = "Type 2 (Squashfs)"
        offset = None

        try:
            res = subprocess.run(
                [str(self.path), "--appimage-offset"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip().isdigit():
                offset = int(res.stdout.strip())
        except Exception:
            pass

        arch = "x86_64"
        try:
            with open(self.path, "rb") as f:
                hdr = f.read(20)
                if hdr.startswith(b"\x7fELF"):
                    e_machine = int.from_bytes(hdr[18:20], "little")
                    if e_machine == 0x3E:
                        arch = "x86_64"
                    elif e_machine == 0xB7:
                        arch = "aarch64"
                    elif e_machine == 0x03:
                        arch = "i386"
                    elif e_machine == 0x28:
                        arch = "arm"
        except Exception:
            pass

        return {
            "path": str(self.path),
            "size": file_size,
            "sha256": sha256,
            "type": app_type,
            "offset": offset,
            "arch": arch,
        }

    def extract_assets(self, work_dir: Path) -> Tuple[Optional[Path], List[Path]]:
        make_executable(self.path)
        work_dir.mkdir(parents=True, exist_ok=True)
        squash_root = work_dir / "squashfs-root"

        patterns = ["*.desktop", ".DirIcon", "*.png", "*.svg", "usr/share/icons/*"]
        has_desktop = False
        has_icon = False

        for pat in patterns:
            try:
                subprocess.run(
                    [str(self.path), "--appimage-extract", pat],
                    cwd=work_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            except Exception:
                pass

            if squash_root.exists():
                if not has_desktop:
                    has_desktop = bool(list(squash_root.glob("*.desktop")) + list(squash_root.glob("usr/share/applications/*.desktop")))
                if not has_icon:
                    has_icon = (squash_root / ".DirIcon").exists() or bool(list(squash_root.rglob("*.png"))) or bool(list(squash_root.rglob("*.svg")))
                if has_desktop and has_icon:
                    break

        if not squash_root.exists() or not any(squash_root.iterdir()):
            try:
                subprocess.run(
                    [str(self.path), "--appimage-extract"],
                    cwd=work_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            except Exception:
                pass

        if not squash_root.exists():
            return None, []

        desktop_candidates = list(squash_root.glob("*.desktop")) + list(squash_root.glob("usr/share/applications/*.desktop"))
        desktop_file = desktop_candidates[0] if desktop_candidates else None

        icon_candidates: List[Path] = []
        dir_icon = squash_root / ".DirIcon"
        if dir_icon.exists():
            icon_candidates.append(dir_icon)

        for p in squash_root.rglob("*.png"):
            if p not in icon_candidates:
                icon_candidates.append(p)
        for p in squash_root.rglob("*.svg"):
            if p not in icon_candidates:
                icon_candidates.append(p)

        return desktop_file, icon_candidates

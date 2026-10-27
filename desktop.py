"""
Desktop entry creation, icon synthesis, and Freedesktop database synchronization.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from adopt.config import APPLICATIONS_DIR, ICONS_DIR, PIXMAPS_DIR, AppManifest
except ImportError:
    from config import APPLICATIONS_DIR, ICONS_DIR, PIXMAPS_DIR, AppManifest


class DesktopParser:
    @staticmethod
    def parse(file_path: Path) -> Dict[str, str]:
        data: Dict[str, str] = {}
        if not file_path or not file_path.exists():
            return data
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                in_entry = False
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line == "[Desktop Entry]":
                        in_entry = True
                        continue
                    elif line.startswith("[") and in_entry:
                        break
                    if in_entry and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if "[" not in k and k not in data:
                            data[k] = v
        except Exception:
            pass
        return data


def generate_desktop_file(manifest: AppManifest, icon_id: str) -> Path:
    desktop_path = APPLICATIONS_DIR / f"adopt-{manifest.id}.desktop"
    exec_target = f"{manifest.wrapper_file} %U"

    categories_str = ";".join(manifest.categories)
    if categories_str and not categories_str.endswith(";"):
        categories_str += ";"
    if not categories_str:
        categories_str = "Utility;Application;"

    comment_val = manifest.comment or f"{manifest.name} (managed by adopt)"
    wm_class_line = f"StartupWMClass={manifest.wm_class}\n" if manifest.wm_class else ""

    content = f"""[Desktop Entry]
Type=Application
Name={manifest.name}
GenericName={manifest.name}
Comment={comment_val}
Exec={exec_target}
Icon={icon_id}
Terminal=false
Categories={categories_str}
{wm_class_line}Keywords=adopt;appimage;{manifest.name};{manifest.id};
X-Adopt-ID={manifest.id}
X-Adopt-Managed=true
X-Adopt-Version={manifest.version}
"""
    desktop_path.write_text(content, encoding="utf-8")
    return desktop_path


def get_png_dimensions(path: Path) -> Optional[Tuple[int, int]]:
    try:
        with open(path, "rb") as f:
            header = f.read(24)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                width = int.from_bytes(header[16:20], "big")
                height = int.from_bytes(header[20:24], "big")
                return (width, height)
    except Exception:
        pass
    return None


def generate_svg_icon(name: str, dest_path: Path) -> None:
    initial = (name.strip()[:1] or "A").upper()
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#38bdf8;stop-opacity:1" />
      <stop offset="50%" style="stop-color:#6366f1;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#a855f7;stop-opacity:1" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-opacity="0.3"/>
    </filter>
  </defs>
  <rect width="232" height="232" x="12" y="12" rx="52" fill="url(#grad)" filter="url(#shadow)"/>
  <text x="128" y="165" font-family="system-ui, -apple-system, sans-serif" font-size="115" font-weight="800" fill="#ffffff" text-anchor="middle">{initial}</text>
</svg>"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(svg_content, encoding="utf-8")


def install_app_icons(app_id: str, app_name: str, extracted_icons: List[Path]) -> List[str]:
    installed_icon_paths: List[str] = []
    icon_id = f"adopt-{app_id}"
    icon_installed = False

    svg_candidates = [i for i in extracted_icons if i.suffix.lower() == ".svg"]
    if svg_candidates:
        target_svg = ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{icon_id}.svg"
        target_svg.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(svg_candidates[0], target_svg)
        installed_icon_paths.append(str(target_svg))

        target_pixmap = PIXMAPS_DIR / f"{icon_id}.svg"
        target_pixmap.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(svg_candidates[0], target_pixmap)
        installed_icon_paths.append(str(target_pixmap))
        icon_installed = True

    png_candidates = [i for i in extracted_icons if i.suffix.lower() == ".png" or i.name == ".DirIcon"]
    for icon_src in png_candidates:
        dims = get_png_dimensions(icon_src)
        if dims and dims[0] == dims[1]:
            size_folder = f"{dims[0]}x{dims[1]}"
            target_png = ICONS_DIR / "hicolor" / size_folder / "apps" / f"{icon_id}.png"
        else:
            target_png = ICONS_DIR / "hicolor" / "256x256" / "apps" / f"{icon_id}.png"

        target_png.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(icon_src, target_png)
            installed_icon_paths.append(str(target_png))

            pixmap_png = PIXMAPS_DIR / f"{icon_id}.png"
            pixmap_png.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(icon_src, pixmap_png)
            installed_icon_paths.append(str(pixmap_png))
            icon_installed = True
        except Exception:
            pass

    if not icon_installed:
        fallback_svg = ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{icon_id}.svg"
        generate_svg_icon(app_name, fallback_svg)
        installed_icon_paths.append(str(fallback_svg))

        pixmap_fallback = PIXMAPS_DIR / f"{icon_id}.svg"
        generate_svg_icon(app_name, pixmap_fallback)
        installed_icon_paths.append(str(pixmap_fallback))

    return installed_icon_paths


def update_system_databases() -> None:
    if shutil.which("update-desktop-database"):
        subprocess.run(
            ["update-desktop-database", str(APPLICATIONS_DIR)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if shutil.which("gtk-update-icon-cache"):
        hicolor_dir = ICONS_DIR / "hicolor"
        if hicolor_dir.exists():
            subprocess.run(
                ["gtk-update-icon-cache", "-q", "-t", "-f", str(hicolor_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    for kbuild in ["kbuildsycoca6", "kbuildsycoca5"]:
        if shutil.which(kbuild):
            subprocess.run(
                [kbuild, "--noincremental"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            break

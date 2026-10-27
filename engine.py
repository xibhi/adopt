"""
Direct, minimal lifecycle engine for adoption, updates, and zero-trace eradication.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from adopt.config import (
        APPLICATIONS_DIR,
        APPS_DIR,
        BIN_DIR,
        BLACKLISTED_KEYS,
        HOME,
        ICONS_DIR,
        PIXMAPS_DIR,
        PROTECTED_PATHS,
        XDG_CACHE_HOME,
        XDG_CONFIG_HOME,
        XDG_DATA_HOME,
        XDG_STATE_HOME,
        AppManifest,
    )
    from adopt.desktop import (
        DesktopParser,
        generate_desktop_file,
        generate_svg_icon,
        install_app_icons,
        update_system_databases,
    )
    from adopt.inspector import AppImageInspector, make_executable
    from adopt.utils import (
        Style,
        c,
        calculate_sha256,
        format_size,
        get_dir_size,
        get_running_app_pids,
        terminate_running_app,
    )
except ImportError:
    from config import (
        APPLICATIONS_DIR,
        APPS_DIR,
        BIN_DIR,
        BLACKLISTED_KEYS,
        HOME,
        ICONS_DIR,
        PIXMAPS_DIR,
        PROTECTED_PATHS,
        XDG_CACHE_HOME,
        XDG_CONFIG_HOME,
        XDG_DATA_HOME,
        XDG_STATE_HOME,
        AppManifest,
    )
    from desktop import (
        DesktopParser,
        generate_desktop_file,
        generate_svg_icon,
        install_app_icons,
        update_system_databases,
    )
    from inspector import AppImageInspector, make_executable
    from utils import (
        Style,
        c,
        calculate_sha256,
        format_size,
        get_dir_size,
        get_running_app_pids,
        terminate_running_app,
    )

def sanitize_slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).strip().lower()
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    return cleaned or "app"


def download_file(url: str, dest_path: Path) -> None:
    print(f" {Style.PACKAGE} fetching remote appimage: {c(url, Style.CYAN)}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "adopt/1.0.0 (Linux; x86_64)"}
    )
    with urllib.request.urlopen(req) as response:
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 65536
        start_time = time.time()

        with open(dest_path, "wb") as out:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)

                if total_size > 0:
                    percent = min(100.0, (downloaded / total_size) * 100)
                    speed = downloaded / max(0.001, (time.time() - start_time))
                    bar_len = 28
                    filled = int(bar_len * downloaded / total_size)
                    bar = "━" * filled + "┄" * (bar_len - filled)
                    sys.stdout.write(
                        f"\r   [{c(bar, Style.GREEN)}] {percent:5.1f}% "
                        f"({format_size(downloaded)}/{format_size(total_size)}) "
                        f"{format_size(int(speed))}/s"
                    )
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r   downloaded: {format_size(downloaded)}...")
                    sys.stdout.flush()
        sys.stdout.write("\n")


class AdoptEngine:
    def __init__(self):
        APPS_DIR.mkdir(parents=True, exist_ok=True)
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
        ICONS_DIR.mkdir(parents=True, exist_ok=True)
        PIXMAPS_DIR.mkdir(parents=True, exist_ok=True)

    def get_manifest_path(self, app_id: str) -> Path:
        return APPS_DIR / app_id / "adopt.json"

    def load_manifest(self, app_id: str) -> Optional[AppManifest]:
        mpath = self.get_manifest_path(app_id)
        if not mpath.exists():
            return None
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
            return AppManifest.from_dict(data)
        except Exception:
            return None

    def save_manifest(self, manifest: AppManifest) -> None:
        mpath = self.get_manifest_path(manifest.id)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

    def list_apps(self) -> List[AppManifest]:
        apps: List[AppManifest] = []
        if not APPS_DIR.exists():
            return apps
        for item in sorted(APPS_DIR.iterdir()):
            if item.is_dir():
                m = self.load_manifest(item.name)
                if m:
                    apps.append(m)
        return apps

    def find_app(self, query: str) -> Optional[AppManifest]:
        query_clean = query.strip().lower()
        m = self.load_manifest(query_clean)
        if m:
            return m
        for app in self.list_apps():
            if (
                app.id.lower() == query_clean
                or app.name.lower() == query_clean
                or app.exec_name.lower() == query_clean
                or query_clean in [t.lower() for t in app.trace_identifiers]
            ):
                return app
        return None

    def generate_wrapper(self, manifest: AppManifest) -> Path:
        wrapper_path = BIN_DIR / manifest.exec_name
        appimage_path = manifest.appimage_path
        app_dir = APPS_DIR / manifest.id
        sandbox_dir = app_dir / "sandbox"

        portable_block = ""
        if manifest.portable:
            portable_block = f"""
# Sandboxed isolation
SANDBOX_DIR="{sandbox_dir}"
mkdir -p "$SANDBOX_DIR/config" "$SANDBOX_DIR/cache" "$SANDBOX_DIR/data" "$SANDBOX_DIR/state" "$SANDBOX_DIR/home"
export XDG_CONFIG_HOME="$SANDBOX_DIR/config"
export XDG_CACHE_HOME="$SANDBOX_DIR/cache"
export XDG_DATA_HOME="$SANDBOX_DIR/data"
export XDG_STATE_HOME="$SANDBOX_DIR/state"
export HOME="$SANDBOX_DIR/home"
"""

        script = f"""#!/usr/bin/env bash
# Autogenerated CLI wrapper by adopt for: {manifest.name} ({manifest.id})
set -e
APPIMAGE_BIN="{appimage_path}"
{portable_block}
if [ ! -x "$APPIMAGE_BIN" ]; then
    echo "adopt error: Executable not found at $APPIMAGE_BIN" >&2
    exit 1
fi

exec "$APPIMAGE_BIN" "$@"
"""
        wrapper_path.write_text(script, encoding="utf-8")
        make_executable(wrapper_path)
        return wrapper_path

    def install(self, source: str, portable: bool = False) -> AppManifest:
        with tempfile.TemporaryDirectory(prefix="adopt_install_") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            raw_path: Path
            is_remote_url = source.startswith("http://") or source.startswith("https://")

            if is_remote_url:
                url_parsed = urllib.parse.urlparse(source)
                url_filename = Path(url_parsed.path).name or "application.AppImage"
                if not url_filename.lower().endswith(".appimage"):
                    url_filename += ".AppImage"
                raw_path = tmp_dir / url_filename
                download_file(source, raw_path)
            else:
                raw_path = Path(source).expanduser().resolve()
                if not raw_path.exists():
                    raise FileNotFoundError(f"Source file not found: {source}")

            make_executable(raw_path)
            inspector = AppImageInspector(raw_path)
            meta = inspector.inspect_binary()

            inspect_work = tmp_dir / "inspect"
            extracted_desktop, extracted_icons = inspector.extract_assets(inspect_work)
            parsed_desktop = DesktopParser.parse(extracted_desktop) if extracted_desktop else {}

            base_name = parsed_desktop.get("Name") or raw_path.stem.replace(".AppImage", "").replace(".appimage", "")
            base_name = re.sub(r"[-_](x86_64|amd64|i386|arm64|aarch64)$", "", base_name, flags=re.I)

            app_id = sanitize_slug(base_name)
            app_dir = APPS_DIR / app_id
            app_dir.mkdir(parents=True, exist_ok=True)
            installed_appimage = app_dir / f"{app_id}.AppImage"

            versions_dir = app_dir / "versions"
            versions_dir.mkdir(exist_ok=True)
            prev_backup = versions_dir / "previous.AppImage"
            if installed_appimage.exists() and (raw_path.resolve() != installed_appimage.resolve() or not prev_backup.exists()):
                shutil.copy2(installed_appimage, prev_backup)

            if raw_path.resolve() != installed_appimage.resolve():
                shutil.copy2(raw_path, installed_appimage)

            make_executable(installed_appimage)
            installed_icons = install_app_icons(app_id, base_name, extracted_icons)
            icon_id = f"adopt-{app_id}"

            raw_exec = parsed_desktop.get("Exec", "").split()[0] if parsed_desktop.get("Exec") else ""
            raw_exec_name = Path(raw_exec).name if raw_exec else ""
            wm_class = parsed_desktop.get("StartupWMClass") or parsed_desktop.get("WMClass") or base_name

            trace_keys: Set[str] = {app_id, base_name, base_name.lower(), app_id.lower()}
            if raw_exec_name and (app_id == sanitize_slug(raw_exec_name) or base_name.lower() == raw_exec_name.lower()):
                trace_keys.add(raw_exec_name)
                trace_keys.add(raw_exec_name.lower())
            if wm_class:
                trace_keys.add(wm_class)
                trace_keys.add(wm_class.lower())

            clean_traces = [k for k in trace_keys if k and len(k) >= 3 and k.lower() not in BLACKLISTED_KEYS]
            if app_id not in clean_traces:
                clean_traces.append(app_id)

            categories_raw = parsed_desktop.get("Categories", "Utility;")
            categories = [c_item.strip() for c_item in categories_raw.split(";") if c_item.strip()]
            version = parsed_desktop.get("X-AppImage-Version") or parsed_desktop.get("Version") or "1.0"
            comment = parsed_desktop.get("Comment") or f"{base_name} application"

            now_iso = datetime.now().isoformat()

            manifest = AppManifest(
                id=app_id,
                name=base_name,
                version=version,
                exec_name=app_id,
                wm_class=wm_class,
                comment=comment,
                categories=categories,
                installed_at=now_iso,
                updated_at=now_iso,
                appimage_path=str(installed_appimage),
                original_filename=raw_path.name,
                binary_sha256=meta["sha256"],
                binary_size=meta["size"],
                desktop_file="",
                icon_files=installed_icons,
                wrapper_file="",
                portable=portable,
                trace_identifiers=clean_traces,
                source_url=source if is_remote_url else None,
            )

            wrapper_path = self.generate_wrapper(manifest)
            manifest.wrapper_file = str(wrapper_path)

            desktop_path = generate_desktop_file(manifest, icon_id)
            manifest.desktop_file = str(desktop_path)

            self.save_manifest(manifest)
            update_system_databases()
            return manifest

    def uninstall(self, query: str, yes: bool = False, dry_run: bool = False) -> Tuple[bool, List[Tuple[str, int]]]:
        app = self.find_app(query)
        if not app:
            raise FileNotFoundError(f"No adopted application matching '{query}' found.")

        pids = get_running_app_pids(app.id, Path(app.appimage_path), app.wm_class)
        if pids:
            if dry_run:
                print(f" {Style.WARN} active processes would be stopped: {pids}")
            else:
                ok = terminate_running_app(pids, force=yes)
                if not ok:
                    return False, []

        eradication_targets: Dict[Path, int] = {}

        def register_target(path: Path) -> None:
            resolved = path.resolve()
            if resolved in PROTECTED_PATHS:
                return
            if resolved.parent in {Path("/"), Path("/home")} and resolved != HOME:
                return
            if not path.exists() and not path.is_symlink():
                return
            eradication_targets[path] = get_dir_size(path)

        register_target(APPS_DIR / app.id)
        register_target(APPLICATIONS_DIR / f"adopt-{app.id}.desktop")
        register_target(APPLICATIONS_DIR / f"{app.id}.desktop")
        if app.desktop_file:
            register_target(Path(app.desktop_file))

        register_target(BIN_DIR / app.exec_name)
        if app.wrapper_file:
            register_target(Path(app.wrapper_file))

        for icon_path in app.icon_files:
            register_target(Path(icon_path))
        for icon_file in ICONS_DIR.rglob(f"adopt-{app.id}.*"):
            register_target(icon_file)
        for pixmap_file in PIXMAPS_DIR.glob(f"adopt-{app.id}.*"):
            register_target(pixmap_file)

        search_dirs = [
            XDG_CACHE_HOME,
            XDG_CONFIG_HOME,
            XDG_DATA_HOME,
            XDG_STATE_HOME,
            HOME,
        ]

        for key in app.trace_identifiers:
            if not key or len(key) < 3 or key.lower() in BLACKLISTED_KEYS:
                continue

            for base_dir in search_dirs:
                if base_dir == HOME:
                    for dot_target in [HOME / f".{key}", HOME / f".{key.lower()}"]:
                        if dot_target.exists() and dot_target not in PROTECTED_PATHS:
                            register_target(dot_target)
                else:
                    for candidate in [base_dir / key, base_dir / key.lower()]:
                        if candidate.exists() and candidate not in PROTECTED_PATHS:
                            if base_dir == XDG_DATA_HOME:
                                has_unmanaged = any(candidate.glob("*.AppImage")) or any(candidate.glob("*.appimage"))
                                if has_unmanaged and not candidate.is_relative_to(APPS_DIR):
                                    continue
                            register_target(candidate)

        try:
            for tmp_match in Path("/tmp").glob(f"*{app.id}*"):
                if tmp_match.is_file() or tmp_match.is_socket():
                    register_target(tmp_match)
        except Exception:
            pass

        total_freed = sum(eradication_targets.values())
        sorted_targets = sorted(eradication_targets.items(), key=lambda x: str(x[0]))

        if not yes and not dry_run:
            print(f"\n {Style.TRASH} {c('eradication target analysis for:', Style.BOLD)} {c(app.name, Style.MAGENTA)} ({app.id})")
            print(f"   items found: {c(str(len(sorted_targets)), Style.CYAN)}")
            print(f"   space to reclaim: {c(format_size(total_freed), Style.GREEN)}\n")
            print("   the following paths will be permanently eliminated:")
            for p, size in sorted_targets:
                size_str = f"({format_size(size)})" if size > 0 else ""
                print(f"    - {p} {c(size_str, Style.GRAY)}")

            try:
                confirm = input(f"\n {c('proceed with zero-trace eradication? [y/n]: ', Style.BOLD)}").strip().lower()
                if confirm != "y":
                    print(f" {Style.FAIL} eradication canceled by user.")
                    return False, []
            except (KeyboardInterrupt, EOFError):
                print(f"\n {Style.FAIL} canceled.")
                return False, []

        removed_records: List[Tuple[str, int]] = []
        for path, size in sorted_targets:
            if dry_run:
                removed_records.append((str(path), size))
                continue
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                removed_records.append((str(path), size))
            except Exception as e:
                print(f" {Style.WARN} could not delete {path}: {e}")

        if not dry_run:
            mimeapps = XDG_CONFIG_HOME / "mimeapps.list"
            if mimeapps.exists():
                try:
                    lines = mimeapps.read_text(encoding="utf-8").splitlines()
                    cleaned = [l for l in lines if f"adopt-{app.id}.desktop" not in l and f"{app.id}.desktop" not in l]
                    mimeapps.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
                except Exception:
                    pass

            update_system_databases()

        return True, removed_records

    def update_app(self, app_id: str, new_source: Optional[str] = None) -> AppManifest:
        app = self.find_app(app_id)
        if not app:
            raise FileNotFoundError(f"Application '{app_id}' not found.")

        source = new_source or app.source_url or app.appimage_path
        print(f" {Style.PACKAGE} updating {c(app.name, Style.BOLD)} from: {source}")
        return self.install(source=source, portable=app.portable)

    def rollback(self, app_id: str) -> bool:
        app = self.find_app(app_id)
        if not app:
            raise FileNotFoundError(f"Application '{app_id}' not found.")

        app_dir = APPS_DIR / app.id
        backup = app_dir / "versions" / "previous.AppImage"
        active = Path(app.appimage_path)

        if not backup.exists():
            raise FileNotFoundError(f"No previous version backup exists for '{app.id}'.")

        temp_swap = app_dir / "versions" / "current_swap.AppImage"
        shutil.move(active, temp_swap)
        shutil.move(backup, active)
        shutil.move(temp_swap, backup)

        make_executable(active)
        app.updated_at = datetime.now().isoformat()
        app.binary_sha256 = calculate_sha256(active)
        app.binary_size = active.stat().st_size
        self.save_manifest(app)
        update_system_databases()
        return True

    def doctor(self, repair: bool = False) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        apps = self.list_apps()

        for app in apps:
            issues: List[str] = []
            bin_path = Path(app.appimage_path)
            if not bin_path.exists():
                issues.append("AppImage binary is missing")
            elif not os.access(bin_path, os.X_OK):
                issues.append("AppImage binary lacks executable permissions")
                if repair:
                    make_executable(bin_path)

            wrap_path = Path(app.wrapper_file)
            if not wrap_path.exists():
                issues.append("CLI wrapper binary is missing")
                if repair:
                    self.generate_wrapper(app)
            elif not os.access(wrap_path, os.X_OK):
                issues.append("CLI wrapper lacks executable bit")
                if repair:
                    make_executable(wrap_path)

            desk_path = Path(app.desktop_file)
            if not desk_path.exists():
                issues.append("Desktop entry is missing")
                if repair:
                    generate_desktop_file(app, f"adopt-{app.id}")

            icon_missing = not any(Path(p).exists() for p in app.icon_files)
            if icon_missing:
                issues.append("All registered icon files are missing")
                if repair:
                    fallback_svg = ICONS_DIR / "hicolor" / "scalable" / "apps" / f"adopt-{app.id}.svg"
                    generate_svg_icon(app.name, fallback_svg)
                    app.icon_files = [str(fallback_svg)]
                    self.save_manifest(app)

            results.append({
                "app": app,
                "healthy": len(issues) == 0,
                "issues": issues,
            })

        if repair:
            update_system_databases()

        return results

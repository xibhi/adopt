"""
Formatting, styling, process lifecycle, and table rendering utilities.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from adopt.config import AppManifest
except ImportError:
    from config import AppManifest


class Style:
    USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ

    RESET = "\033[0m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    DIM = "\033[2m" if USE_COLOR else ""
    ITALIC = "\033[3m" if USE_COLOR else ""
    UNDERLINE = "\033[4m" if USE_COLOR else ""

    RED = "\033[38;5;196m" if USE_COLOR else ""
    GREEN = "\033[38;5;46m" if USE_COLOR else ""
    YELLOW = "\033[38;5;226m" if USE_COLOR else ""
    BLUE = "\033[38;5;39m" if USE_COLOR else ""
    MAGENTA = "\033[38;5;213m" if USE_COLOR else ""
    CYAN = "\033[38;5;51m" if USE_COLOR else ""
    WHITE = "\033[38;5;231m" if USE_COLOR else ""
    GRAY = "\033[38;5;244m" if USE_COLOR else ""
    ORANGE = "\033[38;5;208m" if USE_COLOR else ""

    SUCCESS = f"{GREEN}✓{RESET}"
    FAIL = f"{RED}✗{RESET}"
    WARN = f"{YELLOW}!{RESET}"
    INFO = f"{BLUE}ℹ{RESET}"
    PACKAGE = f"{CYAN}📦{RESET}"
    TRASH = f"{RED}🗑️{RESET}"
    DOCTOR = f"{BLUE}🩺{RESET}"
    SHIELD = f"{ORANGE}🛡️{RESET}"


def c(text: str, color: str) -> str:
    return f"{color}{text}{Style.RESET}" if Style.USE_COLOR else str(text)


def format_size(bytes_size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_size)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{bytes_size} B"


def get_dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file() or entry.is_symlink():
                    total += entry.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return total


def calculate_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(131072):
            hasher.update(chunk)
    return hasher.hexdigest()


def visible_len(text: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", str(text)))


def pad_cell(text: str, width: int) -> str:
    vlen = visible_len(text)
    return text + (" " * max(0, width - vlen))


def get_running_app_pids(app_id: str, appimage_path: Path, wm_class: Optional[str] = None) -> List[Tuple[int, str]]:
    pids: List[Tuple[int, str]] = []
    appimage_str = str(appimage_path.resolve())
    app_id_lower = app_id.lower()

    proc = Path("/proc")
    if not proc.exists():
        return pids

    for pid_dir in proc.glob("[0-9]*"):
        try:
            pid = int(pid_dir.name)
            if pid == os.getpid():
                continue
            cmdline_file = pid_dir / "cmdline"
            if not cmdline_file.exists():
                continue

            with open(cmdline_file, "rb") as f:
                cmd_raw = f.read()
            cmd_args = [arg.decode("utf-8", errors="ignore") for arg in cmd_raw.split(b"\x00") if arg]
            cmd_joined = " ".join(cmd_args)

            matched = False
            if appimage_str in cmd_joined:
                matched = True
            elif f"adopt/apps/{app_id}" in cmd_joined:
                matched = True
            elif cmd_args and Path(cmd_args[0]).name.lower() == app_id_lower:
                matched = True
            elif wm_class and wm_class.lower() in cmd_joined.lower():
                matched = True

            if matched:
                comm_file = pid_dir / "comm"
                comm = comm_file.read_text(encoding="utf-8", errors="ignore").strip() if comm_file.exists() else "unknown"
                pids.append((pid, comm))
        except (OSError, ValueError):
            continue
    return pids


def terminate_running_app(pids: List[Tuple[int, str]], force: bool = False) -> bool:
    if not pids:
        return True

    print(f" {Style.WARN} active processes detected:")
    for pid, name in pids:
        print(f"    - pid {c(str(pid), Style.YELLOW)}: {name}")

    if not force:
        try:
            choice = input(f" {c('terminate active processes to proceed with clean removal? [y/n]: ', Style.BOLD)}").strip().lower()
            if choice and choice != "y":
                print(f" {Style.FAIL} aborted by user.")
                return False
        except (KeyboardInterrupt, EOFError):
            print(f"\n {Style.FAIL} aborted.")
            return False

    for pid, _ in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    time.sleep(0.5)
    for _ in range(4):
        alive = [p for p in pids if Path(f"/proc/{p[0]}").exists()]
        if not alive:
            break
        time.sleep(0.5)

    for pid, _ in pids:
        if Path(f"/proc/{pid}").exists():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    return True


def render_apps_table(apps: List[AppManifest]) -> None:
    if not apps:
        print(f"\n {Style.INFO} no adopted applications found.")
        print(f"   adopt one with: {c('adopt -S <file|url>', Style.BOLD)}\n")
        return

    print(f"\n {Style.PACKAGE} {c('adopted applications', Style.BOLD)} ({len(apps)} total)\n")
    header = f" {pad_cell('ID', 16)} {pad_cell('NAME', 22)} {pad_cell('VERSION', 10)} {pad_cell('MODE', 12)} {pad_cell('SIZE', 10)} {pad_cell('COMMAND', 16)}"
    print(c(header, Style.BOLD))
    print(c(" " + "━" * 90, Style.GRAY))

    for a in apps:
        mode = "sandbox" if a.portable else "standard"
        mode_colored = c(mode, Style.MAGENTA if a.portable else Style.GRAY)
        size_str = format_size(a.binary_size)
        id_str = pad_cell(c(a.id, Style.CYAN), 16)
        name_str = pad_cell(a.name, 22)
        ver_str = pad_cell(a.version, 10)
        m_str = pad_cell(mode_colored, 12)
        sz_str = pad_cell(size_str, 10)
        cmd_str = pad_cell(c(a.exec_name, Style.YELLOW), 16)
        print(f" {id_str} {name_str} {ver_str} {m_str} {sz_str} {cmd_str}")
    print()

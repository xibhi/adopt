"""
Environment initialization, PATH configuration, and self-uninstallation hooks.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

try:
    from adopt.config import APPS_DIR, BIN_DIR, HOME, XDG_DATA_HOME
    from adopt.utils import Style, c
except ImportError:
    from config import APPS_DIR, BIN_DIR, HOME, XDG_DATA_HOME
    from utils import Style, c


def init() -> None:
    print(f"\n {Style.PACKAGE} {c('initializing adopt on system...', Style.BOLD)}")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    comp_dir = XDG_DATA_HOME / "bash-completion" / "completions"
    comp_dir.mkdir(parents=True, exist_ok=True)

    comp_file = comp_dir / "adopt"
    comp_candidates = [
        Path(__file__).resolve().parent / "completions" / "adopt.bash",
        XDG_DATA_HOME / "adopt" / "src" / "completions" / "adopt.bash",
    ]
    for comp_src in comp_candidates:
        if comp_src.exists():
            shutil.copy2(comp_src, comp_file)
            print(f"   {c('✓', Style.GREEN)} bash completions installed ({comp_file})")
            break

    bin_str = str(BIN_DIR)
    shell_configs = [
        HOME / ".bashrc",
        HOME / ".zshrc",
        HOME / ".profile",
        HOME / ".bash_profile",
    ]
    export_line = f'export PATH="{bin_str}:$PATH"\n'

    for sh_cfg in shell_configs:
        if sh_cfg.exists():
            content = sh_cfg.read_text(encoding="utf-8", errors="ignore")
            if bin_str not in content:
                with open(sh_cfg, "a", encoding="utf-8") as f:
                    f.write(f"\n# adopt PATH\n{export_line}")
                print(f"   {c('✓', Style.GREEN)} added {bin_str} to {sh_cfg.name}")
            else:
                print(f"   {c('✓', Style.GREEN)} {sh_cfg.name} already contains {bin_str}")

    print(f"\n {Style.SUCCESS} {c('adopt initialized successfully.', Style.BOLD)}")
    print(f"   run {c('adopt', Style.CYAN)} to see available commands.\n")


def uninstall(yes: bool = False) -> None:
    print(f"\n {Style.TRASH} {c('adopt self-uninstall', Style.BOLD)}")
    if not yes:
        try:
            confirm = input(f" {c('completely remove adopt and all of its data? [y/N]: ', Style.BOLD)}").strip().lower()
            if confirm != "y":
                print(f" {Style.FAIL} uninstallation canceled.")
                return
        except (KeyboardInterrupt, EOFError):
            print(f"\n {Style.FAIL} canceled.")
            return

    launcher = BIN_DIR / "adopt"
    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()
        print(f"   {c('✓', Style.GREEN)} removed launcher: {launcher}")

    comp_file = XDG_DATA_HOME / "bash-completion" / "completions" / "adopt"
    if comp_file.exists():
        comp_file.unlink()
        print(f"   {c('✓', Style.GREEN)} removed completions: {comp_file}")

    adopt_home = XDG_DATA_HOME / "adopt"
    if adopt_home.exists():
        shutil.rmtree(adopt_home, ignore_errors=True)
        print(f"   {c('✓', Style.GREEN)} removed adopt data: {adopt_home}")
    print(f"\n {Style.SUCCESS} adopt and all of its data have been removed from your system.\n")

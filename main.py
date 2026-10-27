"""
adopt - main command-line interface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

# Add current directory to path if run standalone
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from adopt import __version__
    from adopt.engine import AdoptEngine
    from adopt import hooks
    from adopt.utils import Style, c, format_size, render_apps_table
except ImportError:
    from __init__ import __version__
    from engine import AdoptEngine
    import hooks
    from utils import Style, c, format_size, render_apps_table

HELP_MENU = """Usage: adopt [OPTIONS] COMMAND [ARGS]...

  for people who'd rather not chmod +x

Options:
  --version      Show the version and exit.
  --help         Show this message.
  --init         Add adopt to PATH for system-wide use.
  --uninstall    Remove adopt and all of its data.

Commands:
  -S             Install an AppImage from a local file.
    --portable   Install an AppImage from a URL.
  -U             Update an app, keeping a backup for rollback.
  -B             Revert the last update and restore the previous version.
  -Syu           Update every adopted app and repair integrations.
  -Q             List adopted apps and their status.
  -D             Check app health and desktop integrations.
    --repair     Fix broken wrappers, desktop entries and icon caches.
  -R             Remove an app along with all of its caches and traces.
    -n           Dry run: list what would be removed.
    -y           Remove without asking for confirmation.

Tip: Run adopt <command> --help for details (e.g. adopt -S --help)."""

FLAG_HELPS: Dict[str, str] = {
    "-S": """Usage: adopt -S [OPTIONS] <FILE|URL>

  Install an AppImage from a local file or remote URL.

Options:
  --portable     Isolate configs and caches inside app directory.""",

    "-U": """Usage: adopt -U <ID> [FILE|URL]

  Update an app, keeping a backup for rollback.""",

    "-B": """Usage: adopt -B <ID>

  Revert the last update and restore the previous version.""",

    "-Syu": """Usage: adopt -Syu

  Update every adopted app and repair integrations.""",

    "-Q": """Usage: adopt -Q [--json]

  List adopted apps and their status.""",

    "-D": """Usage: adopt -D [OPTIONS]

  Check app health and desktop integrations.

Options:
  --repair       Fix broken wrappers, desktop entries and icon caches.""",

    "-R": """Usage: adopt -R [OPTIONS] <ID>

  Remove an app along with all of its caches and traces.

Options:
  -n             Dry run: list what would be removed.
  -y             Remove without asking for confirmation.""",
}

FLAG_HELPS["install"] = FLAG_HELPS["-S"]
FLAG_HELPS["update"] = FLAG_HELPS["-U"]
FLAG_HELPS["rollback"] = FLAG_HELPS["-B"]
FLAG_HELPS["update-all"] = FLAG_HELPS["-Syu"]
FLAG_HELPS["ls"] = FLAG_HELPS["-Q"]
FLAG_HELPS["list"] = FLAG_HELPS["-Q"]
FLAG_HELPS["doctor"] = FLAG_HELPS["-D"]
FLAG_HELPS["uninstall"] = FLAG_HELPS["-R"]
FLAG_HELPS["remove"] = FLAG_HELPS["-R"]


def print_minimal_help() -> None:
    print(HELP_MENU)


def normalize_argv(argv: List[str]) -> List[str]:
    if len(argv) < 2:
        return argv
    cmd = argv[1]
    if cmd in {"-S", "-Si", "install"}:
        return [argv[0], "install"] + argv[2:]
    if cmd in {"-U", "-Ui", "update"}:
        return [argv[0], "update"] + argv[2:]
    if cmd in {"-B", "rollback"}:
        return [argv[0], "rollback"] + argv[2:]
    if cmd in {"-Syu", "-Syyu", "-Su", "update-all"}:
        return [argv[0], "update-all"] + argv[2:]
    if cmd in {"-Q", "-Qs", "-Qe", "list", "ls"}:
        return [argv[0], "ls"] + argv[2:]
    if cmd in {"-D", "doctor"}:
        return [argv[0], "doctor"] + argv[2:]
    if cmd in {"-R", "-Rs", "-Rns", "uninstall", "remove"}:
        return [argv[0], "uninstall"] + argv[2:]
    if cmd == "-Ry":
        return [argv[0], "uninstall", "-y"] + argv[2:]
    if cmd == "-Rn":
        return [argv[0], "uninstall", "-n"] + argv[2:]
    return argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adopt",
        add_help=False,
    )
    parser.add_argument("-v", "--version", action="version", version=f"adopt {__version__}")
    parser.add_argument("-h", "--help", action="store_true", help="Show this message.")
    parser.add_argument("--init", action="store_true", help="Add adopt to PATH for system-wide use.")
    parser.add_argument("--uninstall", action="store_true", help="Remove adopt and all of its data.")
    subparsers = parser.add_subparsers(dest="subcommand", help="Command to execute")

    # -S
    for alias in ["install", "-S"]:
        p_install = subparsers.add_parser(alias, add_help=False)
        p_install.add_argument("source", help="Path to .AppImage file or remote URL")
        p_install.add_argument("--portable", action="store_true", help="Install an AppImage from a URL / isolate in app folder")

    # -U
    for alias in ["update", "-U"]:
        p_up = subparsers.add_parser(alias, add_help=False)
        p_up.add_argument("target", help="Application ID")
        p_up.add_argument("source", nargs="?", help="New AppImage file or URL (optional)")

    # -B
    for alias in ["rollback", "-B"]:
        p_rb = subparsers.add_parser(alias, add_help=False)
        p_rb.add_argument("target", help="Application ID")

    # -Syu
    for alias in ["update-all", "-Syu"]:
        subparsers.add_parser(alias, add_help=False)

    # -Q
    for alias in ["list", "ls", "-Q"]:
        p_ls = subparsers.add_parser(alias, add_help=False)
        p_ls.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # -D
    for alias in ["doctor", "-D"]:
        p_doc = subparsers.add_parser(alias, add_help=False)
        p_doc.add_argument("--repair", action="store_true", help="Fix broken wrappers, desktop entries and icon caches.")

    # -R
    for alias in ["uninstall", "-R", "remove"]:
        p_un = subparsers.add_parser(alias, add_help=False)
        p_un.add_argument("target", help="Application ID to remove")
        p_un.add_argument("-n", action="store_true", help="Dry run: list what would be removed.")
        p_un.add_argument("-y", action="store_true", help="Remove without asking for confirmation.")

    return parser


def cmd_install(args: argparse.Namespace, engine: AdoptEngine) -> None:
    print(f"\n {Style.PACKAGE} {c('adopting appimage application...', Style.BOLD)}")
    try:
        manifest = engine.install(
            source=args.source,
            portable=args.portable,
        )
    except Exception as e:
        print(f"\n {Style.FAIL} {c('installation failed:', Style.RED)} {e}")
        sys.exit(1)

    print(f"\n {Style.SUCCESS} {c('successfully adopted:', Style.GREEN)} {c(manifest.name, Style.BOLD)}")
    print(f"   - app id:       {c(manifest.id, Style.CYAN)}")
    print(f"   - cli command:  {c(manifest.exec_name, Style.YELLOW)} (run directly from terminal)")
    print(f"   - desktop entry:{manifest.desktop_file}")
    print(f"   - binary size:  {format_size(manifest.binary_size)}")
    print(f"\n {c('launch with:', Style.DIM)} {c(manifest.exec_name, Style.BOLD)} {c('or find it in your application launcher.', Style.DIM)}\n")


def cmd_uninstall(args: argparse.Namespace, engine: AdoptEngine) -> None:
    try:
        success, removed = engine.uninstall(
            query=args.target,
            yes=args.y,
            dry_run=args.n,
        )
    except Exception as e:
        print(f"\n {Style.FAIL} {c('uninstall failed:', Style.RED)} {e}")
        sys.exit(1)

    if not success:
        return

    mode_str = "[dry-run] would remove" if args.n else "eradicated"
    print(f"\n {Style.TRASH} {c(f'zero-trace eradication complete ({mode_str}):', Style.BOLD)}")
    total_freed = sum(r[1] for r in removed)

    for path, size in removed:
        size_label = f"[{format_size(size)}]" if size > 0 else ""
        print(f"   {c('✓', Style.GREEN)} {path} {c(size_label, Style.GRAY)}")

    print(f"\n {Style.SUCCESS} {c('summary:', Style.BOLD)} {len(removed)} items purged. {c(format_size(total_freed), Style.GREEN)} disk space reclaimed.")
    print(f" {Style.SHIELD} system is completely pristine. zero traces remain.\n")


def cmd_update(args: argparse.Namespace, engine: AdoptEngine) -> None:
    try:
        updated = engine.update_app(args.target, new_source=args.source)
        print(f"\n {Style.SUCCESS} {c(updated.name, Style.BOLD)} successfully updated to latest version.")
        print(f"   previous version backed up. use {c(f'adopt -B {updated.id}', Style.YELLOW)} if needed.\n")
    except Exception as e:
        print(f"\n {Style.FAIL} update failed: {e}")
        sys.exit(1)


def cmd_rollback(args: argparse.Namespace, engine: AdoptEngine) -> None:
    try:
        engine.rollback(args.target)
        print(f"\n {Style.SUCCESS} successfully rolled back {c(args.target, Style.BOLD)} to previous version.\n")
    except Exception as e:
        print(f"\n {Style.FAIL} rollback failed: {e}")
        sys.exit(1)


def cmd_update_all(args: argparse.Namespace, engine: AdoptEngine) -> None:
    print(f"\n {Style.PACKAGE} {c('starting full system upgrade (-Syu)...', Style.BOLD)}")
    apps = engine.list_apps()
    if not apps:
        print(f" {Style.INFO} no adopted applications found.\n")
        return

    updated_count = 0
    for app in apps:
        print(f"\n {c('::', Style.CYAN)} synchronizing {c(app.name, Style.BOLD)}...")
        src = app.source_url or app.appimage_path
        try:
            engine.update_app(app.id, new_source=src)
            print(f"    {c('✓', Style.GREEN)} {app.name} is synchronized.")
            updated_count += 1
        except Exception as e:
            print(f"    {c('!', Style.YELLOW)} failed updating {app.name}: {e}")

    print(f"\n {Style.DOCTOR} auditing system integrations...")
    engine.doctor(repair=True)
    print(f"\n {Style.SUCCESS} upgrade finished. {len(apps)} application(s) checked.\n")


def cmd_doctor(args: argparse.Namespace, engine: AdoptEngine) -> None:
    print(f"\n {Style.DOCTOR} {c('checking app health and desktop integrations...', Style.BOLD)}")
    reports = engine.doctor(repair=args.repair)
    all_healthy = True

    for rep in reports:
        app = rep["app"]
        if rep["healthy"]:
            print(f"   {c('✓', Style.GREEN)} {c(app.name, Style.BOLD)} ({app.id}): healthy")
        else:
            all_healthy = False
            action_tag = "[repaired]" if args.repair else "[issue]"
            print(f"   {c('!', Style.YELLOW)} {c(app.name, Style.BOLD)} ({app.id}) {action_tag}:")
            for issue in rep["issues"]:
                print(f"      - {issue}")

    if all_healthy:
        print(f"\n {Style.SUCCESS} all adopted applications and desktop integrations are operational.\n")
    else:
        if not args.repair:
            print(f"\n {Style.WARN} run {c('adopt -D --repair', Style.BOLD)} to fix broken wrappers, desktop entries and icon caches.\n")
        else:
            print(f"\n {Style.SUCCESS} repair operations completed.\n")


def main() -> None:
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help", "help"}):
        print_minimal_help()
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] == "--init":
        hooks.init()
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] in {"--uninstall", "self-uninstall"}:
        hooks.uninstall(yes="-y" in sys.argv or "--yes" in sys.argv)
        sys.exit(0)

    if len(sys.argv) == 3 and sys.argv[2] in {"-h", "--help"}:
        flag = sys.argv[1]
        if flag in FLAG_HELPS:
            print(FLAG_HELPS[flag])
            sys.exit(0)

    norm_argv = normalize_argv(sys.argv)
    parser = build_parser()
    args = parser.parse_args(norm_argv[1:])
    engine = AdoptEngine()
    cmd = args.subcommand

    if cmd in {"install", "-S"}:
        cmd_install(args, engine)
    elif cmd in {"uninstall", "-R", "remove"}:
        cmd_uninstall(args, engine)
    elif cmd in {"update", "-U"}:
        cmd_update(args, engine)
    elif cmd in {"rollback", "-B"}:
        cmd_rollback(args, engine)
    elif cmd in {"update-all", "-Syu"}:
        cmd_update_all(args, engine)
    elif cmd in {"doctor", "-D"}:
        cmd_doctor(args, engine)
    elif cmd in {"list", "ls", "-Q"}:
        if getattr(args, "json", False):
            print(json.dumps([a.to_dict() for a in engine.list_apps()], indent=2))
        else:
            render_apps_table(engine.list_apps())
    else:
        print_minimal_help()


if __name__ == "__main__":
    main()

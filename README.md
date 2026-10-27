# adopt

[![PyPI version](https://img.shields.io/pypi/v/adopt.svg?color=blue)](https://pypi.org/project/adopt/)
[![Python versions](https://img.shields.io/pypi/pyversions/adopt.svg)](https://pypi.org/project/adopt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/xibhi/adopt/blob/master/LICENSE)

adopt installs .AppImage as native desktop apps on Linux, with menu entries, terminal commands, rollback-safe updates, and clean removal.

## Features

**Install**
- Install an AppImage from a local file or a URL
- Create Freedesktop `.desktop` entries for launchers and docks
- Extract embedded PNG and SVG icons, with a vector fallback
- Add a CLI wrapper to `~/.local/bin/` so apps launch from the terminal

**Maintain**
- Update one app with automatic backup (`-U`) and instant rollback (`-B`)
- Update every adopted app and repair integrations in one go (`-Syu`)
- Audit installed apps and fix missing desktop files or icons (`-D --repair`)

**Remove**
- Remove an app along with its configs, caches and state (`-R`)
- Preview exactly what a removal will delete (`-R <id> -n`)

**Setup**
- Add itself to your PATH and register shell completions (`--init`)
- Remove itself cleanly (`--uninstall`)

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/xibhi/adopt/master/scripts/install.sh | bash
```

Or from source:

```bash
git clone https://github.com/xibhi/adopt.git
cd adopt
./scripts/install.sh
```
## Commands

| Command | Description |
|---|---|
| `adopt --version` | Show the version and exit. |
| `adopt --help` | Show this message. |
| `adopt --init` | Add adopt to PATH for system-wide use. |
| `adopt --uninstall` | Remove adopt and all of its data. |
| `adopt -S <file>` | Install an AppImage from a local file. |
| `adopt -S --portable <url>` | Install an AppImage from a URL. |
| `adopt -U <id>` | Update an app, keeping a backup for rollback. |
| `adopt -B <id>` | Revert the last update and restore the previous version. |
| `adopt -Syu` | Update every adopted app and repair integrations. |
| `adopt -Q` | List adopted apps and their status. |
| `adopt -D` | Check app health and desktop integrations. |
| `adopt -D --repair` | Fix broken wrappers, desktop entries and icon caches. |
| `adopt -R <id>` | Remove an app along with all of its caches and traces. |
| `adopt -R <id> -n` | Dry run: list what would be removed. |
| `adopt -R <id> -y` | Remove without asking for confirmation. |

## Architecture

```text
adopt/
├── __init__.py           # version string
├── __main__.py           # module runner (python3 -m adopt)
├── config.py             # XDG paths, security guards and models
├── desktop.py            # .desktop entries, icons and database sync
├── engine.py             # install, update, rollback and removal
├── hooks.py              # --init / --uninstall, PATH and completions
├── inspector.py          # ELF offset analysis and asset extraction
├── main.py               # CLI commands, argument router and handlers
├── utils.py              # styling, process scanner and table formatters
├── completions/
│   └── adopt.bash        # bash completion script
├── scripts/
│   ├── install.sh        # local and remote installer
│   └── uninstall.sh      # uninstaller
├── LICENSE               # MIT License
├── pyproject.toml        # packaging configuration
└── README.md
```

## How It Works

Adopt runs entirely in user space, with no root or sudo required.

- **Asset extraction**: Desktop files, PNGs, SVGs and `.DirIcon` are read from the embedded squashfs via `--appimage-extract`, without mounting or running the binary.
- **Desktop integration**: Entries are written to `~/.local/share/applications/adopt-<id>.desktop` and icons to `~/.local/share/icons/hicolor/`. GNOME, GTK and KDE Plasma caches are refreshed automatically.
- **CLI wrappers**: Each app gets a wrapper in `~/.local/bin/<alias>` that passes arguments straight through to the AppImage.
- **Complete removal**: Most uninstallers delete only the binary. Adopt also clears leftovers in `~/.config`, `~/.cache` and `~/.local/share`.
- **Rollback**: Each update keeps the previous build at `~/.local/share/adopt/apps/<id>/versions/previous.AppImage`, so `adopt -B <id>` restores it in seconds.

## FAQ

**Does adopt need root or sudo?**

No. Everything lives in standard XDG user directories (`~/.local/share/adopt`, `~/.local/bin`, `~/.local/share/applications`).

**Can I preview what `adopt -R` will delete?**

Yes. `adopt -R <id> -n` lists every matched file, directory and size without changing anything.

**How do I uninstall adopt itself?**

Run `adopt --uninstall` or `./scripts/uninstall.sh`. This removes the launcher and shell completions, and leaves your app data intact.

## License

This project is licensed under the [MIT License](LICENSE).

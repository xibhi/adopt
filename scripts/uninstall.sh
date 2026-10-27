#!/usr/bin/env bash
# adopt - universal uninstaller
set -euo pipefail

PREFIX="${PREFIX:-${HOME}/.local}"
BIN_DIR="${PREFIX}/bin"
COMPLETION_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/bash-completion/completions"

echo "Uninstalling adopt from ${BIN_DIR}..."

if [ -f "${BIN_DIR}/adopt" ] || [ -L "${BIN_DIR}/adopt" ]; then
    rm -f "${BIN_DIR}/adopt"
    echo "✓ Removed ${BIN_DIR}/adopt"
fi

if [ -f "${COMPLETION_DIR}/adopt" ]; then
    rm -f "${COMPLETION_DIR}/adopt"
    echo "✓ Removed ${COMPLETION_DIR}/adopt"
fi

SRC_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/adopt/src"
if [ -d "${SRC_DIR}" ]; then
    rm -rf "${SRC_DIR}"
    echo "✓ Removed ${SRC_DIR}"
fi

echo "adopt uninstalled successfully."
echo "(Your adopted application data at ~/.local/share/adopt is preserved)"

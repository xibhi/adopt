#!/usr/bin/env bash
# adopt - universal installer
set -euo pipefail

PREFIX="${PREFIX:-${HOME}/.local}"
BIN_DIR="${PREFIX}/bin"
DATA_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/adopt"
SRC_DIR="${DATA_DIR}/src"
COMPLETION_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/bash-completion/completions"

# Check Python 3.9+
if ! command -v python3 >/dev/null 2>&1; then
    echo "adopt error: python3 is required but not installed." >&2
    exit 1
fi

if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    echo "adopt error: Python 3.9 or higher is required." >&2
    exit 1
fi

# Detect whether script is executed locally or piped via curl/stdin
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

mkdir -p "${BIN_DIR}" "${SRC_DIR}" "${COMPLETION_DIR}"

if [ -n "${SCRIPT_DIR}" ] && [ -f "${SCRIPT_DIR}/../main.py" ]; then
    LOCAL_REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
    cp -r "${LOCAL_REPO}"/*.py "${SRC_DIR}/"
    [ -d "${LOCAL_REPO}/completions" ] && cp -r "${LOCAL_REPO}/completions" "${SRC_DIR}/"
    [ -f "${LOCAL_REPO}/LICENSE" ] && cp "${LOCAL_REPO}/LICENSE" "${SRC_DIR}/"
    [ -f "${LOCAL_REPO}/README.md" ] && cp "${LOCAL_REPO}/README.md" "${SRC_DIR}/"
    [ -f "${LOCAL_REPO}/pyproject.toml" ] && cp "${LOCAL_REPO}/pyproject.toml" "${SRC_DIR}/"
else
    # Piped or remote installation: clone or download repository
    if command -v git >/dev/null 2>&1; then
        if [ -d "${SRC_DIR}/.git" ]; then
            git -C "${SRC_DIR}" pull --quiet 2>/dev/null || true
        else
            rm -rf "${SRC_DIR}"
            mkdir -p "${SRC_DIR}"
            git clone --depth 1 https://github.com/xibhi/adopt.git "${SRC_DIR}" --quiet
        fi
    elif command -v curl >/dev/null 2>&1 && command -v tar >/dev/null 2>&1; then
        mkdir -p "${SRC_DIR}"
        curl -fsSL https://github.com/xibhi/adopt/archive/refs/heads/master.tar.gz | tar -xz --strip-components=1 -C "${SRC_DIR}"
    elif command -v wget >/dev/null 2>&1 && command -v tar >/dev/null 2>&1; then
        mkdir -p "${SRC_DIR}"
        wget -qO- https://github.com/xibhi/adopt/archive/refs/heads/master.tar.gz | tar -xz --strip-components=1 -C "${SRC_DIR}"
    else
        echo "adopt error: git or curl+tar required to install." >&2
        exit 1
    fi
fi

# Generate launcher in bin dir
cat << 'EOF' > "${BIN_DIR}/adopt"
#!/usr/bin/env bash
SRC_DIR="${XDG_DATA_HOME:-${HOME}/.local/share}/adopt/src"
if [ ! -f "${SRC_DIR}/main.py" ]; then
    echo "adopt error: installation directory not found at ${SRC_DIR}" >&2
    exit 1
fi
exec python3 "${SRC_DIR}/main.py" "$@"
EOF

chmod +x "${BIN_DIR}/adopt"

# Copy completions
if [ -f "${SRC_DIR}/completions/adopt.bash" ]; then
    cp "${SRC_DIR}/completions/adopt.bash" "${COMPLETION_DIR}/adopt"
fi

# Run init to configure PATH and ensure completions
"${BIN_DIR}/adopt" --init

echo "adopt installation complete."

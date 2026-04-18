#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${CEOS_VENV_DIR:-$ROOT_DIR/.venv}"
USER_BIN_DIR="${CEOS_USER_BIN_DIR:-$HOME/.local/bin}"
REMOVE_VENV=0

usage() {
  cat <<'EOF'
Usage: ./scripts/uninstall.sh [--remove-venv] [--user-bin-dir PATH] [--venv-path PATH]

Removes user-level CLI shims created by scripts/install.sh.

Options:
  --remove-venv         Also remove the local virtual environment.
  --venv-path PATH      Use a custom virtual environment path.
  --user-bin-dir PATH   Use a custom user-level bin directory.
  -h, --help            Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove-venv)
      REMOVE_VENV=1
      shift
      ;;
    --venv-path)
      VENV_DIR="$2"
      shift 2
      ;;
    --user-bin-dir)
      USER_BIN_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

remove_shim() {
  local name="$1"
  local shim_path="$USER_BIN_DIR/$name"

  if [[ ! -e "$shim_path" ]]; then
    return 0
  fi

  if ! grep -q "Installed by Contract-Evidence OS install.sh" "$shim_path" 2>/dev/null; then
    echo "Skipping unmanaged file: $shim_path" >&2
    return 0
  fi

  rm -f "$shim_path"
}

remove_shim "ceos"
remove_shim "ceos-server"
remove_shim "ceos-worker"
remove_shim "ceos-dispatcher"
remove_shim "ceos-maintenance"

if [[ "$REMOVE_VENV" -eq 1 && -d "$VENV_DIR" ]]; then
  rm -rf "$VENV_DIR"
fi

cat <<EOF

Contract-Evidence OS user-level CLI shims were removed from:
  $USER_BIN_DIR

EOF

if [[ "$REMOVE_VENV" -eq 1 ]]; then
  cat <<EOF
The virtual environment was removed:
  $VENV_DIR

EOF
else
  cat <<EOF
The virtual environment was left in place:
  $VENV_DIR

To remove it too, run:
  ./scripts/uninstall.sh --remove-venv

EOF
fi

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${CEOS_VENV_DIR:-$ROOT_DIR/.venv}"
USER_BIN_DIR="${CEOS_USER_BIN_DIR:-$HOME/.local/bin}"
CONFIG_PATH="$ROOT_DIR/runtime/config.local.json"
ENV_PATH="$ROOT_DIR/runtime/.env.local"
WITH_DEV=0
FORCE=0
INIT_CONFIG=0
SERVICE_PORT=8080

usage() {
  cat <<'EOF'
Usage: ./scripts/install.sh [--with-dev] [--force] [--init-config] [--venv-path PATH] [--user-bin-dir PATH] [--config-path PATH] [--env-path PATH] [--service-port PORT]

Installs Contract-Evidence OS into a local virtual environment and exposes the
main CLI commands through a user-level bin directory.

Options:
  --with-dev            Install development dependencies too.
  --force               Overwrite existing shim commands created elsewhere.
  --init-config         Generate a local config.local.json and .env.local profile.
  --venv-path PATH      Use a custom virtual environment path.
  --user-bin-dir PATH   Use a custom user-level bin directory.
  --config-path PATH    Write generated JSON config to this path.
  --env-path PATH       Write generated env config to this path.
  --service-port PORT   Use this local operator port in generated config.
  -h, --help            Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-dev)
      WITH_DEV=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --init-config)
      INIT_CONFIG=1
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
    --config-path)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --env-path)
      ENV_PATH="$2"
      shift 2
      ;;
    --service-port)
      SERVICE_PORT="$2"
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

mkdir -p "$USER_BIN_DIR"
mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$ENV_PATH")"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

"$PIP_BIN" install --upgrade pip

INSTALL_SPEC="."
if [[ "$WITH_DEV" -eq 1 ]]; then
  INSTALL_SPEC=".[dev]"
fi

(
  cd "$ROOT_DIR"
  "$PIP_BIN" install -e "$INSTALL_SPEC"
)

create_shim() {
  local name="$1"
  local target="$VENV_DIR/bin/$name"
  local shim_path="$USER_BIN_DIR/$name"

  if [[ ! -x "$target" ]]; then
    echo "Expected executable not found after install: $target" >&2
    exit 1
  fi

  if [[ -e "$shim_path" && "$FORCE" -ne 1 ]]; then
    if ! grep -q "Installed by Contract-Evidence OS install.sh" "$shim_path" 2>/dev/null; then
      echo "Refusing to overwrite existing file: $shim_path" >&2
      echo "Re-run with --force if you want this installer to replace it." >&2
      exit 1
    fi
  fi

  cat >"$shim_path" <<EOF
#!/usr/bin/env bash
# Installed by Contract-Evidence OS install.sh
exec "$target" "\$@"
EOF
  chmod +x "$shim_path"
}

create_shim "ceos"
create_shim "ceos-server"
create_shim "ceos-worker"
create_shim "ceos-dispatcher"
create_shim "ceos-maintenance"

generate_init_config() {
  local config_path="$1"
  local env_path="$2"
  local service_port="$3"
  local storage_root="$ROOT_DIR/runtime"
  local software_repo_path="${CEOS_CLI_ANYTHING_REPO_PATH:-}"
  local token

  if [[ -e "$config_path" && "$FORCE" -ne 1 ]]; then
    echo "Refusing to overwrite existing config file: $config_path" >&2
    echo "Re-run with --force if you want this installer to replace it." >&2
    exit 1
  fi

  if [[ -e "$env_path" && "$FORCE" -ne 1 ]]; then
    echo "Refusing to overwrite existing env file: $env_path" >&2
    echo "Re-run with --force if you want this installer to replace it." >&2
    exit 1
  fi

  token="$("$PYTHON_BIN" - <<'PY'
import secrets

print(secrets.token_urlsafe(24))
PY
)"

  CONFIG_PATH_PY="$config_path" \
  STORAGE_ROOT_PY="$storage_root" \
  SERVICE_PORT_PY="$service_port" \
  SOFTWARE_REPO_PATH_PY="$software_repo_path" \
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import json
import os

config_path = Path(os.environ["CONFIG_PATH_PY"])
storage_root = os.environ["STORAGE_ROOT_PY"]
service_port = int(os.environ["SERVICE_PORT_PY"])
software_repo_path = os.environ["SOFTWARE_REPO_PATH_PY"]
payload = {
    "storage_root": storage_root,
    "service": {
        "host": "127.0.0.1",
        "port": service_port,
        "token_env": "CEOS_OPERATOR_TOKEN",
    },
    "external_backend": {
        "kind": "sqlite",
        "url": "",
        "namespace": "ceos",
    },
    "shared_state_backend": {
        "kind": "sqlite",
        "url": "",
        "schema": "public",
    },
    "software_control": {
        "enabled": True,
        "source_kind": "cli-anything",
        "repo_path": software_repo_path,
        "allow_auto_task": True,
        "macro_enabled": True,
        "macro_default_approval": True,
    },
    "observability": {
        "enabled": True,
        "snapshot_interval_seconds": 60,
        "prometheus_enabled": True,
        "alerts_enabled": True,
        "history_window_hours": 24,
    },
    "maintenance": {
        "daemon_enabled": True,
        "poll_interval_seconds": 30,
        "heartbeat_seconds": 30,
        "lease_seconds": 300,
    },
}
config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

  cat >"$env_path" <<EOF
# Local environment generated by Contract-Evidence OS install.sh --init-config
export CEOS_OPERATOR_TOKEN="$token"
export CEOS_STORAGE_ROOT="$storage_root"
# export CEOS_CLI_ANYTHING_REPO_PATH=""
EOF
}

if [[ "$INIT_CONFIG" -eq 1 ]]; then
  generate_init_config "$CONFIG_PATH" "$ENV_PATH" "$SERVICE_PORT"
fi

"$VENV_DIR/bin/ceos" --help >/dev/null

cat <<EOF

Contract-Evidence OS is installed.

Virtual environment:
  $VENV_DIR

CLI shims:
  $USER_BIN_DIR/ceos
  $USER_BIN_DIR/ceos-server
  $USER_BIN_DIR/ceos-worker
  $USER_BIN_DIR/ceos-dispatcher
  $USER_BIN_DIR/ceos-maintenance

Quick checks:
  ceos system-report
  ceos api-contract

EOF

if [[ "$INIT_CONFIG" -eq 1 ]]; then
  cat <<EOF
Generated local runtime profile:
  $CONFIG_PATH

Generated local environment file:
  $ENV_PATH

Recommended next steps:
  source "$ENV_PATH"
  ceos --config "$CONFIG_PATH" system-report
  ceos-server --config "$CONFIG_PATH"

EOF
fi

case ":$PATH:" in
  *":$USER_BIN_DIR:"*)
    ;;
  *)
    cat <<EOF
$USER_BIN_DIR is not currently on your PATH.
Add this line to your shell profile, then open a new shell:

  export PATH="$USER_BIN_DIR:\$PATH"

EOF
    ;;
esac

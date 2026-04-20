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
INTERACTIVE=0
CONFIGURED_PROVIDER_KIND="deterministic"
CONFIGURED_PROVIDER_BASE_URL="https://api.openai.com/v1"
CONFIGURED_PROVIDER_MODEL="gpt-4.1-mini"
CONFIGURED_PROVIDER_API_KEY=""
CONFIGURED_OPERATOR_TOKEN=""
CONFIGURED_VERIFY_PROVIDER=0
BUILD_FRONTEND=1
FRONTEND_BUILD_STATUS="not-run"
FRONTEND_BUILD_MESSAGE=""

if [[ -t 0 && -t 1 ]]; then
  INTERACTIVE=1
fi

usage() {
  cat <<'EOF'
Usage: ./scripts/install.sh [--with-dev] [--force] [--init-config] [--skip-frontend-build] [--venv-path PATH] [--user-bin-dir PATH] [--config-path PATH] [--env-path PATH] [--service-port PORT]

Installs Contract-Evidence OS into a local virtual environment and exposes the
main CLI commands through a user-level bin directory.

Options:
  --with-dev            Install development dependencies too.
  --force               Overwrite existing shim commands created elsewhere.
  --init-config         Generate a local config.local.json and .env.local profile.
  --skip-frontend-build Skip the React/Vite dashboard install + production build step.
  --venv-path PATH      Use a custom virtual environment path.
  --user-bin-dir PATH   Use a custom user-level bin directory.
  --config-path PATH    Write generated JSON config to this path.
  --env-path PATH       Write generated env config to this path.
  --service-port PORT   Use this local operator port in generated config.
  -h, --help            Show this help message.
EOF
}

prompt_with_default() {
  local __resultvar="$1"
  local prompt_text="$2"
  local default_value="$3"
  local answer=""

  if [[ "$INTERACTIVE" -eq 1 ]]; then
    read -r -p "$prompt_text [$default_value]: " answer
  fi
  printf -v "$__resultvar" "%s" "${answer:-$default_value}"
}

prompt_secret() {
  local __resultvar="$1"
  local prompt_text="$2"
  local default_value="${3:-}"
  local answer=""

  if [[ "$INTERACTIVE" -eq 1 ]]; then
    read -r -s -p "$prompt_text: " answer
    echo
  fi
  printf -v "$__resultvar" "%s" "${answer:-$default_value}"
}

prompt_yes_no() {
  local __resultvar="$1"
  local prompt_text="$2"
  local default_value="$3"
  local answer=""
  local normalized_default="y"

  if [[ "$default_value" =~ ^[Nn]$ ]]; then
    normalized_default="n"
  fi
  if [[ "$INTERACTIVE" -eq 1 ]]; then
    read -r -p "$prompt_text [$normalized_default]: " answer
  fi
  answer="${answer:-$normalized_default}"
  answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"
  if [[ "$answer" == "y" || "$answer" == "yes" ]]; then
    printf -v "$__resultvar" "%s" "1"
  else
    printf -v "$__resultvar" "%s" "0"
  fi
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
    --skip-frontend-build)
      BUILD_FRONTEND=0
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

build_frontend_bundle() {
  if [[ "$BUILD_FRONTEND" -ne 1 ]]; then
    FRONTEND_BUILD_STATUS="skipped"
    FRONTEND_BUILD_MESSAGE="Skipped frontend build by request."
    return 0
  fi

  if [[ ! -f "$ROOT_DIR/frontend/package.json" ]]; then
    FRONTEND_BUILD_STATUS="skipped"
    FRONTEND_BUILD_MESSAGE="No frontend package.json found; dashboard build skipped."
    return 0
  fi

  if ! command -v npm >/dev/null 2>&1; then
    FRONTEND_BUILD_STATUS="warning"
    FRONTEND_BUILD_MESSAGE="npm was not found; the API will work, but the web dashboard bundle was not built."
    return 0
  fi

  echo "Preparing the web console dashboard..."
  (
    cd "$ROOT_DIR/frontend"
    if [[ -f package-lock.json ]]; then
      npm ci --no-fund --no-audit
    else
      npm install --no-fund --no-audit
    fi
    if [[ -x ./node_modules/.bin/vite ]]; then
      ./node_modules/.bin/vite build
    else
      npm run build
    fi
  )
  FRONTEND_BUILD_STATUS="ready"
  FRONTEND_BUILD_MESSAGE="Dashboard bundle built in $ROOT_DIR/frontend/dist."
}

prompt_provider_setup() {
  local generated_token=""
  generated_token="$("$PYTHON_BIN" - <<'PY'
import secrets

print(secrets.token_urlsafe(24))
PY
)"
  prompt_with_default SERVICE_PORT "Local operator service port" "$SERVICE_PORT"
  prompt_with_default CONFIGURED_OPERATOR_TOKEN "Operator token (stored in runtime/.env.local)" "$generated_token"

  if [[ "$INTERACTIVE" -eq 1 ]]; then
    cat <<'EOF'

Choose your model API provider:
  1) OpenAI-compatible (recommended)
  2) Anthropic
  3) Skip for now (deterministic/local-only)
EOF
  fi

  local provider_choice="${CEOS_PROVIDER_KIND:-}"
  if [[ -z "$provider_choice" ]]; then
    if [[ "$INTERACTIVE" -eq 1 ]]; then
      provider_choice="1"
    else
      provider_choice="deterministic"
    fi
  fi
  if [[ "$INTERACTIVE" -eq 1 ]]; then
    read -r -p "Provider [1]: " provider_choice
  fi
  provider_choice="${provider_choice:-1}"

  case "$provider_choice" in
    1|"openai-compatible")
      CONFIGURED_PROVIDER_KIND="openai-compatible"
      prompt_with_default CONFIGURED_PROVIDER_BASE_URL "OpenAI-compatible base URL" "${CEOS_API_BASE_URL:-https://api.openai.com/v1}"
      prompt_with_default CONFIGURED_PROVIDER_MODEL "Default model name" "${CEOS_DEFAULT_MODEL:-gpt-4.1-mini}"
      prompt_secret CONFIGURED_PROVIDER_API_KEY "OpenAI-compatible API key (stored in runtime/.env.local)" "${CEOS_API_KEY:-}"
      if [[ -n "$CONFIGURED_PROVIDER_API_KEY" ]]; then
        prompt_yes_no CONFIGURED_VERIFY_PROVIDER "Verify this provider configuration now" "y"
      else
        CONFIGURED_VERIFY_PROVIDER=0
      fi
      ;;
    2|"anthropic")
      CONFIGURED_PROVIDER_KIND="anthropic"
      prompt_with_default CONFIGURED_PROVIDER_BASE_URL "Anthropic base URL" "${CEOS_API_BASE_URL:-https://api.anthropic.com/v1}"
      prompt_with_default CONFIGURED_PROVIDER_MODEL "Default model name" "${CEOS_DEFAULT_MODEL:-claude-sonnet-4-20250514}"
      prompt_secret CONFIGURED_PROVIDER_API_KEY "Anthropic API key (stored in runtime/.env.local)" "${CEOS_API_KEY:-}"
      if [[ -n "$CONFIGURED_PROVIDER_API_KEY" ]]; then
        prompt_yes_no CONFIGURED_VERIFY_PROVIDER "Verify this provider configuration now" "y"
      else
        CONFIGURED_VERIFY_PROVIDER=0
      fi
      ;;
    3|"skip"|"deterministic")
      CONFIGURED_PROVIDER_KIND="deterministic"
      CONFIGURED_PROVIDER_BASE_URL="https://api.openai.com/v1"
      CONFIGURED_PROVIDER_MODEL="gpt-4.1-mini"
      CONFIGURED_PROVIDER_API_KEY=""
      CONFIGURED_VERIFY_PROVIDER=0
      ;;
    *)
      echo "Unsupported provider choice: $provider_choice" >&2
      exit 2
      ;;
  esac
}

generate_init_config() {
  local config_path="$1"
  local env_path="$2"
  local service_port="$3"
  local storage_root="$ROOT_DIR/runtime"
  local software_repo_path="${CEOS_CLI_ANYTHING_REPO_PATH:-}"
  local verification_report=""

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

  prompt_provider_setup
  CONFIG_PATH_PY="$config_path" \
  ENV_PATH_PY="$env_path" \
  STORAGE_ROOT_PY="$storage_root" \
  SERVICE_PORT_PY="$SERVICE_PORT" \
  SOFTWARE_REPO_PATH_PY="$software_repo_path" \
  PROVIDER_KIND_PY="$CONFIGURED_PROVIDER_KIND" \
  PROVIDER_BASE_URL_PY="$CONFIGURED_PROVIDER_BASE_URL" \
  PROVIDER_MODEL_PY="$CONFIGURED_PROVIDER_MODEL" \
  PROVIDER_API_KEY_PY="$CONFIGURED_PROVIDER_API_KEY" \
  OPERATOR_TOKEN_PY="$CONFIGURED_OPERATOR_TOKEN" \
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import os

from contract_evidence_os.bootstrap import (
    build_local_runtime_profile,
    write_local_env_file,
    write_local_runtime_profile,
)

config_path = Path(os.environ["CONFIG_PATH_PY"])
env_path = Path(os.environ["ENV_PATH_PY"])
storage_root = os.environ["STORAGE_ROOT_PY"]
service_port = int(os.environ["SERVICE_PORT_PY"])
software_repo_path = os.environ["SOFTWARE_REPO_PATH_PY"]
provider_kind = os.environ["PROVIDER_KIND_PY"]
provider_base_url = os.environ["PROVIDER_BASE_URL_PY"]
provider_model = os.environ["PROVIDER_MODEL_PY"]
provider_api_key = os.environ["PROVIDER_API_KEY_PY"]
operator_token = os.environ["OPERATOR_TOKEN_PY"]

payload = build_local_runtime_profile(
    storage_root=storage_root,
    service_port=service_port,
    provider_kind=provider_kind,
    provider_default_model=provider_model,
    provider_base_url=provider_base_url,
    software_repo_path=software_repo_path,
)
write_local_runtime_profile(config_path, payload)
write_local_env_file(
    env_path,
    operator_token=operator_token,
    storage_root=storage_root,
    api_key=provider_api_key,
    base_url=provider_base_url,
    provider_kind=provider_kind,
    default_model=provider_model,
    cli_anything_repo_path=software_repo_path,
)
PY

  if [[ "$CONFIGURED_VERIFY_PROVIDER" -eq 1 ]]; then
    verification_report="$(PROVIDER_KIND_PY="$CONFIGURED_PROVIDER_KIND" \
      PROVIDER_BASE_URL_PY="$CONFIGURED_PROVIDER_BASE_URL" \
      PROVIDER_API_KEY_PY="$CONFIGURED_PROVIDER_API_KEY" \
      "$PYTHON_BIN" - <<'PY'
import json
import os

from contract_evidence_os.bootstrap import verify_provider_configuration

report = verify_provider_configuration(
    provider_kind=os.environ["PROVIDER_KIND_PY"],
    base_url=os.environ["PROVIDER_BASE_URL_PY"],
    api_key=os.environ["PROVIDER_API_KEY_PY"],
)
print(json.dumps(report))
PY
)"
    echo
    echo "Provider verification:"
    echo "  $verification_report"
  fi
}

if [[ "$INIT_CONFIG" -eq 1 ]]; then
  generate_init_config "$CONFIG_PATH" "$ENV_PATH" "$SERVICE_PORT"
fi

build_frontend_bundle

"$VENV_DIR/bin/ceos" --help >/dev/null
if [[ "$INIT_CONFIG" -eq 1 ]]; then
  CEOS_OPERATOR_TOKEN="$CONFIGURED_OPERATOR_TOKEN" \
  CEOS_STORAGE_ROOT="$ROOT_DIR/runtime" \
  CEOS_PROVIDER_KIND="$CONFIGURED_PROVIDER_KIND" \
  CEOS_API_KEY="$CONFIGURED_PROVIDER_API_KEY" \
  CEOS_API_BASE_URL="$CONFIGURED_PROVIDER_BASE_URL" \
  CEOS_DEFAULT_MODEL="$CONFIGURED_PROVIDER_MODEL" \
  "$VENV_DIR/bin/ceos" --config "$CONFIG_PATH" system-report >/dev/null
fi

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
  ceos doctor
  ceos api-contract

Dashboard build:
  $FRONTEND_BUILD_STATUS
  $FRONTEND_BUILD_MESSAGE

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
  ceos --config "$CONFIG_PATH" doctor
  ceos --config "$CONFIG_PATH" service-health
  ceos-server --config "$CONFIG_PATH"
  open http://127.0.0.1:$SERVICE_PORT/  # macOS
  xdg-open http://127.0.0.1:$SERVICE_PORT/  # Linux

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

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${CEOS_OPERATOR_TOKEN:?CEOS_OPERATOR_TOKEN must be set}"

ARGS=(--storage-root "${CEOS_STORAGE_ROOT:-$ROOT_DIR/runtime}")
if [[ -n "${CEOS_EXTERNAL_BACKEND_KIND:-}" ]]; then
  ARGS+=(--backend-kind "${CEOS_EXTERNAL_BACKEND_KIND}")
fi
if [[ -n "${CEOS_EXTERNAL_BACKEND_URL:-}" ]]; then
  ARGS+=(--backend-url "${CEOS_EXTERNAL_BACKEND_URL}")
fi

exec ceos-server "${ARGS[@]}" "$@"

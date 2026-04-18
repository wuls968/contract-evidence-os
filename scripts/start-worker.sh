#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${CEOS_WORKER_ID:=worker-local}"

exec ceos-worker --storage-root "${CEOS_STORAGE_ROOT:-$ROOT_DIR/runtime}" --worker-id "$CEOS_WORKER_ID" "$@"

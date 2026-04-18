#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

exec ceos-maintenance --storage-root "${CEOS_STORAGE_ROOT:-$ROOT_DIR/runtime}" "$@"

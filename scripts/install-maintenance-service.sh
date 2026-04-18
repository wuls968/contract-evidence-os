#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
  --launchd)
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$ROOT_DIR/deploy/launchd/com.contractevidenceos.maintenance.plist" "$HOME/Library/LaunchAgents/"
    echo "Installed launchd plist"
    ;;
  --systemd)
    mkdir -p "$HOME/.config/systemd/user"
    cp "$ROOT_DIR/deploy/systemd/ceos-maintenance.service" "$HOME/.config/systemd/user/"
    echo "Installed systemd unit"
    ;;
  *)
    echo "Usage: $0 --launchd | --systemd" >&2
    exit 2
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  --launchd)
    rm -f "$HOME/Library/LaunchAgents/com.contractevidenceos.maintenance.plist"
    echo "Removed launchd plist"
    ;;
  --systemd)
    rm -f "$HOME/.config/systemd/user/ceos-maintenance.service"
    echo "Removed systemd unit"
    ;;
  *)
    echo "Usage: $0 --launchd | --systemd" >&2
    exit 2
    ;;
esac

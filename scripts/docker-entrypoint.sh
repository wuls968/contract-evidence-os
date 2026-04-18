#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ -z "${CEOS_OPERATOR_TOKEN:-}" ]; then
  CEOS_OPERATOR_TOKEN="$(python3 - <<'PY'
import secrets

print(secrets.token_urlsafe(24))
PY
)"
  export CEOS_OPERATOR_TOKEN
  printf '%s\n' "Generated ephemeral CEOS_OPERATOR_TOKEN for container startup." >&2
  printf '%s %s\n' "CEOS_OPERATOR_TOKEN=" "${CEOS_OPERATOR_TOKEN}" >&2
fi

exec ceos-server --host 0.0.0.0

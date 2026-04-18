# 0.9.0 Migration Guide

This release aligns the project around `runtime OS`, `AMOS memory OS`, `software control fabric`, and `operator api v1`.

## What changed

- Operator HTTP routes are versioned and snapshotted through `operator_api_contract()`.
- `ceos` now exposes `metrics-report`, `maintenance-report`, and richer governed software-control reporting.
- `ceos-maintenance` now supports resident daemon mode with explicit poll, heartbeat, and lease controls.
- Observability now follows `SQLite authoritative + Prometheus exporter + Grafana assets`.
- Governed software control now includes macros, replay diagnostics, recovery hints, and failure clusters.

## Migration steps

1. Upgrade to package version `0.9.0`.
2. Refresh release assets:
   - `docs/api/operator-v1.snapshot.json`
   - `docs/cli/ceos-help.snapshot.txt`
   - `docs/cli/ceos-maintenance-help.snapshot.txt`
3. Reinstall background maintenance as a system service if you use it:
   - macOS: `scripts/install-maintenance-service.sh --launchd`
   - Linux: `scripts/install-maintenance-service.sh --systemd`
4. If you deploy observability tooling, copy `deploy/observability/prometheus.yml` and `deploy/observability/grafana-dashboard.json`.

## Rollback

- Revert to the previous package version.
- Restore the previous API and CLI snapshots if your CI checks them.
- Remove the resident maintenance service until the previous version is active.

## Post-migration validation

- `ceos api-contract`
- `ceos metrics-report --window-hours 24`
- `ceos maintenance-report`
- `ceos software-control-report`
- `ceos-maintenance --once`

# ADR-071 Shared Backend Fallback Policy

## Status

Accepted

## Decision

When shared artifact mirrors exist but the shared backend is unavailable, AMOS now recommends and executes a local fallback rebuild instead of silently doing nothing.

## Why

Repairing a shared mirror is not always possible. The runtime still needs a safe, auditable degraded path that preserves local retrieval and project-state visibility.


# Milestone 8 Implementation Plan

**Goal:** Add a real external backend option and cross-host runtime hardening without weakening the contract/evidence/audit/replay core.

**Implementation slices**

1. Backend boundary hardening
- Extend queue and coordination abstractions with typed backend descriptors, health records, and external-backend capability metadata.
- Keep SQLite as the reference backend.
- Add a Redis-backed queue and coordination implementation that mirrors operational state into the durable repository for replay and audit.

2. Cross-host worker and lease lifecycle
- Add host-aware worker identity, heartbeat, renewal, and drain records.
- Strengthen lease renewal with explicit renewal attempts, expiry forecasts, fencing, and reclaim records.
- Add conservative, auditable work stealing only for stale or drain-eligible owners.

3. Provider-pool balancing under sustained load
- Extend provider-pool state with reservations, fairness tracking, and delay reasons.
- Make routing and operator surfaces expose reservation pressure, fairness, and degraded routing rationale.

4. Network and control-plane security
- Extend auth with service principals, scoped service credentials, rotation/revocation records, and anti-replay state for sensitive actions.
- Harden server defaults with bounded request sizes, explicit admin-vs-health behavior, and stricter scoped authorization for sensitive paths.

5. Deployment, tests, and docs
- Add multi-host role/config support, Redis validation, and startup checks.
- Add backend contract tests, cross-host coordination tests, work-steal tests, provider-pool fairness tests, security tests, and distributed eval coverage.
- Add ADRs, runbooks, and examples documenting the Redis boundary, cross-host lease ownership, work stealing, provider fairness, and practical network security assumptions.

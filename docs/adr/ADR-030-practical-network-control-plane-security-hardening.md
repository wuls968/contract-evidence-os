# ADR-030: Practical Network and Control-Plane Security Hardening

## Decision

Harden the remote control plane with scoped principals, service credentials, rotation and revocation records, request-size limits, allowlist-aware sensitive actions, and replay-protected control-plane requests.

## Why

The control plane can now approve risky actions, drain hosts, rotate credentials, and steer policy. Those operations need stronger protection without introducing heavyweight IAM infrastructure that the runtime cannot realistically operate.

## Security Model

- In-app:
  - principal and scope checks,
  - replay protection,
  - idempotency linkage,
  - credential status tracking,
  - audit linkage for each sensitive request.
- Deployment edge:
  - trusted reverse proxy or private-network placement,
  - optional TLS termination,
  - non-public defaults for admin surfaces.

## Consequences

- Sensitive operator actions are materially harder to replay or perform with stale credentials.
- Security assumptions stay explicit and documented instead of implied.


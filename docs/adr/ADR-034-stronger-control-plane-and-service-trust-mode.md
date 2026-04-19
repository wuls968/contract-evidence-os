# ADR-034: Stronger Control-Plane and Service Trust Mode

## Decision

Add an HMAC-based trust mode for sensitive service-to-service requests, layered on top of scoped credentials, replay protection, and audit logging.

## Why

The previous model was strong enough for local-runtime operator control but not expressive enough for a production-like topology where dispatcher, workers, and control plane may cross host boundaries.

## Consequences

- Sensitive requests can require both credential scope and signed request intent.
- Security incidents become typed runtime data rather than only HTTP failures.
- This remains practical to operate because it does not require a full enterprise IAM system.


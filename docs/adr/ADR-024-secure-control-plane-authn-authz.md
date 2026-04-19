# ADR-024: Secure Control-Plane Authn/Authz

## Decision

Replace simple bearer-token equality checks with typed principals, credentials, scopes, auth events, revocation records, and replay-protected request records.

## Why

The remote operator surface now controls queue drain, provider disablement, policy promotion, and approvals. Those actions need materially stronger protection and audit linkage.

## Consequences

- Sensitive actions are scope-gated.
- Requests carry replay-protection records.
- Credential revocation and bootstrap rotation are part of the runtime model, not ad hoc config only.

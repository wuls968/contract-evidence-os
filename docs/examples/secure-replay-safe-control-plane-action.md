# Example: Secure Replay-Safe Control-Plane Action

An operator submits a sensitive request with request id, nonce, and idempotency key. The first request is accepted and audited. A replay of the same request is rejected as a replay attempt.

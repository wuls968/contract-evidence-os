# Replay-Protected Sensitive Control-Plane Action

An operator submits a sensitive runtime override with a scoped credential, request ID, nonce, and idempotency key. The control plane authenticates the principal, checks scope, rejects duplicates inside the replay window, and links the accepted action to audit and control-plane request records.

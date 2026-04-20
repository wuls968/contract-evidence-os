# Replay-Protected Sensitive Action Under Stronger Trust Mode

A dispatcher submits a sensitive governance change with a scoped credential, request ID, nonce, timestamp, and HMAC signature. The control plane verifies the signature, checks replay state, confirms scope, and records both the authenticated action and the trust decision.

# Runbook: Credential Rotation and Revocation

1. Issue a replacement credential with the required scopes.
2. Verify the new credential can authenticate and authorize the expected actions.
3. Revoke the previous credential.
4. Confirm revoked credentials cannot authenticate.
5. Review auth events for any attempted use after revocation.

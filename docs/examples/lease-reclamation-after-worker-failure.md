# Example: Lease Reclamation After Worker Failure

A worker stops heartbeating. Coordination marks it stale, reclaims its active ownership records, and requeues the lease so another worker can resume from the durable checkpoint.

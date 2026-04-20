# Worker Takeover After Host Failure

Host A stops heartbeating during active execution. The coordination backend marks the worker stale, reclaims the lease, and host B resumes from the latest checkpoint and handoff packet. Ownership conflict and transfer records explain why takeover was permitted and how replay remains clear.


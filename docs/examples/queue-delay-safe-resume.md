# Example: Queue Delay Then Safe Resume

A task is interrupted after planning and returned to the queue. Later:

- the lease is recovered,
- the task is re-admitted,
- continuity and handoff state remain available,
- execution resumes from the durable checkpoint rather than replaying the whole transcript.

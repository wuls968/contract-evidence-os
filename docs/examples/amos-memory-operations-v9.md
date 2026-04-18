# AMOS Memory Operations v9

Milestone 22 extends AMOS maintenance into a more resident worker and rollout governance loop.

## Example flow

1. A maintenance worker registers and heartbeats.
2. The worker claims a due background maintenance schedule.
3. The run interrupts after recommendation generation, holding the schedule claim.
4. The same worker resumes the run and releases the claim.
5. A learned maintenance controller promotion is recommended.
6. The operator applies the rollout, making `v2` active.
7. The operator later rolls the rollout back to `v1`.
8. A shared backend outage creates a maintenance incident and degraded mode.
9. After recovery, the incident is explicitly resolved and the scope returns to normal mode.

## Operator-visible outputs

- maintenance workers
- maintenance schedules and claims
- maintenance incidents and maintenance mode
- maintenance controller state
- maintenance rollout records

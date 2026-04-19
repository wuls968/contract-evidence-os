# AMOS Memory Operations v8

Milestone 21 extends AMOS maintenance from a helper flow into a longer-running operational fabric.

## Example flow

1. AMOS schedules background maintenance for one scope.
2. A due run is interrupted after recommendation generation.
3. The operator resumes the run and AMOS records recovery.
4. A shared artifact mirror drifts from the local source-grounded index.
5. AMOS detects drift, recommends `reconcile_shared_artifacts`, and rewrites the shared mirror.
6. The shared backend becomes unavailable later.
7. AMOS records a maintenance incident, falls back to local artifacts, and exposes the scope as `degraded`.

## Operator-visible outputs

- maintenance schedules
- maintenance recoveries
- maintenance canary runs and promotion recommendations
- artifact drift records
- maintenance incidents
- maintenance mode
- maintenance analytics

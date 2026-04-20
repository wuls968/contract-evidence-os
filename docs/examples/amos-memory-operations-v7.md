# AMOS Memory Operations V7

Milestone 20 extends AMOS maintenance into a more continuous operator-grade loop.

## Example 1: Scheduled Background Maintenance

1. Schedule background maintenance for a scope.
2. Run due maintenance and interrupt after recommendation.
3. Resume the interrupted run later.
4. Inspect analytics to confirm what actions were actually executed.

## Example 2: Learned Maintenance Recommendation

1. Train the maintenance controller from prior diagnostics and maintenance runs.
2. Run a maintenance canary comparing baseline and learned recommendation behavior.
3. Generate a promotion recommendation from the canary result.
4. Feed that recommendation into the evolution mining path.

## Example 3: Shared Backend Fallback

1. A scope has shared artifact mirrors.
2. The shared backend becomes unavailable.
3. AMOS recommends `fallback_local_artifacts`.
4. Background maintenance rebuilds local artifacts instead of leaving the scope without usable indexes.

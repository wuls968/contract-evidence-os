# Example: Policy Promotion From Scorecard Traces

Runtime scorecards show that a low-cost routing bias improves provider-pressure survival without increasing policy violations.

1. Build a policy candidate from runtime traces.
2. Evaluate it with operational metrics.
3. Promote only if the run passes.
4. Roll back if later evidence shows degradation.

The candidate is promoted as a policy artifact, not as an ungoverned config mutation.

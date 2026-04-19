# AMOS Memory Policy Lifecycle Example

## Scenario

A task produces three kinds of memory events:

- a risky procedural candidate that hints at bypassing approval
- evolving semantic facts about what the user is working on
- a later request to durably remove the task memory scope

## Admission

The runtime applies a strict admission policy for the task scope.

The risky procedural candidate is:

- scored for poison risk
- quarantined instead of consolidated
- recorded as both an admission decision and a governance decision

## Timeline Reconstruction

Later semantic facts show:

- user working on AMOS design
- user still working on AMOS design
- user then switching to memory policy work

AMOS reconstructs timeline segments so the operator can see:

- the AMOS design phase
- the later memory policy phase
- the transition point between them

## Hard Purge

If the operator requests hard purge for the task scope:

- raw episodes are physically removed
- semantic facts are physically removed
- matrix pointers are physically removed

Subsequent evidence packs and dashboards no longer surface the purged state.

## Policy Evolution

The lifecycle outcomes are recorded as a memory lifecycle trace.
That trace can propose a memory-policy candidate which must still pass the `memory-lifecycle` evaluation suite before promotion.

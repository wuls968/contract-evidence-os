# Operator-Forced Low-Cost Mode

An operator can call the remote governance endpoint with:

- action: `force_low_cost_mode`
- operator identity
- rationale for the override

The runtime records:
- a human intervention,
- a new execution mode state,
- a governance event explaining the override.

Future resumptions of the task can then respect the cheaper mode without losing contract, evidence, or audit continuity.

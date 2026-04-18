# Budget-Triggered Mode Switch

If the initialized task budget is small enough that only reserve-safe execution remains, the runtime:

1. creates the task budget policy and ledger,
2. activates `low_cost` mode,
3. records a `budget_mode_activated` event,
4. persists the new execution mode and routing policy,
5. routes later provider requests through cheaper compatible paths when possible.

The switch is operator-visible through the governance API and trace bundle.

# Scorecard-Driven Routing Decision

Example decision factors for a low-cost extraction node:

- `anthropic_live` has slightly lower reliability than `openai_live`.
- `anthropic_live` has lower average cost and better latency.
- current execution mode is `low_cost`.
- structured output is still supported by both providers.

The routing policy therefore selects `anthropic_live`, and the persisted routing decision records:
- all candidates considered,
- the cost-aware policy override,
- the scorecard signals that drove the decision.

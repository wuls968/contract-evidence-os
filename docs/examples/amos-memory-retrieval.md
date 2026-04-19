# AMOS Memory Retrieval Example

## Scenario

The runtime completes a task with:

- a prohibition not to delete audit history
- a preference for structured output
- grounded delivery facts extracted from attachments

## What Gets Stored

- raw task request episode
- working memory snapshot with active goal and pending actions
- semantic facts for prohibitions and preferences
- matrix pointers aimed at those semantic facts
- raw delivery episode and semantic facts for final grounded statements

## What Retrieval Returns

When the operator asks:

`什么约束要求不能删除审计历史？`

AMOS builds an evidence pack containing:

- relevant raw episodes
- active semantic facts
- associative matrix pointers
- temporal notes if superseded facts exist

The answer path stays source grounded because matrix recall only points to evidence; it does not invent the final fact.

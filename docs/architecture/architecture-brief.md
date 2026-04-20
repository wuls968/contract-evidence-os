# Architecture Brief

## Positioning

Contract-Evidence OS is an audit-native runtime for long-horizon agent execution.

## Core Flow

User goal -> TaskContract -> ContractLattice -> PlanGraph -> Role allocation -> Tool actions
-> EvidenceGraph -> Shadow verification -> Reconciliation -> Delivery -> AuditLedger
-> Evolution candidate extraction -> Offline evaluation -> Canary -> Promotion or rollback

## Execution State Machine

- `created`
- `compiled`
- `planned`
- `executing`
- `verifying`
- `reconciling`
- `delivered`
- `recovering`
- `failed`
- `blocked`

## Core Modules

- `contracts`: contract schema, compiler, lattice updates
- `planning`: plan graphs and replanning
- `agents`: role passports and output profiles
- `tools`: typed tool adapters with risk and validation hooks
- `evidence`: graph of claims, sources, tests, contradictions, and decisions
- `verification`: shadow lane and validation reports
- `policy`: permission lattice and approvals
- `audit`: append-only event ledger with replay support
- `memory`: layered memory with promotion and rollback
- `recovery`: checkpoints, failures, retries, and branch recovery
- `evolution`: candidates, evaluation, canaries, promotion, rollback

## MVP

The first slice compiles a task into a contract, creates a small plan graph, executes a
real file retrieval tool, records evidence and audit events, runs shadow verification, and
returns an evidence-bound delivery packet.

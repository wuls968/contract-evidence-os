# ADR-037: CLI-Anything Bridge and Task-Native Software Control

## Status

Accepted

## Context

The HKUDS CLI-Anything repository contains:

- methodology documents
- agent skills/plugins
- generated harness conventions

It does not currently expose a standalone builder service that this runtime can safely treat as a generic remote backend.

At the same time, this system requires all meaningful actions to remain:

- task-native
- auditable
- approval-aware
- evidence-bound

## Decision

We introduce a bridge layer instead of pretending CLI-Anything is already an always-on builder backend.

The bridge layer manages:

- configured repository path
- Codex skill installation path
- build/refine/validate request tracking

Direct software invocation is also task-native:

- if a task is supplied, the invocation joins that task
- if no task is supplied, the runtime creates a minimal software-control task automatically

This preserves consistent audit, budget, approval, and evidence behavior.

## Consequences

### Positive

- No bypass path around the runtime's governance model.
- Direct software control and build-side integration stay explicit and operator-visible.
- Compatible with future deeper builder automation if CLI-Anything later exposes a cleaner machine-callable backend.

### Negative

- Build requests are tracked and bridged rather than fully auto-executed inside the runtime today.
- Operators must still ensure the configured CLI-Anything repository is present and healthy.

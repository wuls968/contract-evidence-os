# ADR-036: Governed Software Control via CLI-Anything

## Status

Accepted

## Context

The runtime already had:

- contract-first execution
- tool governance
- approval gating
- evidence graphs
- audit-native receipts

The new requirement was to deeply integrate HKUDS CLI-Anything so the agent can control desktop software without collapsing into a brittle GUI-clicking architecture.

CLI-Anything's core contribution is not raw computer-use automation. Its real contribution is generating agent-usable software harnesses such as `cli-anything-gimp`, `cli-anything-blender`, and similar CLIs with JSON output and structured command groups.

## Decision

We treat CLI-Anything as a software harness source, not as the system's primary runtime loop.

We introduce:

- a harness registry
- a governed invocation adapter
- approval-aware software command execution
- evidence capture from command output
- operator-visible control-plane surfaces for registration, validation, and invocation

## Consequences

### Positive

- Preserves the original contract/evidence/audit identity.
- Makes software control replayable and operator-visible.
- Avoids brittle screenshot/pixel automation as the default path.
- Allows future harness sources besides CLI-Anything.

### Negative

- Coverage depends on harness availability.
- Build-side automation is less immediate than a universal GUI automation promise.
- Help parsing is only a first-pass command discovery mechanism.

## Non-Goals

- Replacing the runtime with a generic GUI agent.
- Claiming universal control over every closed-source application.
- Bypassing approval, budget, or audit requirements for software actions.

# Milestone 10 Implementation Plan

## Goal

Add a governed software-control fabric on top of the existing contract/evidence/audit runtime, with deep integration of [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) as the first external software harness source.

## Positioning

This milestone does not turn the system into a generic GUI agent or unrestricted desktop controller.

Instead, it adds a task-native software control layer with these properties:

- software capabilities are exposed through registered harnesses
- every invocation remains contract-bound and audit-native
- high-risk commands are approval-gated
- command outputs become evidence, not just terminal noise
- build/refine/validate flows from CLI-Anything are managed through a bridge layer, not treated as a magical always-on builder backend

## Integration Shape

### 1. Harness Registry

Persist:

- `SoftwareHarnessRecord`
- `SoftwareCommandDescriptor`
- `SoftwareControlPolicy`
- `SoftwareHarnessValidation`
- `SoftwareControlBridgeConfig`
- `SoftwareBuildRequest`

These records are stored through the existing version-safe `runtime_state_records` channel so they inherit schema-versioning and replay behavior without fragmenting the schema.

### 2. Governed Invocation Adapter

Add a `CLIAnythingHarnessTool` that can:

- discover installed `cli-anything-*` executables
- register and validate a harness
- parse top-level commands from `--help`
- enforce policy before execution
- require JSON output where possible
- emit typed `ToolInvocation` and `ToolResult`

### 3. Runtime Wiring

Add runtime entry points to:

- discover/register/list/validate harnesses
- invoke a harness under a task
- auto-create a minimal software-control task when no task is supplied
- capture evidence from structured command output
- create approval requests for destructive commands
- update tool scorecards and budget ledgers

### 4. Control Plane

Expose software-control surfaces through the remote operator API:

- `GET /software/harnesses`
- `POST /software/harnesses/discover`
- `POST /software/harnesses/register`
- `POST /software/harnesses/<id>/validate`
- `POST /software/harnesses/<id>/invoke`
- `GET /software/bridge`
- `POST /software/bridge/configure`
- `POST /software/bridge/install-codex-skill`
- `POST /software/build-requests`

### 5. Evaluation

Add strategy comparison for software-control governance:

- completion rate
- approval-gate preservation
- evidence capture rate
- unsafe invocation block rate
- audit trace rate

## Capability Boundary

CLI-Anything does not literally make every installed application controllable by default.

The practical boundary is:

- if a real harness exists, the runtime can govern and invoke it
- if a harness does not exist, the runtime can track build/refine requests through the configured CLI-Anything bridge
- the runtime never silently falls back to unrestricted GUI clicking

## Main Files

- `src/contract_evidence_os/tools/anything_cli/models.py`
- `src/contract_evidence_os/tools/anything_cli/tool.py`
- `src/contract_evidence_os/runtime/service.py`
- `src/contract_evidence_os/storage/repository.py`
- `src/contract_evidence_os/storage/migrations.py`
- `src/contract_evidence_os/api/server.py`
- `src/contract_evidence_os/config.py`
- `src/contract_evidence_os/evals/harness.py`

## Risks

- CLI help parsing is intentionally lightweight and may need deeper introspection for richer harnesses.
- Generated harness build automation remains bridge-based because CLI-Anything itself is primarily a methodology/skill package, not a standalone builder daemon.
- High-risk pattern detection is conservative string matching in this milestone and should later evolve toward harness-native command metadata.

# Runbook: CLI-Anything Bridge Install and Register

## Preconditions

- A local clone of `HKUDS/CLI-Anything` exists.
- The runtime has access to that repository path.
- A generated harness executable such as `cli-anything-demo` or `cli-anything-blender` is installed or otherwise reachable.

## Steps

1. Configure the bridge with the repository path.
2. Install the bundled Codex skill through the bridge if it is not already present.
3. Register the harness executable with the operator API.
4. Validate the harness before first live use.
5. For destructive or high-risk command groups, confirm that approval behavior matches policy.

## Failure Modes

- Missing repo path: bridge stays configured but install/build requests cannot progress.
- Missing executable: registration fails or discovery returns no harnesses.
- JSON mode absent: validation fails and the harness should not be treated as agent-grade.

## Recovery

- Reconfigure the bridge to the correct repository path.
- Reinstall the Codex skill after cleanup if the target skill directory is missing or stale.
- Re-run harness validation after changes.

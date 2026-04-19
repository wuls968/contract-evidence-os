# Host Drain and Rolling Restart

## Goal

Move work away from a host without losing lease safety, continuity, or replay clarity.

## Procedure

1. Set the host or worker pool to drain mode.
2. Stop assigning new leases to the draining host.
3. Allow in-flight work to finish when safe, otherwise reclaim through the coordination path.
4. Restart the host or worker processes.
5. Re-register workers with fresh startup epochs and resume queued work from shared state.

## Success criteria

- no duplicate ownership,
- preserved checkpoints and handoff packets,
- clear governance events for the drain window,
- safe re-entry after restart.


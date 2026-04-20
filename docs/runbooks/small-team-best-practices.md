# Small-Team Best Practices Runbook

This runbook explains how to use Contract-Evidence OS as a small self-hosted team without losing clarity around ownership, review, memory, and coordination.

It assumes:

- one shared workspace
- browser console as the default human surface
- `ceos` and `/v1` as operator and automation surfaces
- explicit task ownership, reviewer posture, and evidence expectations

## 1. The Recommended Team Shape

The healthiest default setup is:

- one `admin`
- one or more `operator`
- one primary `reviewer`
- optional `viewer` accounts for inspection-only access

Use roles to separate authority, not to manufacture process overhead.

Good defaults:

- `admin` keeps auth, provider, and system policy healthy
- `operator` drives task execution and collaboration
- `reviewer` signs off on trust-sensitive work
- `viewer` inspects dashboard, audit, and task posture without mutating state

## 2. The Core Task Roles

For each serious task, set these roles explicitly:

- one `owner`
- zero to many `operators`
- one primary `reviewer`
- zero to many `watchers`
- one current `approval_assignee`

If a task feels confused, the first thing to fix is usually ownership or reviewer posture.

## 3. The Daily Operating Loop

For a small team, the most reliable daily rhythm is:

1. open `/dashboard` and inspect queue pressure, approvals, usage, and overall health
2. open `/collaboration` and confirm who owns the active tasks
3. open `/doctor` when provider, auth, or readiness looks suspicious
4. use `/tasks/:taskId` for deep task work instead of trying to infer everything from the dashboard
5. generate handoff or completion summaries before people change shifts or stop work

That loop keeps the runtime coordinated instead of fragmented.

## 4. Ownership, Review, And Watchers

Use these rules consistently:

- the `owner` is accountable for progress
- the `reviewer` is accountable for trust-sensitive review
- `operators` can execute, but should not silently replace the task story
- `watchers` stay informed without taking execution ownership
- the `approval_assignee` should always be someone who can act soon

Bad pattern:

- everyone is an operator
- nobody is the reviewer
- approvals sit with a disconnected admin

Good pattern:

- one visible owner
- one visible reviewer
- one explicit approval assignee
- watchers used for visibility, not hidden responsibility

## 5. Same-Task Concurrency: Lease, Branch, Handoff

Contract-Evidence OS is designed for coordinated concurrency, not free-form simultaneous editing.

Use the three main concurrency tools like this:

### Lease

Use a lease when someone needs controlled authority over a decisive or high-risk task phase.

Best use cases:

- delivery
- verification
- review-sensitive update
- risky tool execution

Rule of thumb:

- one high-risk phase should have one active owner lease

### Branch

Use a branch for parallel work that should not silently rewrite the main task story yet.

Best use cases:

- research branch
- evidence branch
- tool-run branch
- alternative implementation path

Rule of thumb:

- parallel work belongs on branches until it is merged or reviewed

### Handoff

Use a handoff when responsibility moves from one person to another.

Best use cases:

- end of day
- operator goes offline
- reviewer asks another operator to continue
- owner delegates a sub-phase to someone else

Rule of thumb:

- if a human would explain context in chat, generate a handoff summary instead

## 6. How To Use Memory Safely As A Team

The memory system has explicit scopes:

- `personal_private`
- `task_shared`
- `workspace_shared`
- `published_trusted`

Use them this way:

### `personal_private`

Use for:

- scratch notes
- early synthesis
- tentative ideas
- local operator context

Do not treat this as team truth.

### `task_shared`

Use for:

- coordination notes
- per-task decisions
- current blockers
- evidence-backed handoff context

This is the normal shared layer for active work.

### `workspace_shared`

Use for:

- reusable team knowledge
- stable workarounds
- patterns that matter across tasks
- reviewed but not the strongest trust layer

### `published_trusted`

Use only for:

- reviewed memory
- benchmark-backed memory
- high-confidence shared guidance

This is the strongest layer and should be promoted deliberately.

## 7. Summary Best Practices

Use the summary types intentionally:

- `live_working_summary`
- `handoff_summary`
- `task_completion_summary`
- `workspace_digest`

Recommended habits:

- generate `handoff_summary` before ownership changes
- generate `task_completion_summary` before closing serious work
- promote only reviewed or benchmark-backed summaries into stronger shared scopes

## 8. When Review Should Be Mandatory

Require a reviewer when any of these are true:

- the task changes shared trusted memory
- the task promotes memory into `published_trusted`
- the task runs risky software-control actions
- the task changes strategy or routing posture
- the task claims benchmark-grade or audit-sensitive success

If none of those are true, light operator flow is often enough.

## 9. Approvals And Human Review

Use approvals for runtime safety.

Use review for trust.

Use benchmark sign-off for reproducibility.

Those are different control surfaces and should stay distinct.

Recommended flow:

1. operator proposes the action or result
2. reviewer checks evidence and audit context
3. approval assignee resolves runtime-sensitive approvals
4. benchmark sign-off happens only when reproducibility matters

## 10. Tool And Provider Strategy In Team Use

The runtime now exposes strategy posture. Use that as a team control signal.

Best practices:

- use balanced defaults for normal work
- prefer lower-cost profiles when the task is exploratory
- prefer stronger-quality or review-oriented profiles when reviewer trust matters
- inspect `/usage` before letting one task dominate provider spend
- use strategy candidates and canaries rather than changing routing assumptions informally

If a provider degrades or costs spike:

1. inspect `/usage`
2. inspect `/doctor`
3. inspect task-level strategy posture
4. adjust policy deliberately rather than by ad hoc prompt edits

## 11. What To Watch Every Day

If you only monitor a few things, monitor these:

- active tasks without clear owners
- approvals waiting too long
- tasks with branches but no merge or review movement
- fallback-heavy or degraded-provider usage
- maintenance incidents
- stale sessions or stale invitations
- memory promotions without corresponding review posture

## 12. Good Weekly Hygiene

Once or twice a week, do this:

1. inspect `/maintenance`
2. inspect `/audit`
3. inspect `/benchmarks`
4. inspect `/collaboration`
5. inspect `workspace_shared` and `published_trusted` memory posture
6. revoke stale sessions or invitations
7. review strategy candidates that have enough feedback to matter

## 13. Anti-Patterns To Avoid

Avoid these patterns:

- using `workspace_shared` as a dumping ground
- letting multiple people operate a high-risk phase without a lease
- skipping handoff summaries because “people can read the timeline”
- treating watchers as silent owners
- promoting memory without review
- letting approvals accumulate without an explicit assignee
- changing policy or provider posture by convention instead of through strategy records

## 14. Recommended Starting Configuration For A Small Team

For a team of 2-5 people, start with:

- one admin
- one reviewer
- one or two operators
- local accounts first
- OIDC later if needed
- one provider profile and one default model
- browser console as the default human surface
- CLI and `/v1` for automation and debugging

Then add complexity only when the runtime signals that you actually need it.

## 15. Related Docs

- [Getting Started](../manual/getting-started.md)
- [Complete User Guide](../manual/user-guide.md)
- [Operator API v1](../api/operator-v1.md)
- [Operator API v1 User Manual](../api/operator-v1-user-manual.md)

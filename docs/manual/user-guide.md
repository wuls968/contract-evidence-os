# Contract-Evidence OS User Guide

This is the complete operator manual for Contract-Evidence OS.

It is written for two audiences at the same time:

- people evaluating whether this system is the right runtime for their team
- people who need to install it, configure it, launch it, operate it, and troubleshoot it

If you only want the shortest first-run path, read [getting-started.md](getting-started.md).

If you want the full picture of how the system works and how to use it well, keep reading here.

## 1. What Contract-Evidence OS Is

Contract-Evidence OS is a **trusted runtime for contract-and-evidence work**.

That means it tries to answer a different question than a typical agent framework.

Instead of asking:

- “Can the model complete this prompt?”

it asks:

- “Can this work be compiled into an explicit contract?”
- “Can the result be linked back to evidence?”
- “Can another person inspect what happened?”
- “Can the system remember long-term state without losing traceability?”
- “Can risky actions stay governed?”
- “Can the runtime recover from interruption and still tell the truth about what happened?”

The system is built for local-first and self-hosted use, with small-team collaboration in mind.

## 2. The Core Mental Model

Contract-Evidence OS has four major layers.

### Trusted Runtime Core

The trusted runtime core handles:

- contract compilation
- execution coordination
- evidence-aware work
- approval and review logic
- audit logging
- benchmark and reproducibility surfaces

### AMOS Memory OS

AMOS is the long-term memory system.

It includes:

- episodic memory
- semantic memory
- procedural memory
- temporal memory
- source-grounded matrix pointers
- purge, rebuild, repair, contradiction handling, and maintenance

### Software Control Fabric

The software control fabric is the governed automation layer.

It is how the runtime can operate software through:

- harness manifests
- capability records
- action receipts
- replay diagnostics
- recovery hints
- failure clusters
- macros

### Browser Trust Console

The browser console is the default human interface.

It turns the runtime into something that can be operated by a person or a small team rather than only scripted from the CLI.

## 3. What The System Is Good At

The system is particularly strong when you need:

- an auditable AI agent
- a long-term memory agent
- a self-hosted AI agent runtime
- governed desktop automation
- human review inside the agent workflow
- task continuity across sessions
- token usage monitoring and cost visibility
- a browser console for operating the runtime

## 4. Recommended Install Path

From a fresh clone:

```bash
git clone https://github.com/wuls968/contract-evidence-os.git contract-evidence-os
cd contract-evidence-os
./scripts/install.sh --init-config
```

The installer will:

- create `.venv`
- install the project
- expose `ceos`, `ceos-server`, `ceos-worker`, `ceos-dispatcher`, and `ceos-maintenance`
- build the frontend bundle when `npm` is available
- guide you through local configuration
- write `runtime/config.local.json`
- write `runtime/.env.local`

## 5. What The Installer Configures

The installer asks for:

- operator host and port
- `CEOS_OPERATOR_TOKEN`
- provider kind
- provider base URL
- default model
- `CEOS_API_KEY`
- whether to run a lightweight provider verification

These are the two credentials you need to keep conceptually separate:

- `CEOS_OPERATOR_TOKEN`
  Protects the operator HTTP service and browser control plane.
- `CEOS_API_KEY`
  Authenticates against your model provider.

The operator token is for your runtime.

The API key is for your model provider.

## 6. Files You Will End Up With

### `runtime/config.local.json`

This stores structured runtime configuration, including:

- storage root
- service host and port
- observability toggles
- maintenance toggles
- software-control repo path
- provider kind
- default model
- default base URL

### `runtime/.env.local`

This stores local environment variables, including:

- `CEOS_OPERATOR_TOKEN`
- `CEOS_PROVIDER_KIND`
- `CEOS_API_KEY`
- `CEOS_API_BASE_URL`
- `CEOS_DEFAULT_MODEL`

This file is local plaintext by design. That is a tradeoff made for local-first usability.

## 7. The First Successful Launch

The most reliable first-start path is:

```bash
source runtime/.env.local
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos-server --config runtime/config.local.json
```

If that works:

- `doctor` tells you whether the runtime is ready
- `system-report` gives you a system-level summary
- `service-health` gives you a live runtime snapshot
- `ceos-server` keeps running and serves the dashboard

Then open:

- [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

## 8. Browser Console Flow

The browser flow is:

1. `/setup` if no bootstrap admin exists
2. `/login` once the admin exists
3. `/dashboard` after sign-in

This means the browser console is not only for inspection. It also participates in bootstrap and ongoing operations.

## 9. Dashboard Pages

### `/dashboard`

Use this page to get the overall trust posture:

- runtime health
- recent tasks
- blocked reasons
- approval inbox
- token usage summary
- audit trend
- benchmark posture
- collaboration counts

### `/tasks/:taskId`

This is the task cockpit.

It is the most important page when you need to understand one task deeply.

It shows:

- current status
- phase
- checkpoint
- usage for that task
- timeline
- collaboration state
- open questions
- approvals
- evidence trace
- trusted playbook
- memory snapshot
- collaboration leases, branches, and handoff windows
- strategy feedback, candidates, canaries, and promotion posture

This page is now also where you can actively coordinate work, not just inspect it.

Typical actions from the task cockpit include:

- acquire a lease for a phase such as `delivery` or `verification`
- create a branch for parallel evidence or tool work
- open a handoff window from one operator to another
- record strategy feedback after review
- propose and promote a strategy candidate after evaluation and canary

### `/memory`

This is the AMOS overview.

Use it when you want to inspect:

- task memory views
- project state
- maintenance posture

### `/software`

This is the governed automation console.

Use it to inspect:

- harnesses
- manifests
- failure clusters
- recovery hints

### `/maintenance`

This page shows the resident maintenance daemon and related runtime operations:

- incidents
- daemon runs
- recommendations
- mode

### `/usage`

This page is for token and cost monitoring.

Use it to inspect:

- 1h, 24h, and 7d windows
- provider-level consumption
- task-level token totals
- estimated cost
- fallback-heavy or degraded-provider patterns

### `/audit`

This is the audit ledger view.

Use it when you need an append-only view of what the runtime has been doing.

### `/benchmarks`

This page surfaces benchmark and reproducibility posture.

Use it to inspect:

- benchmark suites
- recent runs
- reproducibility status

### `/playbooks`

This page shows trusted execution templates and their step structure.

### `/collaboration`

This page surfaces:

- users
- roles
- sessions
- invitations
- task ownership and reviewer posture

### `/mcp`

This page is the MCP runtime surface.

Use it to inspect:

- connected or declared MCP servers
- exposed tools
- recent invocations
- permission decisions

### `/settings`

This is the configuration center.

It covers:

- provider configuration
- runtime settings
- OIDC providers
- roles and auth-adjacent configuration

### `/doctor`

This is the trust diagnostics page.

Use it first when something does not feel right.

It is designed to answer:

- is the config valid?
- is the provider ready?
- is OIDC configured correctly?
- is the frontend bundle available?
- is benchmark reproducibility ready?
- is audit ledger health okay?

## 10. Local Accounts, Roles, and OIDC

Contract-Evidence OS supports local accounts and browser sessions as the default shared-user model.

The core roles are:

- `admin`
- `operator`
- `reviewer`
- `viewer`

The model is still scope-aware internally, but the browser surface makes those permissions more visible.

OIDC is optional.

You can keep the system local-account-only if that is enough for your team.

When you need it, the settings surface supports generic OIDC configuration and provider testing.

## 11. Provider Configuration and API Setup

### OpenAI-compatible setup

Use this when you are calling:

- OpenAI
- a compatible OpenAI-style gateway
- a self-hosted compatible endpoint

Typical values:

- `CEOS_PROVIDER_KIND=openai-compatible`
- `CEOS_API_BASE_URL=https://api.openai.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=gpt-4.1-mini`

### Anthropic setup

Typical values:

- `CEOS_PROVIDER_KIND=anthropic`
- `CEOS_API_BASE_URL=https://api.anthropic.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=claude-sonnet-4-20250514`

### Deterministic fallback

If you want a local-only or partially configured setup at first, you can choose deterministic fallback behavior.

That lets you:

- start the runtime
- use the browser console
- inspect tasks, memory, maintenance, and software-control surfaces

without immediately depending on a live provider.

## 12. How To Change Configuration Later

You can change configuration in two ways:

1. file-based local config
2. browser settings center

The file-based path remains compatible and is still the most direct for local control.

When editing files manually, you usually touch:

- `runtime/config.local.json`
- `runtime/.env.local`

After editing `.env.local`, reload it:

```bash
source runtime/.env.local
```

Then rerun:

```bash
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json service-health
```

## 13. Task Flow, Approvals, and Human Review

The runtime is designed to keep risky or trust-sensitive work visible.

That means:

- tasks can block on approvals
- evidence can be reviewed
- outputs can stay in `draft` or `needs_review`
- delivery review can be explicit instead of implied
- benchmark sign-off can be part of the workflow

This is one of the biggest differences from a typical prompt-driven agent system.

### What a healthy task flow looks like

For one serious task, the intended path is usually:

1. create or resume the task
2. inspect the contract, status, and evidence trace
3. assign or confirm owner, reviewer, and approval assignee
4. use leases and branches when multiple people are involved
5. use a handoff summary when work changes hands
6. approve, deny, or review where required
7. inspect usage, audit, and memory before considering the task complete

This is why task operation is centered on the cockpit rather than on a bare task list.

### Concurrent task coordination

The system is designed for coordinated concurrency, not free-form simultaneous editing.

The main primitives are:

- **task ownership**: who is primarily responsible right now
- **lease**: who currently holds a controlled right to work a phase
- **branch**: a parallel slice of work such as evidence gathering or tool execution
- **handoff**: an explicit transfer window from one collaborator to another
- **reviewer**: the person accountable for review-sensitive decisions
- **watcher**: an observer who stays informed without taking execution ownership

The safest pattern is:

- one owner lease for the high-risk phase
- parallel branches for research, evidence, or tool runs
- merge and review before shared conclusions become the main task story

## 14. Evidence, Audit, Playbooks, and Benchmarks

### Evidence

Evidence in Contract-Evidence OS is not just “a source URL”.

The trusted-runtime direction adds and surfaces:

- source records
- evidence spans
- claims
- validation linkage

The goal is to answer:

- where did this conclusion come from?
- what exact part of the source matters?
- what was validated, and how?

### Audit

The audit ledger is the append-only trail of runtime activity.

It is designed to capture:

- contract activity
- evidence activity
- approval activity
- maintenance activity
- benchmark activity
- governed automation receipts
- MCP-related actions

### Playbooks

Playbooks are structured trusted execution patterns.

They are how the system can encode expected checkpoints, evidence requirements, and review expectations for recurring task types.

### Benchmarks and reproducibility

The benchmark and repro surfaces are there so the system can do more than “seem to work”.

They are there so you can observe whether changes remain reproducible and whether operational behavior still matches expectations.

## 15. AMOS Memory OS In Practice

AMOS is the memory layer behind long-horizon operation.

In practical terms, that means:

- the system remembers task state across sessions
- memory can be surfaced as timelines and project state
- memory can be maintained, repaired, purged, and rebuilt
- memory is source-grounded rather than left as a black box

When you inspect memory from the dashboard, you are not only seeing “chat history”.

You are seeing a runtime memory system with operational semantics.

### Memory scopes

The memory layer now has explicit trust and audience scopes:

- `personal_private`
- `task_shared`
- `workspace_shared`
- `published_trusted`

This matters because not every useful memory item should become team-trusted state immediately.

Use the scopes like this:

- `personal_private` for tentative notes, early thoughts, and individual scratch state
- `task_shared` for coordination state that belongs to one task and one team effort
- `workspace_shared` for reusable shared memory that is not yet the strongest trusted layer
- `published_trusted` for reviewed or benchmark-backed memory suitable for the highest shared trust posture

### Summary types

AMOS also separates summary types so long-horizon work stays understandable:

- `live_working_summary`
- `handoff_summary`
- `task_completion_summary`
- `workspace_digest`

In practice:

- use a handoff summary when another person needs to take over
- use a completion summary when the task is effectively done
- use a workspace digest when you want to lift repeated learning out of one task into broader shared memory

### Memory promotion and review

The default trust logic is intentionally conservative.

- Personal summaries can be generated freely.
- Shared summaries should be evidence-bound.
- `published_trusted` memory should only appear after explicit review or benchmark-backed confidence.

That conservative model is what lets memory stay useful without becoming a hidden source of drift.

## 16. Software Control Fabric

The software control fabric is how Contract-Evidence OS performs automation without abandoning governance.

Instead of opaque automation scripts, the system tries to surface:

- what capability exists
- what harness is responsible
- what risk class applies
- what receipt was produced
- how replay works
- what failure patterns have been seen before
- what recovery hints are available

This is why software automation remains inspectable.

## 17. MCP Runtime Surface

The MCP direction here is not “let MCP bypass the runtime”.

The goal is the opposite:

- expose CEOS capabilities through governed MCP surfaces
- connect external MCP tools without losing schema, permission, and audit context
- make MCP part of the trust model instead of a side channel

From the operator point of view, the important questions are:

- which MCP servers are available?
- which tools exist?
- what was invoked?
- what was denied?
- what got written to audit?

## 18. CLI and Operator API v1

The browser console is the default human surface, but the CLI and API still matter.

Useful commands include:

```bash
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos --config runtime/config.local.json api-contract
ceos --config runtime/config.local.json metrics-report
ceos --config runtime/config.local.json maintenance-report
ceos --config runtime/config.local.json software-control-report
```

The operator API v1 remains the stable programmatic surface.

Read:

- [../api/operator-v1.md](../api/operator-v1.md)

### Useful API recipes

Inspect the runtime:

```bash
curl \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  http://127.0.0.1:8080/v1/reports/system
```

Inspect one task:

```bash
curl \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  http://127.0.0.1:8080/v1/tasks/<task-id>/collaboration
```

Inspect one task's strategy state:

```bash
curl \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "http://127.0.0.1:8080/v1/strategy/overview?scope_key=<task-id>"
```

Create a collaboration branch:

```bash
curl \
  -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"actor":"operator@example.com","branch_kind":"evidence","title":"Collect final evidence"}' \
  http://127.0.0.1:8080/v1/tasks/<task-id>/branches
```

Create a strategy candidate:

```bash
curl \
  -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scope_key":"<task-id>","actor":"reviewer@example.com","strategy_kind":"summarization_policy","target_component":"summary.handoff","hypothesis":"Prefer reviewed handoff summaries.","supporting_signal_ids":["<signal-id>"]}' \
  http://127.0.0.1:8080/v1/strategy/candidates
```

## 19. Maintenance and Ongoing Operations

The maintenance layer is part of the runtime, not a separate afterthought.

Use `ceos-maintenance` when you want explicit maintenance actions.

Examples:

### Run one maintenance pass

```bash
ceos-maintenance --config runtime/config.local.json --once
```

### Start the resident loop

```bash
ceos-maintenance --config runtime/config.local.json --daemon --max-cycles 1
```

Use the dashboard maintenance page when you want the human-readable view of:

- daemon state
- incidents
- recommendations
- rollout posture

## 20. Token Usage and Cost Monitoring

The `/usage` page exists to answer:

- which provider is using tokens?
- which tasks are the biggest spenders?
- is fallback behavior increasing?
- is degraded provider behavior changing cost or usage posture?

This makes token monitoring operational instead of incidental.

## 21. Recommended Ways To Use The System

### Personal local operator

Use:

- local accounts
- deterministic fallback or one configured provider
- browser console + CLI

This is the simplest successful shape.

### Small team shared operator

Use:

- local accounts with clear roles
- shared browser console
- approvals and review queue
- benchmark posture in dashboard
- maintenance center
- OIDC if you need it

This is the default organizational shape the system is designed for right now.

### Small-team daily operating pattern

For a small team, a strong default rhythm is:

1. admins manage users, sessions, invitations, and provider/OIDC settings
2. operators own or branch work inside task cockpit pages
3. reviewers record feedback, approve risky actions, and promote strategy changes
4. watchers stay informed through collaboration views and audit
5. everyone uses `/usage`, `/maintenance`, `/audit`, and `/doctor` as shared operational truth surfaces

If you keep those responsibilities visible, the runtime stays much easier to trust.

### Enterprise-adjacent self-hosted exploration

You can also use the project as a base for more formal internal deployment.

Just keep in mind that the current architecture is:

- self-hosted first
- small-team first
- not yet a full enterprise multi-tenant platform

## 22. Troubleshooting

### `ceos` command not found

Your user-level bin directory is probably not on `PATH`.

The installer tells you which directory to add, typically:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### `ceos-server` exits immediately

The most common reason is missing operator token configuration.

Try:

```bash
source runtime/.env.local
ceos-server --config runtime/config.local.json
```

### Startup still fails

Run:

```bash
ceos --config runtime/config.local.json doctor
```

That report is the fastest way to understand whether:

- the operator token is missing
- provider configuration is invalid
- the dashboard bundle is missing
- bootstrap admin setup is incomplete
- OIDC readiness is not satisfied

### Provider is configured but the runtime still behaves like fallback

Check:

- `CEOS_API_KEY` is present
- `CEOS_API_BASE_URL` is correct
- `CEOS_PROVIDER_KIND` matches your endpoint
- you reloaded `.env.local`

### Collaboration actions succeed but the page still looks stale

Refresh the task cockpit or collaboration page and re-check:

- the selected task id
- the current browser session
- whether the action wrote an audit-visible event

If needed, compare the browser view with:

```bash
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json api-contract
```

and the corresponding `/v1/tasks/<task-id>/...` route.

### Strategy candidates are visible but do not promote

Usually this means one of three things:

- the feedback signal was recorded but the candidate still needs evaluation
- the canary has not been run or did not pass cleanly
- the acting user does not have the right reviewer / approver posture

Check the task cockpit strategy panel, then inspect the same task through the operator API if needed.

## 23. Documentation Map

If you want to go deeper after this guide:

- [getting-started.md](getting-started.md) for the shortest first-run path
- [../runbooks/small-team-best-practices.md](../runbooks/small-team-best-practices.md) for team coordination, memory hygiene, handoffs, and review posture
- [../api/operator-v1.md](../api/operator-v1.md) for API contract details
- [../api/operator-v1-user-manual.md](../api/operator-v1-user-manual.md) for practical API usage patterns and `curl` examples
- [../architecture/future-extension-path.md](../architecture/future-extension-path.md) for roadmap direction
- [../examples](../examples) for example runtime scenarios
- [../runbooks](../runbooks) for operational procedures
- [../adr](../adr) for architectural decisions

## 24. Final Guidance

If you only remember five things, remember these:

1. `runtime/config.local.json` is the structured runtime profile.
2. `runtime/.env.local` is where tokens and provider secrets live.
3. `ceos doctor` is the fastest way to understand why the runtime or dashboard is not ready.
4. The browser console is the best first place to operate the system once it is running.
5. Contract-Evidence OS is strongest when you use it as a trusted runtime with evidence, audit, review, memory, and governed automation together, not as a bare prompt wrapper.

If you remember five more:

1. Use the task cockpit as the main place to work one task deeply.
2. Use scoped memory instead of treating all memory as equally trusted.
3. Use leases, branches, and handoffs when multiple people are involved.
4. Use the strategy control plane to improve behavior through governed feedback, not hidden tweaks.
5. Treat `/usage`, `/maintenance`, `/audit`, `/benchmarks`, and `/doctor` as the runtime's operational truth surfaces.

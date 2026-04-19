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

## 23. Documentation Map

If you want to go deeper after this guide:

- [getting-started.md](getting-started.md) for the shortest first-run path
- [../api/operator-v1.md](../api/operator-v1.md) for API contract details
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

# Contract-Evidence OS Getting Started

This is the shortest reliable first-run guide for Contract-Evidence OS.

If you want the complete operator manual, read [user-guide.md](user-guide.md).

## 1. Install

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
- build the dashboard bundle when `npm` is available
- write `runtime/config.local.json`
- write `runtime/.env.local`

## 2. What You Will Be Asked

The installer will interactively ask for:

- the local operator service port
- `CEOS_OPERATOR_TOKEN`
- provider kind
- `CEOS_API_BASE_URL`
- default model
- `CEOS_API_KEY`
- whether to run a lightweight provider verification

These are different credentials:

- `CEOS_OPERATOR_TOKEN` protects your local control plane
- `CEOS_API_KEY` is your model provider API key

## 3. Start The System

The most reliable startup path is:

```bash
source runtime/.env.local
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos-server --config runtime/config.local.json
```

Then open:

- [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

Expected flow:

- `/setup` if no bootstrap admin exists
- `/login` after bootstrap
- `/dashboard` after sign-in

## 4. Important Dashboard Pages

- `/dashboard` for health, recent tasks, approvals, usage, and trust posture
- `/tasks/:taskId` for a single task timeline, evidence trace, playbook, collaboration state, and strategy actions
- `/memory` for AMOS overview
- `/software` for governed automation surfaces
- `/maintenance` for incidents and daemon posture
- `/usage` for token and cost monitoring
- `/settings` for runtime, provider, auth, and OIDC configuration
- `/doctor` for startup and readiness diagnostics

## 4.5. First Useful Operator Loop

Once the dashboard is open, a good first pass is:

1. open `/doctor` and confirm the runtime is actually ready
2. open `/settings` and verify provider + auth posture
3. open `/dashboard` and inspect system health, approvals, and usage
4. open one `/tasks/:taskId` page and confirm timeline, evidence, collaboration, and strategy state are visible
5. open `/collaboration` if you plan to use the runtime with more than one person

## 5. Most Common Startup Failure

The most common error is a missing operator token.

Typical fix:

```bash
source runtime/.env.local
ceos-server --config runtime/config.local.json
```

If you prefer, you can also pass the token directly:

```bash
ceos-server --config runtime/config.local.json --token "your-token"
```

## 6. API Configuration

### OpenAI-compatible

Typical values:

- `CEOS_PROVIDER_KIND=openai-compatible`
- `CEOS_API_BASE_URL=https://api.openai.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=gpt-4.1-mini`

### Anthropic

Typical values:

- `CEOS_PROVIDER_KIND=anthropic`
- `CEOS_API_BASE_URL=https://api.anthropic.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=claude-sonnet-4-20250514`

### Local-only fallback

If you want to bring the system up before configuring a live provider, choose deterministic fallback during install.

## 7. Useful Commands

```bash
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos --config runtime/config.local.json api-contract
ceos --config runtime/config.local.json metrics-report
ceos --config runtime/config.local.json maintenance-report
ceos --config runtime/config.local.json software-control-report
```

Useful API inspection:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" http://127.0.0.1:8080/v1/reports/system
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" http://127.0.0.1:8080/v1/tasks/<task-id>/collaboration
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" "http://127.0.0.1:8080/v1/strategy/overview?scope_key=<task-id>"
```

## 8. Maintenance

Run one maintenance pass:

```bash
ceos-maintenance --config runtime/config.local.json --once
```

Run the resident loop:

```bash
ceos-maintenance --config runtime/config.local.json --daemon --max-cycles 1
```

## 9. If Something Is Wrong

Start with:

```bash
ceos --config runtime/config.local.json doctor
```

That report tells you whether:

- the operator token is present
- the provider config is valid
- the frontend bundle exists
- bootstrap admin setup is complete
- OIDC readiness is okay

## 10. Read Next

- [Complete User Guide](user-guide.md)
- [Small-Team Best Practices Runbook](../runbooks/small-team-best-practices.md)
- [Operator API v1](../api/operator-v1.md)
- [Operator API v1 User Manual](../api/operator-v1-user-manual.md)

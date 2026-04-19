# Contract-Evidence OS Getting Started

This guide is the full local-first manual for installing, configuring, starting, and troubleshooting Contract-Evidence OS.

It is written for the two most common first-run questions:

1. Why does the service not start after install?
2. Where do I put the API configuration?

## 1. What Gets Configured

Contract-Evidence OS needs two separate kinds of credentials:

- `CEOS_OPERATOR_TOKEN`
  This protects the local or remote operator HTTP service started by `ceos-server`.
- `CEOS_API_KEY`
  This is the model provider key used when you want live provider requests instead of deterministic local fallback behavior.

These are different on purpose.

- The operator token secures your control plane.
- The API key talks to your model provider.

## 2. Recommended Install Path

From a fresh clone:

```bash
git clone https://github.com/wuls968/contract-evidence-os.git contract-evidence-os
cd contract-evidence-os
./scripts/install.sh --init-config
```

The installer will:

- create `.venv`
- install Contract-Evidence OS
- expose `ceos`, `ceos-server`, `ceos-worker`, `ceos-dispatcher`, and `ceos-maintenance`
- ask interactive questions and write local config for you

## 3. What The Installer Will Ask

When you use `--init-config`, the installer will ask for:

- the local operator service port
- the operator token to store as `CEOS_OPERATOR_TOKEN`
- which provider to use
  - OpenAI-compatible
  - Anthropic
  - Skip for now
- the provider base URL
- the default model name
- the provider API key to store as `CEOS_API_KEY`
- whether to run a lightweight provider verification now

By default, the installer writes:

- `runtime/config.local.json`
- `runtime/.env.local`

## 4. Files You Will End Up With

### `runtime/config.local.json`

This file stores structured runtime settings such as:

- storage root
- local host and port
- observability settings
- maintenance settings
- software control defaults
- provider kind, default model, and default base URL

### `runtime/.env.local`

This file stores local environment variables such as:

- `CEOS_OPERATOR_TOKEN`
- `CEOS_STORAGE_ROOT`
- `CEOS_PROVIDER_KIND`
- `CEOS_API_KEY`
- `CEOS_API_BASE_URL`
- `CEOS_DEFAULT_MODEL`

This file is local plaintext. That is intentional for local-first usability.

## 5. Starting The System Successfully

The most reliable first-start path is:

```bash
source runtime/.env.local
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos-server --config runtime/config.local.json
```

If everything is configured correctly:

- `system-report` should return JSON
- `doctor` should explain whether config, provider, admin setup, and dashboard bundle are ready
- `service-health` should return JSON with a healthy local runtime summary
- `ceos-server` should stay running instead of exiting immediately

## 5A. Open The Web Console

Once `ceos-server` is running, open:

- [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

The browser flow is:

- `/setup` on first run if no bootstrap admin exists
- `/login` once the admin account exists
- `/dashboard` after sign-in

Important routes:

- `/dashboard` for recent tasks, health, incidents, and usage summary
- `/tasks/:taskId` for task cockpit, evidence, approvals, and continuity
- `/memory` for AMOS overview, timeline, and project-state views
- `/software` for harnesses, manifests, macros, failure clusters, and recovery hints
- `/maintenance` for daemon state, incidents, and recommendations
- `/usage` for task-level and provider-level token monitoring
- `/settings` for runtime, provider, and OIDC configuration
- `/doctor` for startup and configuration diagnostics

## 6. Why Startup Sometimes Fails

The most common startup failure is:

```text
operator token is required via --token or CEOS_OPERATOR_TOKEN
```

That usually means you forgot to load the generated env file.

Fix:

```bash
source runtime/.env.local
ceos-server --config runtime/config.local.json
```

If you do not want to source the env file, you can also pass the token directly:

```bash
ceos-server --config runtime/config.local.json --token "your-token"
```

## 7. API Configuration

### OpenAI-compatible setup

Use this if you want to talk to:

- OpenAI
- a compatible OpenAI-style gateway
- a self-hosted compatible endpoint

Typical values:

- `CEOS_PROVIDER_KIND=openai-compatible`
- `CEOS_API_BASE_URL=https://api.openai.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=gpt-4.1-mini`

The runtime uses the configured base URL and resolves the live request path internally.

### Anthropic setup

Typical values:

- `CEOS_PROVIDER_KIND=anthropic`
- `CEOS_API_BASE_URL=https://api.anthropic.com/v1`
- `CEOS_API_KEY=...`
- `CEOS_DEFAULT_MODEL=claude-sonnet-4-20250514`

## 8A. Token And Cost Monitoring

The console usage page is designed to answer:

- which provider is consuming tokens
- which tasks are currently the biggest spenders
- whether fallback-heavy or degraded-provider behavior is spiking

Open `/usage` to inspect:

- 1h / 24h / 7d windows
- provider token totals
- task token totals
- estimated cost where available

## 8. How To Change API Settings Later

Open:

- `runtime/.env.local`
- `runtime/config.local.json`

The env file is where you usually change secrets and override values.

After editing:

```bash
source runtime/.env.local
```

Then rerun:

```bash
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
```

## 9. How Provider Verification Works

If you choose verification during install, the installer will run a lightweight connectivity check:

- OpenAI-compatible providers are checked through a simple authorized request
- Anthropic providers are checked through a lightweight authenticated endpoint probe

This is meant to catch:

- wrong API key
- wrong base URL
- unreachable endpoint
- auth failure

If verification fails, installation still completes, but you should fix `runtime/.env.local` before running live tasks.

## 10. Useful Commands

### Local inspection

```bash
ceos --config runtime/config.local.json doctor
ceos --config runtime/config.local.json system-report
ceos --config runtime/config.local.json service-health
ceos --config runtime/config.local.json api-contract
```

### Start the local control plane

```bash
source runtime/.env.local
ceos-server --config runtime/config.local.json
```

### Run maintenance

```bash
ceos-maintenance --config runtime/config.local.json --once
```

### Start the resident maintenance loop

```bash
ceos-maintenance --config runtime/config.local.json --daemon --max-cycles 1
```

## 11. Troubleshooting

### `ceos` command not found

Your user-level bin directory is not on `PATH`.

The installer tells you which directory to add, usually:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Service exits immediately

Usually this means:

- you did not `source runtime/.env.local`
- `CEOS_OPERATOR_TOKEN` is missing

Start with:

```bash
ceos --config runtime/config.local.json doctor
```

That report will tell you whether the operator token, provider config, bootstrap admin, and frontend bundle are ready.

### Live provider is configured but tasks still behave like deterministic fallback

Check:

- `CEOS_API_KEY` is present
- `CEOS_API_BASE_URL` is correct
- `CEOS_PROVIDER_KIND` matches your endpoint
- you reloaded the env file after editing it

### I want local-only behavior for now

Choose `Skip for now (deterministic/local-only)` during install.

That lets you start the system without live provider access while still using the local runtime, memory, operator surface, and governed software-control paths.

## 12. Mental Model

If you remember only one thing, remember this:

- `runtime/config.local.json` is the structured runtime profile
- `runtime/.env.local` is where tokens and provider secrets live
- `ceos doctor` is the fastest way to understand why startup or the dashboard is not ready
- `runtime/.env.local` is where the secrets and local overrides live

The shortest reliable loop is:

```bash
source runtime/.env.local
ceos --config runtime/config.local.json system-report
ceos-server --config runtime/config.local.json
```

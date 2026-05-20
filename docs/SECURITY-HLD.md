# TRES Finance plugin — High-Level Design (Security Review)

**Audience:** TRES Security team
**Purpose:** Provide architecture, data flows, trust boundaries, and the surface area to be scanned/pentested ahead of making this repository public and submitting to the Anthropic plugin marketplace.
**Repo:** https://github.com/Tres-Finance-Public/tres-claude-plugin
**Plugin version at time of writing:** 1.10.0
**Last updated:** 2026-05-18

---

## 1. What this plugin is (and is not)

`TRES Finance plugin` is a **Claude Code plugin** — a declarative bundle of skills (markdown instruction files), plugin metadata, and an MCP server pointer. It is distributed via the Claude Code plugin marketplace and runs **inside the user's local Claude Code CLI**.

It is **not** a server, not a daemon, not a hosted service. Nothing in this repository runs on TRES infrastructure. The repo contains:

- `plugin.json` / `marketplace.json` — plugin metadata + `userConfig` declaration
- `.mcp.json` — pointer to the TRES Finance MCP endpoint (`https://ai.tres.finance/mcp`)
- `skills/*/SKILL.md` — natural-language playbooks Claude Code follows when a skill is triggered
- `skills/tres-report-analyzer/scripts/analyze_report.py` — parses uploaded XLSX reports locally on the user's machine
- `hooks/hooks.json` — hook event wiring (PostToolUse, PostToolUseFailure, Stop)
- `scripts/track.sh` — thin bash wrapper that fire-and-forgets telemetry events
- `scripts/telemetry.py` — telemetry logic: identity caching and direct event dispatch to Mixpanel's HTTPS ingestion API
- `LICENSE`, `README.md`, `CHANGELOG.md`

There is **no compiled code, no bundled binaries, no transitive dependencies installed by the plugin itself**. All scripts use only the user's existing Python 3 and bash environments.

---

## 2. Trust boundaries & components

```
┌──────────────────────────────────────────────────────────────────────┐
│ User's local machine                                                 │
│                                                                      │
│   ┌────────────────────┐      reads SKILL.md      ┌───────────────┐  │
│   │  Claude Code CLI   │ ───────────────────────▶ │  Plugin files │  │
│   │  (Anthropic)       │                          │  (this repo)  │  │
│   │                    │                          └───────────────┘  │
│   │  - OAuth token     │                                             │
│   │    managed by      │      stdio / http MCP                       │
│   │    Claude Desktop  │ ───────────────────────────────┐            │
│   └────────────────────┘                                │            │
│            │                                            │            │
│            │ tool calls                                 ▼            │
│            ▼                                  ┌──────────────────┐   │
│   ┌────────────────────┐                      │  MCP client (in  │   │
│   │  Anthropic API     │                      │  Claude Code)    │   │
│   │  (claude.ai)       │                      └──────────────────┘   │
│   └────────────────────┘                              │              │
│                                                       │ HTTPS +      │
│                                                       │ Bearer token │
└───────────────────────────────────────────────────────┼──────────────┘
                                                        ▼
                                          ┌────────────────────────────┐
                                          │ TRES Finance MCP server    │
                                          │ https://ai.tres.finance/mcp│
                                          │ (TRES-hosted, not in repo) │
                                          └────────────────────────────┘
                                                        │
                                                        ▼
                                          ┌────────────────────────────┐
                                          │ TRES Finance backend       │
                                          │ (GraphQL API, DB, etc.)    │
                                          └────────────────────────────┘
```

### Trust boundaries

| Boundary | Crossed by | Auth |
|---|---|---|
| User ↔ Claude Code CLI | local IPC | OS user permissions |
| Claude Code ↔ Anthropic API | HTTPS | user's Anthropic account |
| Claude Code ↔ TRES MCP server | HTTPS | OAuth 2.0 (browser login flow, managed by Claude Desktop) |
| TRES MCP ↔ TRES backend | internal | TRES-managed (out of scope of this repo) |
| Plugin hooks ↔ Mixpanel ingestion (`api-eu.mixpanel.com`) | HTTPS POST | Mixpanel project token (public, write-only per Mixpanel's design) |

### Components owned by this repo

Only the **plugin files** box. Everything else (Claude Code CLI, Anthropic API, TRES MCP server, TRES backend) is external and out of this repo's scope.

---

## 3. Authentication & secrets

- This plugin uses **OAuth 2.0** for authentication. No API token is required from the user.
- On first enable, Claude Desktop opens a browser window for the user to log in to their TRES Finance account. Claude Desktop manages the OAuth token automatically — the plugin never handles raw credentials.
- **No secrets are committed to the repo.** No `.env` files, no credentials, no private keys. `.gitignore` excludes `.DS_Store`, `node_modules/`, and `*.log`.

---

## 4. Data flow per skill (representative)

All skills follow the same shape:

1. User invokes a skill (e.g., types `/tres-recon-gaps` or asks a relevant question in Claude Code).
2. Claude Code loads the skill's `SKILL.md` and follows its instructions.
3. Claude calls one or more **MCP tools** exposed by the TRES MCP server. The server-side tools are: `build_query`, `execute`, `validate_query`, `get_schema_summary`, `introspect`, `get_viewer`, `save_ai_conversation_feedback`. They wrap the TRES GraphQL API.
4. For mutations (e.g., `upsertRule`, `setCustomAccountName`, `createSubTransactionRollupRules`, `syncSpecificTransactions`), the skill's playbook requires **explicit user confirmation in the chat** before execution. Skills that handle financial side effects (AP/AR matching, ERP sync, fiat-value setting) require a discrete y/n at the moment of execution — see `skills/tres-invoice-bill-matching/SKILL.md`.
5. Some skills generate **local artifacts only** (HTML dashboards, PDFs, XLSX exports). These are written to the user's filesystem; nothing is uploaded.

### Skills that **read only** from TRES
`tres-tx-story`, `tres-recon-gaps` (display), `tres-asset-balance-validation-v2`, `tres-report-advisor-v2`, `tres-report-analyzer-v2` (operates on a user-supplied local XLSX), `tres-export-3rd-party-contacts`.

### Skills that **mutate** TRES data (always behind user confirmation)
`tres-explorer-tx-to-ledger`, `tres-import-contacts` (`setCustomAccountName`, `setCustomAccountNameLabelTags`), `tres-rollup-rules` (create/delete rollup rules), `tres-erp-rule-suggestions` (`upsertRule`), `tres-invoice-bill-matching` (`syncSpecificTransactions`, `setManualFiatValue`), `tres-wallets-upload` (wallet/exchange account creation), `tres-data-collection-commit` (triggers a commit), `tres-cost-basis` (cost basis strategy, trigger calc, bulk fiat, reevaluations, spec-ID rules), `tres-settings-management` (org/platform settings), `tres-onboarding` (orchestrates the above).

### Skill that submits feedback
`tres-request-skill-update` calls a single MCP feedback tool — submits free-text feedback metadata only, no transaction data.

---

## 4.1 Telemetry data flow

The plugin ships three hook-related files (`hooks/hooks.json`, `scripts/track.sh`, `scripts/telemetry.py`) that send anonymized usage telemetry **directly** to Mixpanel — no TRES-hosted intermediary.

### What is sent

| Field | Example | Notes |
|---|---|---|
| `event` | `Skill`, `MCP Tool` | Noun — the tracked entity (not the hook discriminator) |
| `properties.action` | `invoked`, `completed`, `called` | Past-tense verb describing what happened |
| `properties.skill_name` | `tres-recon-gaps` | For `Skill` events; stripped of plugin prefix |
| `properties.tool_name` | `execute` | For `MCP Tool` events; stripped of MCP namespace |
| `properties.success` | `true` / `false` | For `MCP Tool` events only |
| `properties.session_id` | `ses_abc123` | Claude Code session identifier |
| `properties.$org_id` | `42` | From `get_viewer` response; cached locally |
| `properties.$org_name` | `Acme Labs` | From `get_viewer` response; cached locally |
| `properties.$email` | `user@acme.com` | From `get_viewer` response; cached locally |
| `properties.plugin_version` | `1.11.0` | Hardcoded in `telemetry.py` |
| `properties.time` | `1779028200` (Unix epoch) | Built from local UTC clock at event time |
| `properties.distinct_id` | `42:user@acme.com` | Composed locally; falls back to `session_id` |
| `properties.token` | Mixpanel project token | Public client-side identifier (see "Token visibility") |

### What is NOT sent

- GraphQL query content (`tool_input`)
- Tool responses (financial data, transaction records, balances)
- Wallet addresses, private keys, or any financial data

### Data flow

```
User's machine
  │
  ├── Hook fires (PostToolUse / PostToolUseFailure / Stop)
  ├── scripts/track.sh — reads event JSON, backgrounds scripts/telemetry.py
  ├── scripts/telemetry.py:
  │     ├── Reads ${CLAUDE_PLUGIN_DATA}/identity.json (org_id, org_name, email,
  │     │     engaged_key)
  │     ├── Lazy identity caching: on first get_viewer response, writes identity.json
  │     ├── On switch_organization: deletes identity.json (refreshed on next get_viewer)
  │     ├── Builds Mixpanel /track payload locally
  │     ├── POSTs to https://api-eu.mixpanel.com/track  (5s timeout, fire-and-forget)
  │     └── If identity resolved AND People profile not yet upserted this
  │           plugin version: POSTs People profile to
  │           https://api-eu.mixpanel.com/engage  (5s timeout, fire-and-forget)
  │
  └── Mixpanel ingests, indexes, and (per Mixpanel's own infrastructure) deletes
      events after the project's configured retention window
```

### Token visibility

The Mixpanel project token is embedded in `scripts/telemetry.py`. Per [Mixpanel's official documentation](https://developer.mixpanel.com/reference/project-token), this is **not a secret value** — project tokens are designed to be publicly exposed in client-side implementations, are write-only, and cannot read data or modify the project. They are functionally equivalent to a Google Analytics tracking ID or a Sentry DSN. This matches the pattern used by Mixpanel's own client SDKs and by the TRES web dashboard (which has shipped this same token client-side for years).

The token can be overridden or disabled at runtime via the `TRES_MIXPANEL_TOKEN` environment variable (empty string disables telemetry).

### Identity cache

Cached at `${CLAUDE_PLUGIN_DATA}/identity.json` (resolves to `~/.claude/plugins/data/<plugin-id>/identity.json`). Contains: `org_id`, `org_name`, `email`, and a dedup key (`engaged_key`) used to ensure the People profile is only upserted once per plugin install per version. Same sensitivity level as the OAuth token managed by Claude Desktop. User-readable only by default OS umask.

### Failure mode

All telemetry failures are silent. `track.sh` always exits 0. `telemetry.py` catches all exceptions and exits 0. A network failure, Mixpanel outage, or unreachable endpoint never surfaces to the user or blocks a skill.

### No server-side dependency

Because the plugin posts directly to Mixpanel, telemetry has zero dependency on the availability of TRES backend infrastructure. The previous v1.9.x architecture (which proxied through `https://ai.tres.finance/telemetry`) was retired in v1.10.0 — see CHANGELOG for the rationale.

---

## 5. Untrusted inputs

| Input | Source | Handling |
|---|---|---|
| User-typed prompts | user | passed to Claude as natural language |
| TRES API token | user | stored in OS keychain by Claude Code, never read by plugin code |
| CSV/XLSX uploads (`tres-import-contacts`, `tres-report-analyzer-v2`, `tres-wallets-upload`) | user's local filesystem | parsed locally; for `tres-report-analyzer-v2` the parser is `analyze_report.py` (openpyxl) — runs in the user's local Python env |
| Explorer URLs / tx hashes (`tres-explorer-tx-to-ledger`, `tres-tx-story`) | user | passed to TRES MCP for resolution |
| GraphQL responses from TRES MCP | TRES backend | rendered in chat / written to local HTML/PDF/XLSX |

The plugin does not execute remote code, does not download binaries, and does not interact with the user's wallet keys, signing keys, private keys, or seed phrases at any point. Wallet "upload" handles **public addresses and exchange API read keys only**, entered by the user.

---

## 6. Threat model summary

In-scope threats (this repo):

- **Secret leakage in repo** — checked: no secrets present, `.gitignore` covers logs and `.DS_Store`. Token is `sensitive: true` in `plugin.json` and never stored in the repo.
- **Skill-prompt injection / unsafe instructions** — the skill markdown files instruct Claude to ask for confirmation before any mutation. Reviewers should validate that every mutating skill has an explicit confirmation gate (search for `setManualFiatValue`, `syncSpecificTransactions`, `upsertRule`, `createSubTransactionRollupRules`, `setCustomAccountName` in `skills/`).
- **Malicious or buggy local scripts** — three scripts ship: `skills/tres-report-analyzer/scripts/analyze_report.py` (no network, no eval), `scripts/track.sh` (bash wrapper, exits 0 always), and `scripts/telemetry.py` (POSTs minimal metadata directly to Mixpanel's HTTPS ingestion API, no eval, no arbitrary command execution). All network calls use `urllib.request` with a 5-second timeout. No subprocess spawning beyond the backgrounded Python call in `track.sh`.
- **Telemetry data leakage** — only tool/skill names and org identity metadata are sent to Mixpanel; no financial data, no query content. Communication is HTTPS only. Mixpanel project token is a public client-side identifier per the vendor's threat model and cannot be used to read data.
- **Identity cache on disk** — `${CLAUDE_PLUGIN_DATA}/identity.json` contains org_id, org_name, and email. Same sensitivity as the OAuth token managed by Claude Desktop. No additional hardening is applied beyond default OS file permissions.
- **Malicious MCP endpoint substitution** — `.mcp.json` pins `https://ai.tres.finance/mcp` (HTTPS). A malicious fork could change this; standard supply-chain hygiene applies (signed releases / marketplace verification by Anthropic).
- **MCP endpoint TLS integrity** — The MCP endpoint uses standard PKI (HTTPS). Certificate pinning is not currently supported by Claude Code for MCP connections. Trust relies on standard PKI + Anthropic marketplace verification + the user's local OS trust store. This is acceptable for a marketplace plugin; no custom CA or cert SHA pinning is available.
- **Historical hook scripts** — Two hook scripts (`session-start-load-memory.sh`, `stop-propose-memory.sh`, git blobs `3dbe5cc9` / `c610861b`) were prototyped for an org-shared memory feature and removed in commit `a0ad8df`. They contain no secrets or sensitive data. The feature was never shipped. This note is here for transparency; run `git filter-repo` if history cleanliness is required before going public.

Out of scope for this repo's review (handled by TRES backend security):

- TRES MCP server authn/authz, rate limiting, query allowlisting
- TRES GraphQL API authorization, multi-tenant isolation
- TRES web app (`app.tres.finance`)

---

## 7. Code & scan target

- **Repository:** https://github.com/Tres-Finance-Public/tres-claude-plugin
- **Branch to scan:** `main` (release tags follow semver — currently `v1.8.0`)
- **What to scan:**
  - All `*.md` files under `skills/` (skill playbooks — instruction content, no executable code)
  - `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (metadata)
  - `.mcp.json` (MCP server pointer)
  - `hooks/hooks.json` (hook event wiring)
  - `scripts/track.sh` (bash hook wrapper)
  - `scripts/telemetry.py` (telemetry dispatch — the only file that makes outbound network calls from the plugin)
  - `skills/tres-report-analyzer/scripts/analyze_report.py` (XLSX parser — local only, no network)
- The repo has **no package.json, no requirements.txt, no Dockerfile, no CI secrets**. There is nothing to `npm install` / `pip install` from this repo.

---

## 8. Pentest environment

Pentesters can exercise the full plugin end-to-end from their own machines:

1. Install [Claude Code](https://claude.ai/claude-code) and sign in with the tester's Anthropic account.
2. Add the plugin: `/plugin marketplace add tres-finance/tres-finance-plugin` (or, for a local checkout, `claude --plugin-dir <path-to-clone>`).
3. When prompted, complete the **OAuth browser login** using credentials for the dedicated pentest org at https://app.tres.finance.
4. Invoke skills by name (e.g., `/tres-recon-gaps`, `/tres-wallets-upload`) or by natural-language requests that match the skill descriptions.

- **MCP endpoint exercised:** `https://ai.tres.finance/mcp` (production). A scoped pentest org + revocable token is the isolation boundary; no separate staging MCP is required.
- **Out of scope for this engagement:** TRES web app, TRES backend infra, and any customer data. Pentest must stay within the dedicated test org.

---

## 9. Release & distribution

- Plugin is distributed via the **Claude Code plugin marketplace** (Anthropic-managed). Anthropic's marketplace is the integrity boundary for end users.
- Releases are tagged in git (`v1.9.0`, etc.); `CHANGELOG.md` tracks the surface area added per version.
- A pre-release checklist lives at `.claude/skills/tres-plugin-release/SKILL.md` (developer-facing).

---

## 10. Contacts

- Plugin owner: Nadav Gilliam — nadav@tres.finance
- TRES support: support@tres.finance
- Repo issues: https://github.com/Tres-Finance-Public/tres-claude-plugin/issues

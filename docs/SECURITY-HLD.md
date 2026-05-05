# TRES Finance plugin — High-Level Design (Security Review)

**Audience:** TRES Security team
**Purpose:** Provide architecture, data flows, trust boundaries, and the surface area to be scanned/pentested ahead of making this repository public and submitting to the Anthropic plugin marketplace.
**Repo:** https://github.com/Tres-Finance-Public/tres-claude-plugin
**Plugin version at time of writing:** 1.8.0
**Last updated:** 2026-04-27

---

## 1. What this plugin is (and is not)

`TRES Finance plugin` is a **Claude Code plugin** — a declarative bundle of skills (markdown instruction files), plugin metadata, and an MCP server pointer. It is distributed via the Claude Code plugin marketplace and runs **inside the user's local Claude Code CLI**.

It is **not** a server, not a daemon, not a hosted service. Nothing in this repository runs on TRES infrastructure. The repo contains:

- `plugin.json` / `marketplace.json` — plugin metadata + `userConfig` declaration
- `.mcp.json` — pointer to the TRES Finance MCP endpoint (`https://ai.tres.finance/mcp`)
- `skills/*/SKILL.md` — natural-language playbooks Claude Code follows when a skill is triggered
- One helper script: `skills/tres-report-analyzer-v2/scripts/analyze_report.py` (parses uploaded XLSX reports locally on the user's machine)
- `LICENSE`, `README.md`, `CHANGELOG.md`

There is **no compiled code, no bundled binaries, no transitive dependencies installed by the plugin itself**. The Python script uses only the user's existing Python environment.

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
`explorer-tx-to-ledger`, `tres-import-contacts` (`setCustomAccountName`, `setCustomAccountNameLabelTags`), `tres-rollup-rules` (create/delete rollup rules), `tres-erp-rule-suggestions` (`upsertRule`), `tres-invoice-bill-matching` (`syncSpecificTransactions`, `setManualFiatValue`), `wallets-upload-v3` (wallet/exchange account creation), `tres-data-collection-commit` (triggers a commit), `tres-settings-management` (org/platform settings), `tres-onboarding` (orchestrates the above).

### Skill that submits feedback
`request-skill-update` calls a single MCP feedback tool — submits free-text feedback metadata only, no transaction data.

---

## 5. Untrusted inputs

| Input | Source | Handling |
|---|---|---|
| User-typed prompts | user | passed to Claude as natural language |
| TRES API token | user | stored in OS keychain by Claude Code, never read by plugin code |
| CSV/XLSX uploads (`tres-import-contacts`, `tres-report-analyzer-v2`, `wallets-upload-v3`) | user's local filesystem | parsed locally; for `tres-report-analyzer-v2` the parser is `analyze_report.py` (openpyxl) — runs in the user's local Python env |
| Explorer URLs / tx hashes (`explorer-tx-to-ledger`, `tres-tx-story`) | user | passed to TRES MCP for resolution |
| GraphQL responses from TRES MCP | TRES backend | rendered in chat / written to local HTML/PDF/XLSX |

The plugin does not execute remote code, does not download binaries, and does not interact with the user's wallet keys, signing keys, private keys, or seed phrases at any point. Wallet "upload" handles **public addresses and exchange API read keys only**, entered by the user.

---

## 6. Threat model summary

In-scope threats (this repo):

- **Secret leakage in repo** — checked: no secrets present, `.gitignore` covers logs and `.DS_Store`. Token is `sensitive: true` in `plugin.json` and never stored in the repo.
- **Skill-prompt injection / unsafe instructions** — the skill markdown files instruct Claude to ask for confirmation before any mutation. Reviewers should validate that every mutating skill has an explicit confirmation gate (search for `setManualFiatValue`, `syncSpecificTransactions`, `upsertRule`, `createSubTransactionRollupRules`, `setCustomAccountName` in `skills/`).
- **Malicious or buggy local script** — only one script ships: `skills/tres-report-analyzer-v2/scripts/analyze_report.py`. It parses XLSX with openpyxl on the user's machine and emits findings to stdout. No network, no eval.
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
  - `skills/tres-report-analyzer-v2/scripts/analyze_report.py` (the only executable file)
- The repo has **no package.json, no requirements.txt, no Dockerfile, no CI secrets**. There is nothing to `npm install` / `pip install` from this repo.

---

## 8. Pentest environment

Pentesters can exercise the full plugin end-to-end from their own machines:

1. Install [Claude Code](https://claude.ai/claude-code) and sign in with the tester's Anthropic account.
2. Add the plugin: `/plugin marketplace add tres-finance/tres-finance-plugin` (or, for a local checkout, `claude --plugin-dir <path-to-clone>`).
3. When prompted, complete the **OAuth browser login** using credentials for the dedicated pentest org at https://app.tres.finance.
4. Invoke skills by name (e.g., `/tres-recon-gaps`, `/wallets-upload-v3`) or by natural-language requests that match the skill descriptions.

- **MCP endpoint exercised:** `https://ai.tres.finance/mcp` (production). A scoped pentest org + revocable token is the isolation boundary; no separate staging MCP is required.
- **Out of scope for this engagement:** TRES web app, TRES backend infra, and any customer data. Pentest must stay within the dedicated test org.

---

## 9. Release & distribution

- Plugin is distributed via the **Claude Code plugin marketplace** (Anthropic-managed). Anthropic's marketplace is the integrity boundary for end users.
- Releases are tagged in git (`v1.8.0`, etc.); `CHANGELOG.md` tracks the surface area added per version.
- A pre-release checklist lives at `.claude/skills/tres-plugin-release/SKILL.md` (developer-facing).

---

## 10. Contacts

- Plugin owner: Nadav Gilliam — nadav@tres.finance
- TRES support: support@tres.finance
- Repo issues: https://github.com/Tres-Finance-Public/tres-claude-plugin/issues

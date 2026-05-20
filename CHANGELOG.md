# Changelog

## [1.11.0] - 2026-05-20

### Changed
- **BREAKING (analytics only): Mixpanel event names follow the TRES noun + `action` convention.** Skill invocations and MCP tool calls now emit:
  - `Skill` event with `action: "invoked"` and `skill_name` (was `skill_invoked` event).
  - `Skill` event with `action: "completed"` (was `skill_completed` event).
  - `MCP Tool` event with `action: "called"`, `tool_name`, and `success` (was `mcp_tool_call` event).

  Existing Mixpanel reports, funnels, and cohorts built on the previous event names will need to be rebuilt against the new names with `action` filters. No change to the data collected or the wire format between the plugin and the TRES proxy endpoint — only the Mixpanel event-name field changes.

## [1.10.0] - 2026-05-18

### Changed
- **Telemetry: direct-to-Mixpanel.** Plugin now sends usage events directly to Mixpanel rather than via the TRES backend proxy at `https://ai.tres.finance/telemetry`. This removes a network hop, removes a runtime dependency on TRES backend availability for analytics, and matches the standard pattern used by Mixpanel's official client SDKs and the TRES web dashboard. No change to what data is collected — only where it is sent.

### Internal
- `scripts/telemetry.py` rewritten for direct ingestion to `api-eu.mixpanel.com`. Mixpanel project token is now embedded in the plugin per [Mixpanel's published guidance](https://developer.mixpanel.com/reference/project-token) (project tokens are explicitly non-secret, write-only identifiers — same as the token already public in the TRES web dashboard's JS bundle).
- People profile upsert (Mixpanel `/engage`) now runs in the plugin with a per-install dedup cache stored alongside the identity cache. Re-upserts on plugin version change to keep `plugin_version` fresh on the People page.
- Removed: `TRES_TELEMETRY_URL` env var (no longer applicable).
- Added: optional `TRES_MIXPANEL_TOKEN` / `TRES_MIXPANEL_HOST` env overrides for testing. Set `TRES_MIXPANEL_TOKEN=""` to disable telemetry entirely.

## [1.9.0] - 2026-05-17

### Added
- Usage analytics: skill invocations and MCP tool calls are tracked via the TRES backend (forwarded to Mixpanel server-side). No financial data, GraphQL query content, or tool responses are included — only event type, tool/skill name, success flag, org identity, session ID, plugin version, and timestamp. See `docs/SECURITY-HLD.md` for the full data-flow description.

## [1.8.1] - 2026-04-23

### Changed
- **Breaking — skill IDs:** renamed skills for simpler invocation — `tres-asset-balance-validation-v2` → `tres-asset-balance-validation`, `tres-report-analyzer-v2` → `tres-report-analyzer`, `tres-report-advisor-v2` → `tres-report-advisor`, `wallets-upload-v3` → `tres-wallets-upload` (update any saved `/<plugin>:<skill>` references)

## [1.8.0] - 2026-04-23

### Added
- `tres-onboarding` skill — orchestrates full entity/customer onboarding across wallets upload, data collection commit, balance validation, reconciliation, org/cost basis settings, 3rd-party contact export/import, and rollup rules

## [1.7.0] - 2026-04-23

### Added
- `tres-export-3rd-party-contacts` skill — exports unidentified external counterparty addresses from `accountTxsSummary` as an XLSX workbook (Contacts import sheet + Address details enrichment; dedupe, sort by volume, user fills names/tags)

## [1.6.0] - 2026-04-23

### Added
- `tres-import-contacts` skill — import address book contacts from CSV or XLSX (Contact Name, Contact Address, Contact Tag) via `setCustomAccountName` and `setCustomAccountNameLabelTags`, with validation, preview, and batched mutations

## [1.5.0] - 2026-04-23

### Added
- `tres-rollup-rules` skill — create, list, and delete sub-transaction rollup rules (daily/monthly aggregation) via `subTransactionRollupRule`, `createSubTransactionRollupRules`, and `deleteSubTransactionRollupRules`, with guided wallet/asset selection and validation guardrails

## [1.4.0] - 2026-04-19

### Added
- `tres-erp-rule-suggestions` skill — guides users through ERP rule mapping for crypto orgs: fetches wallets, chart of accounts, existing rules, and transaction profiles via the TRES MCP, proposes a layered rule set aligned to the org's cost basis mode, and applies it via `upsertRule` after approval
- `tres-request-skill-update` skill — submit plugin feedback (bugs, features, improvements, new skill ideas, MCP issues, or praise) via the TRES MCP feedback tool (zero config for end users)

## [1.3.0] - 2026-04-13

### Added
- `tres-invoice-bill-matching` skill — match TRES ledger transactions to ERP invoices/bills (AP/AR), pick a COA payment account, optionally align fiat values, and sync to the connected ERP (Xero, QuickBooks Online, NetSuite)

## [1.2.0] - 2026-04-12

### Added
- Bundled TRES Finance MCP connector (`.mcp.json`) — auto-starts when plugin is enabled
- `userConfig` for `TRES_API_TOKEN` — users are prompted on first enable, token stored securely in system keychain

## [1.0.0] - 2026-04-12

### Added
- Initial plugin scaffold with marketplace support
- `tres-explorer-tx-to-ledger` skill (placeholder)

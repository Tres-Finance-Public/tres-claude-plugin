# Changelog

## [1.8.1] - 2026-04-23

### Changed
- **Breaking — skill IDs:** renamed skills for simpler invocation — `tres-asset-balance-validation-v2` → `tres-asset-balance-validation`, `tres-report-analyzer-v2` → `tres-report-analyzer`, `tres-report-advisor-v2` → `tres-report-advisor`, `wallets-upload-v3` → `wallets-upload` (update any saved `/<plugin>:<skill>` references)

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
- `request-skill-update` skill — submit plugin feedback (bugs, features, improvements, new skill ideas, MCP issues, or praise) via the TRES MCP feedback tool (zero config for end users)

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
- `explorer-tx-to-ledger` skill (placeholder)

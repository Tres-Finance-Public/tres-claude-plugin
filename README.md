# TRES Finance plugin

The official [TRES Finance](https://tres.finance) plugin for [Claude Code](https://claude.ai/claude-code) — blockchain accounting workflows, ledger management, and transaction analysis.

## Structure

```
tres-finance-plugin/
├── .claude-plugin/
│   ├── plugin.json        # Plugin metadata & userConfig
│   └── marketplace.json   # Marketplace listing
├── skills/
│   ├── explorer-tx-to-ledger/         # Explorer TX -> ledger entry
│   ├── tres-tx-story/                 # TX flow diagram & explanation
│   ├── tres-recon-gaps/               # Reconciliation gap resolution
│   ├── tres-asset-balance-validation/ # Balance validation vs DeBank (+ DeFi positions)
│   ├── tres-report-analyzer/       # Analyze TRES report XLSX exports
│   ├── tres-report-advisor/        # Recommend the right TRES report
│   ├── tres-invoice-bill-matching/    # Match txs to ERP invoices/bills + sync
│   ├── tres-erp-rule-suggestions/     # ERP rule mapping for accounting entries
│   ├── tres-export-3rd-party-contacts/ # Export unidentified counterparties to XLSX
│   ├── tres-import-contacts/          # Import contacts from CSV/XLSX
│   ├── tres-rollup-rules/             # Sub-transaction rollup rules (aggregate txs)
│   ├── tres-onboarding/               # Full entity onboarding (orchestrates sub-skills)
│   ├── wallets-upload/             # Upload & onboard on-chain wallets / exchange accounts
│   ├── tres-data-collection-commit/   # Trigger on-chain data collection (Commit)
│   ├── tres-cost-basis/               # Cost basis strategy, calculation, issues, exports
│   ├── tres-settings-management/      # Manage org & platform settings via MCP
│   └── request-skill-update/          # Submit plugin feedback via MCP
├── .mcp.json              # TRES Finance MCP connector
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## Skills

### `explorer-tx-to-ledger`
Add a blockchain explorer transaction to the TRES Finance ledger. Provide an explorer URL or transaction hash, and this skill parses the on-chain data into a structured ledger entry.

### `tres-tx-story`
Analyze a blockchain transaction by hash — generates an animated SVG flow diagram showing all asset movements, plus a plain-language explanation of what happened.

### `tres-recon-gaps`
Query, display, and resolve reconciliation gaps between the TRES ledger and on-chain balances. Renders an interactive HTML dashboard with plug-once and auto-fill actions.

### `tres-asset-balance-validation`
Validate wallet balances in TRES Finance against DeBank (token balances and DeFi protocol positions). Generates an interactive HTML report and a PDF with match/minor/major/missing/untracked/position status badges.

### `tres-report-analyzer`
Analyze uploaded TRES Finance report exports (XLSX): identifies the report type from sheet structure, runs targeted checks via `scripts/analyze_report.py`, and summarizes anomalies and action items.

### `tres-report-advisor`
Recommend the right TRES Finance report for a goal (month-end, audit, tax, reconciliation). Points users to the right tabs, columns, and export API types.

### `tres-invoice-bill-matching`
Match a TRES ledger transaction to an open ERP invoice or bill (AP/AR), pick the payment account from the COA, optionally align fiat values, and sync the transaction to the connected ERP (Xero, QuickBooks Online, NetSuite).

### `tres-erp-rule-suggestions`
Guide users through creating ERP accounting rules for crypto organizations. Fetches wallets, chart of accounts, existing rules, and transaction profiles via the TRES MCP, then proposes a layered rule set (inventory, behavioral, fee/gain-loss) aligned to the org's cost basis mode — and applies it via `upsertRule` after approval.

### `tres-export-3rd-party-contacts`
Pull unidentified external addresses from `accountTxsSummary`, deduplicate and sort by activity, and build a two-tab XLSX (import-ready Contacts + Address details) for labeling and re-import into TRES.

### `tres-import-contacts`
Import labeled contacts into TRES from a CSV or XLSX file (headers: Contact Name, Contact Address, Contact Tag). Parses the file, validates rows, previews imports, and applies `setCustomAccountName` / `setCustomAccountNameLabelTags` in batches with progress and failure reporting.

### `tres-rollup-rules`
Create, list, and delete rollup rules that consolidate high-volume sub-transactions into daily or monthly aggregated ledger entries (wallet, asset, direction, fees, optional filters), using the TRES MCP GraphQL API.

### `tres-onboarding`
Run the full new-entity pipeline in order: wallets upload, data collection commit, balance validation, reconciliation gaps, cost basis (`tres-cost-basis`), export/import contacts for counterparties, and rollup rules — only when the user explicitly asks for full onboarding.

### `wallets-upload`
Upload and onboard multiple on-chain wallets or exchange accounts into TRES — from a CSV/Excel file or typed manually. Guides through wallet type selection, input collection, validation, an editable HTML preview, exchange credential collection, and batched creation via the TRES MCP API.

### `tres-data-collection-commit`
Trigger on-chain data collection (a "Commit") in TRES for wallets that are already onboarded. Sits between `wallets-upload` and `tres-asset-balance-validation` in the onboarding flow — pulls balances, syncs wallets, and refreshes on-chain data.

### `tres-cost-basis`
Manage cost basis end-to-end via the TRES MCP: strategy (FIFO, LIFO, AVG, etc.), trigger recalculation, per-asset results, financial issues, missing fiat fixes, reevaluations/impairments, spec-ID rules, and cost basis report exports.

### `tres-settings-management`
View and modify Organization Settings and Platform Settings via the TRES MCP GraphQL API — feature flags, balance diff, commit strategy, cost basis strategy, ERP, pricing, sync boundaries, enable/disable platforms, and other config.

### `wallets-upload-v3`
Upload and onboard multiple on-chain wallets or exchange accounts into TRES — from a CSV/Excel file or typed manually. Guides through wallet type selection, input collection, validation, an editable HTML preview, exchange credential collection, and batched creation via the TRES MCP API.

### `tres-data-collection-commit`
Trigger on-chain data collection (a "Commit") in TRES for wallets that are already onboarded. Sits between `wallets-upload-v3` and `tres-asset-balance-validation-v2` in the onboarding flow — pulls balances, syncs wallets, and refreshes on-chain data.

### `tres-settings-management`
View and modify Organization Settings and Platform Settings via the TRES MCP GraphQL API — feature flags, balance diff, commit strategy, cost basis strategy, ERP, pricing, sync boundaries, enable/disable platforms, and other config.

### `request-skill-update`
Submit feedback about any part of the plugin — bug reports, feature requests, skill improvements, new skill ideas, MCP issues, or positive feedback. Guides you through articulating clear, actionable feedback and saves it via the TRES MCP.

## Submit Feedback

Have feedback about the plugin? Use the `request-skill-update` skill directly in Claude Code — it guides you through describing your feedback clearly and submits it for the team to review.

## MCP Connector

This plugin bundles the TRES Finance MCP server (`https://ai.tres.finance/mcp`), which provides GraphQL tools for querying and mutating TRES data: `build_query`, `execute`, `get_schema_summary`, `get_viewer`, `validate_query`, and `introspect`.

On first enable, a browser window opens for you to log in to your TRES Finance account. Authentication is handled automatically via OAuth — no API token required.

## Installation

Install via the Claude Code plugin system:

```bash
/plugin marketplace add tres-finance/tres-finance-plugin
```

Or for local development:

```bash
claude --plugin-dir ./tres-finance-plugin
```

## License

MIT

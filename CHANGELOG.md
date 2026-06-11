# Changelog

## [1.11.0] - 2026-06-11

### Added
- `tres-operation-link` skill — gives the user a direct, clickable dashboard link to **anything** they just created or changed via the MCP. Generic by design with verified recipes for: ledger transactions and rollup transactions (pinned by `transactionHash` with `dateType=All time` so pending/backdated rows show immediately without a data collect; rollups add `showSpam=true`); automation rules — rollup, gap-fill, recurring report, classification — via `/automation-create?type=<type>&id=<id>` plus a "transactions this rollup rule targets" ledger link; ERP rules via `/erp/rules?ruleType=custom&ruleId=<id>`; and single wallet / ticket / invoice / bill / framework. Unlisted entities fall back to their named section page rather than fabricating query params. Resolves the org subdomain from `get_viewer` and renders a Markdown hyperlink. Defers ad-hoc filtered ledger views to plain link-building guidance

## [1.10.0] - 2026-06-10

### Added
- `tres-rollup-review` skill — computes the exact sub-transaction impact of a rollup rule (every filter applied, via `subTransactionRollupRulePreview`) and flags zero-match, overlap, and config problems. Runs as a pre-create quality gate for `tres-rollup-rules` (Mode A) and standalone to review submitted/pending rules (Mode B)

### Changed
- **Reworked `tres-rollup-rules`** from a manual create/view/delete wizard into a data-driven discovery pipeline, mirroring the platform "gold standard": scope → inventory → aggregation discovery by (wallet, asset, platform, direction) → mandatory `tres-rollup-review` validation gate → HTML proposal report + numbered proposal table → user approval → batch create (open-ended by default, `createdBy: AI`). Adds the four-dimension rule key model, the asset-class bridge, naming-convention inference, the `excludeRollups` discovery rule, and an HTML report template under `references/`. Retains list and delete operations

## [1.9.9] - 2026-06-02

### Changed
- **Breaking — skill ID:** renamed `asc845-swap-reprice-skill` → `tres-asc845-swap-reprice-skill` (update any saved `/<plugin>:<skill>` references)

## [1.9.8] - 2026-06-02

### Added
- `asc845-swap-reprice-skill` — ASC 845 equal-value exchange repricing for swap legs; bundled `scripts/reprice_swaps.py` and `scripts/orchestrate_reprice.py` to zero clearing account residuals via `setManualFiatValue`

## [1.9.7] - 2026-06-02

### Added
- `tres-upload-tx-header-validation` skill — exact display-name header row for TRES bulk transaction CSV uploads; prevents snake_case / wrong column name rejections

## [1.9.6] - 2026-05-24

### Fixed
- **Telemetry observability:** `scripts/telemetry.py` now appends a one-line JSON outcome (`ok` / `http_error` / `transport_error` / `encode_error`) to `$CLAUDE_PLUGIN_DATA/telemetry.log` on every invocation. The wrapping hook chain is fully muted (`2>/dev/null`, bare excepts, fire-and-forget background), so users previously had no way to tell whether telemetry was actually reaching the proxy. The log is size-capped at 256 KiB with one rotation.
- **MCP soft-errors no longer reported as successes:** the bff-mcp tool handlers catch their own exceptions and return error-shaped responses, which Claude Code surfaces via `PostToolUse` (success). `telemetry.py` now inspects `tool_response` and flips `success=false` when the response is shaped like an `ErrorResponse` (top-level `error`, or `status: "error"`). Previously every MCP tool call recorded `success=true`.
- **Backgrounded telemetry can no longer be reaped by Claude Code:** `track.sh` now detaches the python child via `setsid` (preferred), `nohup` (fallback), or `disown` (last resort), so the HTTP POST has time to complete even if Claude Code cleans up the hook's process group.

### Changed
- Bumped `.claude-plugin/marketplace.json` from `1.9.0` to `1.9.6` so marketplace installs no longer pin to a stale matcher (was the indirect cause of the regression PR #11 fixed).

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

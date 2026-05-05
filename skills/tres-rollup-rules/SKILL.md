---
name: tres-rollup-rules
description: >
  Create, view, and delete rollup rules in TRES Finance that consolidate many small
  sub-transactions into aggregated rollup transactions per interval (daily or monthly).
  Trigger this skill whenever the user asks about rollup rules, transaction aggregation,
  consolidating transactions, reducing transaction noise, rolling up gas fees, rolling up
  staking rewards, rolling up micro-transactions, or anything related to collapsing many
  small ledger entries into fewer summary entries. Also trigger when the user says
  "create a rollup rule", "show my rollup rules", "delete a rollup rule", "aggregate
  transactions", "too many transactions", "reduce transaction count", "roll up fees",
  "daily rollup", "monthly rollup", or similar. If the user mentions that a wallet has
  too many transactions, high-frequency activity, or noisy ledger entries, proactively
  suggest rollup rules as a solution.
compatibility: "Requires TRES Finance MCP connector"
---

# TRES Finance — Rollup Rules

End-to-end skill for creating, viewing, and deleting rollup rules that consolidate
high-volume sub-transactions into clean aggregated entries per day or month.

---

## What is a Rollup?

A rollup consolidates many individual sub-transactions into a single aggregated
transaction for a given time period (daily or monthly). This is essential for wallets
that generate an enormous number of transactions — gas fees firing hundreds of times
a day, micro staking rewards, or high-frequency DeFi interactions. Instead of each
one hitting the ledger as a separate line item, a rollup collapses them into one clean
summary transaction per day or per month.

The original raw transactions are always preserved and visible in the
**Rollup Breakdown** report — rollups are non-destructive.

---

## MCP Server

All calls use the TRES Finance MCP connector.

All variable keys and nested input fields MUST use **camelCase** (e.g. `internalAccountId`,
`balanceFactor`), NEVER snake_case.

---

## Step 1 — Authenticate and confirm org

Call `get_viewer` with no arguments. Confirm the org name with the user if there
is any ambiguity.

---

## Step 2 — Understand what the user wants

Based on the user's request, route to the appropriate section:

- **"Show my rollup rules"** / **"List rules"** → Section A (View existing rules)
- **"Create a rollup rule"** / **"Roll up transactions"** / **"Too many transactions"** → Section B (Create rules)
- **"Delete a rollup rule"** → Section C (Delete rules)

If the user's intent is unclear, ask which operation they need.

---

## A. View existing rollup rules

Fetch all rollup rules for the organization.

```graphql
query SubTransactionRollupRule($limit: Int, $offset: Int) {
  subTransactionRollupRule(limit: $limit, offset: $offset) {
    totalCount
    results {
      id
      name
      interval
      startDate
      endDate
      nextActivationDate
      status
      rule
    }
  }
}
```

Variables: `{"limit": 50, "offset": 0}`

The `rule` field is a JSON object containing all the filter details (wallet ID, asset,
direction, fee handling, filters). Parse and present it clearly.

### Presenting rules

For each rule, show:
- **Name** and **ID**
- **Status** (PENDING, ACTIVE, etc.)
- **Interval** (DAY or MONTH)
- **Date range** (startDate → endDate, or "indefinite")
- **Rule filters**: wallet, asset, direction, fee handling, and any optional filters

If there are no rules, let the user know and offer to help create one.

### Filtering by status

Use `status` or `status_In` to filter:
```graphql
query SubTransactionRollupRule($status_In: [String]) {
  subTransactionRollupRule(status_In: $status_In) { ... }
}
```

---

## B. Create rollup rules — guided flow

This is the main flow. Walk the user through each required decision, resolving
wallet IDs and asset keys along the way. Collect all parameters before creating.

**Important UX rule**: When presenting lists for the user to choose from (wallets,
assets, existing rules), ALWAYS use numbered markdown tables — never the
AskUserQuestion tool. AskUserQuestion is limited to 4 options and most TRES orgs
have many more wallets/assets than that. Reserve AskUserQuestion only for small
fixed-choice questions (direction, interval, fee handling) where there are 2-3
options.

### B.1 — Identify the target wallet

If the user already specified a wallet by name or address, look it up directly using
`name_Icontains` or `identifier_Icontains`. Otherwise, fetch ALL wallets and present
them as a numbered table so the user can pick.

**Always fetch wallets with this query** (do NOT filter by `status_In: ["active"]` —
use no status filter so READY wallets appear):

```graphql
query FindWallets($limit: Int, $name_Icontains: String, $identifier_Icontains: String) {
  internalAccount(
    limit: $limit,
    name_Icontains: $name_Icontains,
    identifier_Icontains: $identifier_Icontains
  ) {
    totalCount
    results {
      id
      name
      identifier
      parentPlatform
      activePlatforms
      status
    }
  }
}
```

**Presenting wallets**: Always display results as a **numbered markdown table** — never
use the AskUserQuestion tool for wallet selection, because it only supports 4 options
and orgs typically have many more wallets. Format like this:

> | # | Name | Address | Platform | Status |
> |---|------|---------|----------|--------|
> | 1 | Main Wallet | 0xABCD...1234 | ETHEREUM | READY |
> | 2 | Staking Hot | 0xEF01...5678 | ETHEREUM + ARBITRUM | READY |
> | 3 | BTC Treasury | bc1q...xyz | BITCOIN | READY |
>
> Which wallet should this rollup rule apply to? Just give me the number or name.

For the address column, show the first 6 and last 4 characters (e.g. `0xABCD...1234`).
For the platform column, parse `activePlatforms` JSON and list platforms where the
value is `true`, alongside `parentPlatform`.

Paginate if `totalCount` > 50 — fetch additional pages and present the full list.

After the user picks, record the **`id`** (this is the `internalAccountId` for the rule)
and the **`parentPlatform`** / **`activePlatforms`** (needed for the `platform` field).

### B.2 — Identify the target asset

Ask: **"Which asset should this rule target?"** (e.g. ETH, USDC, SOL)

Look up the asset key for this wallet:

```graphql
query WalletAssets($belongsTo_Id: Float, $limit: Int, $currency: String) {
  assetBalance(
    belongsTo_Id: $belongsTo_Id,
    limit: $limit,
    currency: $currency,
    excludeUnderDelegation: true
  ) {
    totalCount
    results {
      asset {
        identifier
        platform
        symbol
        name
        type
      }
      calculatedBalance
      fiatValue {
        value
      }
    }
  }
}
```

Variables: `{"belongsTo_Id": <wallet_id>, "limit": 50, "currency": "usd"}`

**Presenting assets**: Like wallets, always display assets as a **numbered markdown table**
— never use AskUserQuestion for asset selection, since wallets can hold many assets.
Format like this:

> | # | Symbol | Name | Platform | Balance | USD Value | Asset Key |
> |---|--------|------|----------|---------|-----------|-----------|
> | 1 | ETH | Ether | ETHEREUM | 12.5 | $24,500 | ethereum_native |
> | 2 | USDC | USD Coin | ETHEREUM | 50,000 | $50,000 | ethereum_0xa0b8...eb48 |
> | 3 | ARB | Arbitrum | ARBITRUM | 1,200 | $1,440 | arbitrum_native |
>
> Which asset should this rollup rule target? Give me the number or symbol.

- The **`asset.identifier`** is the `assetId` for the rule (e.g. `ethereum_native`,
  `ethereum_0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48` for USDC).
- The **`asset.platform`** is the `platform` for the rule (e.g. `ETHEREUM`, `SOLANA`).
- Paginate if `totalCount` > 50.

### B.3 — Direction

Ask: **"Should this rule target inflows (incoming) or outflows (outgoing)?"**

Explain that rollup rules are per-direction — if the user wants both directions
rolled up, they need two separate rules. Offer to create both.

Values: `INFLOW` or `OUTFLOW`

### B.4 — Interval

Ask: **"Should transactions be rolled up daily or monthly?"**

- **DAY** — One aggregated transaction per day. Best for high-frequency activity.
- **MONTH** — One aggregated transaction per month. Best for moderate-frequency activity
  where daily granularity isn't needed.

### B.5 — Fee handling

Ask: **"How should fees (like gas) be handled?"**

- **INCLUDE** — Roll up transactions together with their associated fees (most common).
- **EXCLUDE** — Roll up the transactions but leave fees as separate line items.
- **ONLY** — Roll up ONLY the fee sub-transactions (e.g. create a gas-only rollup).
  This is useful when you want to aggregate gas costs separately.

Default recommendation: **INCLUDE** for most use cases. Use **ONLY** for dedicated
gas fee rollups.

### B.6 — Optional filters (ask if needed)

After collecting the required fields, ask: **"Do you want to add any optional filters
to narrow which transactions get rolled up?"**

Present the available filters:

| Filter | Description | Notes |
|--------|-------------|-------|
| `activity` | Financial activity classification | e.g. `STAKING_REWARD`, `OPERATIONS`, `OFFCHAIN_TRADE` |
| `minAmount` / `maxAmount` | Amount range filter | Useful for targeting micro-transactions (e.g. maxAmount: 0.01) |
| `senderIdentifier` | Exact sender address | Only valid on INFLOW rules |
| `recipientIdentifier` | Exact recipient address | Only valid on OUTFLOW rules |
| `originalSenderPrefix` | Prefix match on raw sender | Only valid on INFLOW rules. For custodian sources like `VAULT_ACCOUNT\|PRODUCTION` |
| `originalRecipientPrefix` | Prefix match on raw recipient | Only valid on OUTFLOW rules. For custodian destinations |
| `methodIds` | On-chain method/function IDs | e.g. `["0x00000000"]` for native transfers |
| `subtxType` | Financial action type | e.g. `NATIVE_TRANSFER`, `TOKEN_TRANSFER`, `REWARD`, `GAS`, `FEE` |
| `excludeFiat` | Exclude fiat-denominated transactions | Boolean, default false |
| `excludeInternal` | Exclude internal transfers | Boolean, default false |
| `rollupInternalTransfersOnly` | Only rollup internal transfers | Boolean, automatically links outflow to inflow counterpart |
| `bufferInDays` | Days to wait before closing a period | Allows late-arriving transactions to be included |
| `cutoffTime` | Daily cutoff time (HH:MM) | e.g. `"17:00"` — transactions after this time roll into next period |

#### Direction-based filter validation

Enforce these rules — the API will reject invalid combinations:
- `senderIdentifier` and `originalSenderPrefix` → **INFLOW only**, mutually exclusive
- `recipientIdentifier` and `originalRecipientPrefix` → **OUTFLOW only**, mutually exclusive
- `mergeWithInflowTx` → Only meaningful on OUTFLOW rules

If the user doesn't need filters, skip this step entirely.

### B.7 — Date range (optional)

Ask: **"Should this rule have a start/end date, or run indefinitely?"**

- `startDate` (YYYY-MM-DD) — If omitted, applies from beginning of time.
- `endDate` (YYYY-MM-DD) — If omitted, runs indefinitely.

Most users want indefinite rules. Only set dates if the user has a specific period.

### B.8 — Rule name

Generate a descriptive name following this pattern:
`[Interval] [Asset] [Direction] [Optional: filter hint] - [Wallet short identifier]`

Examples:
- `Daily ETH Inflow - 0x84E0`
- `Monthly USDC Outflow (Staking Rewards) - Main Wallet`
- `Daily ETH Gas Fees Only - 0xAB12`

Present the suggested name and let the user modify it.

### B.9 — Preview and confirm

Before creating, present a clear summary of the rule:

> **Rollup Rule Preview:**
>
> | Field | Value |
> |-------|-------|
> | Name | Daily ETH Inflow - 0x84E0 |
> | Wallet | Main Staking Wallet (ID: 123) |
> | Asset | ethereum_native (ETH) |
> | Platform | ETHEREUM |
> | Direction | INFLOW |
> | Interval | DAY |
> | Fees | INCLUDE |
> | Date range | Indefinite |
> | Filters | activity: STAKING_REWARD |
>
> **Create this rule?**

Wait for explicit user confirmation before proceeding.

### B.10 — Create the rule

```graphql
mutation CreateSubTransactionRollupRules($rules: [RollupRuleCreationRequest]!) {
  createSubTransactionRollupRules(rules: $rules) {
    results {
      rollupRuleId
      validationIssues {
        blocking
        type
        message
      }
    }
  }
}
```

Variables:
```json
{
  "rules": [
    {
      "name": "Daily ETH Inflow - 0x84E0",
      "interval": "DAY",
      "startDate": null,
      "endDate": null,
      "rule": {
        "internalAccountId": 123,
        "assetId": "ethereum_native",
        "platform": "ETHEREUM",
        "balanceFactor": "INFLOW",
        "fees": "INCLUDE",
        "activity": "STAKING_REWARD"
      }
    }
  ]
}
```

Only include optional filter fields that the user explicitly set — do NOT send null
for optional fields, just omit them from the `rule` object.

### Handling the response

- **Success** (`rollupRuleId` returned, no blocking issues): Report the rule ID
  and confirm creation. The rule starts in `PENDING` status and will activate
  on the next processing cycle.
- **Validation issues** (non-blocking): Report them as warnings but the rule was
  still created.
- **Blocking validation issues**: The rule was NOT created. Report the issues
  clearly and help the user fix the parameters. Common issues:
  - Wrong direction + filter combo (e.g. senderIdentifier on OUTFLOW)
  - Invalid asset key for the platform
  - Duplicate rule (same wallet + asset + direction combo already exists)

### Creating multiple rules

If the user wants both INFLOW and OUTFLOW rolled up, create both rules in a
single batch call:

```json
{
  "rules": [
    {
      "name": "Daily ETH Inflow - 0x84E0",
      "interval": "DAY",
      "rule": {
        "internalAccountId": 123,
        "assetId": "ethereum_native",
        "platform": "ETHEREUM",
        "balanceFactor": "INFLOW",
        "fees": "INCLUDE"
      }
    },
    {
      "name": "Daily ETH Outflow - 0x84E0",
      "interval": "DAY",
      "rule": {
        "internalAccountId": 123,
        "assetId": "ethereum_native",
        "platform": "ETHEREUM",
        "balanceFactor": "OUTFLOW",
        "fees": "INCLUDE"
      }
    }
  ]
}
```

---

## C. Delete rollup rules

Only rules with **PENDING** status can be deleted. Active rules require support
intervention.

First, list the rules (Section A) so the user can identify which to delete.
Then confirm the rule ID(s) with the user before deleting.

```graphql
mutation DeleteSubTransactionRollupRules($ruleIds: [Int]!) {
  deleteSubTransactionRollupRules(ruleIds: $ruleIds) {
    results {
      deletedIds
      failures {
        ruleId
        reason
      }
    }
  }
}
```

Report results:
- **deletedIds**: Successfully deleted rules.
- **failures**: Rules that could not be deleted, with reasons (typically because
  they are already active).

---

## Common rollup patterns

When users describe their problem rather than specifying exact parameters, use these
patterns as starting points:

### Pattern 1: Gas fee rollup
**User says**: "I have hundreds of gas transactions per day"
```json
{
  "name": "Daily Gas Fees - [Wallet]",
  "interval": "DAY",
  "rule": {
    "internalAccountId": "<wallet_id>",
    "assetId": "<native_asset>",
    "platform": "<platform>",
    "balanceFactor": "OUTFLOW",
    "fees": "ONLY"
  }
}
```

### Pattern 2: Staking rewards rollup
**User says**: "Too many staking reward entries cluttering the ledger"
```json
{
  "name": "Daily Staking Rewards - [Wallet]",
  "interval": "DAY",
  "rule": {
    "internalAccountId": "<wallet_id>",
    "assetId": "<reward_asset>",
    "platform": "<platform>",
    "balanceFactor": "INFLOW",
    "fees": "INCLUDE",
    "activity": "STAKING_REWARD"
  }
}
```

### Pattern 3: Micro-transaction rollup
**User says**: "We receive thousands of small payments daily"
```json
{
  "name": "Daily Micro Inflows - [Wallet]",
  "interval": "DAY",
  "rule": {
    "internalAccountId": "<wallet_id>",
    "assetId": "<asset>",
    "platform": "<platform>",
    "balanceFactor": "INFLOW",
    "fees": "INCLUDE",
    "maxAmount": 0.01
  }
}
```

### Pattern 4: Internal transfer rollup
**User says**: "Too many internal transfers between our wallets"
```json
{
  "name": "Daily Internal Transfers - [Wallet]",
  "interval": "DAY",
  "rule": {
    "internalAccountId": "<wallet_id>",
    "assetId": "<asset>",
    "platform": "<platform>",
    "balanceFactor": "OUTFLOW",
    "fees": "INCLUDE",
    "rollupInternalTransfersOnly": true
  }
}
```
Note: When `rollupInternalTransfersOnly` is true, the system automatically sets
`mergeWithInflowTx` and `runInternalTransferClassificationOnRollups` to true.

---

## Guardrails

- **Always confirm before creating**: Present the full rule preview and wait for
  explicit user confirmation before calling the create mutation.
- **Direction + filter validation**: Enforce that sender filters are INFLOW-only
  and recipient filters are OUTFLOW-only. Catch this before sending to the API.
- **One direction per rule**: Remind users that each rule handles one direction.
  Offer to create paired rules for both INFLOW and OUTFLOW.
- **Asset key accuracy**: Always look up the exact `assetId` from the wallet's
  asset balances — never guess. The format varies by platform (e.g. `ethereum_native`,
  `solana_native`, `ethereum_0x...` for tokens).
- **Platform must match**: The `platform` in the rule must match the asset's platform,
  which must match one of the wallet's active platforms.
- **Deletion limits**: Only PENDING rules can be deleted via API. If the user wants
  to delete an active rule, direct them to contact TRES support.
- **Fee-only rules**: When `fees: "ONLY"`, the rule only captures fee sub-transactions
  (like gas). This is a separate rule from the main transaction rollup — the user
  might want both a transaction rollup (fees: INCLUDE or EXCLUDE) and a fee-only
  rollup for the same wallet+asset.

---

## FinancialAction enum values (for subtxType filter)

TRACE_TRANSFER, TOKEN_TRANSFER, NATIVE_TRANSFER, DELEGATION, UNDELEGATION,
VEST, UNVEST, VALIDATOR_CREATION, REWARD, COMMISSION, GAS, FEE,
EXCHANGE_WITHDRAWAL, EXCHANGE_DEPOSIT, EXCHANGE_TRANSFER, EXCHANGE_BUY,
EXCHANGE_SELL, EXCHANGE_LOAN, EXCHANGE_SETTLEMENT, REBATE, FIAT_TRANSFER,
BURNED, ROLLUP, ROLLUP_FEE, PLUG, GROUP, FUNDING, INTEREST,
TRANSFER_DELEGATION_REWARD, REEVALUATION, PAYMENT, BANK_DEPOSIT,
BANK_WITHDRAWAL, MINING_REWARD

---

## Limitations — not available via MCP

1. **Editing existing rules** — There is no update/edit mutation. To change a rule,
   delete it (if PENDING) and recreate with updated parameters.
2. **Activating/deactivating rules** — Rule activation is managed by the backend
   processing pipeline, not directly controllable via API.
3. **Viewing rollup breakdown** — The detailed breakdown of which raw transactions
   were aggregated into each rollup is available via the Rollup Breakdown report
   in the TRES dashboard, not via a direct MCP query.
4. **Active rule deletion** — Rules that are already ACTIVE cannot be deleted via
   the API. Direct the user to contact TRES support.

For any of these, direct the user to the TRES Finance dashboard or TRES support.

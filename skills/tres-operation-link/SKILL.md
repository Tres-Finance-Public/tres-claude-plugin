---
name: tres-operation-link
description: >
  Give the user a direct, clickable TRES Finance dashboard link to an operation they just performed
  via the TRES MCP — a created/updated transaction, a rollup, or an ERP rule. Use it right after
  creating or modifying one of these so the user can open and verify the result immediately. Also
  trigger when the user asks "give me a link", "url to this tx", "link to the rule", "where can I
  see this", or "open this in the dashboard". For an ad-hoc filtered ledger view described in plain
  English (e.g. "last month's Ethereum spam"), build that link directly instead — this skill is only
  for linking to one identifiable operation.
---

# Link to Operation

You produce a single dashboard link to a specific thing the user just created or modified through
the TRES MCP (a transaction, a rollup, or an ERP rule), and present it as a clickable Markdown
hyperlink.

Why this matters: manual transactions are created in a **pending** state and only enter the default
ledger view after the next data collect (which can take hours), and they are often **backdated**
(e.g. opening balances). A normal ledger view therefore hides them, which makes users think the
operation failed. Pinning the link by `transactionHash` with `dateType=All%20time` bypasses both the
ready/pending filter and the date range, so the row is visible right away.

## Step 1 — Get the org subdomain

Every link is `https://<subdomain>.tres.finance/...`. Resolve `<subdomain>` from the MCP `get_viewer`
query (use the returned `orgName`). Do not ask the user for it.

```graphql
query { viewer { orgName } }
```

State the subdomain you used in your reply so the user can correct it in one shot if it is wrong.

## Step 2 — Build the link for the operation type

URL-encode every value (spaces become `%20`). When passing several items in one parameter, join them
with a literal comma; encode any comma that appears inside a single value.

**A created or updated transaction:**

```
https://<subdomain>.tres.finance/ledger?dateType=All%20time&transactionHash=<identifier>
```

`<identifier>` is the transaction's `identifier` — the value you passed to, or got back from,
`createOrUpdateManualTransaction` / `createManualTransactionWithSubTransactions`. For several at once,
join them: `transactionHash=<id1>,<id2>`.

**A rollup transaction** (same as above, plus `showSpam=true`, because rollups often bundle
reward/spam-tagged assets that are otherwise hidden):

```
https://<subdomain>.tres.finance/ledger?dateType=All%20time&transactionHash=<rollup_identifier>&showSpam=true
```

A rollup identifier looks like `rollup_<name>_<epoch>_<direction>`, e.g.
`rollup_Atom%20rewards%20monthly_1704067200_inflow`.

**An ERP rule:**

```
https://<subdomain>.tres.finance/erp/rules?ruleType=custom&ruleId=<ruleId>
```

`<ruleId>` is the rule's id (e.g. returned by `upsertRule`). Use `ruleType=custom` for a user-defined
rule or `ruleType=default` for a default rule; when unsure, use `custom`. To link to the rules page
without a specific rule, use `https://<subdomain>.tres.finance/erp/rules`.

## Step 3 — Reply with a clickable hyperlink

Present the link as Markdown link text the user can click, followed by a short note of the subdomain
you used. Keep anchor text short and descriptive.

## Self-check before replying

Confirm all of the following, and fix anything that fails:
1. The link is a Markdown hyperlink (`[anchor](url)`), not a bare URL.
2. For a transaction or rollup, the query has both `dateType=All%20time` and `transactionHash`, and no
   narrower date range that would hide pending or backdated rows.
3. No boolean parameter is set to `false` (omit it instead of writing `=false`).
4. Each parameter appears once; multiple values are comma-joined rather than repeated keys.
5. Spaces are encoded as `%20`.

<example>
Context: you just created a manual transaction with identifier
`opening-balance-2024-12-31` for org `acme` (returned by get_viewer → orgName "acme").

Reply:
Created the opening-balance transaction. It's pending until the next data collect, but you can
[view it in the ledger now](https://acme.tres.finance/ledger?dateType=All%20time&transactionHash=opening-balance-2024-12-31).
(Subdomain used: `acme` — let me know if that's wrong.)
</example>

<example>
Context: you just saved a custom ERP rule with ruleId `4821` for org `globex`.

Reply:
Rule saved. [Open the rule](https://globex.tres.finance/erp/rules?ruleType=custom&ruleId=4821) to
review or edit it. (Subdomain used: `globex`.)
</example>

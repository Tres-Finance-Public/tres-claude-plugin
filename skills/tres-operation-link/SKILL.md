---
name: tres-operation-link
description: >
  Give the user a direct, clickable TRES Finance dashboard link to anything they just created or
  changed via the TRES MCP — a transaction, a rollup, an automation/rule (rollup, gap-fill,
  recurring report, classification), an ERP rule, a wallet, a report, an invoice/bill, and more.
  Generic by design: use it right after any create/modify operation so the user can open and verify
  the result immediately. Also trigger when the user asks "give me a link", "url to this", "where
  can I see this", or "open this in the dashboard". For an ad-hoc filtered ledger view described in
  plain English (e.g. "last month's Ethereum spam"), build that link directly instead.
---

# Link to Operation

Whenever the user creates or changes *anything* in TRES and would benefit from seeing it, hand them a
single clickable Markdown link straight to that thing in the dashboard. This skill is **generic** —
the recipes below are the common cases, but the principle applies to every entity the product has a
page for. Never refuse just because an entity is not listed; fall back to the section-page rule in
Step 3.

Why this matters: things created through the MCP are often **not visible in the default view**. Manual
transactions are created **pending** (they only enter the default ledger after the next data collect,
which can take hours) and are frequently **backdated** (opening balances), so a normal ledger view
hides them and the user thinks the operation failed. Rollup rules start **pending** until activated,
then generate rollup transactions asynchronously. A precise deep link removes all doubt.

## Step 1 — Get the org subdomain

Every link is `https://<subdomain>.tres.finance/...`. Resolve `<subdomain>` from the MCP `get_viewer`
query (use the returned `orgName`). Do not ask the user.

```graphql
query { viewer { orgName } }
```

State the subdomain you used in your reply so the user can correct it in one shot if it is wrong.

## Step 2 — Build the most specific link you can

URL-encode every value (spaces become `%20`). When passing several values in one parameter, join them
with a literal comma; encode any comma that appears *inside* a single value.

### Ledger — a created/updated transaction
```
https://<subdomain>.tres.finance/ledger?dateType=All%20time&transactionHash=<identifier>
```
`<identifier>` is the transaction's `identifier` (passed to / returned by
`createOrUpdateManualTransaction` / `createManualTransactionWithSubTransactions`). Several at once:
`transactionHash=<id1>,<id2>`. The `dateType=All%20time` + `transactionHash` combination is what makes
pending and backdated rows show immediately — always include both.

### Ledger — a rollup transaction
Same as a transaction, plus `showSpam=true` (rollups often bundle reward/spam-tagged legs that are
otherwise hidden):
```
https://<subdomain>.tres.finance/ledger?dateType=All%20time&transactionHash=<rollup_identifier>&showSpam=true
```
A rollup identifier looks like `rollup_<name>_<epoch>_<direction>`, e.g.
`rollup_Atom%20rewards%20monthly_1704067200_inflow`.

### Automations — a rule you created/edited (rollup rule, gap-fill rule, recurring report, classification rule)
Open the rule itself for review/edit:
```
https://<subdomain>.tres.finance/automation-create?type=<automationType>&id=<ruleId>
```
`<automationType>` is one of `generateRollup` (transaction roll-up), `reconciliationGapsFiller`,
`recurringReport`, `setTransactionActivity` (set-activity / classification). `<ruleId>` is the id
returned by the create mutation (e.g. `createSubTransactionRollupRules` → `rollupRuleId`). For the full
list instead, use `https://<subdomain>.tres.finance/automations`.

For a **rollup rule**, you can also link the user to the transactions it targets:
```
https://<subdomain>.tres.finance/ledger?automations=<ruleId>&dateType=All%20time
```

> Note: a new rollup rule is created **pending**. After you activate it (`activatePendingRollupRules`)
> it generates rollup transactions asynchronously, so the rule link works immediately while the
> rollup-transaction link populates a little later.

### ERP — an accounting rule
```
https://<subdomain>.tres.finance/erp/rules?ruleType=custom&ruleId=<ruleId>
```
Use `ruleType=custom` for a user-defined rule, `ruleType=default` for a default rule; when unsure use
`custom`. Rules page without a specific rule: `https://<subdomain>.tres.finance/erp/rules`.

### Other common entities (path-based)
- A single wallet: `https://<subdomain>.tres.finance/accounts/wallet/<walletId>`
- A ticket: `https://<subdomain>.tres.finance/tickets/<ticketId>`
- An invoice: `https://<subdomain>.tres.finance/payments/invoice/<invoiceId>`
- A bill: `https://<subdomain>.tres.finance/payments/bills/<billId>`
- A framework: `https://<subdomain>.tres.finance/frameworks/<frameworkId>`

## Step 3 — Fallback for anything not listed above

If you created/changed something without a specific recipe here, **do not invent query parameters**.
Link to that feature's section page instead and name it, so the user lands in the right place:
accounts `/accounts`, alerts `/alerts`, reports `/reports`, positions `/positions`,
integrations `/integrations`, payments `/payments`, assets `/assets`, overview `/overview`.
Prefer the most specific real URL you can justify over a guessed deep link.

## Step 4 — Reply with a clickable hyperlink

Present the link as Markdown link text the user can click, with short descriptive anchor text,
followed by a short note of the subdomain you used. If the thing is pending/async (manual tx, freshly
activated rollup rule), say so in one short clause so the user is not surprised.

## Self-check before replying

Confirm all of the following, and fix anything that fails:
1. The link is a Markdown hyperlink (`[anchor](url)`), not a bare URL.
2. For a ledger transaction or rollup, the query has both `dateType=All%20time` and `transactionHash`,
   and no narrower date range that would hide pending/backdated rows.
3. A rollup transaction link includes `showSpam=true`.
4. No boolean parameter is set to `false` (omit it instead of writing `=false`).
5. Each parameter appears once; multiple values are comma-joined rather than repeated keys.
6. Spaces are encoded as `%20`.
7. You used the most specific recipe available; if you fell back to a section page, you named the
   section rather than fabricating an id/param.

<example>
Context: you just created a manual transaction with identifier `opening-balance-2024-12-31`
for org `acme` (get_viewer → orgName "acme").

Reply:
Created the opening-balance transaction. It's pending until the next data collect, but you can
[view it in the ledger now](https://acme.tres.finance/ledger?dateType=All%20time&transactionHash=opening-balance-2024-12-31).
(Subdomain used: `acme` — let me know if that's wrong.)
</example>

<example>
Context: you just created and activated a transaction roll-up rule with id `40847` for org `globex`.

Reply:
Roll-up rule created and activated — it'll generate rollup transactions shortly.
[Open the rule](https://globex.tres.finance/automation-create?type=generateRollup&id=40847), or
[see the transactions it targets](https://globex.tres.finance/ledger?automations=40847&dateType=All%20time).
(Subdomain used: `globex`.)
</example>

<example>
Context: you just saved a custom ERP rule with ruleId `4821` for org `globex`.

Reply:
Rule saved. [Open the rule](https://globex.tres.finance/erp/rules?ruleType=custom&ruleId=4821) to
review or edit it. (Subdomain used: `globex`.)
</example>

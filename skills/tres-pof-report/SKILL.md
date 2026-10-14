---
name: tres-pof-report
description: >
  Export a Proof of Funds (PoF) account balances report — one CSV row per token balance of every
  wallet in a PoF snapshot (timestamp, network, accountAddress, block, custodian, source, vault name,
  token, amount, unit price, fiat value) — for the organization's latest snapshot or a given date.
  Runs a local read-only script against the TRES API; no database access. Trigger phrases include:
  "PoF report", "proof of funds report", "proof of funds balances", "export PoF balances",
  "accountBalances CSV", "PoF snapshot export", "PoF balances as of end of September",
  "give me the PoF CSV for <date>". Do NOT trigger for regular TRES balance, ledger or reconciliation
  reports (use tres-report-create / tres-report-advisor), and do NOT trigger for PoF positions.
---

# TRES PoF Account Balances Report

You export the PoF `accountBalances` snapshot of the organization to a CSV file by running the
bundled script `scripts/pof_report.py`. It calls the existing read-only TRES API PoF endpoints
(`/pof/snapshot-status`, `/pof/aggregate-account-balances`, `/pof/find-account-balances`) — it never
writes anything and never touches a database.

Output columns (exact order):
`timestamp,network,accountAddress,blockNumber,blockTimestamp,custodianName,source,sourceAddressName,sourceAddressType,sourceOriginId,tokenAddress,amount,symbol,unitFiatPrice,fiatValue,fiat`

## Workflow

```
- [ ] Step 0: Check credentials
- [ ] Step 1: Resolve the requested timestamp to UTC
- [ ] Step 2: Check-only run (snapshot exists? how many rows?)
- [ ] Step 3: Export
- [ ] Step 4: Report the result and hand over the file
```

### Step 0 — Credentials

The script reads credentials **from the environment only**:

- `TRES_CLIENT_ID` + `TRES_CLIENT_SECRET` — the organization's TRES API key (TRES app → Settings →
  API key), **or**
- `TRES_API_TOKEN` — an existing bearer token for the organization.

The report is for the organization those credentials belong to. Check presence without printing values:

```bash
python3 -c "import os; print({k: bool(os.environ.get(k)) for k in ['TRES_CLIENT_ID','TRES_CLIENT_SECRET','TRES_API_TOKEN']})"
```

If they are missing, tell the user to export them in the shell that launches Claude Code (or in their
shell profile) and restart the session. **Never ask the user to paste a secret into the chat, never echo
it, and never write it to a file.**

The script reads the PoF organization name (e.g. `nonco`) from the organization's settings and names the
file `<org>-pof.accountBalances.<date>.csv`, e.g. `nonco-pof.accountBalances.2026-10-01.csv` (the JSON
summary's `organization` field). It never overwrites an existing file — it adds ` (1)`, ` (2)`, ….
Only pass `--org-label <name>` if the user explicitly wants a different file name prefix.

### Step 1 — Resolve the timestamp

Default is `latest` (the newest completed snapshot, searching back up to ~13 months). Otherwise convert the user's
wording to an ISO-8601 UTC instant **yourself** and pass only `latest` or ISO to the script:

| User says | Pass |
|---|---|
| nothing / "latest" / "current" | `latest` |
| "end of September" / "EOM September" / "September close" | `2026-10-01T00:00:00Z` (first day of the next month, 00:00 UTC) |
| "end of Q3" | `YYYY-10-01T00:00:00Z` |
| "end of year 2025" / "year end" | `2026-01-01T00:00:00Z` |
| "July 1st" / "2026-07-01" | `2026-07-01T00:00:00Z` |
| an explicit time / epoch ms | that instant in UTC |

When no year is given, use the most recent occurrence that is not in the future. Always tell the user
the instant you resolved, e.g. *"End of September → 2026-10-01T00:00:00Z."*

### Step 2 — Check-only run

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/tres-pof-report/scripts/pof_report.py" \
  --timestamp <latest|ISO> --check-only
```

stdout is a JSON summary; progress goes to stderr. Handle the exit code:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Snapshot exists and is within the row limit | Tell the user the snapshot and expected rows/accounts/networks, then continue to Step 3 |
| 2 | No completed snapshot at that time (not on the org's schedule, no data, or still in progress) | Stop. Show `message` and the `nearest` completed snapshots (before/after) and ask which one to use |
| 3 | More rows than the limit (default 1,000,000 — Excel's sheet limit is 1,048,576) | Do **not** export. Show the total, `topNetworks` and the `suggestedSplit` groups, and offer to run one export per group with `--networks a,b,c` (or `--sources`). Run them only after the user confirms. A network listed in `networksAboveLimitOnTheirOwn` must be split by `--sources` |
| 1 | Error (credentials, network, API) | Show `message`. HTTP 400 "No proof of funds settings found" means the organization has no PoF configured; 401/403 means the credentials are invalid or lack read access |

### Step 3 — Export

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/skills/tres-pof-report/scripts/pof_report.py" \
  --timestamp <resolved ISO from Step 2's "snapshot"> --out <dir>
```

- Use the exact `snapshot` value returned in Step 2 (this pins `latest`).
- `--out` defaults to the current directory; use the directory the user asked for.
- Optional filters: `--networks ethereum,base`, `--sources "FB LLC"` (comma-separated).
- The script writes to a `.part` file and renames it when complete; if the row count passes
  `--max-rows` mid-export it aborts and deletes the partial file (exit 3).
- Large organizations can take several minutes — run it in the background if it exceeds ~2 minutes and
  tell the user.

### Step 4 — Result

Summarize from the JSON `export` block: file path, rows, accounts (`documents`), networks,
`rowsMissingPrice` (rows without a unit price — usually illiquid/unpriced tokens) and
`fiatValueBySource`. Then send the CSV to the user (e.g. with SendUserFile when available).
Do not paste CSV rows into the chat beyond a few sample lines.

Add this note when handing over the file: the CSV holds exact values (integers for `blockNumber` /
`blockTimestamp`, plain decimals with full precision for `amount` / `unitFiatPrice` / `fiatValue`).
Double-clicking it in Excel shows large and tiny numbers in scientific notation and rounds values beyond
15 significant digits; to view it losslessly use Excel → Data → From Text/CSV and set those columns to
Text, and never save over the original CSV from Excel.

## Rules

- Read-only: the script only calls snapshot-status, aggregate (row count) and find. Never call any other
  PoF endpoint (accounts create/delete, enable-networks, network-token-policy are writes).
- Credentials come from the environment only — never request, echo, log or store them.
- Always run the check-only step first; never bypass the row limit by raising `--max-rows` above
  1,000,000 without the user explicitly asking for it.
- Never truncate account or token addresses when showing samples.
- The CSV contains customer balances: write it only where the user asked, never to a shared location.

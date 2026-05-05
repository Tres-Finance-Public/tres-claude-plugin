---
name: tres-plugin-release
description: >
  Pre-release checklist for the TRES Finance plugin itself. Use this skill whenever a
  developer working in the plugin repo has added or modified a skill, changed the MCP
  config, edited the manifest, or otherwise prepared changes for distribution and is
  about to commit, open a PR, or cut a release. Trigger phrases include: "ship the
  plugin", "release the plugin", "bump the plugin version", "I added a skill",
  "I updated a skill", "ready to push the plugin", "prep the plugin release",
  "plugin checklist", "before I PR the plugin", "/tres-plugin-release". This skill
  walks the developer through README updates, version bumps in both plugin.json and
  marketplace.json, CHANGELOG entry, validation, local test, and a security pass.
  Do NOT trigger when an end user is just using the plugin's other skills — only when
  the user is acting as a plugin maintainer making changes to this repo.
---

# TRES Plugin Release Checklist

You are guiding a plugin maintainer through the steps that must happen before
distributing changes to the `tres-finance-plugin`. The goal: catch the easy-to-miss
items (forgotten README entry, version mismatch between manifests, stale CHANGELOG,
missing validation) before they ship to clients.

Work through the steps in order. After each step, briefly confirm what was done
before moving on. If a step doesn't apply (e.g. no skill changes), say so and skip.

---

## Step 0 — Confirm Context

Verify the maintainer is in the plugin repo:

```bash
pwd && git rev-parse --show-toplevel
```

Both should resolve to the `tres-finance-plugin` repo. If not, stop and tell the
user to run the skill from inside the plugin repo.

Then list what changed since `main`:

```bash
git status --short && git diff --stat main...HEAD
```

Tell the user **"Here's what changed — let's walk through the release checklist."**

---

## Step 1 — Identify the Change Type

Classify the change so version bump and CHANGELOG section are correct:

| Change | Bump | CHANGELOG section |
|---|---|---|
| New skill added | minor (`1.8.0` → `1.9.0`) | `### Added` |
| New capability in existing skill | minor | `### Added` or `### Changed` |
| Bug fix only | patch (`1.8.0` → `1.8.1`) | `### Fixed` |
| Breaking change (removed skill, renamed) | major (`1.x` → `2.0.0`) | `### Removed` / `### Changed` |
| Docs/README only | no bump needed | n/a |
| MCP config / userConfig change | minor (or major if breaking) | `### Changed` |

Confirm the classification with the user before proceeding.

---

## Step 2 — README Updates

Open [README.md](../../README.md). Update **both** places — they're easy to miss
one:

1. **Structure tree** (the `tres-finance-plugin/` ASCII tree near the top) —
   add/remove the skill folder line.
2. **Skills section** (`### \`skill-name\``) — add a new heading and 1–2 sentence
   description for any new skill, or edit the existing one.

Cross-check: list `skills/*/SKILL.md` and confirm every skill folder has a matching
README section, and the README has no entries for folders that no longer exist.

```bash
ls skills/ | sort
```

Compare against the README. Flag any drift to the user.

---

## Step 3 — Version Bump (BOTH manifests)

The version must match in both files or the marketplace listing breaks.

1. Bump in [.claude-plugin/plugin.json](../../.claude-plugin/plugin.json) (`version` field).
2. Bump in [.claude-plugin/marketplace.json](../../.claude-plugin/marketplace.json)
   (`plugins[0].version` field).

After editing, verify they match:

```bash
grep '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

If they don't match, fix before continuing.

---

## Step 4 — CHANGELOG Entry

Add a new entry at the top of [CHANGELOG.md](../../CHANGELOG.md):

```markdown
## [<new-version>] - <YYYY-MM-DD>

### Added
- `<skill-name>` skill — <one-sentence summary of what it does>

### Changed
- <if applicable>

### Fixed
- <if applicable>
```

- Use today's date in `YYYY-MM-DD` format.
- Keep entries terse — one bullet per change.
- Match the style of existing entries (see the rest of the file).

---

## Step 5 — SKILL.md Hygiene (for new/modified skills)

For every skill folder that was added or edited, verify:

1. **Frontmatter `name:` matches the directory name** exactly.
2. **`description:` is detailed** — includes trigger phrases and clear "do NOT trigger"
   conditions where relevant. Vague descriptions cause the model to mis-route.
3. **No absolute paths** in the skill body. Use `${CLAUDE_PLUGIN_ROOT}/...` for
   bundled scripts/assets, or paths relative to the skill folder.
4. **No secrets or example credentials** anywhere — no hardcoded API tokens, no
   real-looking keys, no `.env` contents.

Quick scan:

```bash
grep -rn '/Users/\|/home/\|TRES_API_TOKEN=' skills/<changed-skill>/ || echo "clean"
```

---

## Step 6 — Validate the Plugin

Run the official validator:

```bash
claude plugin validate .
```

Must report `✔ Validation passed`. If it fails, fix the reported errors and re-run
before continuing. Do not skip this step.

---

## Step 7 — Local Test

Test the plugin end-to-end against a real session before pushing. The maintainer's
preferred local invocation:

```bash
claude --plugin-dir "$(git rev-parse --show-toplevel)"
```

Ask the user: **"Have you exercised the new/changed skill in a local session? Any
issues to flag before we commit?"** If they haven't tested yet, recommend doing so —
type-check passes don't catch flow regressions.

---

## Step 8 — Security Pass (Fireblocks)

Final security review before the change leaves the repo:

- No hardcoded secrets, tokens, mnemonics, or private keys.
- No new external endpoints or MCP servers added without explicit review.
- No `--no-verify`, `verify=False`, or other security control bypasses.
- Skill outputs that show identifiers follow the project rule: tx hash (truncated)
  and account name only — never `subTxId` or `depositAccountId`.

If anything is unclear, surface it to the user — do not silently let it through.

---

## Step 9 — Commit & PR

Once everything above is green:

1. Stage explicitly (avoid `git add -A`):
   ```bash
   git add .claude-plugin/plugin.json .claude-plugin/marketplace.json \
           CHANGELOG.md README.md skills/<changed-skill>/
   ```
2. Commit with a descriptive message in the existing style (see `git log --oneline -5`).
3. Push the branch and open a PR to `main` with `gh pr create`.

Do NOT run destructive git operations (force push, reset --hard, --no-verify) without
explicit user confirmation.

---

## Step 10 — Summary

After the PR is open, give the user a 3-line recap:

> Released **`<plugin-name>` v`<new-version>`**.
> Changed: `<short summary>`.
> PR: `<url>`.

Done.

---

## Quick Reference — What to Update When

| You did this | Files to touch |
|---|---|
| Added a new skill | `skills/<name>/`, `README.md` (tree + descriptions), `plugin.json`, `marketplace.json`, `CHANGELOG.md` |
| Renamed a skill | All of the above + grep for old name across repo |
| Removed a skill | `skills/<name>/` (delete), `README.md`, `plugin.json`, `marketplace.json`, `CHANGELOG.md` (Removed section) |
| Edited a skill body only | `CHANGELOG.md` if user-visible; bump patch version |
| Changed `.mcp.json` | `CHANGELOG.md`, version bump (minor or major), `README.md` MCP section if surface changed |
| README typo / docs only | Just commit; no version bump |

---

## Error Handling

| Situation | Action |
|---|---|
| `claude plugin validate .` fails | Stop. Fix errors. Re-run. Do not proceed. |
| Versions in `plugin.json` and `marketplace.json` don't match | Fix immediately — the marketplace listing breaks otherwise. |
| User wants to skip the local test | Note it in the PR description so reviewer knows. |
| Pre-commit hook fails | Investigate the hook output. Do NOT pass `--no-verify`. Fix the underlying issue and create a NEW commit. |
| User asks to bypass any step | Ask why first. If they insist, document the skipped step in the PR. |

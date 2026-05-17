# TRES Finance Plugin — Project Instructions

## Analytics hook matchers

This plugin tracks usage via `hooks/hooks.json` and `scripts/telemetry.py`.

**Whenever a new TRES MCP tool is added** (i.e., a new tool becomes available on the `TRES Finance` MCP server), add it to the `matcher` string in **both** the `PostToolUse` MCP entry and the `PostToolUseFailure` entry in `hooks/hooks.json`. The format is:

```
mcp__claude_ai_tres-finance__<tool_name>
```

**Whenever a new skill is added** under `skills/`, no matcher change is needed — the `Skill` tool matcher (`"matcher": "Skill"`) already captures all skills automatically, and `telemetry.py` filters to `tres-finance-plugin:` prefixed skills only.

**After any hook or telemetry change**, also bump the `PLUGIN_VERSION` constant in `scripts/telemetry.py` to match the new version in `.claude-plugin/plugin.json`.

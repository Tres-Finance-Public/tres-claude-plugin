---
name: cc-plugin-dev
description: Create, update, test, debug, and distribute Claude Code plugins with skills, subagents, hooks, MCP servers, and LSP servers. Use this skill whenever the user mentions building a Claude Code plugin, creating a plugin for Claude Code, working on a plugin manifest (plugin.json), setting up a plugin marketplace, submitting a plugin to the Anthropic marketplace, adding skills/agents/hooks/MCP servers to a plugin, debugging plugin loading issues, converting standalone .claude/ configurations to plugins, or distributing plugins to teams or clients. Also trigger when the user mentions plugin.json, marketplace.json, SKILL.md in a plugin context, --plugin-dir, /reload-plugins, /plugin install, or any Claude Code plugin lifecycle task. Even if the user just says "plugin" in a Claude Code context, use this skill.
---

# Claude Code Plugin Developer Skill

Build, test, and distribute Claude Code plugins that extend Claude with custom skills, subagents, hooks, MCP servers, and LSP servers.

## Before you start

Read `references/plugin-system.md` in this skill's directory for the complete technical reference covering all plugin components, manifest schema, marketplace creation, and common pitfalls. That file is your source of truth — consult it whenever you need specifics on field names, directory structure, hook events, or distribution options.

## Core workflow

### 1. Scaffold a new plugin

When the user wants to create a new plugin, ask for:
- **Plugin name** (kebab-case, e.g. `tres-finance`)
- **Description** (one-liner for the plugin manager)
- **Which components** they need: skills, agents, hooks, MCP servers, LSP servers
- **Distribution target**: official marketplace, team marketplace, or local use

Then generate the directory structure. Always start with the minimal required files and expand based on what the user needs.

**Minimal scaffold:**
```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── <first-skill>/
│       └── SKILL.md
└── README.md
```

**Full scaffold** (when user needs all components):
```
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── <skill-name>/
│       └── SKILL.md
├── agents/
│   └── <agent-name>.md
├── hooks/
│   └── hooks.json
├── bin/
├── scripts/
├── .mcp.json
├── settings.json
├── README.md
├── LICENSE
└── CHANGELOG.md
```

The `.claude-plugin/` directory contains ONLY `plugin.json`. Never place skills, agents, hooks, or any other component directories inside `.claude-plugin/`.

### 2. Write the plugin manifest

Create `.claude-plugin/plugin.json` with at minimum:
```json
{
  "name": "<plugin-name>",
  "description": "<description>",
  "version": "1.0.0",
  "author": {
    "name": "<author>"
  }
}
```

If the plugin connects to external services and needs user credentials, add `userConfig`:
```json
{
  "userConfig": {
    "api_endpoint": {
      "description": "API endpoint URL",
      "sensitive": false
    },
    "api_key": {
      "description": "Authentication key",
      "sensitive": true  // REQUIRED for any credential — stores value in OS keychain, never in chat or config files
    }
  }
}
```

If targeting the official Anthropic marketplace, also include: `homepage`, `repository`, `license`, `keywords`.

### 3. Add components

#### Skills
Create `skills/<name>/SKILL.md` with frontmatter:
```markdown
---
name: <skill-name>
description: <when-to-use description — be specific and slightly pushy to ensure triggering>
---

Instructions for the skill. Reference $ARGUMENTS for user input.
```

Each skill is invoked as `/<plugin-name>:<skill-name>`. Write descriptions that clearly state WHEN Claude should auto-invoke this skill, not just what it does.

#### Subagents
Create `agents/<name>.md`:
```markdown
---
name: <agent-name>
description: <when Claude should delegate to this agent>
model: sonnet
tools: Read, Grep, Glob, Bash
maxTurns: 20
---

System prompt describing the agent's role and behavior.
```

Plugin agents CANNOT use hooks, mcpServers, or permissionMode in frontmatter (security restriction). If the user needs those, advise copying the agent to `~/.claude/agents/` or `.claude/agents/` instead.

#### Hooks
Create `hooks/hooks.json`:
```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "<ToolName|Pattern>",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/<script>.sh"
          }
        ]
      }
    ]
  }
}
```

Always use `${CLAUDE_PLUGIN_ROOT}` for script paths. Make scripts executable with `chmod +x`.

#### MCP Servers
Create `.mcp.json` at plugin root:
```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/<server>",
      "args": [],
      "env": {}
    }
  }
}
```

Use `${CLAUDE_PLUGIN_DATA}` for persistent state that survives plugin updates (like node_modules or caches).

### 4. Test locally

Run:
```bash
claude --plugin-dir ./tres-finance-plugin
```

Testing checklist:
- `/help` shows skills under the plugin namespace
- `/tres-finance-plugin:<skill-name>` works correctly
- `/agents` lists plugin agents
- `/reload-plugins` picks up changes without restart
- `/plugin validate .` passes validation
- Hooks fire on expected events
- MCP server tools appear in Claude's toolkit

For iterative development, edit files and run `/reload-plugins` — no restart needed.

### 5. Validate before distribution

Run:
```bash
claude plugin validate .
# or inside Claude Code:
/plugin validate .
```

This checks plugin.json syntax, skill/agent/command frontmatter, and hooks.json.

Pre-distribution checklist:
- [ ] All paths are relative (start with `./`)
- [ ] No files referenced outside the plugin directory
- [ ] Hook scripts are executable (`chmod +x`)
- [ ] All `${CLAUDE_PLUGIN_ROOT}` references are correct
- [ ] Version bumped from previous release
- [ ] README.md has installation and usage instructions
- [ ] LICENSE file present (if distributing publicly)
- [ ] Plugin name is kebab-case
- [ ] No reserved marketplace names used

### 6. Marketplace distribution

This plugin uses a dual-distribution model:

**Client distribution (marketplace):** Clients add the GitHub repo as a marketplace source:
```bash
/plugin marketplace add tres-finance/tres-finance-plugin
/plugin install tres-finance-plugin@tres-finance
```

**Official Anthropic marketplace:** Submit via:
- Claude.ai: https://claude.ai/settings/plugins/submit
- Console: https://platform.claude.com/plugins/submit

**Team auto-setup:** Clients can add to their project's `.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": {
    "tres-finance": {
      "source": {
        "source": "github",
        "repo": "tres-finance/tres-finance-plugin"
      }
    }
  },
  "enabledPlugins": {
    "tres-finance-plugin@tres-finance": true
  }
}
```

### 7. Update & version management

When updating the plugin:
1. Make changes to components
2. Bump version in BOTH `plugin.json` AND `marketplace.json`
3. Update CHANGELOG.md
4. Push to GitHub
5. Users run `/plugin marketplace update tres-finance`

### 8. Project structure

```
tres-finance-plugin/
├── .claude/                      # Internal dev tools (NOT distributed)
│   └── skills/
│       └── cc-plugin-dev/        # This skill
├── .claude-plugin/               # Plugin metadata (distributed)
│   ├── plugin.json
│   └── marketplace.json
├── skills/                       # User-facing skills (distributed)
│   └── explorer-tx-to-ledger/
│       └── SKILL.md
├── LICENSE
├── CHANGELOG.md
└── README.md
```

## Debugging common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Plugin not loading | Invalid plugin.json | Run `/plugin validate .` |
| Skills not appearing | Wrong directory structure | Ensure skills/ is at root, not inside .claude-plugin/ |
| Hooks not firing | Script not executable | `chmod +x script.sh` |
| MCP server fails | Missing ${CLAUDE_PLUGIN_ROOT} | Use variable for all plugin paths |
| Path errors | Absolute paths used | All paths must be relative with `./` |
| Agent missing hooks/MCP | Plugin security restriction | Copy agent to ~/.claude/agents/ instead |
| Changes not taking effect | Forgot reload | Run `/reload-plugins` |
| Users don't see updates | Version not bumped | Increment version in plugin.json AND marketplace.json |
| Files not found after install | Referencing outside plugin dir | Use symlinks or restructure |

For deep debugging, run: `claude --debug`

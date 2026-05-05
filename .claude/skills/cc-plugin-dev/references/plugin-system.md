# Claude Code Plugin System — Complete Reference

## Table of Contents
1. [Plugin Structure](#plugin-structure)
2. [Plugin Manifest (plugin.json)](#plugin-manifest)
3. [Skills](#skills)
4. [Subagents](#subagents)
5. [Hooks](#hooks)
6. [MCP Servers](#mcp-servers)
7. [LSP Servers](#lsp-servers)
8. [Marketplace Creation & Distribution](#marketplace)
9. [Testing & Debugging](#testing)
10. [Official Marketplace Submission](#submission)
11. [Environment Variables & Paths](#env-vars)
12. [Common Pitfalls](#pitfalls)

---

## 1. Plugin Structure <a name="plugin-structure"></a>

A plugin is a self-contained directory. The `.claude-plugin/` directory holds ONLY `plugin.json`. Everything else goes at the plugin root.

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json           # Manifest (metadata + config)
├── skills/                   # Skill directories with SKILL.md
│   └── my-skill/
│       ├── SKILL.md
│       ├── scripts/          # Optional helper scripts
│       └── references/       # Optional reference docs
├── commands/                 # Flat .md skill files (legacy, prefer skills/)
├── agents/                   # Subagent markdown files
│   └── my-agent.md
├── hooks/
│   └── hooks.json            # Hook event handlers
├── bin/                      # Executables added to Bash PATH
├── output-styles/            # Output style definitions
├── settings.json             # Default settings (currently only `agent` key)
├── .mcp.json                 # MCP server definitions
├── .lsp.json                 # LSP server definitions
├── scripts/                  # Utility scripts for hooks etc.
├── README.md
├── LICENSE
└── CHANGELOG.md
```

CRITICAL: Never put skills/, commands/, agents/, hooks/ INSIDE .claude-plugin/. Only plugin.json goes there.

---

## 2. Plugin Manifest <a name="plugin-manifest"></a>

File: `.claude-plugin/plugin.json`

### Minimal manifest:
```json
{
  "name": "my-plugin",
  "description": "Brief description",
  "version": "1.0.0"
}
```

### Full manifest fields:
| Field | Required | Type | Description |
|-------|----------|------|-------------|
| name | Yes | string | Kebab-case identifier, becomes namespace prefix |
| version | No | string | Semver (MAJOR.MINOR.PATCH) |
| description | No | string | Shown in plugin manager |
| author | No | object | `{name, email?, url?}` |
| homepage | No | string | Documentation URL |
| repository | No | string | Source code URL |
| license | No | string | SPDX identifier (MIT, Apache-2.0) |
| keywords | No | array | Discovery tags |
| skills | No | string/array | Custom skill directory paths |
| commands | No | string/array | Custom command file paths |
| agents | No | string/array | Custom agent file paths |
| hooks | No | string/array/object | Hook config paths or inline |
| mcpServers | No | string/array/object | MCP config paths or inline |
| lspServers | No | string/array/object | LSP config paths or inline |
| outputStyles | No | string/array | Output style paths |
| userConfig | No | object | User-prompted config values |
| channels | No | array | Channel declarations |

### userConfig example:
```json
{
  "userConfig": {
    "api_endpoint": {
      "description": "Your TRES Finance API endpoint",
      "sensitive": false
    },
    "api_token": {
      "description": "API authentication token",
      "sensitive": true
    }
  }
}
```
- Non-sensitive values stored in settings.json
- Sensitive values stored in system keychain
- Available as `${user_config.KEY}` in MCP/LSP/hook configs
- Exported as `CLAUDE_PLUGIN_OPTION_<KEY>` env vars

---

## 3. Skills <a name="skills"></a>

Location: `skills/<skill-name>/SKILL.md`
Namespaced as: `/plugin-name:skill-name`

### SKILL.md format:
```markdown
---
name: my-skill
description: What this skill does and when Claude should use it
disable-model-invocation: true  # Optional: only manual invocation
---

Instructions for the skill. Use $ARGUMENTS for user input.
```

- Skills can include helper scripts in `scripts/` subdirectory
- Skills can include reference docs in `references/` subdirectory
- The `description` field in frontmatter drives when Claude auto-invokes the skill
- Use `$ARGUMENTS` placeholder for dynamic user input

---

## 4. Subagents <a name="subagents"></a>

Location: `agents/<agent-name>.md`

### Agent file format:
```markdown
---
name: agent-name
description: When Claude should delegate to this agent
model: sonnet
effort: medium
maxTurns: 20
tools: Read, Grep, Glob, Bash
disallowedTools: Write, Edit
memory: user
background: false
isolation: worktree
color: blue
---

System prompt for the agent describing role, expertise, and behavior.
```

### Supported frontmatter for plugin agents:
- name, description (required)
- model: sonnet | opus | haiku | inherit | full model ID
- effort: low | medium | high | max
- maxTurns: integer
- tools: comma-separated tool names
- disallowedTools: comma-separated tool names
- skills: list of skills to preload
- memory: user | project | local
- background: true | false
- isolation: worktree
- color: red|blue|green|yellow|purple|orange|pink|cyan

### NOT supported for plugin agents (security):
- hooks
- mcpServers
- permissionMode

---

## 5. Hooks <a name="hooks"></a>

Location: `hooks/hooks.json` or inline in plugin.json

### hooks.json format:
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolName|OtherTool",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/my-script.sh"
          }
        ]
      }
    ]
  }
}
```

### Available events:
| Event | When it fires |
|-------|--------------|
| SessionStart | Session begins or resumes |
| UserPromptSubmit | Before Claude processes prompt |
| PreToolUse | Before tool execution (can block) |
| PostToolUse | After successful tool execution |
| PostToolUseFailure | After failed tool execution |
| PermissionRequest | Permission dialog appears |
| PermissionDenied | Tool call denied |
| SubagentStart | Subagent spawned |
| SubagentStop | Subagent finished |
| Stop | Claude finishes responding |
| StopFailure | Turn ends due to API error |
| Notification | Claude sends notification |
| TaskCreated | Task created via TaskCreate |
| TaskCompleted | Task marked completed |
| TeammateIdle | Agent team teammate going idle |
| InstructionsLoaded | CLAUDE.md loaded |
| ConfigChange | Config file changes |
| CwdChanged | Working directory changes |
| FileChanged | Watched file changes (matcher = filename) |
| WorktreeCreate | Worktree being created |
| WorktreeRemove | Worktree being removed |
| PreCompact | Before context compaction |
| PostCompact | After context compaction |
| Elicitation | MCP server requests user input |
| ElicitationResult | User responds to elicitation |
| SessionEnd | Session terminates |

### Hook types:
- **command**: Execute shell command/script
- **http**: POST event JSON to URL
- **prompt**: Evaluate prompt with LLM ($ARGUMENTS placeholder)
- **agent**: Run agentic verifier with tools

### Exit codes for PreToolUse hooks:
- 0: Allow
- 2: Block (error message via stderr shown to Claude)

---

## 6. MCP Servers <a name="mcp-servers"></a>

Location: `.mcp.json` at plugin root, or inline in plugin.json

### .mcp.json format:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/my-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
      "env": {
        "MY_VAR": "${user_config.api_endpoint}"
      }
    }
  }
}
```

- Always use `${CLAUDE_PLUGIN_ROOT}` for paths to bundled files
- Use `${CLAUDE_PLUGIN_DATA}` for persistent state (survives updates)
- Servers start automatically when plugin is enabled
- Server types: stdio, http, sse, ws

---

## 7. LSP Servers <a name="lsp-servers"></a>

Location: `.lsp.json` at plugin root

```json
{
  "language-name": {
    "command": "binary-name",
    "args": ["serve"],
    "extensionToLanguage": {
      ".ext": "language"
    }
  }
}
```

Required fields: command, extensionToLanguage
Optional: args, transport (stdio|socket), env, initializationOptions, settings, workspaceFolder, startupTimeout, shutdownTimeout, restartOnCrash, maxRestarts

---

## 8. Marketplace Creation & Distribution <a name="marketplace"></a>

### Marketplace file: `.claude-plugin/marketplace.json`

```json
{
  "name": "marketplace-name",
  "owner": {
    "name": "Team Name",
    "email": "team@example.com"
  },
  "metadata": {
    "description": "Brief marketplace description",
    "version": "1.0.0",
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "plugin-name",
      "source": "./plugins/plugin-name",
      "description": "Plugin description",
      "version": "1.0.0",
      "category": "category-name",
      "tags": ["tag1", "tag2"]
    }
  ]
}
```

### Plugin source types:
1. **Relative path**: `"source": "./plugins/my-plugin"` (within same repo)
2. **GitHub**: `{"source": "github", "repo": "owner/repo", "ref": "v1.0", "sha": "abc123"}`
3. **Git URL**: `{"source": "url", "url": "https://gitlab.com/team/plugin.git"}`
4. **Git subdirectory**: `{"source": "git-subdir", "url": "...", "path": "tools/plugin"}`
5. **npm**: `{"source": "npm", "package": "@org/plugin", "version": "^2.0.0"}`

### Reserved marketplace names (cannot use):
claude-code-marketplace, claude-code-plugins, claude-plugins-official, anthropic-marketplace, anthropic-plugins, agent-skills, knowledge-work-plugins, life-sciences

### Marketplace commands:
```bash
# Add marketplace
/plugin marketplace add owner/repo
/plugin marketplace add https://gitlab.com/company/plugins.git
/plugin marketplace add ./local-marketplace

# Manage
/plugin marketplace list
/plugin marketplace update marketplace-name
/plugin marketplace remove marketplace-name
```

### Team distribution via .claude/settings.json:
```json
{
  "extraKnownMarketplaces": {
    "team-tools": {
      "source": {
        "source": "github",
        "repo": "your-org/claude-plugins"
      }
    }
  },
  "enabledPlugins": {
    "plugin-name@team-tools": true
  }
}
```

---

## 9. Testing & Debugging <a name="testing"></a>

### Local testing:
```bash
claude --plugin-dir ./my-plugin
```

### During development:
- `/reload-plugins` — reload without restarting
- `/plugin validate .` — validate manifest and components
- `claude --debug` — see plugin loading details
- `/help` — verify skills listed under plugin namespace
- `/agents` — verify agents appear

### Test checklist:
1. Skills work: `/plugin-name:skill-name`
2. Agents appear in `/agents`
3. Hooks trigger on expected events
4. MCP servers start and tools appear
5. `$ARGUMENTS` substitution works in skills
6. `${CLAUDE_PLUGIN_ROOT}` paths resolve correctly
7. `userConfig` prompts appear on enable

### Loading multiple plugins:
```bash
claude --plugin-dir ./plugin-one --plugin-dir ./plugin-two
```

---

## 10. Official Marketplace Submission <a name="submission"></a>

Submit via in-app forms:
- Claude.ai: https://claude.ai/settings/plugins/submit
- Console: https://platform.claude.com/plugins/submit

Before submitting:
- Include README.md with installation and usage instructions
- Use semantic versioning in plugin.json
- Add LICENSE file
- Test thoroughly with --plugin-dir
- Ensure plugin name is kebab-case
- Verify all paths are relative (start with ./)

---

## 11. Environment Variables & Paths <a name="env-vars"></a>

### Plugin variables:
- `${CLAUDE_PLUGIN_ROOT}` — Plugin installation directory (changes on update)
- `${CLAUDE_PLUGIN_DATA}` — Persistent data directory (survives updates)
  - Resolves to: `~/.claude/plugins/data/{id}/`

### Path rules:
- All paths must be relative to plugin root and start with `./`
- Custom paths for skills/commands/agents/outputStyles REPLACE defaults
- To keep defaults AND add more: `"skills": ["./skills/", "./extras/"]`
- Paths referencing `../` outside plugin root will NOT work after installation (plugin is cached)

### Persistent data pattern (install deps once):
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "diff -q \"${CLAUDE_PLUGIN_ROOT}/package.json\" \"${CLAUDE_PLUGIN_DATA}/package.json\" >/dev/null 2>&1 || (cd \"${CLAUDE_PLUGIN_DATA}\" && cp \"${CLAUDE_PLUGIN_ROOT}/package.json\" . && npm install)"
      }]
    }]
  }
}
```

---

## 12. Common Pitfalls <a name="pitfalls"></a>

1. **Putting components inside .claude-plugin/**: Only plugin.json goes there
2. **Using absolute paths**: All paths must be relative with `./`
3. **Referencing files outside plugin dir**: Won't work after installation (caching)
4. **Forgetting chmod +x on hook scripts**: Scripts must be executable
5. **Not using ${CLAUDE_PLUGIN_ROOT}**: Paths break after installation
6. **Same version after changes**: Users won't see updates without version bump
7. **Hooks/mcpServers/permissionMode in plugin agents**: Not supported (security)
8. **Not running /reload-plugins after changes**: Changes won't take effect
9. **Reserved marketplace names**: Will be rejected
10. **Plugin name not kebab-case**: May cause issues with marketplace sync

### Strict mode (marketplace):
- `strict: true` (default): plugin.json is authority, marketplace can supplement
- `strict: false`: marketplace entry is entire definition, plugin.json components conflict

### Plugin installation scopes:
| Scope | Settings file | Use case |
|-------|--------------|---------|
| user | ~/.claude/settings.json | Personal, all projects |
| project | .claude/settings.json | Team, shared via VCS |
| local | .claude/settings.local.json | Project-specific, gitignored |
| managed | Managed settings | Admin-deployed, read-only |

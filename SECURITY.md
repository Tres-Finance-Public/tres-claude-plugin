# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this repository, please **do not open a public GitHub issue**.

Report it via email to: **security@tres.finance**

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept (if applicable)
- The file(s) and line number(s) involved

We aim to acknowledge reports within 2 business days and provide a resolution timeline within 7 business days.

## Scope

This repository contains natural-language skill playbooks (`.md` files), plugin metadata (`plugin.json`), an MCP server pointer (`.mcp.json`), and one Python helper script. There is no server-side code.

For the full threat model and architecture, see [`docs/SECURITY-HLD.md`](docs/SECURITY-HLD.md).

## Out of Scope

- TRES Finance backend / API (`api.tres.finance`) — report via support@tres.finance
- Anthropic Claude Code CLI — report via Anthropic's own disclosure process
- TRES Finance web app (`app.tres.finance`) — report via support@tres.finance

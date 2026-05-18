#!/usr/bin/env bash
# track.sh — Fire-and-forget telemetry hook for the TRES Finance Claude Code plugin.
# Called by hooks/hooks.json on PostToolUse, PostToolUseFailure, and Stop events.
# Event JSON is piped on stdin. Never blocks Claude (backgrounded).
set -uo pipefail

EVENT_TYPE="${1:-unknown}"

# Background the Python helper so this hook returns immediately.
# Stdin is piped into the subprocess via process substitution.
INPUT=$(cat)
echo "$INPUT" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry.py" "$EVENT_TYPE" 2>/dev/null &

exit 0

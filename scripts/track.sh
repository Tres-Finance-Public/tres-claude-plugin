#!/usr/bin/env bash
# track.sh — Fire-and-forget telemetry hook for the TRES Finance Claude Code plugin.
# Called by hooks/hooks.json on PostToolUse, PostToolUseFailure, and Stop events.
# Event JSON is piped on stdin. Never blocks Claude (backgrounded).
set -uo pipefail

EVENT_TYPE="${1:-unknown}"

# Background the Python helper so this hook returns immediately. We detach it
# from the calling process group (`setsid` when available, `nohup` fallback,
# bare-bash `&` + `disown` as the last resort) so Claude Code's hook lifecycle
# can't reap the child before the HTTP POST completes — that was an invisible
# source of dropped events because everything downstream is muted (>/dev/null,
# bare except, fire-and-forget).
#
# Diagnostic outcomes are written by telemetry.py to
# $CLAUDE_PLUGIN_DATA/telemetry.log regardless of how this script exits.
INPUT=$(cat)

run_detached() {
    if command -v setsid >/dev/null 2>&1; then
        setsid python3 "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry.py" "$EVENT_TYPE" \
            >/dev/null 2>&1 < <(printf '%s' "$INPUT") &
    elif command -v nohup >/dev/null 2>&1; then
        nohup python3 "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry.py" "$EVENT_TYPE" \
            >/dev/null 2>&1 < <(printf '%s' "$INPUT") &
    else
        python3 "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry.py" "$EVENT_TYPE" \
            >/dev/null 2>&1 < <(printf '%s' "$INPUT") &
    fi
    disown 2>/dev/null || true
}

run_detached

exit 0

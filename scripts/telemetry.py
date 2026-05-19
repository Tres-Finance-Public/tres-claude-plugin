"""
telemetry.py — Core telemetry logic for the TRES Finance Claude Code plugin.

Reads a hook event JSON from stdin, enriches it with cached org/user identity,
and POSTs a minimal analytics event to the TRES backend, which forwards to Mixpanel.

Data sent: event type, tool/skill name, success flag, session ID, org ID,
           org name, user email, plugin version, source, and timestamp.
Data NOT sent: GraphQL queries, tool inputs, financial data, tool responses.

Usage: echo '<event_json>' | python3 telemetry.py <event_type>
  event_type: skill_invoked | skill_completed | mcp_tool_call | mcp_tool_failure

Debug: set TRES_DEBUG_HOOKS=1 to write raw hook events to $CLAUDE_PLUGIN_DATA/debug.log
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

PLUGIN_VERSION = "1.9.4"
# Endpoint can be overridden via the TRES_TELEMETRY_URL environment variable.
# Defaults to the production TRES backend (placeholder until the endpoint is live).
TELEMETRY_URL = os.environ.get("TRES_TELEMETRY_URL", "https://ai.tres.finance/telemetry")
TIMEOUT_SECONDS = 5


def _identity_path() -> str:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return os.path.join(data_dir, "identity.json")


def _read_identity() -> dict:
    try:
        with open(_identity_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_identity(identity: dict) -> None:
    try:
        path = _identity_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(identity, f)
    except Exception:
        pass


def _extract_identity_from_viewer_response(tool_response) -> dict:
    """Pull org_id, org_name, email out of a get_viewer tool_response."""
    try:
        if isinstance(tool_response, str):
            tool_response = json.loads(tool_response)
        # The MCP response wraps data: { viewer: { ... } }
        viewer = tool_response
        for key in ("result", "data"):
            if key in viewer and isinstance(viewer[key], dict):
                viewer = viewer[key]
        if "viewer" in viewer and isinstance(viewer["viewer"], dict):
            viewer = viewer["viewer"]

        org_name = viewer.get("orgName", viewer.get("organizationName", ""))
        return {
            "org_id": str(viewer.get("orgId", viewer.get("id", org_name))),
            "org_name": org_name,
            "email": viewer.get("email", viewer.get("displayName", "")),
        }
    except Exception:
        return {}


def _current_skill_path() -> str:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return os.path.join(data_dir, "current_skill.json")


def _write_current_skill(skill_name: str) -> None:
    try:
        path = _current_skill_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"skill_name": skill_name}, f)
    except Exception:
        pass


def _pop_current_skill() -> str:
    """Read and remove the current skill state file. Returns skill name or empty string."""
    try:
        path = _current_skill_path()
        with open(path) as f:
            data = json.load(f)
        os.remove(path)
        return data.get("skill_name", "")
    except Exception:
        return ""


def _debug_log(event: dict, event_type: str) -> None:
    if not os.environ.get("TRES_DEBUG_HOOKS"):
        return
    try:
        data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "/tmp")
        log_path = os.path.join(data_dir, "debug.log")
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": event_type,
            "tool_name": event.get("tool_name", ""),
            "tool_input_keys": list(event.get("tool_input", {}).keys()) if isinstance(event.get("tool_input"), dict) else str(event.get("tool_input", ""))[:200],
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _base_properties(identity: dict, session_id: str) -> dict:
    return {
        "session_id": session_id,
        "org_id": identity.get("org_id", ""),
        "org_name": identity.get("org_name", ""),
        "email": identity.get("email", ""),
        "plugin_version": PLUGIN_VERSION,
        "source": "tres-claude-plugin",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _post(payload: dict) -> None:
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS)
    except Exception:
        pass


def main() -> None:
    event_type = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    tool_response = event.get("tool_response", {})
    session_id = event.get("session_id", "")

    _debug_log(event, event_type)

    identity = _read_identity()

    # Lazy identity caching: extract from get_viewer responses.
    if "get_viewer" in tool_name and not identity.get("org_id"):
        identity = _extract_identity_from_viewer_response(tool_response)
        if identity.get("org_id"):
            _write_identity(identity)

    # Identity refresh after org switch.
    if "switch_organization" in tool_name:
        try:
            os.remove(_identity_path())
        except Exception:
            pass
        identity = {}

    props = _base_properties(identity, session_id)

    if event_type == "skill_invoked":
        # tool_input for the Skill tool: {"skill": "tres-finance-plugin:tres-recon-gaps", ...}
        raw_skill = ""
        if isinstance(tool_input, dict):
            raw_skill = tool_input.get("skill", tool_input.get("name", ""))
        elif isinstance(tool_input, str):
            try:
                raw_skill = json.loads(tool_input).get("skill", "")
            except Exception:
                pass

        # Strip plugin namespace prefix (e.g. "tres-finance-plugin:")
        skill_name = raw_skill.split(":", 1)[-1] if ":" in raw_skill else raw_skill

        # Only track TRES Finance plugin skills.
        if not raw_skill.startswith("tres-finance-plugin:"):
            sys.exit(0)

        props["skill_name"] = skill_name
        _write_current_skill(skill_name)
        payload = {"event": "skill_invoked", "skill_name": skill_name, "properties": props}

    elif event_type == "skill_completed":
        skill_name = _pop_current_skill()
        if skill_name:
            props["skill_name"] = skill_name
        payload = {"event": "skill_completed", "properties": props}

    elif event_type in ("mcp_tool_call", "mcp_tool_failure"):
        # Clean tool name: strip MCP namespace (e.g. "mcp__claude_ai_tres-finance__execute" → "execute")
        clean_tool = tool_name.split("__")[-1] if "__" in tool_name else tool_name
        success = event_type == "mcp_tool_call"
        props["tool_name"] = clean_tool
        props["success"] = success
        payload = {"event": "mcp_tool_call", "tool_name": clean_tool, "success": success, "properties": props}

    else:
        sys.exit(0)

    _post(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

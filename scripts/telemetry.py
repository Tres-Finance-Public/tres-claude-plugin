"""
telemetry.py — Core telemetry logic for the TRES Finance Claude Code plugin.

Reads a hook event JSON from stdin, enriches it with cached org/user identity,
and POSTs a minimal analytics event to the TRES backend, which forwards to Mixpanel.

Data sent: event type, tool/skill name, success flag, session ID, org ID,
           org name, user email, plugin version, source, and timestamp.
Data NOT sent: GraphQL queries, tool inputs, financial data, tool responses.

Usage: echo '<event_json>' | python3 telemetry.py <event_type>
  event_type: skill_invoked | skill_completed | mcp_tool_call | mcp_tool_failure

Diagnostics:
- $CLAUDE_PLUGIN_DATA/telemetry.log: append-only one-line outcome per invocation
  (always on — needed because the wrapping shell hook is fully muted).
- $CLAUDE_PLUGIN_DATA/debug.log: raw inbound hook events. Opt-in via TRES_DEBUG_HOOKS=1.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

PLUGIN_VERSION = "1.10.0"
# Endpoint can be overridden via the TRES_TELEMETRY_URL environment variable.
# Defaults to the production TRES backend (placeholder until the endpoint is live).
TELEMETRY_URL = os.environ.get("TRES_TELEMETRY_URL", "https://ai.tres.finance/telemetry")
TIMEOUT_SECONDS = 5
# Cap the diagnostic log so a long-lived install doesn't grow unbounded.
_OUTCOME_LOG_MAX_BYTES = 256 * 1024


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


def _outcome_log(entry: dict) -> None:
    """Append one JSON line summarizing this invocation's outcome.

    Always on. Without this, the hook + script chain is fully muted
    (`2>/dev/null`, bare except, fire-and-forget background), so users
    have no way to tell whether telemetry is working.
    """
    try:
        data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "/tmp")
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, "telemetry.log")
        if os.path.exists(log_path) and os.path.getsize(log_path) > _OUTCOME_LOG_MAX_BYTES:
            try:
                os.replace(log_path, log_path + ".1")
            except Exception:
                pass
        entry.setdefault(
            "ts", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        entry.setdefault("plugin_version", PLUGIN_VERSION)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _tool_call_succeeded(tool_response) -> bool:
    """Detect MCP "soft errors" — tools that catch their own exceptions
    and return an error-shaped response. From Claude Code's perspective
    such calls are PostToolUse (success), so without this inspection the
    ``success`` flag in Mixpanel is always ``true`` and meaningless.

    Treat as failure iff the response is a dict with a top-level ``error``
    field or matches the bff-mcp ``ErrorResponse`` shape
    (``{"status": "error", ...}``). Everything else — including missing
    response, non-dict response, parse failure — is treated as success
    so the existing happy-path behavior is preserved.
    """
    try:
        if isinstance(tool_response, str):
            tool_response = json.loads(tool_response)
        if not isinstance(tool_response, dict):
            return True
        if "error" in tool_response and tool_response.get("error"):
            return False
        if tool_response.get("status") == "error":
            return False
        return True
    except Exception:
        return True


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


def _post(payload: dict) -> dict:
    """POST the payload and return a structured outcome for the outcome log.

    Never raises. The returned dict always has at least an ``outcome`` key
    (``"ok"`` | ``"http_error"`` | ``"transport_error"`` | ``"encode_error"``).
    """
    try:
        data = json.dumps(payload).encode()
    except Exception as exc:
        return {"outcome": "encode_error", "error_class": type(exc).__name__}

    req = urllib.request.Request(
        TELEMETRY_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return {"outcome": "ok", "http_status": response.status}
    except urllib.error.HTTPError as exc:
        return {"outcome": "http_error", "http_status": exc.code}
    except Exception as exc:
        return {"outcome": "transport_error", "error_class": type(exc).__name__}


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
        # PostToolUse (success) fires for tools that catch their own exception
        # and return an error-shaped response. Inspect the response so the
        # success flag reflects what actually happened on the server side.
        success = event_type == "mcp_tool_call" and _tool_call_succeeded(tool_response)
        props["tool_name"] = clean_tool
        props["success"] = success
        payload = {"event": "mcp_tool_call", "tool_name": clean_tool, "success": success, "properties": props}

    else:
        sys.exit(0)

    result = _post(payload)
    _outcome_log({
        "event_type": event_type,
        "event": payload["event"],
        "tool_name": payload.get("tool_name") or payload.get("skill_name") or "",
        "success": payload.get("success"),
        "session_id": props.get("session_id", ""),
        "org_id": props.get("org_id", ""),
        **result,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

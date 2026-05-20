"""
telemetry.py — Direct Mixpanel ingestion for the TRES Finance Claude Code plugin.

Reads a hook event JSON from stdin, enriches it with cached org/user identity,
and POSTs directly to Mixpanel's HTTPS Track / Engage APIs.

Hook discriminators (skill_invoked, skill_completed, mcp_tool_call) are wire-format
only — not Mixpanel event names. Mixpanel naming follows mixpanel-tracking.mdc:
noun event name + required action property + context properties.

Data sent: event name, action, tool/skill name, success flag, session ID, org ID,
           org name, user email, plugin version, and timestamp.
Data NOT sent: GraphQL queries, tool inputs, financial data, tool responses.

Usage: echo '<event_json>' | python3 telemetry.py <event_type>
  event_type: skill_invoked | skill_completed | mcp_tool_call | mcp_tool_failure

Disable telemetry: set TRES_MIXPANEL_TOKEN="" in your environment.
Debug: set TRES_DEBUG_HOOKS=1 to write raw hook events to $CLAUDE_PLUGIN_DATA/debug.log
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

PLUGIN_VERSION = "1.11.0"

# Mixpanel event names (nouns) and action verbs — see .cursor/rules/mixpanel-tracking.mdc
PLUGIN_MIXPANEL_EVENTS = {
    "skill": "Skill",
    "mcp_tool": "MCP Tool",
}

PLUGIN_MIXPANEL_ACTIONS = {
    "invoked": "invoked",
    "completed": "completed",
    "called": "called",
}

_MIXPANEL_TOKEN = os.environ.get(
    "TRES_MIXPANEL_TOKEN",
    "8054425fe5bc40d580518105019119bd",
)
_MIXPANEL_HOST = os.environ.get(
    "TRES_MIXPANEL_HOST",
    "https://api-eu.mixpanel.com",
).rstrip("/")
_TRACK_URL = f"{_MIXPANEL_HOST}/track"
_ENGAGE_URL = f"{_MIXPANEL_HOST}/engage"

_TIMEOUT_SECONDS = 5


def _identity_path() -> str:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return os.path.join(data_dir, "identity.json")


def _current_skill_path() -> str:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return os.path.join(data_dir, "current_skill.json")


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


def _write_current_skill(skill_name: str) -> None:
    try:
        path = _current_skill_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"skill_name": skill_name}, f)
    except Exception:
        pass


def _pop_current_skill() -> str:
    try:
        path = _current_skill_path()
        with open(path) as f:
            data = json.load(f)
        os.remove(path)
        return data.get("skill_name", "")
    except Exception:
        return ""


def _extract_identity_from_viewer_response(tool_response) -> dict:
    """Pull org_id, org_name, email out of a get_viewer tool_response."""
    try:
        if isinstance(tool_response, str):
            tool_response = json.loads(tool_response)
        viewer = tool_response
        for key in ("data", "result"):
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
            "tool_input_keys": (
                list(event.get("tool_input", {}).keys())
                if isinstance(event.get("tool_input"), dict)
                else str(event.get("tool_input", ""))[:200]
            ),
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _build_distinct_id(org_id: str, email: str, session_id: str) -> str:
    if org_id and email:
        return f"{org_id}:{email}"
    return session_id or "anonymous"


def _iso_to_unix(iso_ts: str) -> int:
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return int(ts.timestamp())
    except Exception:
        return int(datetime.now(timezone.utc).timestamp())


def _base_properties(identity: dict, session_id: str) -> dict:
    return {
        "session_id": session_id,
        "org_id": identity.get("org_id", ""),
        "org_name": identity.get("org_name", ""),
        "email": identity.get("email", ""),
        "plugin_version": PLUGIN_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _post(url: str, body: list) -> None:
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS)
    except Exception:
        pass


def _build_track_payload(event_name: str, props: dict, event_specific: dict) -> dict:
    distinct_id = _build_distinct_id(
        props["org_id"], props["email"], props["session_id"]
    )
    return {
        "event": event_name,
        "properties": {
            "token": _MIXPANEL_TOKEN,
            "distinct_id": distinct_id,
            "time": _iso_to_unix(props["timestamp"]),
            "session_id": props["session_id"],
            "plugin_version": props["plugin_version"],
            "$org_id": props["org_id"],
            "$org_name": props["org_name"],
            "$email": props["email"],
            **event_specific,
        },
    }


def _build_engage_payload(props: dict) -> dict:
    distinct_id = _build_distinct_id(
        props["org_id"], props["email"], props["session_id"]
    )
    return {
        "$token": _MIXPANEL_TOKEN,
        "$distinct_id": distinct_id,
        "$set": {
            "$email": props["email"],
            "org_id": props["org_id"],
            "org_name": props["org_name"],
            "plugin_version": props["plugin_version"],
        },
    }


def _upsert_people_profile_once(identity: dict, props: dict) -> None:
    if not (props["org_id"] and props["email"]):
        return
    distinct_id = _build_distinct_id(
        props["org_id"], props["email"], props["session_id"]
    )
    engage_key = f"{distinct_id}@{props['plugin_version']}"
    if identity.get("engaged_key") == engage_key:
        return
    identity["engaged_key"] = engage_key
    _write_identity(identity)
    _post(_ENGAGE_URL, [_build_engage_payload(props)])


def main() -> None:
    if not _MIXPANEL_TOKEN:
        sys.exit(0)

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

    if "get_viewer" in tool_name and not identity.get("org_id"):
        extracted = _extract_identity_from_viewer_response(tool_response)
        if extracted.get("org_id"):
            identity = {**identity, **extracted}
            _write_identity(identity)

    if "switch_organization" in tool_name:
        try:
            os.remove(_identity_path())
        except Exception:
            pass
        identity = {}

    props = _base_properties(identity, session_id)

    # Mixpanel event naming: noun + action + context — see mixpanel-tracking.mdc
    if event_type == "skill_invoked":
        raw_skill = ""
        if isinstance(tool_input, dict):
            raw_skill = tool_input.get("skill", tool_input.get("name", ""))
        elif isinstance(tool_input, str):
            try:
                raw_skill = json.loads(tool_input).get("skill", "")
            except Exception:
                pass

        if not raw_skill.startswith("tres-finance-plugin:"):
            sys.exit(0)

        skill_name = raw_skill.split(":", 1)[-1] if ":" in raw_skill else raw_skill
        _write_current_skill(skill_name)
        event_name = PLUGIN_MIXPANEL_EVENTS["skill"]
        event_specific = {
            "action": PLUGIN_MIXPANEL_ACTIONS["invoked"],
            "skill_name": skill_name,
        }

    elif event_type == "skill_completed":
        skill_name = _pop_current_skill()
        event_name = PLUGIN_MIXPANEL_EVENTS["skill"]
        event_specific = {"action": PLUGIN_MIXPANEL_ACTIONS["completed"]}
        if skill_name:
            event_specific["skill_name"] = skill_name

    elif event_type in ("mcp_tool_call", "mcp_tool_failure"):
        clean_tool = tool_name.split("__")[-1] if "__" in tool_name else tool_name
        event_name = PLUGIN_MIXPANEL_EVENTS["mcp_tool"]
        event_specific = {
            "action": PLUGIN_MIXPANEL_ACTIONS["called"],
            "tool_name": clean_tool,
            "success": event_type == "mcp_tool_call",
        }

    else:
        sys.exit(0)

    payload = _build_track_payload(event_name, props, event_specific)
    _post(_TRACK_URL, [payload])
    _upsert_people_profile_once(identity, props)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

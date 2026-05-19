"""
telemetry.py — Direct Mixpanel ingestion for the TRES Finance Claude Code plugin.

Reads a hook event JSON from stdin, enriches it with cached org/user identity,
and POSTs directly to Mixpanel's HTTPS Track / Engage APIs.

Architecture
------------
v1.9.x and earlier routed events through a TRES-hosted proxy
(https://ai.tres.finance/telemetry) which forwarded to Mixpanel. v1.10.0+
sends events directly. This:
  - Removes a TRES production dependency from the plugin's critical path.
  - Eliminates the noisy-neighbor risk of co-locating analytics ingestion
    with the latency-sensitive MCP server.
  - Matches the pattern used by every official Mixpanel client SDK and by
    the TRES web dashboard (which has shipped this same token client-side
    for years).

Token visibility
----------------
Mixpanel project tokens are *not* secrets — per Mixpanel's official docs:
  https://developer.mixpanel.com/reference/project-token
  "A project token is not a secret value and is designed to be publicly
   exposed in client-side implementations. The project token is not a form
   of authorization — it serves only as an identification mechanism to
   route data to the correct project."

The same token is already public in the TRES web dashboard's compiled JS
bundle. It is write-only (cannot read or admin the project) and rate-
limited by Mixpanel server-side. Treating it as a secret would only break
Mixpanel's intended client-side architecture without changing the actual
threat surface.

Privacy
-------
Data sent: event type, tool/skill name, success flag, session ID, org ID,
           org name, user email, plugin version, and timestamp.
Data NOT sent: GraphQL queries, tool inputs, financial data, tool
               responses, or any customer business data.

Usage
-----
  echo '<event_json>' | python3 telemetry.py <event_type>
    event_type: skill_invoked | skill_completed | mcp_tool_call | mcp_tool_failure

Disable telemetry: set TRES_MIXPANEL_TOKEN="" in your environment.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

PLUGIN_VERSION = "1.10.0"

# Public Mixpanel project token (EU residency, write-only). See module
# docstring for why this is not a secret. Override for testing via
# TRES_MIXPANEL_TOKEN; set to "" to disable telemetry entirely.
_MIXPANEL_TOKEN = os.environ.get(
    "TRES_MIXPANEL_TOKEN",
    "8054425fe5bc40d580518105019119bd",
)
# TRES Mixpanel project is EU-hosted. Sending to api.mixpanel.com (US)
# silently drops events (Mixpanel returns 200 but never indexes them).
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
        viewer = tool_response
        for key in ("data", "result"):
            if key in viewer and isinstance(viewer[key], dict):
                viewer = viewer[key]
        if "viewer" in viewer and isinstance(viewer["viewer"], dict):
            viewer = viewer["viewer"]

        return {
            "org_id": str(viewer.get("orgId", viewer.get("id", ""))),
            "org_name": viewer.get("orgName", viewer.get("organizationName", "")),
            "email": viewer.get("email", viewer.get("displayName", "")),
        }
    except Exception:
        return {}


def _build_distinct_id(org_id: str, email: str, session_id: str) -> str:
    """Mirror the server-side mapping that used to live in bff-mcp."""
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
    """Fire-and-forget POST to Mixpanel. Never raises."""
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
    """Upsert People profile once per (distinct_id, plugin_version) tuple.

    Dedup via identity.json so repeated hook invocations in the same plugin
    install don't all fire /engage. The plugin_version is included so an
    upgrade refreshes the profile (e.g. surfaces the new version on the
    People page even if the user's identity didn't change).
    """
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
        # User opted out via TRES_MIXPANEL_TOKEN="".
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

    identity = _read_identity()

    # Lazy identity caching: extract from get_viewer responses.
    if "get_viewer" in tool_name and not identity.get("org_id"):
        extracted = _extract_identity_from_viewer_response(tool_response)
        if extracted.get("org_id"):
            identity = {**identity, **extracted}
            _write_identity(identity)

    # Identity refresh after org switch — reset cached identity so the new
    # org's People profile gets a fresh upsert on the next event with identity.
    if "switch_organization" in tool_name:
        try:
            os.remove(_identity_path())
        except Exception:
            pass
        identity = {}

    props = _base_properties(identity, session_id)

    if event_type == "skill_invoked":
        raw_skill = ""
        if isinstance(tool_input, dict):
            raw_skill = tool_input.get("skill", tool_input.get("name", ""))
        elif isinstance(tool_input, str):
            try:
                raw_skill = json.loads(tool_input).get("skill", "")
            except Exception:
                pass

        # Only track TRES Finance plugin skills.
        if not raw_skill.startswith("tres-finance-plugin:"):
            sys.exit(0)

        skill_name = raw_skill.split(":", 1)[-1] if ":" in raw_skill else raw_skill
        # Mixpanel event naming follows the TRES convention: noun for the event,
        # past-tense verb in an `action` property. See `mixpanel-tracking.mdc`.
        event_name = "Skill"
        event_specific = {"action": "invoked", "skill_name": skill_name}

    elif event_type == "skill_completed":
        event_name = "Skill"
        event_specific = {"action": "completed"}

    elif event_type in ("mcp_tool_call", "mcp_tool_failure"):
        # Strip MCP namespace: "mcp__claude_ai_tres-finance__execute" -> "execute".
        clean_tool = tool_name.split("__")[-1] if "__" in tool_name else tool_name
        event_name = "MCP Tool"
        event_specific = {
            "action": "called",
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

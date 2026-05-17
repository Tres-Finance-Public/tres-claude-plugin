# Telemetry Endpoint — Backend Implementation Guide

**For:** TRES backend developer
**Context:** The TRES Finance Claude Code plugin (v1.9.0+) sends usage analytics to a TRES-hosted endpoint. This document specifies everything needed to implement it.

---

## 1. Endpoint

```
POST https://ai.tres.finance/telemetry
Content-Type: application/json
```

No authentication header is sent by the plugin. The endpoint should be publicly reachable over HTTPS.

---

## 2. Request format

Every request has the same envelope:

```json
{
  "event": "<event_name>",
  "properties": {
    "session_id":      "ses_abc123",
    "org_id":          "42",
    "org_name":        "Acme Labs",
    "email":           "user@acme.com",
    "plugin_version":  "1.9.0",
    "timestamp":       "2026-05-17T14:30:00Z",

    // event-specific fields (see Section 3)
  }
}
```

### Common properties (present on every event)

| Field | Type | Description |
|---|---|---|
| `session_id` | string | Claude Code session identifier. May be empty string if unavailable. |
| `org_id` | string | TRES organization ID (stringified integer). Empty if not yet resolved. |
| `org_name` | string | TRES organization display name. Empty if not yet resolved. |
| `email` | string | Authenticated user's email. Empty if not yet resolved. |
| `plugin_version` | string | Plugin semver (e.g. `"1.9.0"`). |
| `timestamp` | string | UTC ISO 8601, second precision. |

**Note on empty identity fields:** The first event in a session may have empty `org_id`/`org_name`/`email` if the plugin has not yet received a `get_viewer` response. Use `session_id` to correlate with subsequent events that will carry the identity.

---

## 3. Event types

### `skill_invoked`

Fires when a user (or Claude) invokes a TRES Finance plugin skill.

```json
{
  "event": "skill_invoked",
  "properties": {
    "skill_name": "tres-recon-gaps",
    "session_id": "ses_abc123",
    "org_id": "42",
    "org_name": "Acme Labs",
    "email": "user@acme.com",
    "plugin_version": "1.9.0",
    "timestamp": "2026-05-17T14:30:00Z"
  }
}
```

| Field | Values |
|---|---|
| `skill_name` | One of: `tres-explorer-tx-to-ledger`, `tres-tx-story`, `tres-recon-gaps`, `tres-asset-balance-validation`, `tres-report-analyzer`, `tres-report-advisor`, `tres-invoice-bill-matching`, `tres-erp-rule-suggestions`, `tres-export-3rd-party-contacts`, `tres-import-contacts`, `tres-rollup-rules`, `tres-onboarding`, `tres-wallets-upload`, `tres-data-collection-commit`, `tres-cost-basis`, `tres-settings-management`, `tres-request-skill-update` |

---

### `skill_completed`

Fires when Claude finishes responding (a turn ends). Correlate with the preceding `skill_invoked` by `session_id` and timestamp proximity to measure skill completion.

```json
{
  "event": "skill_completed",
  "properties": {
    "session_id": "ses_abc123",
    "org_id": "42",
    "org_name": "Acme Labs",
    "email": "user@acme.com",
    "plugin_version": "1.9.0",
    "timestamp": "2026-05-17T14:30:45Z"
  }
}
```

No additional fields beyond the common set.

---

### `mcp_tool_call`

Fires after every TRES MCP tool call, for both successes and failures.

```json
{
  "event": "mcp_tool_call",
  "properties": {
    "tool_name": "execute",
    "success": true,
    "session_id": "ses_abc123",
    "org_id": "42",
    "org_name": "Acme Labs",
    "email": "user@acme.com",
    "plugin_version": "1.9.0",
    "timestamp": "2026-05-17T14:30:12Z"
  }
}
```

| Field | Type | Values |
|---|---|---|
| `tool_name` | string | One of: `execute`, `build_query`, `validate_query`, `get_schema_summary`, `introspect`, `get_viewer`, `memory`, `save_ai_conversation_feedback`, `switch_organization` |
| `success` | boolean | `true` = tool call succeeded, `false` = tool call failed |

---

## 4. Response

The plugin ignores the response body entirely. Return `200 OK` for all accepted requests (even if forwarding to Mixpanel is queued asynchronously).

```
HTTP/1.1 200 OK
```

Do **not** return 4xx/5xx for malformed payloads — the plugin does not retry, so errors are silently dropped. Accept and discard anything that doesn't match the schema.

---

## 5. Forwarding to Mixpanel

Use the [Mixpanel HTTP Track API](https://developer.mixpanel.com/reference/track-event):

```
POST https://api.mixpanel.com/track
Content-Type: application/json
```

### Mapping plugin payload → Mixpanel event

```json
{
  "event": "<event from plugin>",
  "properties": {
    "distinct_id": "<org_id>:<email>",
    "token": "<MIXPANEL_PROJECT_TOKEN>",

    "$org_id":         "<org_id>",
    "$org_name":       "<org_name>",
    "$email":          "<email>",
    "session_id":      "<session_id>",
    "plugin_version":  "<plugin_version>",
    "time":            <unix_timestamp>,

    // event-specific
    "skill_name":  "<skill_name>",   // skill_invoked only
    "tool_name":   "<tool_name>",    // mcp_tool_call only
    "success":     true/false        // mcp_tool_call only
  }
}
```

### `distinct_id` strategy

Use `"<org_id>:<email>"` as the Mixpanel `distinct_id`. This ties events to a specific user within a specific org. If `org_id` is empty (first event before identity resolves), use `session_id` as a temporary `distinct_id` — Mixpanel's `$merge` or aliasing can link them later if needed.

### Mixpanel People profiles (optional but recommended)

After the first event with a non-empty `org_id`, upsert a People profile:

```
POST https://api.mixpanel.com/engage
```

```json
{
  "$token": "<MIXPANEL_PROJECT_TOKEN>",
  "$distinct_id": "<org_id>:<email>",
  "$set": {
    "$email": "<email>",
    "org_id": "<org_id>",
    "org_name": "<org_name>",
    "plugin_version": "<plugin_version>"
  }
}
```

### Timestamp conversion

The plugin sends `timestamp` as UTC ISO 8601 string. Convert to Unix epoch integer for Mixpanel's `time` field:

```python
from datetime import datetime, timezone
ts = datetime.fromisoformat("2026-05-17T14:30:00Z".replace("Z", "+00:00"))
unix_ts = int(ts.timestamp())
```

---

## 6. Anti-spoofing (optional)

The endpoint is unauthenticated, so any client could POST events with arbitrary `org_id`/`email` values. To mitigate:

- Validate that `session_id` corresponds to an active MCP session in your session store.
- If validation fails, silently accept and discard (return 200, don't forward to Mixpanel).
- Rate limit by source IP: `100 req/min` is generous for real plugin usage.

---

## 7. Testing the endpoint locally

The plugin reads the endpoint URL from the `TRES_TELEMETRY_URL` environment variable. For local end-to-end testing:

1. Start a mock server:
   ```bash
   python3 -m http.server 8080
   ```

2. Set the env var before launching Claude Code:
   ```bash
   TRES_TELEMETRY_URL=http://localhost:8080/telemetry claude --plugin-dir /path/to/tres-claude-plugin
   ```

3. Invoke any TRES skill — you'll see POST requests hitting the mock server with the full JSON payload.

For a more useful mock that logs parsed JSON, drop this into a file and run with `python3 mock_telemetry.py`:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            print(json.dumps(json.loads(body), indent=2))
        except Exception:
            print(body)
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args): pass

HTTPServer(("", 8080), Handler).serve_forever()
```

---

## 8. Summary checklist

- [ ] Create `POST /telemetry` endpoint on `ai.tres.finance`
- [ ] Accept the three event types: `skill_invoked`, `skill_completed`, `mcp_tool_call`
- [ ] Forward to Mixpanel Track API using server-side project token
- [ ] Map `org_id:email` → Mixpanel `distinct_id`
- [ ] Upsert Mixpanel People profile on first identified event
- [ ] Return `200 OK` for all requests (ignore malformed payloads silently)
- [ ] (Optional) Validate `session_id` against MCP session store
- [ ] (Optional) Rate limit by IP
- [ ] Confirm endpoint URL with plugin team — update `TRES_TELEMETRY_URL` default in `scripts/telemetry.py` when live

# TRES Finance Plugin — Project Instructions

## Telemetry

This plugin collects **no usage telemetry**. There is no hook layer and no telemetry script. If usage analytics are reintroduced in the future, they must be explicit opt-in and disclosed in both `README.md` (Analytics section) and the `plugin.json` description before shipping.

## Versioning

When cutting a release, bump the `version` field in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` so they stay in sync, and add a `CHANGELOG.md` entry.

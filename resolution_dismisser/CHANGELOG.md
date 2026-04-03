# Changelog

## 1.2.0

- Replace free-text arrays with toggle switches for all known issues, suggestions, and repairs
- Add English translations for friendly labels in the UI
- Keep custom free-text fields for unlisted items
- Fix `repairs/ignore_issue` API call (requires `ignore: true` parameter)
- Fix word-based matching for repair IDs (e.g. `unsupported_os` matches `unsupported_system_os`)
- Fix indentation bug in dismiss_repairs.py
- Empty defaults — nothing dismissed until user enables toggles

## 1.1.0

- Add HA Core repair dismissal via WebSocket API
- Enable `homeassistant_api` for HA Core access
- Debug logging shows all discovered HA repairs

## 1.0.0

- Initial release
- Auto-dismiss configurable issue types from the Resolution Center
- Auto-dismiss configurable suggestion types from the Resolution Center
- Configurable polling interval (30s–86400s)
- Configurable log levels (debug/info/warning/error)

# Changelog

## 1.3.1

- Remove GHCR image field (packages were private, preventing container start)
- Fall back to local builds until GHCR visibility is resolved

## 1.3.0

- Rewrite repair dismissal: REST API for listing (auth handled by Supervisor proxy), WebSocket for ignoring
- Multiple auth strategies: HTTP header auto-auth, fallback to token-based WS auth
- Full WebSocket fallback if REST listing unavailable
- Better error messages for auth failures

## 1.2.1

- Fix WebSocket auth: pass token as HTTP header for Supervisor proxy compatibility
- Handle both proxy auto-auth and manual auth flows

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

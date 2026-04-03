# Home Assistant Add-on: Resolution Dismisser

Automatically dismisses Home Assistant resolution warnings and repair notifications that keep coming back.

## How to use

1. Install and start the add-on
2. Go to the **Configuration** tab
3. Enable the toggle switches for warnings you want auto-dismissed
4. Hit **Save** and **Restart**

Set **log level** to `debug` to see all active issues, suggestions, and repairs in the Log tab.

## Configuration

All options are toggle switches — flip on what you want dismissed.

### General
- **Check interval** — How often (in seconds) to check. Default: `300` (5 min). Min: `30`.
- **Log level** — Set to `debug` to see all discovered items.

### Issues (Supervisor Resolution Center)
Toggle switches for common Supervisor issues like missing backups, DNS failures, low disk space, etc.

### Suggestions (Supervisor Resolution Center)
Toggle switches for common Supervisor suggestions like "create full backup" or "execute update".

### Repairs (HA Core)
Toggle switches for HA Core repair notifications like "Unsupported system - Operating System" or "Unsupported system - Software".

### Custom fields
Free-text lists at the bottom for any issue/suggestion/repair not covered by the toggles. Use `debug` log level to find the exact IDs.

## Support

Open an issue on [GitHub](https://github.com/RENOxDECEPTION/ha-resolution-dismisser/issues).

# Resolution Dismisser

Vibe-coded add-on that auto-dismisses HA warnings you can't permanently disable. If it gets attention I'll polish it up, but it does the job.

## The Problem

HA Supervised on Debian/etc constantly flags your system as "unsupported" (OS, software, job conditions). These generate **issues**, **suggestions**, and **repair notifications** that reappear every healthcheck cycle. There's no built-in way to permanently shut them up.

## The Solution

This add-on polls two APIs on a loop and dismisses everything you tell it to:

- **Supervisor REST API** — `DELETE /resolution/issue/{uuid}` and `DELETE /resolution/suggestion/{uuid}` for resolution center items
- **HA Core WebSocket API** — `repairs/ignore_issue` for repair notifications (like "Unsupported system - Operating System")

## Configuration

Go to the **Configuration** tab. You'll see toggle switches for every known issue, suggestion, and repair. Flip on whatever you want auto-dismissed.

**The two things most Supervised users want:**
1. **Repair: Unsupported OS** — kills the persistent "Unsupported system - Operating System" notification
2. **Repair: Unsupported software** — kills the "Unsupported system - Software" notification

There are also free-text fields at the bottom for anything not in the predefined list. Set **log level** to `debug` to see all discoverable items.

## Installation

1. Go to **Settings → Apps → App Store**
2. Click **⋮** (top right) → **Repositories**
3. Add: `https://github.com/RENOxDECEPTION/ha-resolution-dismisser`
4. Click **Close**, then find **Resolution Dismisser** in the store
5. Click **Install App**
6. Go to the **Configuration** tab, enable the toggles you want, and hit **Start**

## License

MIT

# Resolution Dismisser

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FRENOxDECEPTION%2Fha-resolution-dismisser)

![Supports amd64 Architecture][amd64-shield]
![Supports aarch64 Architecture][aarch64-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]
[![License: MIT][license-shield]](resolution_dismisser/LICENSE)

Home Assistant add-on that auto-dismisses HA warnings you can't permanently disable: "unsupported system" repairs, resolution center issues, and suggestions on Supervised installs.

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

[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
[license-shield]: https://img.shields.io/badge/license-MIT-blue.svg

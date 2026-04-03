#!/usr/bin/env python3
"""Dismiss HA Core repairs via WebSocket API.

Usage: dismiss_repairs.py <pattern1> [pattern2] ...

Connects to HA Core websocket, lists repair issues, and dismisses
(ignores) any whose issue_id matches a provided pattern.
Outputs JSON with results.
"""
import json
import os
import sys
import time

try:
    import websocket
except ImportError:
    print(json.dumps({"error": "websocket-client not installed"}))
    sys.exit(1)

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
WS_URLS = [
    "ws://supervisor/core/websocket",
    "ws://homeassistant:8123/api/websocket",
]


def recv_by_id(ws, msg_id, timeout=30):
    """Receive messages until we get one matching our msg_id, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            msg = json.loads(ws.recv())
        except Exception:
            break
        if msg.get("id") == msg_id:
            return msg
    return None


def try_connect():
    """Try connecting to HA websocket via known URLs."""
    headers = ["Authorization: Bearer " + SUPERVISOR_TOKEN] if SUPERVISOR_TOKEN else []
    for url in WS_URLS:
        try:
            return websocket.create_connection(url, timeout=10, header=headers)
        except Exception:
            continue
    return None


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"listed": 0, "all_repairs": [], "dismissed": [], "errors": ["No patterns provided"]}))
        sys.exit(1)

    patterns = sys.argv[1:]
    results = {"listed": 0, "all_repairs": [], "dismissed": [], "errors": []}

    ws = try_connect()
    if not ws:
        results["errors"].append("Could not connect to HA websocket")
        print(json.dumps(results))
        sys.exit(1)

    try:
        # Wait for initial message
        msg = json.loads(ws.recv())

        if msg.get("type") == "auth_ok":
            # Proxy already authenticated us via HTTP header
            pass
        elif msg.get("type") == "auth_required":
            # Authenticate via WebSocket message
            ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
            msg = json.loads(ws.recv())
            if msg.get("type") != "auth_ok":
                results["errors"].append("Auth failed: " + msg.get("message", "unknown"))
                print(json.dumps(results))
                return
        else:
            results["errors"].append("Unexpected initial message type: " + msg.get("type", "unknown"))
            print(json.dumps(results))
            return

        # List repair issues
        ws.send(json.dumps({"id": 1, "type": "repairs/list_issues"}))
        msg = recv_by_id(ws, 1)
        if not msg or not msg.get("success"):
            err = ""
            if msg:
                err = msg.get("error", {}).get("message", "unknown")
            results["errors"].append("Failed to list repairs: " + err)
            print(json.dumps(results))
            return

        issues = msg.get("result", {}).get("issues", [])
        results["listed"] = len(issues)
        results["all_repairs"] = [
            {"domain": i.get("domain"), "issue_id": i.get("issue_id"), "dismissed": i.get("dismissed_version") is not None}
            for i in issues
        ]

        msg_id = 2
        for issue in issues:
            issue_id = issue.get("issue_id", "")
            domain = issue.get("domain", "")
            dismissed_version = issue.get("dismissed_version")
            full_id = domain + "." + issue_id

            # Check if this issue matches any pattern
            # Supports exact issue_id match or exact domain.issue_id match
            matched = False
            for pattern in patterns:
                pattern = pattern.strip()
                if issue_id == pattern or full_id == pattern:
                    matched = True
                    break
                # Substring match only if the pattern is long enough to be specific
                if len(pattern) > 5 and (pattern in issue_id or pattern in full_id):
                    matched = True
                    break

            if not matched:
                continue

            # Skip if already dismissed
            if dismissed_version:
                continue

            # Dismiss this repair
            ws.send(json.dumps({
                "id": msg_id,
                "type": "repairs/ignore_issue",
                "domain": domain,
                "issue_id": issue_id,
                "ignore": True,
            }))
            resp = recv_by_id(ws, msg_id)
            success = resp.get("success", False) if resp else False
            results["dismissed"].append({
                "domain": domain,
                "issue_id": issue_id,
                "success": success,
            })
            if not success:
                err_msg = ""
                if resp:
                    err_msg = resp.get("error", {}).get("message", "unknown")
                results["errors"].append(
                    "Failed: " + domain + "." + issue_id + ": " + err_msg
                )
            msg_id += 1

    except Exception as e:
        results["errors"].append(str(e))
    finally:
        try:
            ws.close()
        except Exception:
            pass

    print(json.dumps(results))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Dismiss HA Core repairs via WebSocket API.

Usage: dismiss_repairs.py <pattern1> [pattern2] ...

The HA Core repairs API (list + ignore) is WebSocket-only.
Connects via Supervisor proxy, lists repairs, and dismisses matching ones.
Outputs JSON with results.
"""
import json
import os
import sys
import time

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

# Transient "core still starting" condition: reported as info, not an error.
NOT_READY_MSG = "Core websocket not ready, will retry next interval"


# --------------------------------------------------------------------------
# WebSocket helpers
# --------------------------------------------------------------------------
def ws_connect():
    """Connect to HA Core websocket via the Supervisor proxy, retrying while core starts."""
    try:
        import websocket
    except ImportError:
        return None, "websocket-client not installed"

    if not SUPERVISOR_TOKEN:
        return None, "SUPERVISOR_TOKEN not set"

    # Only the Supervisor proxy accepts SUPERVISOR_TOKEN. Core's native
    # /api/websocket rejects it (auth_invalid) and trips HA's http.ban logger,
    # so there is no valid fallback URL.
    url = "ws://supervisor/core/websocket"
    headers = ["Authorization: Bearer " + SUPERVISOR_TOKEN]

    # ponytail: fixed backoff covers the core-startup window; the add-on's
    # main loop retries every check_interval anyway
    for delay in (0, 5, 10, 30):
        if delay:
            time.sleep(delay)
        try:
            ws = websocket.create_connection(url, timeout=10, header=headers)
        except Exception:
            continue
        try:
            msg = json.loads(ws.recv())
            if msg.get("type") == "auth_ok":
                return ws, None
            if msg.get("type") == "auth_required":
                ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
                msg = json.loads(ws.recv())
                if msg.get("type") == "auth_ok":
                    return ws, None
                ws.close()
                return None, "Auth failed: " + msg.get("message", "unknown")
            ws.close()
        except Exception:
            try:
                ws.close()
            except Exception:
                pass
            continue
    return None, NOT_READY_MSG


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


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(json.dumps({"listed": 0, "all_repairs": [], "dismissed": [], "errors": ["No patterns provided"]}))
        sys.exit(1)

    patterns = sys.argv[1:]
    results = {"listed": 0, "all_repairs": [], "dismissed": [], "errors": [], "info": []}

    # --- Step 1: Connect to HA Core WebSocket ---
    ws, ws_err = ws_connect()
    if not ws:
        key = "info" if ws_err == NOT_READY_MSG else "errors"
        results[key].append(ws_err or "Could not connect")
        print(json.dumps(results))
        return

    try:
        msg_id = 1

        # --- Step 2: List repairs via WS ---
        ws.send(json.dumps({"id": msg_id, "type": "repairs/list_issues"}))
        msg = recv_by_id(ws, msg_id)
        msg_id += 1

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
            {"domain": i.get("domain"), "issue_id": i.get("issue_id"),
             "dismissed": i.get("dismissed_version") is not None}
            for i in issues
        ]

        # --- Step 3: Find matching repairs to dismiss ---
        to_dismiss = []
        for issue in issues:
            issue_id = issue.get("issue_id", "")
            domain = issue.get("domain", "")
            dismissed_version = issue.get("dismissed_version")
            full_id = domain + "." + issue_id

            if dismissed_version:
                continue

            matched = False
            for pattern in patterns:
                pattern = pattern.strip()
                if issue_id == pattern or full_id == pattern:
                    matched = True
                    break
                if len(pattern) > 5 and (pattern in issue_id or pattern in full_id):
                    matched = True
                    break
            if matched:
                to_dismiss.append(issue)

        if not to_dismiss:
            print(json.dumps(results))
            return

        # --- Step 4: Dismiss matching repairs via WS ---
        for issue in to_dismiss:
            domain = issue.get("domain", "")
            issue_id = issue.get("issue_id", "")

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
                results["errors"].append("Failed: %s.%s: %s" % (domain, issue_id, err_msg))
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

#!/usr/bin/env python3
"""Dismiss HA Core repairs via Supervisor REST proxy + WebSocket fallback.

Usage: dismiss_repairs.py <pattern1> [pattern2] ...

Lists repair issues via the Supervisor REST API proxy (which handles
HA Core auth automatically), then dismisses matching repairs via WebSocket.
Outputs JSON with results.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
CORE_API = "http://supervisor/core"


# --------------------------------------------------------------------------
# REST helpers (through Supervisor proxy — auth handled automatically)
# --------------------------------------------------------------------------
def rest_get(path):
    """GET from HA Core REST API via Supervisor proxy."""
    req = urllib.request.Request(CORE_API + path)
    req.add_header("Authorization", "Bearer " + SUPERVISOR_TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        return {"error": str(e), "body": body}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


# --------------------------------------------------------------------------
# WebSocket helpers
# --------------------------------------------------------------------------
def ws_connect():
    """Try connecting to HA Core websocket via Supervisor proxy."""
    try:
        import websocket
    except ImportError:
        return None, "websocket-client not installed"

    urls = [
        "ws://supervisor/core/websocket",
        "ws://homeassistant:8123/api/websocket",
    ]
    headers = ["Authorization: Bearer " + SUPERVISOR_TOKEN] if SUPERVISOR_TOKEN else []

    for url in urls:
        try:
            ws = websocket.create_connection(url, timeout=10, header=headers)
            # Handle auth handshake
            msg = json.loads(ws.recv())
            if msg.get("type") == "auth_ok":
                return ws, None
            if msg.get("type") == "auth_required":
                ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
                msg = json.loads(ws.recv())
                if msg.get("type") == "auth_ok":
                    return ws, None
                ws.close()
                # Don't try next URL with same token, it'll fail too
                return None, "Auth failed: " + msg.get("message", "unknown")
            ws.close()
        except Exception:
            continue
    return None, "Could not connect to HA websocket"


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
    results = {"listed": 0, "all_repairs": [], "dismissed": [], "errors": []}

    # --- Step 1: List repairs via REST (reliable, proxy handles auth) ---
    data, status = rest_get("/api/repairs/issues")
    issues = []
    if status == 200:
        # REST response: {"issues": [...]}  or just [...]
        if isinstance(data, dict):
            issues = data.get("issues", data.get("data", {}).get("issues", []))
        elif isinstance(data, list):
            issues = data
    else:
        # REST listing not available, fall back to WebSocket for everything
        results["errors"].append("REST repair listing unavailable (HTTP %d), trying WebSocket" % status)
        return ws_only_fallback(patterns, results)

    results["listed"] = len(issues)
    results["all_repairs"] = [
        {"domain": i.get("domain"), "issue_id": i.get("issue_id"),
         "dismissed": i.get("dismissed_version") is not None}
        for i in issues
    ]

    # --- Step 2: Find matching repairs to dismiss ---
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

    # --- Step 3: Dismiss via WebSocket (repairs/ignore_issue is WS-only) ---
    ws, ws_err = ws_connect()
    if not ws:
        results["errors"].append("Cannot dismiss repairs: " + (ws_err or "WS unavailable"))
        print(json.dumps(results))
        return

    try:
        msg_id = 1
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


def ws_only_fallback(patterns, results):
    """Full WebSocket fallback when REST is unavailable."""
    ws, ws_err = ws_connect()
    if not ws:
        results["errors"].append(ws_err or "Could not connect")
        print(json.dumps(results))
        return

    try:
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
            {"domain": i.get("domain"), "issue_id": i.get("issue_id"),
             "dismissed": i.get("dismissed_version") is not None}
            for i in issues
        ]

        msg_id = 2
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
            if not matched:
                continue

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

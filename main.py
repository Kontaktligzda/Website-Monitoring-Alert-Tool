#!/usr/bin/env python3
"""
Website Monitoring & Alert Tool
- Checks uptime, response time, and content changes
- Sends alerts via Discord webhook or email (optional)
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Dict

import requests

STATE_FILE = "state.json"


def load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: Dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def send_discord(webhook_url: str, message: str) -> None:
    payload = {"content": message}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception:
        pass


def check_site(url: str, timeout: int = 10) -> Dict:
    start = time.time()
    resp = requests.get(url, timeout=timeout)
    elapsed = round(time.time() - start, 3)
    content_hash = hash_content(resp.text)
    return {
        "status_code": resp.status_code,
        "response_time": elapsed,
        "content_hash": content_hash,
    }


def main():
    parser = argparse.ArgumentParser(description="Monitor a website for uptime and content changes")
    parser.add_argument("url", help="Website URL to monitor")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    parser.add_argument("--discord-webhook", help="Discord webhook URL for alerts")
    parser.add_argument("--max-response-time", type=float, default=3.0, help="Alert if response time exceeds this (seconds)")
    args = parser.parse_args()

    state = load_state()
    url_state = state.get(args.url, {})

    print(f"Monitoring {args.url} every {args.interval}s. Press Ctrl+C to stop.")

    while True:
        try:
            result = check_site(args.url)
            now = datetime.utcnow().isoformat() + "Z"

            alerts = []

            # Uptime check
            if result["status_code"] >= 400:
                alerts.append(f"🚨 {args.url} returned status {result['status_code']}")

            # Response time check
            if result["response_time"] > args.max_response_time:
                alerts.append(
                    f"⚠️ Slow response: {result['response_time']}s (> {args.max_response_time}s)"
                )

            # Content change check
            if url_state.get("content_hash") and url_state.get("content_hash") != result["content_hash"]:
                alerts.append("🔄 Website content changed")

            # Save latest state
            url_state = {
                "last_checked": now,
                "status_code": result["status_code"],
                "response_time": result["response_time"],
                "content_hash": result["content_hash"],
            }
            state[args.url] = url_state
            save_state(state)

            log_line = f"[{now}] {args.url} | {result['status_code']} | {result['response_time']}s"
            print(log_line)

            if alerts and args.discord_webhook:
                message = "\n".join(alerts)
                send_discord(args.discord_webhook, message)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()

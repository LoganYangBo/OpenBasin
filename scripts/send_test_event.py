"""Send a test signal to a running OpenBasin server — stands in for the phone.

Reads config.yaml, encrypts a payload with the first device's AES key exactly as
the Android agent would, and POSTs it to /v1/events. Use it to exercise the full
pipeline end-to-end without a real device.

Usage:
    python scripts/send_test_event.py                       # default SMS sample
    python scripts/send_test_event.py --type sms --body "Chase charged $42 at Cafe"
    python scripts/send_test_event.py --url http://localhost:8080
"""

from __future__ import annotations

import argparse
import sys

import httpx

from server.config import load_config
from server.transport import encrypt_envelope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--url", default="")
    parser.add_argument("--type", default="sms", choices=["sms", "email", "notification"])
    parser.add_argument("--body", default="Your Chase card ending 6688 was charged $128.50 "
                                          "at Whole Foods on 06/02.")
    parser.add_argument("--sender", default="Chase")
    parser.add_argument("--source-app", default="")
    parser.add_argument("--subject", default="")  # email only
    args = parser.parse_args()

    config = load_config(args.config)
    if not config.devices:
        print("No devices in config.yaml — add one under devices: first.", file=sys.stderr)
        return 1
    device = config.devices[0]
    url = (args.url or f"http://localhost:{config.server.port}").rstrip("/")

    payload = {"signal_type": args.type, "sender": args.sender}
    if args.type == "sms":
        payload["body"] = args.body
    elif args.type == "email":
        payload["body"] = args.body
        payload["subject"] = args.subject or "Receipt"
    else:  # notification
        payload["title"] = args.sender
        payload["text"] = args.body
    if args.source_app:
        payload["source_app"] = args.source_app

    envelope = encrypt_envelope(payload, device.aes_key, device.device_id)
    resp = httpx.post(
        f"{url}/v1/events",
        json=envelope,
        headers={"X-Device-Token": device.token},
        timeout=120,  # extraction may call your LLM
    )
    print(f"HTTP {resp.status_code}")
    print(resp.json())
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())

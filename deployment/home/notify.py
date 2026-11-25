import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


ALLOWED_SERVICES = (
    "progress-tracker-update.service",
    "progress-tracker-backup.service",
    "test",
)

COOLDOWN_SECONDS = 3600


def send_notification(service):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        raise RuntimeError("Telegram notification configuration is missing.")

    state_directory = (
        Path.home() / ".local/state/progress-tracker/notifications"
    )
    state_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_file = state_directory / service

    if service != "test" and state_file.exists():
        elapsed = time.time() - state_file.stat().st_mtime
        if 0 <= elapsed < COOLDOWN_SECONDS:
            print("Repeated alert suppressed during the one-hour cooldown.")
            return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    server = socket.gethostname()

    if service == "test":
        message = (
            "Progress Tracker: test notification\n"
            f"Server: {server}\n"
            f"Time: {timestamp}\n"
            "Telegram alerts are connected."
        )
    else:
        message = (
            "Progress Tracker: service failed\n"
            f"Server: {server}\n"
            f"Service: {service}\n"
            f"Time: {timestamp}\n\n"
            "Check the server logs:\n"
            f"sudo journalctl -u {service} -n 50 --no-pager"
        )

    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id,
            "text": message,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except (URLError, OSError, ValueError):
        raise RuntimeError(
            "Telegram delivery failed. Check connectivity and credentials."
        ) from None

    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError("Telegram did not confirm message delivery.")

    # Record only confirmed deliveries so a failed send can be retried.
    state_file.touch(mode=0o600)
    print("Telegram notification delivered.")


def main():
    parser = argparse.ArgumentParser(
        description="Send a Progress Tracker service alert."
    )
    parser.add_argument("service", choices=ALLOWED_SERVICES)
    arguments = parser.parse_args()

    try:
        send_notification(arguments.service)
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
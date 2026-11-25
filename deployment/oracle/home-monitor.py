import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import socket
import tempfile
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BASE = Path.home()
CONFIG = BASE / ".config/home-monitor/notifications.env"
STATE_DIRECTORY = BASE / ".local/state/home-monitor"
STATE_FILE = STATE_DIRECTORY / "status.json"
FAILURE_THRESHOLD = 3

TARGETS = {
    "home_ssh": "Home server SSH over Tailscale",
    "tracker": "Progress Tracker readiness",
}


def send_message(text):
    config = {}
    for line in CONFIG.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()

    token = config.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = config.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        raise RuntimeError("Telegram configuration is missing.")

    timestamp = datetime.now(
        ZoneInfo("Asia/Jerusalem")
    ).strftime("%Y-%m-%d %H:%M %Z")

    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id,
            "text": f"{text}\nObserver: Oracle VM\nTime: {timestamp}",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise ValueError
    except (URLError, OSError, ValueError):
        raise RuntimeError("Telegram delivery failed.") from None


def probe(target):
    try:
        if target == "home_ssh":
            with socket.create_connection(("100.64.0.1", 22), timeout=5):
                return True

        if target == "tracker":
            with urlopen(
                "http://100.64.0.1:18743/health/ready/",
                timeout=5,
            ) as response:
                return (
                    response.status == 200
                    and json.load(response) == {"status": "ready"}
                )

        raise ValueError("Unknown monitor target.")
    except (OSError, URLError, ValueError):
        return False


def process_result(key, healthy, previous, sender):
    failures = 0 if healthy else previous.get("failures", 0) + 1
    notified_down = previous.get("notified_down", False)
    delivery_failed = False

    text = None
    if not healthy and failures >= FAILURE_THRESHOLD and not notified_down:
        text = (
            f"🔴 {TARGETS[key]} unreachable from Oracle\n"
            f"Failed checks: {failures}\n"
            "This can indicate a service, network, or Tailscale problem."
        )
    elif healthy and notified_down:
        text = f"✅ {TARGETS[key]} recovered\nThe check is responding again."

    if text:
        try:
            sender(text)
            notified_down = not healthy
        except RuntimeError:
            # Retain the notification state so the next run retries delivery.
            delivery_failed = True

    return {
        "failures": failures,
        "notified_down": notified_down,
    }, delivery_failed


def save_state(state):
    fd, temporary = tempfile.mkstemp(
        prefix=".status-",
        dir=STATE_DIRECTORY,
    )
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(state, file)
            file.write("\n")
        os.replace(temporary, STATE_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    STATE_DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)

    with (STATE_DIRECTORY / "monitor.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0

        if args.test:
            send_message("🧪 External home monitor: test notification")
            print("Test notification delivered.")
            return 0

        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            if not isinstance(state, dict):
                raise ValueError("Invalid monitor state.")
        else:
            state = {}

        delivery_failed = False

        for key, name in TARGETS.items():
            healthy = probe(key)
            state[key], failed = process_result(
                key, healthy, state.get(key, {}), send_message
            )
            delivery_failed = delivery_failed or failed
            print(
                f"{name}: {'UP' if healthy else 'DOWN'} "
                f"(consecutive failures: {state[key]['failures']})"
            )

        save_state(state)

        if delivery_failed:
            print("An alert could not be delivered; next run will retry.")
            return 1

        return 0


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, TypeError):
        print("Monitor failed. Check configuration, state, and connectivity.")
        raise SystemExit(1) from None

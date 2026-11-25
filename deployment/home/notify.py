import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ALLOWED_SERVICES = (
    "progress-tracker-update.service",
    "progress-tracker-backup.service",
    "test",
    "progress-tracker-backup-upload.service",
)

COOLDOWN_SECONDS = 3600

STAGE_LABELS = {
    "configuration": "Loading configuration",
    "image_download": "Downloading the new image",
    "image_inspection": "Checking the image and current container",
    "backup": "Creating the pre-update backup",
    "compose_validation": "Validating deployment configuration",
    "database_migration": "Applying database migrations",
    "catalog_import": "Refreshing the exercise catalog",
    "application_startup": "Starting the new application",
    "readiness_check": "Checking application readiness",
    "saving_release": "Saving the deployed release",
    "completed": "Completing the update",
}


def update_details():
    directory = Path.home() / ".local/state/progress-tracker"
    paused = (directory / "update-blocked").exists()
    details = []

    try:
        payload = json.loads(
            (directory / "update-status.json").read_text()
        )
    except (OSError, ValueError):
        payload = {}

    # Never report a previous successful check as the current failure.
    if isinstance(payload, dict) and payload.get("result") == "failed":
        stage = STAGE_LABELS.get(payload.get("stage"), "Unknown stage")
        details.append(f"Stage: {stage}")

        exit_code = payload.get("exit_code")
        if type(exit_code) is int:
            details.append(f"Exit code: {exit_code}")

        backup = {
            "not_started": "Not started",
            "in_progress": "Did not complete",
            "completed": "Completed",
        }.get(payload.get("backup"), "Unknown")

        details.append(f"Pre-update backup: {backup}")

        try:
            failed_at = datetime.fromisoformat(payload["timestamp"])
            if failed_at.tzinfo is not None:
                local_time = failed_at.astimezone(
                    ZoneInfo("Asia/Jerusalem")
                )
                details.append(
                    "Failure recorded: "
                    + local_time.strftime("%Y-%m-%d %H:%M %Z")
                )
        except (KeyError, ValueError, TypeError):
            pass
    else:
        details.append(
            "Stage: unavailable; inspect the systemd service logs."
        )

    details.append(
        "Automatic updates: "
        + ("Paused - inspection required" if paused else "Not paused")
    )

    return "\n".join(details)


def build_message(service):
    timestamp = datetime.now(
        ZoneInfo("Asia/Jerusalem")
    ).strftime("%Y-%m-%d %H:%M %Z")
    server = socket.gethostname()

    if service == "test":
        return (
            "Progress Tracker: test notification\n"
            f"Server: {server}\n"
            f"Time: {timestamp}\n"
            "Telegram alerts are connected."
        )

    if service == "progress-tracker-update.service":
        title = "⚠️ Progress Tracker update failed"
        details = update_details()
    elif service == "progress-tracker-backup-upload.service":
        title = "⚠️ Progress Tracker off-server backup upload failed"
        details = (
            "The encrypted backup transfer to Oracle did not complete.\n"
            "Local backups were not deleted.\n"
            "The next scheduled transfer will retry."
        )
    else:
        title = "⚠️ Progress Tracker scheduled backup failed"
        details = (
            "A fresh scheduled backup was not confirmed.\n"
            "Check the logs before relying on the latest backup.\n"
            "The application may still be running normally."
        )

    return (
        f"{title}\n"
        f"Server: {server}\n"
        f"Service: {service}\n"
        f"Alert time: {timestamp}\n\n"
        f"{details}\n\n"
        "Inspect logs:\n"
        f"sudo journalctl -u {service} -n 50 --no-pager"
    )


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

    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({
            "chat_id": chat_id,
            "text": build_message(service),
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
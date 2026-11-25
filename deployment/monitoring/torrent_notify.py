import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("event", choices=("added", "finished", "test"))
    parser.add_argument("name")
    args = parser.parse_args()

    config_path = Path(__file__).with_name("telegram.env")

    try:
        config = {}
        for line in config_path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

        token = config["TELEGRAM_BOT_TOKEN"]
        chat_id = config["TELEGRAM_CHAT_ID"]

        if not token or not chat_id:
            raise ValueError
    except (OSError, KeyError, ValueError):
        print("Telegram configuration is missing or invalid.", file=sys.stderr)
        return 1

    titles = {
        "added": "📥 Torrent added",
        "finished": "✅ Torrent download completed",
        "test": "🧪 qBittorrent notification test",
    }

    # Plain text only; no Telegram HTML or Markdown parsing.
    name = " ".join(args.name.split())[:500]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    message = (
        f"{titles[args.event]}\n"
        f"Name: {name}\n"
        "Service: qBittorrent on oriserver\n"
        f"Time: {timestamp}"
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
            result = json.load(response)

        if not isinstance(result, dict) or not result.get("ok"):
            raise ValueError
    except (URLError, OSError, ValueError):
        print("Telegram notification delivery failed.", file=sys.stderr)
        return 1

    print("Telegram notification delivered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

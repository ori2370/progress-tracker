import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "home_notify",
    ROOT / "deployment/home/notify.py",
)
notify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notify)

SERVICE = "progress-tracker-update.service"


class NotificationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)

        home_patch = patch.object(
            notify.Path,
            "home",
            return_value=self.home,
        )
        home_patch.start()
        self.addCleanup(home_patch.stop)

        env_patch = patch.dict(
            notify.os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123:fake-token",
                "TELEGRAM_CHAT_ID": "456",
            },
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def marker(self, service=SERVICE):
        return (
            self.home
            / ".local/state/progress-tracker/notifications"
            / service
        )

    @patch.object(notify, "urlopen")
    def test_missing_credentials_do_not_contact_telegram(self, mock_open):
        with patch.dict(
            notify.os.environ,
            {"TELEGRAM_BOT_TOKEN": ""},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "configuration is missing",
            ):
                notify.send_notification(SERVICE)

        mock_open.assert_not_called()

    @patch.object(notify, "urlopen")
    def test_success_sends_only_operational_details(self, mock_open):
        mock_open.return_value = io.BytesIO(
            json.dumps({"ok": True}).encode()
        )

        notify.send_notification(SERVICE)

        request = mock_open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["chat_id"], "456")
        self.assertIn(SERVICE, payload["text"])
        self.assertNotIn("fake-token", payload["text"])
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(self.marker().exists())

    @patch.object(notify, "urlopen")
    def test_recent_delivery_suppresses_repeated_alert(self, mock_open):
        self.marker().parent.mkdir(parents=True)
        self.marker().touch()

        notify.send_notification(SERVICE)

        mock_open.assert_not_called()

    @patch.object(notify, "urlopen")
    def test_failed_delivery_does_not_start_cooldown(self, mock_open):
        mock_open.side_effect = URLError("Connection unavailable")

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            notify.send_notification(SERVICE)

        self.assertFalse(self.marker().exists())

    @patch.object(notify, "urlopen")
    def test_rejected_response_does_not_start_cooldown(self, mock_open):
        mock_open.return_value = io.BytesIO(
            json.dumps({"ok": False}).encode()
        )

        with self.assertRaisesRegex(RuntimeError, "did not confirm"):
            notify.send_notification(SERVICE)

        self.assertFalse(self.marker().exists())

    @patch.object(notify, "urlopen")
    def test_manual_test_bypasses_cooldown(self, mock_open):
        self.marker("test").parent.mkdir(parents=True)
        self.marker("test").touch()
        mock_open.return_value = io.BytesIO(
            json.dumps({"ok": True}).encode()
        )

        notify.send_notification("test")

        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
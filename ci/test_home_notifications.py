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

    def test_update_message_includes_failure_details(self):
        directory = self.home / ".local/state/progress-tracker"
        directory.mkdir(parents=True)

        (directory / "update-status.json").write_text(json.dumps({
            "stage": "database_migration",
            "backup": "completed",
            "result": "failed",
            "exit_code": 1,
            "timestamp": "2026-11-25T15:00:00+00:00",
        }))
        (directory / "update-blocked").touch()

        message = notify.build_message(SERVICE)

        self.assertIn("Stage: Applying database migrations", message)
        self.assertIn("Exit code: 1", message)
        self.assertIn("Pre-update backup: Completed", message)
        self.assertIn("Automatic updates: Paused", message)
        self.assertIn("2026-11-25 17:00", message)

    def test_successful_status_is_not_presented_as_failure_details(self):
        directory = self.home / ".local/state/progress-tracker"
        directory.mkdir(parents=True)

        (directory / "update-status.json").write_text(json.dumps({
            "stage": "completed",
            "backup": "completed",
            "result": "deployed",
            "exit_code": 0,
        }))

        message = notify.build_message(SERVICE)

        self.assertIn("Stage: unavailable", message)
        self.assertNotIn("Pre-update backup: Completed", message)

    def test_backup_alert_has_separate_wording(self):
        message = notify.build_message(
            "progress-tracker-backup.service"
        )

        self.assertIn("scheduled backup failed", message)
        self.assertNotIn("Pre-update backup:", message)
        self.assertNotIn("Automatic updates:", message)

    def test_malformed_status_still_produces_an_alert(self):
        directory = self.home / ".local/state/progress-tracker"
        directory.mkdir(parents=True)
        (directory / "update-status.json").write_text("invalid JSON")

        message = notify.build_message(SERVICE)

        self.assertIn("Stage: unavailable", message)
        self.assertIn("Inspect logs:", message)

    def test_upload_failure_alert_has_separate_wording(self):
        message = notify.build_message(
            "progress-tracker-backup-upload.service"
        )

        self.assertIn("off-server backup upload failed", message)
        self.assertIn("Local backups were not deleted", message)
        self.assertIn("next scheduled transfer will retry", message)
        self.assertNotIn("Automatic updates:", message)


if __name__ == "__main__":
    unittest.main()
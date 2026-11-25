import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BackupUploadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.directory = Path(temporary.name)
        self.home = self.directory / "home"
        self.backups = self.home / ".local/share/progress-tracker/backups"
        self.config = self.home / ".config/progress-tracker"
        self.bin = self.directory / "bin"
        self.log = self.directory / "rsync-arguments.json"

        self.backups.mkdir(parents=True)
        self.config.mkdir(parents=True)
        self.bin.mkdir()

        (self.config / "oracle-backup-key").write_text("fake test key")
        (self.backups / "database-test.dump.age").write_text(
            "fake encrypted backup"
        )

        fake_rsync = self.bin / "rsync"
        fake_rsync.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            'Path(os.environ["TEST_RSYNC_LOG"]).write_text('
            "json.dumps(sys.argv[1:]))\n"
            'sys.exit(int(os.environ.get("TEST_RSYNC_EXIT", "0")))\n'
        )
        fake_rsync.chmod(0o755)

    def run_upload(self, exit_code=0):
        environment = os.environ.copy()
        environment.pop("BASH_ENV", None)
        environment.pop("ENV", None)
        environment.update({
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + environment["PATH"],
            "TEST_RSYNC_LOG": str(self.log),
            "TEST_RSYNC_EXIT": str(exit_code),
        })

        return subprocess.run(
            ["bash", str(ROOT / "deployment/home/upload-backups.sh")],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_success_uses_encrypted_file_filter_and_restricted_destination(self):
        result = self.run_upload()

        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(self.log.read_text())

        self.assertIn("--include=database-*.dump.age", arguments)
        self.assertIn("--exclude=*", arguments)
        self.assertEqual(arguments[-1], "tracker-backup@100.64.0.4:.")
        self.assertFalse(any(arg.startswith("--delete") for arg in arguments))
        self.assertNotIn("--remove-source-files", arguments)

        ssh_command = arguments[arguments.index("-e") + 1]
        self.assertIn("BatchMode=yes", ssh_command)
        self.assertIn("StrictHostKeyChecking=yes", ssh_command)

    def test_failed_transfer_is_reported_and_preserves_local_backup(self):
        result = self.run_upload(exit_code=23)

        self.assertEqual(result.returncode, 23)
        self.assertTrue(
            (self.backups / "database-test.dump.age").exists()
        )
        self.assertNotIn("completed successfully", result.stdout)

    def test_missing_key_prevents_transfer(self):
        (self.config / "oracle-backup-key").unlink()

        result = self.run_upload()

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_no_encrypted_backups_prevents_transfer(self):
        (self.backups / "database-test.dump.age").unlink()
        (self.backups / "notes.txt").write_text("not a backup")

        result = self.run_upload()

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
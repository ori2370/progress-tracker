import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "ghcr.io/ori2370/progress-tracker"
DIGEST = REPOSITORY + "@sha256:" + "a" * 64


FAKE_COMMAND = r'''
import json
import os
from pathlib import Path
import sys

command = Path(sys.argv[0]).name
args = sys.argv[1:]
scenario = os.environ["TEST_SCENARIO"]
digest = os.environ["TEST_DIGEST"]

with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps([command, *args]) + "\n")

if command == "docker":
    if args[0] == "pull":
        sys.exit(1 if scenario == "pull-failure" else 0)

    if args[:2] == ["image", "inspect"]:
        if ".RepoDigests" in " ".join(args):
            print(digest)
        else:
            print("sha256:new-image")
        sys.exit(0)

    if args[0] == "inspect":
        if ".Config.Image" in " ".join(args):
            print("progress-tracker:home")
        else:
            print(
                "sha256:new-image"
                if scenario == "unchanged"
                else "sha256:old-image"
            )
        sys.exit(0)

    if args[0] == "compose":
        if "ps" in args:
            print("test-web-container")
        elif "exec" in args:
            if scenario == "backup-failure":
                sys.exit(1)
            print("fake database dump")
        elif "migrate" in args and scenario == "migration-failure":
            sys.exit(1)
        elif "up" in args and scenario == "startup-failure":
            sys.exit(1)
        sys.exit(0)

elif command == "age":
    # Fake encryption only for updater control-flow tests.
    output = Path(args[args.index("--output") + 1])
    output.write_bytes(sys.stdin.buffer.read())
    sys.exit(0)

elif command == "curl":
    if scenario == "readiness-failure":
        sys.exit(22)
    print('{"status": "ready"}')
    sys.exit(0)

sys.exit("Unexpected fake command")
'''


class HomeUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.home = self.directory / "home"
        self.project = self.home / "apps/progress-tracker"
        self.config = self.home / ".config/progress-tracker"
        self.state = self.home / ".local/state/progress-tracker"
        self.bin = self.directory / "bin"
        self.log = self.directory / "commands.jsonl"

        self.config.mkdir(parents=True)
        self.bin.mkdir()

        for relative in (
            "deployment/home/update.sh",
            "deployment/home/compose.sh",
            "deployment/home/compose.override.yml",
            "deployment/backup.sh",
            "deployment/compose.yml",
        ):
            destination = self.project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)

        self.env_file = self.config / "home.env"
        self.original_env = (
            "APP_IMAGE=progress-tracker:home\n"
            "APP_PORT=18743\n"
            "TAILNET_IP=100.64.0.1\n"
            "DJANGO_SECRET_KEY=test-secret\n"
            "POSTGRES_PASSWORD=test-password\n"
        )
        self.env_file.write_text(self.original_env)
        (self.config / "backup-recipient.txt").write_text(
            "fake-test-recipient\n"
        )

        for command in ("docker", "age", "curl"):
            path = self.bin / command
            path.write_text(f"#!{sys.executable}\n" + FAKE_COMMAND)
            path.chmod(0o755)

    def run_update(self, scenario):
        environment = os.environ.copy()

        for name in ("APP_IMAGE", "TRACKER_ENV_FILE", "BASH_ENV", "ENV"):
            environment.pop(name, None)

        environment.update({
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + environment["PATH"],
            "TEST_SCENARIO": scenario,
            "TEST_DIGEST": DIGEST,
            "TEST_LOG": str(self.log),
        })

        return subprocess.run(
            ["bash", str(self.project / "deployment/home/update.sh")],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def commands(self):
        if not self.log.exists():
            return []
        return [
            json.loads(line)
            for line in self.log.read_text().splitlines()
        ]

    def test_unchanged_image_skips_backup_and_migrations(self):
        result = self.run_update("unchanged")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already up to date", result.stdout)
        self.assertFalse(any("exec" in cmd for cmd in self.commands()))
        self.assertFalse(any("migrate" in cmd for cmd in self.commands()))
        self.assertEqual(self.env_file.read_text(), self.original_env)

    def test_pull_failure_does_not_change_deployment(self):
        result = self.run_update("pull-failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("migrate" in cmd for cmd in self.commands()))
        self.assertEqual(self.env_file.read_text(), self.original_env)

    def test_backup_failure_prevents_migrations(self):
        result = self.run_update("backup-failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("migrate" in cmd for cmd in self.commands()))
        self.assertFalse(any("up" in cmd for cmd in self.commands()))
        self.assertEqual(self.env_file.read_text(), self.original_env)
        self.assertFalse((self.state / "update-blocked").exists())

    def test_migration_failure_blocks_further_attempts(self):
        result = self.run_update("migration-failure")

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.state / "update-blocked").exists())
        self.assertFalse(any("up" in cmd for cmd in self.commands()))
        self.assertEqual(self.env_file.read_text(), self.original_env)

        commands_before = self.commands()
        retry = self.run_update("success")

        self.assertNotEqual(retry.returncode, 0)
        self.assertEqual(self.commands(), commands_before)

    def test_startup_or_readiness_failure_preserves_configuration(self):
        for scenario in ("startup-failure", "readiness-failure"):
            with self.subTest(scenario=scenario):
                result = self.run_update(scenario)

                self.assertNotEqual(result.returncode, 0)
                self.assertTrue((self.state / "update-blocked").exists())
                self.assertEqual(
                    self.env_file.read_text(),
                    self.original_env,
                )

                # Reset only the isolated test marker for the next case.
                (self.state / "update-blocked").unlink()

    def test_success_records_digest_and_preserves_secrets(self):
        result = self.run_update("success")

        self.assertEqual(result.returncode, 0, result.stderr)
        content = self.env_file.read_text()
        self.assertIn(f"APP_IMAGE={DIGEST}\n", content)
        self.assertIn("POSTGRES_PASSWORD=test-password\n", content)
        self.assertEqual(self.env_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            (self.state / "current-image").read_text().strip(),
            DIGEST,
        )
        self.assertFalse((self.state / "update-blocked").exists())
        self.assertFalse((self.state / "pending-image").exists())

        commands = self.commands()
        backup = next(i for i, cmd in enumerate(commands) if "exec" in cmd)
        migration = next(
            i for i, cmd in enumerate(commands) if "migrate" in cmd
        )
        startup = next(i for i, cmd in enumerate(commands) if "up" in cmd)

        self.assertLess(backup, migration)
        self.assertLess(migration, startup)

    def test_failed_migration_records_stage_and_preserves_original_status(self):
        result = self.run_update("migration-failure")
        self.assertNotEqual(result.returncode, 0)

        status_file = self.state / "update-status.json"
        recorded = json.loads(status_file.read_text())

        self.assertEqual(recorded["stage"], "database_migration")
        self.assertEqual(recorded["backup"], "completed")
        self.assertEqual(recorded["result"], "failed")
        self.assertEqual(recorded["exit_code"], 1)

        original = status_file.read_bytes()
        self.run_update("success")

        self.assertEqual(status_file.read_bytes(), original)

    def test_backup_failure_records_uncompleted_backup(self):
        result = self.run_update("backup-failure")
        self.assertNotEqual(result.returncode, 0)

        recorded = json.loads(
            (self.state / "update-status.json").read_text()
        )

        self.assertEqual(recorded["stage"], "backup")
        self.assertEqual(recorded["backup"], "in_progress")
        self.assertEqual(recorded["result"], "failed")
        self.assertFalse((self.state / "update-blocked").exists())

if __name__ == "__main__":
    unittest.main()
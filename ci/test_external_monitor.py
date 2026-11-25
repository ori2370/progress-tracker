from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(
    str(ROOT / "deployment/oracle/home-monitor.py")
)
process_result = MODULE["process_result"]


class ExternalMonitorTests(unittest.TestCase):
    def setUp(self):
        self.messages = []

    def process(self, healthy, previous):
        return process_result(
            "home_ssh",
            healthy,
            previous,
            self.messages.append,
        )

    def test_healthy_initial_check_does_not_alert(self):
        state, failed = self.process(True, {})

        self.assertEqual(self.messages, [])
        self.assertEqual(state["failures"], 0)
        self.assertFalse(state["notified_down"])
        self.assertFalse(failed)

    def test_three_failures_trigger_one_alert(self):
        state = {}

        for attempt in range(1, 4):
            state, failed = self.process(False, state)
            self.assertFalse(failed)
            self.assertEqual(
                len(self.messages),
                1 if attempt == 3 else 0,
            )

        self.assertTrue(state["notified_down"])
        self.assertIn("unreachable from Oracle", self.messages[0])

    def test_repeated_failures_do_not_repeat_alert(self):
        state = {"failures": 3, "notified_down": True}

        state, failed = self.process(False, state)

        self.assertEqual(state["failures"], 4)
        self.assertEqual(self.messages, [])
        self.assertFalse(failed)

    def test_recovery_sends_one_message(self):
        state = {"failures": 3, "notified_down": True}

        state, failed = self.process(True, state)

        self.assertEqual(len(self.messages), 1)
        self.assertIn("recovered", self.messages[0])
        self.assertFalse(state["notified_down"])
        self.assertEqual(state["failures"], 0)
        self.assertFalse(failed)

        self.process(True, state)
        self.assertEqual(len(self.messages), 1)

    def test_failed_down_alert_is_retried(self):
        def unavailable(message):
            raise RuntimeError("Simulated delivery failure")

        state, failed = process_result(
            "home_ssh",
            False,
            {"failures": 2, "notified_down": False},
            unavailable,
        )

        self.assertTrue(failed)
        self.assertFalse(state["notified_down"])

        state, failed = self.process(False, state)

        self.assertFalse(failed)
        self.assertTrue(state["notified_down"])
        self.assertEqual(len(self.messages), 1)

    def test_failed_recovery_alert_is_retried(self):
        def unavailable(message):
            raise RuntimeError("Simulated delivery failure")

        state, failed = process_result(
            "home_ssh",
            True,
            {"failures": 3, "notified_down": True},
            unavailable,
        )

        self.assertTrue(failed)
        self.assertTrue(state["notified_down"])

        state, failed = self.process(True, state)

        self.assertFalse(failed)
        self.assertFalse(state["notified_down"])
        self.assertIn("recovered", self.messages[0])

    def test_targets_keep_independent_state(self):
        home_state, _ = self.process(
            False,
            {"failures": 2, "notified_down": False},
        )
        tracker_state, _ = process_result(
            "tracker",
            True,
            {},
            self.messages.append,
        )

        self.assertTrue(home_state["notified_down"])
        self.assertFalse(tracker_state["notified_down"])
        self.assertEqual(tracker_state["failures"], 0)


if __name__ == "__main__":
    unittest.main()
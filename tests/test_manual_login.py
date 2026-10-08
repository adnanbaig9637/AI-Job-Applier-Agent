"""Manual login tests use fake time and callbacks, never an actual browser."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


def load_helpers():
    settings = types.ModuleType("config.settings")
    settings.logs_folder_path = "unused-test-logs"
    spec = importlib.util.spec_from_file_location(
        "helpers_under_test", Path(__file__).resolve().parents[1] / "modules" / "helpers.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"config.settings": settings}):
        spec.loader.exec_module(module)
    return module


class ManualLoginTests(unittest.TestCase):
    def setUp(self):
        self.helpers = load_helpers()
        self.elapsed = 0
        self.helpers.monotonic = lambda: self.elapsed
        self.helpers.sleep = Mock(side_effect=self.advance)
        self.helpers.alert = Mock(return_value=None)
        self.helpers.print_lg = Mock()

    def advance(self, seconds):
        self.elapsed += seconds

    def test_existing_login_does_not_prompt(self):
        self.assertTrue(self.helpers.manual_login_retry(Mock(return_value=True)))
        self.helpers.alert.assert_not_called()
        self.helpers.sleep.assert_not_called()

    def test_explicit_dialog_response_still_verifies_browser_login(self):
        check = Mock(side_effect=[False, True])
        self.helpers.alert.return_value = "Confirm Login"
        self.assertTrue(self.helpers.manual_login_retry(check))
        self.assertEqual(check.call_count, 2)
        self.helpers.sleep.assert_not_called()

    def test_unavailable_dialog_polls_until_authenticated(self):
        check = Mock(side_effect=[False, False, True])
        self.assertTrue(self.helpers.manual_login_retry(check, timeout=10, poll_interval=2))
        self.assertEqual(self.elapsed, 4)
        self.helpers.alert.assert_called_once()

    def test_timeout_returns_false_without_skipping_confirmation(self):
        check = Mock(return_value=False)
        self.assertFalse(self.helpers.manual_login_retry(check, timeout=5, poll_interval=2))
        self.assertEqual(self.elapsed, 5)
        self.assertEqual(check.call_count, 4)

    def test_dialog_clicks_do_not_bypass_authentication(self):
        self.helpers.alert.return_value = "Confirm Login"
        check = Mock(return_value=False)
        self.assertFalse(self.helpers.manual_login_retry(check, limit=2, timeout=4))
        self.assertEqual(self.helpers.alert.call_count, 2)
        self.assertEqual(self.elapsed, 4)

    def test_fallback_can_poll_without_repeating_navigation_callback(self):
        navigation_check = Mock(return_value=False)
        page_check = Mock(side_effect=[False, True])
        self.assertTrue(self.helpers.manual_login_retry(
            navigation_check, poll_is_logged_in=page_check, timeout=10))
        navigation_check.assert_called_once()
        self.assertEqual(page_check.call_count, 2)

    def test_five_minute_default_wait_is_bounded(self):
        self.assertFalse(self.helpers.manual_login_retry(Mock(return_value=False)))
        self.assertEqual(self.elapsed, 300)

    def test_invalid_poll_interval_cannot_busy_loop(self):
        with self.assertRaises(ValueError):
            self.helpers.manual_login_retry(Mock(return_value=False), poll_interval=0)


if __name__ == "__main__":
    unittest.main()

"""Offline coverage for safe dialog fallbacks; no native dialogs are opened."""

import unittest
from unittest.mock import Mock, patch

from modules import dialogs


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.alert.return_value = "OK"
        self.backend.confirm.return_value = "Continue"
        patches = [
            patch.object(dialogs, "_dialogs_available", True),
            patch.object(dialogs, "import_module", return_value=self.backend),
            patch.object(dialogs.sys, "stdin", Mock(isatty=Mock(return_value=False))),
            patch("builtins.print"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_informational_alert_works_normally(self):
        self.assertEqual(dialogs.alert("Done", "Status"), "OK")
        self.backend.alert.assert_called_once_with("Done", "Status", "OK")

    def test_failed_alert_is_logged_once_and_no_longer_attempted(self):
        self.backend.alert.side_effect = RuntimeError("unusable init.tcl")
        self.assertIsNone(dialogs.alert("Done"))
        self.assertIsNone(dialogs.alert("Done again"))
        self.backend.alert.assert_called_once()

    def test_broken_dialog_uses_only_explicit_conservative_default(self):
        self.backend.confirm.side_effect = RuntimeError("unusable init.tcl")
        result = dialogs.confirm("Review", buttons=["Discard", "Submit"], default="Discard")
        self.assertEqual(result, "Discard")

    def test_required_pause_cannot_silently_continue_without_tk_or_terminal(self):
        self.backend.confirm.side_effect = RuntimeError("unusable init.tcl")
        with self.assertRaises(dialogs.DialogUnavailableError):
            dialogs.acknowledge("Please answer the missing question")

    def test_interactive_terminal_can_explicitly_approve(self):
        self.backend.confirm.side_effect = RuntimeError("unusable init.tcl")
        dialogs.sys.stdin.isatty.return_value = True
        with patch("builtins.input", return_value="2"):
            result = dialogs.confirm("Review", buttons=["Discard", "Submit"], default="Discard")
        self.assertEqual(result, "Submit")

    def test_blank_terminal_response_does_not_approve(self):
        self.backend.confirm.side_effect = RuntimeError("unusable init.tcl")
        dialogs.sys.stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["", "invalid", "q"]) as read:
            result = dialogs.confirm("Review", buttons=["Discard", "Submit"], default="Discard")
        self.assertEqual(result, "Discard")
        self.assertEqual(read.call_count, 3)

    def test_terminal_eof_cannot_acknowledge(self):
        self.backend.confirm.side_effect = RuntimeError("unusable init.tcl")
        dialogs.sys.stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=EOFError), self.assertRaises(dialogs.DialogUnavailableError):
            dialogs.acknowledge("Complete this step")

    def test_closing_working_dialog_does_not_approve_or_open_terminal(self):
        self.backend.confirm.return_value = None
        with patch("builtins.input") as read:
            self.assertEqual(dialogs.confirm("Review", buttons=["Discard", "Submit"],
                                             default="Discard"), "Discard")
        read.assert_not_called()

    def test_gui_pause_requires_a_response(self):
        self.assertEqual(dialogs.acknowledge("Complete this step"), "Continue")
        self.backend.confirm.return_value = None
        with self.assertRaises(dialogs.DialogUnavailableError):
            dialogs.acknowledge("Complete this step")

    def test_invalid_default_rejected_before_showing_dialog(self):
        with self.assertRaises(ValueError):
            dialogs.confirm("Review", buttons=["Discard", "Submit"], default="Unknown")
        self.backend.confirm.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Exercise the bot's application flow without importing its startup side effects."""

import ast
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import Mock

from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from modules.dialogs import DialogUnavailableError


def application_flow_code():
    """Compile the actual Easy Apply branch inside a single mocked job iteration.

    Reading the AST avoids executing the bot's config imports, browser creation,
    and main routine. Keeping its exception handler exercises failure/discard
    behavior as well as the decision to click Review or Submit application.
    """
    path = Path(__file__).resolve().parents[1] / "runAiBot.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    apply_function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "apply_to_jobs"
    )
    branch = next(
        node for node in ast.walk(apply_function)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "is_easy_apply"
    )
    loop = ast.For(
        target=ast.Name(id="_fixture_job", ctx=ast.Store()),
        iter=ast.Tuple(elts=[ast.Constant(value=0)], ctx=ast.Load()),
        body=branch.body,
        orelse=[],
    )
    return compile(ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])), str(path), "exec")


class ApplicationPauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flow = application_flow_code()

    def setUp(self):
        self.driver = Mock(name="driver")
        self.modal = Mock(name="modal")
        self.next_button = Mock(name="next_button")
        self.dialogs = Mock(name="dialogs")
        self.wait_span_click = Mock(name="wait_span_click", return_value=True)

        def find_next(by, selector):
            if "Review" in selector:
                raise NoSuchElementException("Review is not on this question screen")
            return self.next_button

        self.modal.find_element.side_effect = find_next
        self.state = {
            "driver": self.driver,
            "find_by_class": Mock(return_value=self.modal),
            "wait_span_click": self.wait_span_click,
            "dialogs": self.dialogs,
            "pause_at_failed_question": True,
            "pause_before_submit": False,
            "screenshot": Mock(return_value="fixture.png"),
            "screenshot_name": "Not Available",
            "job_id": "fixture-job",
            "job_link": "https://example.invalid/job",
            "date_listed": None,
            "application_link": "Easy Applied",
            "answer_questions": Mock(return_value=set()),
            "work_location": "Remote",
            "description": "Fixture job description",
            "useNewResume": False,
            "uploaded": False,
            "upload_resume": Mock(),
            "default_resume_path": "unused.pdf",
            "buffer": Mock(),
            "click_gap": 0,
            "follow_company": Mock(),
            "datetime": datetime,
            "actions": Mock(),
            "By": By,
            "Keys": Keys,
            "NoSuchElementException": NoSuchElementException,
            "ElementClickInterceptedException": ElementClickInterceptedException,
            "print_lg": Mock(),
            "print": Mock(),
            "critical_error_log": Mock(),
            "failed_job": Mock(),
            "failed_count": 0,
            "discard_job": Mock(),
        }

    def run_flow(self):
        exec(self.flow, self.state)

    def clicked_labels(self):
        return [call.args[1] for call in self.wait_span_click.call_args_list]

    def assert_discarded_without_review_or_submission(self):
        self.assertNotIn("Review", self.clicked_labels())
        self.assertNotIn("Submit application", self.clicked_labels())
        self.state["follow_company"].assert_not_called()
        self.state["discard_job"].assert_called_once_with()
        self.state["failed_job"].assert_called_once()
        self.assertEqual(self.state["failed_count"], 1)

    def test_unavailable_required_acknowledgement_discards_without_submitting(self):
        unavailable = DialogUnavailableError("No interactive acknowledgement is available")
        self.dialogs.acknowledge.side_effect = unavailable

        self.run_flow()

        self.dialogs.acknowledge.assert_called_once()
        self.assert_discarded_without_review_or_submission()
        self.assertIs(self.state["critical_error_log"].call_args.args[1], unavailable)

    def test_stuck_questions_discard_even_when_submission_pause_is_disabled(self):
        self.state["pause_at_failed_question"] = False

        self.run_flow()

        self.dialogs.acknowledge.assert_not_called()
        self.assert_discarded_without_review_or_submission()
        self.assertIn("stuck", str(self.state["critical_error_log"].call_args.args[1]))

    def test_normal_question_completion_still_reaches_submission(self):
        self.next_button.click.side_effect = ElementClickInterceptedException("Question flow completed")

        self.run_flow()

        self.assertEqual(self.clicked_labels(), ["Next", "Review", "Submit application", "Done"])
        self.dialogs.confirm.assert_not_called()
        self.state["discard_job"].assert_not_called()
        self.state["failed_job"].assert_not_called()
        self.assertIsInstance(self.state["date_applied"], datetime)

    def test_missing_next_button_still_allows_final_review_and_submission(self):
        self.modal.find_element.side_effect = NoSuchElementException("No remaining question buttons")

        self.run_flow()

        self.assertEqual(self.clicked_labels(), ["Next", "Review", "Submit application", "Done"])
        self.state["discard_job"].assert_not_called()
        self.state["failed_job"].assert_not_called()
        self.assertEqual(self.state["failed_count"], 0)

    def test_discard_response_at_final_confirmation_prevents_submission(self):
        self.state["pause_before_submit"] = True
        self.modal.find_element.side_effect = NoSuchElementException("No remaining question buttons")
        self.dialogs.confirm.return_value = "Discard Application"

        self.run_flow()

        self.dialogs.confirm.assert_called_once()
        self.assertNotIn("Submit application", self.clicked_labels())
        self.state["discard_job"].assert_called_once_with()
        self.state["failed_job"].assert_called_once()


if __name__ == "__main__":
    unittest.main()

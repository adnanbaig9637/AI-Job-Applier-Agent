"""Offline runner wiring tests; browser, configuration, and desktop imports are injected."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def fake_module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_file(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_runner():
    """Load real runner/dialog code with no real profile, browser, or GUI imports."""
    desktop = fake_module("pyautogui", alert=Mock(return_value="OK"))
    shared_search = fake_module(
        "config.search", search_terms=["LinkedIn-only term"],
        date_posted="Past month", sort_by="Most recent",
    )
    adapter = fake_module(
        "modules.naukri.naukri_config",
        get_search_terms=Mock(return_value=["AI Engineer"]),
        get_date_posted=Mock(return_value="Any time"),
        get_sort_by=Mock(return_value="Most relevant"),
        describe=Mock(return_value="Naukri fixture preferences"),
        naukri_file_name="fixture-applied.csv",
        naukri_failed_file_name="fixture-failed.csv",
    )
    apply = fake_module(
        "modules.naukri.naukri_apply", apply_to_jobs=Mock(),
        stats={"applied": 0, "external": 0, "failed": 0, "skipped": 0, "search_failed": 2},
        skip_reasons={}, randomly_answered_questions=set(),
    )
    helpers = fake_module(
        "modules.helpers", print_lg=Mock(), buffer=Mock(), sleep=Mock(),
        critical_error_log=Mock(), make_directories=Mock(),
    )
    browser = fake_module("modules.open_chrome", driver=Mock(), wait=Mock())
    login = fake_module("modules.naukri.naukri_login", ensure_logged_in=Mock())
    stubs = {
        "pyautogui": desktop,
        "config": fake_module("config", __path__=[]),
        "config.search": shared_search,
        "config.questions": fake_module("config.questions", default_resume_path="fixture-resume.pdf"),
        "config.secrets": fake_module("config.secrets", use_AI=False, ai_provider="openai"),
        "config.settings": fake_module(
            "config.settings", run_in_background=False, run_non_stop=False,
            alternate_sortby=False, cycle_date_posted=False, stop_date_cycle_at_24hr=True,
            logs_folder_path="fixture-logs",
        ),
        "modules": fake_module("modules", __path__=[]),
        "modules.helpers": helpers,
        "modules.open_chrome": browser,
        "modules.validator": fake_module("modules.validator", validate_config=Mock()),
        "modules.relevance": fake_module("modules.relevance", describe=Mock(return_value="Fixture rules")),
        "modules.naukri": fake_module("modules.naukri", __path__=[]),
        "modules.naukri.naukri_config": adapter,
        "modules.naukri.naukri_apply": apply,
        "modules.naukri.naukri_login": login,
    }
    with patch.dict(sys.modules, stubs):
        dialogs = load_file("modules.naukri.naukri_dialogs", "modules/naukri/naukri_dialogs.py")
        sys.modules["modules.naukri.naukri_dialogs"] = dialogs
        runner = load_file("naukri_runner_under_test", "runNaukriBot.py")
    return types.SimpleNamespace(
        runner=runner, desktop=desktop, shared_search=shared_search, adapter=adapter,
        apply=apply, helpers=helpers, browser=browser, login=login, dialogs=dialogs,
    )


class NaukriRunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_runner()
        self.runner = self.fixture.runner

    def summary(self):
        return next(
            call.args[0] for call in self.fixture.helpers.print_lg.call_args_list
            if call.args and isinstance(call.args[0], str) and call.args[0].startswith("Total runs:")
        )

    def test_initial_filters_come_from_naukri_preferences(self):
        self.assertEqual(self.runner.current_date_posted, "Any time")
        self.assertEqual(self.runner.current_sort_by, "Most relevant")
        self.fixture.adapter.get_date_posted.assert_called_once_with()
        self.fixture.adapter.get_sort_by.assert_called_once_with()

    def test_run_uses_naukri_terms_without_modifying_shared_search(self):
        self.assertEqual(self.runner.run(1), 2)

        self.fixture.apply.apply_to_jobs.assert_called_once_with(
            self.fixture.browser.driver, self.fixture.browser.wait, ["AI Engineer"], None,
            sort_by="Most relevant", date_posted="Any time",
        )
        self.fixture.adapter.get_search_terms.assert_called_once_with()
        self.assertEqual(self.fixture.shared_search.search_terms, ["LinkedIn-only term"])
        self.assertEqual(self.fixture.shared_search.date_posted, "Past month")
        self.assertEqual(self.fixture.shared_search.sort_by, "Most recent")
        self.fixture.helpers.sleep.assert_not_called()

    def test_run_preserves_current_cycle_filters(self):
        self.runner.current_date_posted = "Past 24 hours"
        self.runner.current_sort_by = "Most recent"

        self.runner.run(2)

        self.assertEqual(self.fixture.apply.apply_to_jobs.call_args.kwargs, {
            "sort_by": "Most recent", "date_posted": "Past 24 hours",
        })

    def test_summary_dialog_tcl_failure_does_not_interrupt_browser_cleanup(self):
        self.fixture.desktop.alert.side_effect = RuntimeError("Can't find a usable init.tcl")

        self.runner.main()

        self.fixture.desktop.alert.assert_called_once()
        self.assertFalse(self.fixture.dialogs._dialogs_available)
        self.fixture.browser.driver.quit.assert_called_once_with()
        self.fixture.helpers.critical_error_log.assert_not_called()

    def test_error_and_summary_dialogs_survive_unavailable_tcl(self):
        error = ValueError("Fixture login failed")
        self.fixture.login.ensure_logged_in.side_effect = error
        self.fixture.desktop.alert.side_effect = RuntimeError("Can't find a usable init.tcl")

        self.runner.main()

        self.fixture.helpers.critical_error_log.assert_called_once_with("In Naukri Applier Main", error)
        self.fixture.desktop.alert.assert_called_once()
        self.fixture.apply.apply_to_jobs.assert_not_called()
        self.fixture.browser.driver.quit.assert_called_once_with()
        self.assertIn("Failed searches: 2", self.summary())

    def test_summary_distinguishes_search_failures_from_job_failures(self):
        self.runner.main()

        self.assertIn("Failed searches: 2", self.summary())
        self.assertIn("Failed jobs: 0", self.summary())
        self.assertIn("Jobs applied on Naukri: 0", self.summary())

    def test_summary_defaults_missing_search_failure_counter_to_zero(self):
        self.fixture.apply.stats.pop("search_failed")

        self.runner.main()

        self.assertIn("Failed searches: 0", self.summary())
        self.fixture.browser.driver.quit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

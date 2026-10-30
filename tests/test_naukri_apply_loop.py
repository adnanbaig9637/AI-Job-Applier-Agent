"""Offline regression tests for Naukri result pagination."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import NoSuchWindowException, WebDriverException


ROOT = Path(__file__).resolve().parents[1]


def fake_module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


def load_apply_module():
    search_config = fake_module(
        "config.search", randomize_search_order=False, easy_apply_only=True,
        pause_after_filters=False, about_company_bad_words=[], about_company_good_words=[],
        bad_words=[], security_clearance=False, did_masters=False, current_experience=3,
    )
    settings = fake_module(
        "config.settings", close_tabs=True, keep_screen_awake=False,
        logs_folder_path="logs", run_in_background=False,
    )
    secrets = fake_module("config.secrets", use_AI=False, ai_provider="openai")
    questions = fake_module(
        "config.questions", pause_before_submit=False, pause_at_failed_question=False,
    )
    adapter = fake_module(
        "modules.naukri.naukri_config", max_pages_per_search=2,
        _opt=lambda module, name, default: default,
    )
    search = fake_module(
        "modules.naukri.naukri_search",
        NaukriAccessError=type("NaukriAccessError", (Exception,), {}),
        NaukriSearchError=type("NaukriSearchError", (Exception,), {}),
        open_search=Mock(return_value=True), apply_ui_filters=Mock(),
        get_job_cards=Mock(), get_card_details=Mock(), matches_experience_range=Mock(return_value=True),
    )
    helpers = fake_module(
        "modules.helpers", print_lg=Mock(), calculate_date_posted=Mock(),
        critical_error_log=Mock(), truncate_for_csv=str,
    )
    clickers = fake_module("modules.clickers_and_finders", try_xp=Mock(), scroll_to_view=Mock())
    answers = fake_module("modules.answers")
    relevance = fake_module("modules.relevance")
    chatbot = fake_module("modules.naukri.naukri_questions")
    dialogs = fake_module(
        "modules.naukri.naukri_dialogs", confirm=Mock(return_value="Continue"),
        keep_awake=Mock(),
    )
    package = fake_module(
        "modules.naukri", __path__=[], naukri_config=adapter, naukri_search=search,
        naukri_questions=chatbot, naukri_dialogs=dialogs,
    )
    modules = fake_module(
        "modules", __path__=[], answers=answers, relevance=relevance,
    )
    stubs = {
        "config": fake_module("config", __path__=[]),
        "config.search": search_config,
        "config.settings": settings,
        "config.secrets": secrets,
        "config.questions": questions,
        "modules": modules,
        "modules.answers": answers,
        "modules.relevance": relevance,
        "modules.helpers": helpers,
        "modules.clickers_and_finders": clickers,
        "modules.naukri": package,
        "modules.naukri.naukri_config": adapter,
        "modules.naukri.naukri_search": search,
        "modules.naukri.naukri_questions": chatbot,
        "modules.naukri.naukri_dialogs": dialogs,
    }
    spec = importlib.util.spec_from_file_location(
        "naukri_apply_under_test", ROOT / "modules" / "naukri" / "naukri_apply.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module, search


class NaukriApplyPaginationTests(unittest.TestCase):
    def test_processes_every_card_before_advancing_past_thirty_successes(self):
        apply, search = load_apply_module()
        cards = [object() for _ in range(31)]
        details = [{"job_id": str(index), "title": f"AI Engineer {index}"} for index in range(31)]
        search.get_job_cards.side_effect = [cards, []]
        search.get_card_details.side_effect = details
        driver = Mock()
        driver.current_window_handle = "naukri-tab"
        events = []
        search.open_search.side_effect = lambda *args: events.append(("page", args[3])) or True
        process_job = Mock(side_effect=lambda *args: events.append(("job", args[2]["job_id"])) or True)

        with patch.object(apply, "get_applied_job_ids", return_value=set()), \
             patch.object(apply, "process_job", process_job):
            apply.apply_to_jobs(driver, Mock(), ["AI Engineer"])

        self.assertEqual(process_job.call_count, 31)
        self.assertEqual(events[0], ("page", 1))
        self.assertEqual(events[32], ("page", 2))
        self.assertEqual([event for event in events if event[0] == "job"][-1], ("job", "30"))


if __name__ == "__main__":
    unittest.main()
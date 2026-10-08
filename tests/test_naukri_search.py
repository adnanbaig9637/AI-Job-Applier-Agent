"""Offline Naukri search checks: fake config, browser, clocks and wait states."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, call, patch
from urllib.parse import parse_qs, urlsplit

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By


def load_search():
    settings = types.ModuleType("config.settings")
    settings.click_gap = 0
    helpers = types.ModuleType("modules.helpers")
    helpers.print_lg, helpers.buffer, helpers.sleep = Mock(), Mock(), Mock()
    clickers = types.ModuleType("modules.clickers_and_finders")
    clickers.try_xp, clickers.scroll_to_view = Mock(), Mock()
    adapter = types.ModuleType("modules.naukri.naukri_config")
    adapter.get_search_locations = Mock(return_value=["Hyderabad", "Pune", "Mumbai"])
    adapter.get_experience_years = Mock(return_value=2)
    adapter.get_search_experience_range = Mock(return_value=(2, 3))
    adapter.get_job_age = Mock(return_value=7)
    adapter.get_sort = Mock(return_value="f")
    adapter.get_work_modes = Mock(return_value=["2", "3"])
    adapter.get_job_type_labels = Mock(return_value=[])
    adapter.salary_filter = "6to10"
    package = types.ModuleType("modules.naukri")
    package.__path__ = []
    package.naukri_config = adapter
    spec = importlib.util.spec_from_file_location(
        "naukri_search_under_test",
        Path(__file__).resolve().parents[1] / "modules" / "naukri" / "naukri_search.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        "config.settings": settings, "modules.helpers": helpers,
        "modules.clickers_and_finders": clickers,
        "modules.naukri": package, "modules.naukri.naukri_config": adapter,
    }):
        spec.loader.exec_module(module)
    return module, adapter


def browser():
    driver = Mock()
    driver.current_url = "https://www.naukri.com/ai-engineer-jobs"
    driver.get.side_effect = lambda url: setattr(driver, "current_url", url)
    driver.find_elements.return_value = []
    return driver


def element(visible=True, text=""):
    item = Mock()
    item.is_displayed.return_value = visible
    item.text = text
    return item


class SearchURLTests(unittest.TestCase):
    def setUp(self):
        self.search, self.config = load_search()

    def test_multiple_cities_stay_in_query_with_canonical_keyword_route(self):
        url = urlsplit(self.search.build_search_url("AI Engineer", page=2))
        query = parse_qs(url.query)
        self.assertEqual(url.path, "/ai-engineer-jobs-2")
        self.assertEqual(query["k"], ["AI Engineer"])
        self.assertEqual(query["l"], ["Hyderabad, Pune, Mumbai"])
        self.assertEqual(query["experience"], ["2"])
        self.assertEqual(query["wfhType"], ["2,3"])

    def test_simple_retry_preserves_all_eligibility_filters(self):
        initial = urlsplit(self.search.build_search_url("AI Engineer", page=2))
        simpler = urlsplit(self.search.build_search_url("AI Engineer", page=2, simple=True))
        initial_query, simpler_query = parse_qs(initial.query), parse_qs(simpler.query)
        self.assertEqual(initial.path, simpler.path)
        self.assertEqual(initial_query.pop("sort"), ["f"])
        self.assertEqual(simpler_query, initial_query)
        self.assertEqual(simpler_query["jobAge"], ["7"])
        self.assertEqual(simpler_query["ctcFilter"], ["6to10"])

    def test_single_city_simple_retry_changes_route_without_dropping_city(self):
        self.config.get_search_locations.return_value = ["Hyderabad"]
        initial = urlsplit(self.search.build_search_url("AI Engineer"))
        simpler = urlsplit(self.search.build_search_url("AI Engineer", simple=True))
        self.assertEqual(initial.path, "/ai-engineer-jobs-in-hyderabad")
        self.assertEqual(simpler.path, "/ai-engineer-jobs")
        self.assertEqual(parse_qs(simpler.query)["l"], ["Hyderabad"])

    def test_explicit_cycle_filters_are_passed_to_configuration(self):
        self.search.build_search_url("AI Engineer", sort_by="Most relevant", date_posted="Past 24 hours")
        self.config.get_sort.assert_called_once_with("Most relevant")
        self.config.get_job_age.assert_called_once_with("Past 24 hours")


class SearchNavigationTests(unittest.TestCase):
    def setUp(self):
        self.search, self.config = load_search()
        self.driver = browser()
        self.shared_wait = types.SimpleNamespace(_timeout=5)
        self.search_wait = Mock()
        self.search.WebDriverWait = Mock(return_value=self.search_wait)

    def open(self, states):
        self.search_wait.until.side_effect = states
        return self.search.open_search(self.driver, self.shared_wait, "AI Engineer")

    def test_results_finish_without_refreshing_or_recovering(self):
        self.assertTrue(self.open(["results"]))
        self.driver.get.assert_called_once()
        self.driver.refresh.assert_not_called()
        self.search.WebDriverWait.assert_called_once_with(self.driver, 20)
        self.search_wait.until.assert_called_once_with(self.search._search_state)
        self.search.sleep.assert_not_called()

    def test_longer_caller_wait_is_preserved(self):
        self.shared_wait._timeout = 45
        self.assertTrue(self.open(["results"]))
        self.search.WebDriverWait.assert_called_once_with(self.driver, 45)

    def test_only_explicit_empty_result_returns_false(self):
        self.assertFalse(self.open(["empty"]))
        self.driver.refresh.assert_not_called()
        self.assertTrue(any("reported no results" in str(args) for args in self.search.print_lg.call_args_list))

    def test_generic_loading_error_can_recover_after_one_refresh(self):
        self.assertTrue(self.open(["error", "results"]))
        self.driver.refresh.assert_called_once()
        self.driver.get.assert_called_once()
        self.search.sleep.assert_called_once_with(2)

    def test_error_then_refresh_error_recovers_using_simple_route(self):
        self.assertTrue(self.open(["error", "error", "results"]))
        self.driver.refresh.assert_called_once()
        self.assertEqual(self.driver.get.call_count, 2)
        normal_url, recovery_url = [args.args[0] for args in self.driver.get.call_args_list]
        initial_query, recovery_query = parse_qs(urlsplit(normal_url).query), parse_qs(urlsplit(recovery_url).query)
        initial_query.pop("sort")
        self.assertEqual(initial_query, recovery_query)
        self.search.sleep.assert_has_calls([call(2), call(2)])

    def test_persistent_error_raises_instead_of_claiming_zero_jobs(self):
        with self.assertRaisesRegex(self.search.NaukriSearchError, "page-loading error.*not a zero-jobs result"):
            self.open(["error", "error", "error"])
        self.assertEqual(self.search_wait.until.call_count, 3)
        self.assertFalse(any("No job cards" in str(args) or "reported no results" in str(args)
                             for args in self.search.print_lg.call_args_list))

    def test_loading_timeout_is_not_an_empty_result(self):
        with self.assertRaisesRegex(self.search.NaukriSearchError, "did not finish loading"):
            self.open([TimeoutException(), TimeoutException(), TimeoutException()])
        self.driver.refresh.assert_called_once()
        self.assertEqual(self.driver.get.call_count, 2)

    def test_access_gate_requires_user_without_refresh_or_fallback(self):
        with self.assertRaises(self.search.NaukriAccessError):
            self.open(["blocked"])
        self.driver.get.assert_called_once()
        self.driver.refresh.assert_not_called()
        self.search.sleep.assert_not_called()

    def test_access_gate_after_refresh_stops_before_simple_retry(self):
        with self.assertRaises(self.search.NaukriAccessError):
            self.open(["error", "blocked"])
        self.driver.get.assert_called_once()
        self.driver.refresh.assert_called_once()

    def test_identical_simple_route_is_not_retried_redundantly(self):
        self.config.get_sort.return_value = None
        with self.assertRaises(self.search.NaukriSearchError):
            self.open(["error", "error"])
        self.assertEqual(self.search_wait.until.call_count, 2)
        self.driver.get.assert_called_once()


class SearchStateTests(unittest.TestCase):
    def setUp(self):
        self.search, _ = load_search()
        self.driver = browser()

    def show(self, *, cards=(), error=(), empty=(), blocked=(), captcha=()):
        for items, default_text in [(error, "Oops! Something went wrong"),
                                    (empty, "No jobs found"), (blocked, "Access denied")]:
            for item in items:
                if not item.text:
                    item.text = default_text
        def find(by, selector):
            if by == By.CSS_SELECTOR and selector == "div.srp-jobtuple-wrapper":
                return list(cards)
            if by == By.XPATH:
                if "access denied" in selector:
                    return list(blocked)
                if "captcha" in selector:
                    return list(captcha)
                if "oops! something went wrong" in selector:
                    return list(error)
                if "no jobs found" in selector:
                    return list(empty)
            return []
        self.driver.find_elements.side_effect = find

    def test_visible_card_is_a_result(self):
        self.show(cards=[element()])
        self.assertEqual(self.search._search_state(self.driver), "results")

    def test_hidden_loading_card_and_hidden_status_placeholders_are_ignored(self):
        self.show(cards=[element(False)], error=[element(False)], empty=[element(False)],
                  blocked=[element(False)], captcha=[element(False)])
        self.assertIs(self.search._search_state(self.driver), False)

    def test_visible_generic_error_wins_over_cached_cards(self):
        self.show(cards=[element()], error=[element()])
        self.assertEqual(self.search._search_state(self.driver), "error")

    def test_explicit_visible_empty_marker_is_distinguished(self):
        self.show(empty=[element()])
        self.assertEqual(self.search._search_state(self.driver), "empty")

    def test_visible_access_gate_wins_over_cached_results(self):
        self.show(cards=[element()], blocked=[element()])
        self.assertEqual(self.search._search_state(self.driver), "blocked")

    def test_visible_captcha_requires_manual_verification(self):
        self.show(captcha=[element()])
        self.assertEqual(self.search._search_state(self.driver), "blocked")

    def test_login_redirect_requires_manual_sign_in(self):
        self.driver.current_url = "https://www.naukri.com/nlogin/login"
        self.assertEqual(self.search._search_state(self.driver), "blocked")

    def test_stale_marker_does_not_hide_a_following_visible_marker(self):
        stale = element()
        stale.is_displayed.side_effect = StaleElementReferenceException()
        self.show(error=[stale, element()])
        self.assertEqual(self.search._search_state(self.driver), "error")

    def test_visible_error_text_normalizes_case_and_whitespace(self):
        self.show(error=[element(text=" OOPS!\n Something    went   wrong ")])
        self.assertEqual(self.search._search_state(self.driver), "error")

    def test_matching_dom_text_without_matching_rendered_text_is_ignored(self):
        self.show(error=[element(text="A visible unrelated status")])
        self.assertIs(self.search._search_state(self.driver), False)


class ExperienceRangeTests(unittest.TestCase):
    def setUp(self):
        self.search, self.config = load_search()

    def test_overlapping_job_ranges_include_boundaries(self):
        for experience in ["2-3 Yrs", "0-5 Yrs", "3-8 Yrs", "2 Yrs", "2.5–3.5 Yrs"]:
            with self.subTest(experience=experience):
                self.assertTrue(self.search.matches_experience_range(experience))

    def test_senior_and_junior_only_ranges_are_outside_preference(self):
        for experience in ["4-8 Yrs", "0-1 Yrs", "3.5 Yrs", "4+ Yrs"]:
            with self.subTest(experience=experience):
                self.assertFalse(self.search.matches_experience_range(experience))

    def test_open_ended_range_can_overlap_preference(self):
        self.assertTrue(self.search.matches_experience_range("1+ Yrs"))
        self.assertTrue(self.search.matches_experience_range("3+ Yrs"))

    def test_missing_experience_defers_to_existing_profile_and_description_checks(self):
        for experience in ["", "Not disclosed", None]:
            with self.subTest(experience=experience):
                self.assertTrue(self.search.matches_experience_range(experience))

    def test_absent_preference_does_not_add_a_job_range_filter(self):
        self.config.get_search_experience_range.return_value = None
        self.assertTrue(self.search.matches_experience_range("10-15 Yrs"))


if __name__ == "__main__":
    unittest.main()

"""Resolve Naukri preferences using fake config modules, never real credentials."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


def load_config(preferences=None, shared_values=None, settings_values=None):
    package = types.ModuleType("config")
    package.__path__ = []
    shared = types.ModuleType("config.search")
    shared.__dict__.update({
        "search_terms": ["Shared role one", "Shared role two"],
        "search_location": "India", "current_experience": 2,
        "experience_level": ["Associate"], "date_posted": "Past week",
        "sort_by": "Most recent", "on_site": ["On-site"],
        "job_type": ["Full-time"],
    })
    shared.__dict__.update(shared_values or {})
    settings = types.ModuleType("config.settings")
    settings.__dict__.update(settings_values or {})
    secrets = types.ModuleType("config.secrets")
    helpers = types.ModuleType("modules.helpers")
    helpers.print_lg = Mock()
    replacements = {
        "config": package, "config.search": shared,
        "config.settings": settings, "config.secrets": secrets,
        "modules.helpers": helpers,
    }
    package.search, package.settings, package.secrets = shared, settings, secrets
    if preferences is not None:
        filters = types.ModuleType("config.naukri_filter_config")
        filters.__dict__.update(preferences)
        replacements["config.naukri_filter_config"] = filters
    spec = importlib.util.spec_from_file_location(
        "naukri_config_under_test",
        Path(__file__).resolve().parents[1] / "modules" / "naukri" / "naukri_config.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, replacements):
        if preferences is None:
            sys.modules.pop("config.naukri_filter_config", None)
        spec.loader.exec_module(module)
    return module, shared


PREFERENCES = {
    "search_terms": ["AI Engineer"],
    "search_locations": ["Hyderabad", "Pune", "Mumbai"],
    "experience_min": 2, "experience_max": 3,
    "on_site": ["Remote", "Hybrid"],
    "date_posted": "Any time", "sort_by": "Most relevant",
}


class NaukriConfigTests(unittest.TestCase):
    def test_local_preferences_override_shared_search(self):
        config, shared = load_config(PREFERENCES)
        self.assertEqual(config.get_search_terms(), ["AI Engineer"])
        self.assertEqual(config.get_search_locations(), ["Hyderabad", "Pune", "Mumbai"])
        self.assertEqual(config.get_search_location(), "Hyderabad, Pune, Mumbai")
        self.assertEqual(config.get_work_modes(), ["2", "3"])
        self.assertEqual(config.get_search_experience_range(), (2, 3))
        self.assertEqual(config.get_experience_years(), 2)
        self.assertIsNone(config.get_job_age())
        self.assertEqual(config.get_sort(), "r")
        self.assertEqual(config.get_sort_ui_label(), "Relevance")
        self.assertEqual(shared.search_location, "India")
        self.assertEqual(shared.current_experience, 2)
        self.assertEqual(shared.on_site, ["On-site"])

    def test_absent_optional_file_preserves_existing_configuration(self):
        config, _ = load_config()
        self.assertEqual(config.get_search_terms(), ["Shared role one", "Shared role two"])
        self.assertEqual(config.get_search_locations(), ["India"])
        self.assertEqual(config.get_experience_years(), 2)
        self.assertIsNone(config.get_search_experience_range())
        self.assertEqual(config.get_date_posted(), "Past week")
        self.assertEqual(config.get_job_age(), 7)
        self.assertEqual(config.get_sort_by(), "Most recent")
        self.assertEqual(config.get_sort(), "f")
        self.assertEqual(config.get_work_modes(), ["0"])

    def test_partial_preferences_fall_back_per_setting(self):
        config, _ = load_config({"search_terms": ["AI Engineer"]})
        self.assertEqual(config.get_search_terms(), ["AI Engineer"])
        self.assertEqual(config.get_search_locations(), ["India"])
        self.assertEqual(config.get_work_modes(), ["0"])
        self.assertEqual(config.get_job_type_labels(), ["Full Time"])

    def test_search_range_does_not_change_claimed_experience(self):
        config, shared = load_config(
            {"experience_min": 3, "experience_max": 4},
            settings_values={"naukri_experience_years": 5})
        self.assertEqual(config.get_experience_years(), 3)
        self.assertEqual(shared.current_experience, 2)
        self.assertIn("Applicant experience (unchanged): 2", config.describe())

    def test_explicit_run_loop_date_and_sort_override_local_defaults(self):
        config, _ = load_config(PREFERENCES)
        self.assertEqual(config.get_job_age("Past 24 hours"), 1)
        self.assertEqual(config.get_sort("Most recent"), "f")
        self.assertEqual(config.get_sort_ui_label("Most recent"), "Date")

    def test_empty_preferences_can_clear_shared_filters(self):
        config, _ = load_config({"search_locations": [], "on_site": []})
        self.assertEqual(config.get_search_location(), "")
        self.assertEqual(config.get_work_modes(), [])

    def test_locations_can_be_comma_separated_and_are_deduplicated(self):
        config, _ = load_config({"search_locations": " Hyderabad, Pune, Mumbai, Pune, "})
        self.assertEqual(config.get_search_locations(), ["Hyderabad", "Pune", "Mumbai"])

    def test_getters_return_copies_of_mutable_configuration(self):
        config, shared = load_config()
        terms = config.get_search_terms()
        terms.clear()
        self.assertEqual(shared.search_terms, ["Shared role one", "Shared role two"])

    def test_invalid_range_fails_before_searching(self):
        for minimum, maximum in [(3, 2), (-1, 3), (2.5, 3), (True, 3), (2, "3")]:
            with self.subTest(minimum=minimum, maximum=maximum):
                config, _ = load_config({"experience_min": minimum, "experience_max": maximum})
                with self.assertRaises(ValueError):
                    config.get_experience_years()

    def test_old_settings_experience_override_still_works_without_new_file(self):
        config, shared = load_config(settings_values={"naukri_experience_years": 4})
        self.assertEqual(config.get_experience_years(), 4)
        self.assertEqual(shared.current_experience, 2)

    def test_nested_import_errors_are_not_hidden_as_missing_optional_config(self):
        with patch("importlib.import_module", side_effect=ModuleNotFoundError(name="missing_dependency")):
            with self.assertRaises(ModuleNotFoundError):
                load_config(PREFERENCES)


if __name__ == "__main__":
    unittest.main()

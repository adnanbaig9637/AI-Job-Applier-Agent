"""Optional real Chrome checks of Naukri state detection using local HTML only.

Set NAUKRI_TEST_CHROMEDRIVER to an existing compatible ChromeDriver executable,
then run ``python -B -m unittest discover -s tests -p test_naukri_search_browser.py -v``.
The fixtures cannot load external resources, submit forms, or access credentials.
"""

import os
from pathlib import Path
import unittest
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


DRIVER_PATH = os.environ.get("NAUKRI_TEST_CHROMEDRIVER")


@unittest.skipUnless(DRIVER_PATH, "Set NAUKRI_TEST_CHROMEDRIVER to run local Chrome tests")
class LocalChromeSearchStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_naukri_search import load_search

        if not Path(DRIVER_PATH).is_file():
            raise unittest.SkipTest("NAUKRI_TEST_CHROMEDRIVER is not an existing executable")
        cls.search = load_search()[0]
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--window-size=1280,900")
        cls.driver = webdriver.Chrome(service=Service(DRIVER_PATH), options=options)
        cls.addClassCleanup(cls.driver.quit)

    def state_for(self, body):
        html = """<!doctype html><html><head><meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy"
              content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'">
        </head><body>""" + body + "</body></html>"
        self.driver.get("data:text/html;charset=utf-8," + quote(html))
        self.assertEqual(self.driver.execute_script("return location.protocol"), "data:")
        return self.search._search_state(self.driver)

    def test_screenshot_loading_error_is_detected_in_div_and_span(self):
        for body in (
            "<div>Oops! Something went wrong.</div>",
            "<div><span>There was an error loading the page.</span> Please reload to view the content.</div>",
            "<div><span>Oops! <strong>Something went wrong.</strong></span></div>",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.state_for(body), "error")

    def test_explicit_empty_result_is_detected(self):
        for body in (
            "<div>No jobs found</div>",
            "<p>Your search did not match any jobs</p>",
            "<section class='no-result'>Nothing to show</section>",
            "<p>No <strong>jobs</strong> found</p>",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.state_for(body), "empty")

    def test_visible_job_card_is_a_result(self):
        state = self.state_for("<div class='srp-jobtuple-wrapper'>AI Engineer</div>")

        self.assertEqual(state, "results")
        self.assertEqual(len(self.search.get_job_cards(self.driver)), 1)

    def test_hidden_messages_and_job_cards_are_ignored(self):
        state = self.state_for("""
            <div hidden>Oops! Something went wrong.</div>
            <div style="display:none">There was an error loading the page.</div>
            <div hidden>No jobs found</div>
            <section class="no-result" style="display:none">Nothing to show</section>
            <div class="srp-jobtuple-wrapper" hidden>AI Engineer</div>
            <h1 hidden>Access denied</h1>
            <div>Loading...</div>""")

        self.assertFalse(state)
        self.assertEqual(self.search.get_job_cards(self.driver), [])

    def test_visible_access_gate_is_blocked_regardless_of_container(self):
        for body in (
            "<h1>Access denied</h1>",
            "<div>Access denied</div>",
            "<span>Verify you are human</span>",
            "<p>Verify that you are human</p>",
            "<p>We detected unusual traffic</p>",
        ):
            with self.subTest(body=body):
                self.assertEqual(self.state_for(body), "blocked")

    def test_visible_captcha_frame_is_blocked(self):
        # about:blank is local; CSP disallows even loading the fixture frame.
        self.assertEqual(self.state_for(
            '<iframe src="about:blank#captcha" title="Verification"></iframe>'
        ), "blocked")

    def test_hidden_access_text_inside_visible_container_is_ignored(self):
        state = self.state_for('<p>Loading...<span hidden>Access denied</span></p>')

        self.assertFalse(state)

    def test_error_takes_precedence_over_stale_visible_cards(self):
        self.assertEqual(self.state_for("""
            <div class="srp-jobtuple-wrapper">Previous result</div>
            <div>Oops! Something went wrong.</div>"""), "error")


if __name__ == "__main__":
    unittest.main()

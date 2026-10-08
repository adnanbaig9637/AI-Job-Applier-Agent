"""Optional Chrome regressions against local HTML, with fake credentials only.

Set LINKEDIN_TEST_CHROMEDRIVER to an existing compatible ChromeDriver executable,
then run ``python -B -m unittest discover -s tests -p test_linkedin_login_browser.py -v``.
These tests never import the bot, open LinkedIn, or submit an external form.
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

from modules import linkedin_login


DRIVER_PATH = os.environ.get("LINKEDIN_TEST_CHROMEDRIVER")
FAKE_USERNAME = "fixture@example.invalid"
FAKE_PASSWORD = "fixture-password-only"


@unittest.skipUnless(DRIVER_PATH, "Set LINKEDIN_TEST_CHROMEDRIVER to run local Chrome tests")
class LocalChromeLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Path(DRIVER_PATH).is_file():
            raise unittest.SkipTest("LINKEDIN_TEST_CHROMEDRIVER is not an existing executable")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--window-size=1280,900")
        cls.driver = webdriver.Chrome(service=Service(DRIVER_PATH), options=options)
        cls.addClassCleanup(cls.driver.quit)

    def load_fixture(self, fields, delay_ms=0):
        # CSP blocks all resources and form navigation, even if preventDefault
        # is accidentally removed from the fixture's submission handler.
        html = """<!doctype html><html><head><meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy"
              content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; form-action 'none'">
        </head><body><main id="fixture"></main><script>
        window.submissions = [];
        window.ssoClicks = 0;
        document.addEventListener('submit', event => {
            event.preventDefault();
            window.submissions.push(Object.fromEntries(new FormData(event.target)));
        });
        setTimeout(() => {
            document.getElementById('fixture').innerHTML = FIELDS;
        }, DELAY);
        </script></body></html>""".replace("FIELDS", json.dumps(fields)).replace("DELAY", str(delay_ms))
        self.driver.get("data:text/html;charset=utf-8," + quote(html))
        self.assertEqual(self.driver.execute_script("return location.protocol"), "data:")

    def submit(self, timeout=3):
        # Only the Python-level origin guard is patched. Chrome still hosts a
        # local data document; selectors, visibility, typing and clicks are real.
        with patch.object(WebDriver, "current_url", new_callable=PropertyMock,
                          return_value=linkedin_login.LOGIN_URL):
            return linkedin_login.submit_credentials(
                self.driver, FAKE_USERNAME, FAKE_PASSWORD, timeout=timeout
            )

    def assert_submission(self):
        self.assertEqual(self.driver.execute_script("return window.submissions"), [
            {"email": FAKE_USERNAME, "secret": FAKE_PASSWORD}
        ])
        self.assertEqual(self.driver.execute_script("return location.protocol"), "data:")
        self.assertEqual(self.driver.execute_script("return window.ssoClicks"), 0)

    def test_label_linked_arbitrary_ids_and_nested_button_label(self):
        self.load_fixture("""
            <button type="button" onclick="window.ssoClicks++">Sign in with Microsoft</button>
            <form><label for="identity-941">Email or phone</label>
                <input id="identity-941" name="email" type="text">
                <label for="secret-638">Password</label>
                <input id="secret-638" name="secret" type="password">
                <button type="submit"><span>Sign in</span></button>
            </form>""")

        self.assertTrue(self.submit())
        self.assert_submission()

    def test_hidden_old_ids_are_skipped_for_names_and_autocomplete(self):
        self.load_fixture("""
            <input id="username" style="display:none"><input id="password" style="display:none">
            <form><input name="session_key" autocomplete="username">
                <input name="session_password" autocomplete="current-password" type="password">
                <button type="submit"><span>Sign in</span></button>
            </form>""")

        self.assertTrue(self.submit())
        self.assertEqual(self.driver.execute_script("return window.submissions"), [
            {"session_key": FAKE_USERNAME, "session_password": FAKE_PASSWORD}
        ])
        self.assertEqual(self.driver.execute_script(
            "return [document.getElementById('username').value, document.getElementById('password').value]"
        ), ["", ""])

    def test_waits_for_delayed_rendering_and_autocomplete_fields(self):
        self.load_fixture("""
            <form><input name="email" autocomplete="username">
                <input name="secret" autocomplete="current-password" type="password">
                <button type="submit"><span>Sign in</span></button>
            </form>""", delay_ms=700)

        self.assertTrue(self.submit())
        self.assert_submission()

    def test_missing_password_never_types_username_or_submits(self):
        self.load_fixture("""
            <form><input name="email" autocomplete="username">
                <button type="submit"><span>Sign in</span></button>
            </form>""")

        with self.assertRaises(TimeoutException):
            self.submit(timeout=0.1)
        self.assertEqual(self.driver.execute_script("return window.submissions"), [])
        self.assertEqual(self.driver.execute_script("return document.querySelector('input').value"), "")
        self.assertEqual(self.driver.execute_script("return location.protocol"), "data:")


if __name__ == "__main__":
    unittest.main()

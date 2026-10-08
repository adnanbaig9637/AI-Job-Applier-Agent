"""Offline regressions for LinkedIn authentication, without importing the bot.

Run with: .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import ElementNotInteractableException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from modules import linkedin_login


def fast_wait(driver, timeout, **kwargs):
    """Use Selenium's real polling, with short intervals for offline fixtures."""
    return WebDriverWait(driver, timeout, poll_frequency=0.001, **kwargs)


class FakeElement:
    def __init__(self, name, actions, displayed=True, enabled=True, retain_value=True):
        self.name = name
        self.actions = actions
        self.displayed = displayed
        self.enabled = enabled
        self.retain_value = retain_value
        self.value = ""
        self.children = {}

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return self.enabled

    def clear(self):
        self.actions.append((self.name, "clear"))
        self.value = ""

    def send_keys(self, value):
        self.actions.append((self.name, "fill"))
        if self.retain_value:
            self.value += value

    def get_attribute(self, name):
        return self.value if name == "value" else None

    def click(self):
        self.actions.append((self.name, "click"))

    def find_elements(self, by, selector):
        return self.children.get((by, selector), [])


class CredentialSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.actions = []
        self.user = FakeElement("username", self.actions)
        self.password = FakeElement("password", self.actions)
        self.button = FakeElement("signin", self.actions)
        self.driver = Mock()
        self.driver.current_url = "https://www.linkedin.com/login"
        self.elements = {
            linkedin_login.USERNAME_LOCATORS[0]: [self.user],
            linkedin_login.PASSWORD_LOCATORS[0]: [self.password],
            linkedin_login.SUBMIT_LOCATORS[0]: [self.button],
        }
        self.driver.find_elements.side_effect = lambda by, selector: self.elements.get((by, selector), [])
        self.wait_patch = patch.object(linkedin_login, "WebDriverWait", side_effect=fast_wait)
        self.wait_patch.start()
        self.addCleanup(self.wait_patch.stop)

    def submit(self):
        return linkedin_login.submit_credentials(self.driver, " test@example.invalid ", "test-password", timeout=0.03)

    def test_both_credentials_are_filled_before_submission(self):
        self.assertTrue(self.submit())

        self.assertEqual(self.user.value, "test@example.invalid")
        self.assertEqual(self.password.value, "test-password")
        self.assertEqual(self.actions, [
            ("username", "clear"), ("username", "fill"),
            ("password", "clear"), ("password", "fill"), ("signin", "click"),
        ])

    def test_delayed_password_does_not_cause_partial_fill(self):
        password_polls = 0

        def find(by, selector):
            nonlocal password_polls
            if (by, selector) == linkedin_login.PASSWORD_LOCATORS[0]:
                password_polls += 1
                if password_polls < 3:
                    self.assertEqual(self.actions, [])
                    return []
            return self.elements.get((by, selector), [])

        self.driver.find_elements.side_effect = find

        self.assertTrue(self.submit())
        self.assertGreaterEqual(password_polls, 3)
        self.assertEqual(self.actions[-1], ("signin", "click"))

    def test_hidden_disabled_and_stale_duplicates_are_skipped(self):
        hidden = FakeElement("hidden-user", self.actions, displayed=False)
        disabled = FakeElement("disabled-user", self.actions, enabled=False)
        stale = Mock()
        stale.is_displayed.side_effect = StaleElementReferenceException()
        self.elements[linkedin_login.USERNAME_LOCATORS[0]] = [hidden, disabled, stale, self.user]

        self.assertTrue(self.submit())
        self.assertFalse(any(name in ("hidden-user", "disabled-user") for name, _ in self.actions))

    def test_missing_password_never_fills_or_submits(self):
        self.elements[linkedin_login.PASSWORD_LOCATORS[0]] = []

        with self.assertRaises(TimeoutException):
            self.submit()
        self.assertEqual(self.actions, [])

    def test_unretained_field_value_prevents_submission(self):
        self.password.retain_value = False

        with self.assertRaises(ElementNotInteractableException):
            self.submit()
        self.assertNotIn(("signin", "click"), self.actions)

    def test_autocomplete_fields_work_when_old_ids_are_absent(self):
        self.elements.pop(linkedin_login.USERNAME_LOCATORS[0])
        self.elements.pop(linkedin_login.PASSWORD_LOCATORS[0])
        self.elements[(By.CSS_SELECTOR, 'input[autocomplete="username"], input[autocomplete="email"], input[type="email"]')] = [self.user]
        self.elements[(By.CSS_SELECTOR, 'input[autocomplete="current-password"], input[type="password"]')] = [self.password]

        self.assertTrue(self.submit())
        self.assertEqual(self.actions[-1], ("signin", "click"))

    def test_nested_signin_button_is_found_inside_credential_form(self):
        form = FakeElement("form", self.actions)
        form.children[(By.XPATH, './/button[@type="submit" and normalize-space(.)="Sign in"]')] = [self.button]
        self.password.children[(By.XPATH, './ancestor::form[1]')] = [form]
        unrelated = FakeElement("unrelated-submit", self.actions)
        self.elements[linkedin_login.SUBMIT_LOCATORS[0]] = [unrelated]

        self.assertTrue(self.submit())
        self.assertEqual(self.actions[-1], ("signin", "click"))
        self.assertNotIn(("unrelated-submit", "click"), self.actions)

    def test_generic_submit_is_only_used_inside_credential_form(self):
        form = FakeElement("form", self.actions)
        form.children[(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')] = [self.button]
        self.password.children[(By.XPATH, './ancestor::form[1]')] = [form]
        self.elements.pop(linkedin_login.SUBMIT_LOCATORS[0])

        self.assertTrue(self.submit())
        self.assertEqual(self.actions[-1], ("signin", "click"))

    def test_external_page_never_receives_credentials(self):
        self.driver.current_url = "https://example.com/login"

        with self.assertRaises(TimeoutException):
            self.submit()
        self.assertEqual(self.actions, [])


class AuthenticationStateTests(unittest.TestCase):
    def make_driver(self, url):
        driver = Mock()
        driver.current_url = url
        driver.find_elements.return_value = []
        return driver

    def test_feed_with_query_is_authenticated_without_navigation(self):
        driver = self.make_driver("https://www.linkedin.com/feed/?trk=login")

        self.assertTrue(linkedin_login.is_logged_in(driver))
        driver.get.assert_not_called()
        driver.refresh.assert_not_called()

    def test_unauthenticated_and_external_urls_are_rejected(self):
        for url in (
            "https://www.linkedin.com/login",
            "https://www.linkedin.com/checkpoint/challenge/123",
            "https://www.linkedin.com/uas/login",
            "https://www.linkedin.com/",
            "https://www.linkedin.com/jobs/",
            "https://example.com/feed/",
            "https://www.linkedin.com.example.com/feed/",
        ):
            with self.subTest(url=url):
                driver = self.make_driver(url)
                self.assertFalse(linkedin_login.is_logged_in(driver))
                driver.get.assert_not_called()
                driver.refresh.assert_not_called()

    def test_visible_authenticated_navigation_recognizes_jobs_session(self):
        driver = self.make_driver("https://www.linkedin.com/jobs/")
        nav = FakeElement("nav", [])
        driver.find_elements.side_effect = lambda by, selector: (
            [nav] if (by, selector) == linkedin_login.AUTHENTICATED_LOCATORS[0] else []
        )

        self.assertTrue(linkedin_login.is_logged_in(driver))
        nav.displayed = False
        self.assertFalse(linkedin_login.is_logged_in(driver))

    def test_login_form_takes_precedence_over_feed_url(self):
        driver = self.make_driver("https://www.linkedin.com/feed/")
        password = FakeElement("password", [])
        driver.find_elements.side_effect = lambda by, selector: (
            [password] if (by, selector) == linkedin_login.PASSWORD_LOCATORS[0] else []
        )

        self.assertFalse(linkedin_login.is_logged_in(driver))

    def test_challenge_takes_precedence_over_authenticated_navigation(self):
        driver = self.make_driver("https://www.linkedin.com/checkpoint/challenge/123")
        driver.find_elements.return_value = [FakeElement("nav", [])]

        self.assertFalse(linkedin_login.is_logged_in(driver))


class LoginFlowTests(unittest.TestCase):
    def setUp(self):
        self.driver = Mock()
        self.driver.current_url = "https://www.linkedin.com/login"
        self.driver.find_elements.return_value = []
        def finish_manual_login():
            self.driver.current_url = "https://www.linkedin.com/feed/"
            return True

        self.manual_login = Mock(side_effect=finish_manual_login)
        self.log = Mock()
        self.fields_patch = patch.object(linkedin_login, "_credential_fields", return_value=(Mock(), Mock()))
        self.fields_patch.start()
        self.addCleanup(self.fields_patch.stop)
        self.wait_patch = patch.object(linkedin_login, "WebDriverWait", side_effect=fast_wait)
        self.wait_patch.start()
        self.addCleanup(self.wait_patch.stop)

    def login(self, username="test@example.invalid", password="test-password"):
        return linkedin_login.login(
            self.driver,
            username,
            password,
            manual_login=self.manual_login,
            log=self.log,
            timeout=0.01,
        )

    def test_existing_session_skips_credentials_and_manual_login(self):
        with patch.object(linkedin_login, "is_logged_in", return_value=True), patch.object(
            linkedin_login, "submit_credentials"
        ) as submit:
            self.assertTrue(self.login())

        submit.assert_not_called()
        self.manual_login.assert_not_called()

    def test_successful_automatic_login_skips_manual_prompt(self):
        def submit(*args, **kwargs):
            self.driver.current_url = "https://www.linkedin.com/feed/"
            return True

        with patch.object(linkedin_login, "submit_credentials", side_effect=submit) as fill:
            self.assertTrue(self.login())

        self.assertEqual(fill.call_count, 1)
        self.manual_login.assert_not_called()

    def test_missing_credentials_use_manual_login_without_form_fill(self):
        for username, password in (("", "password"), ("test@example.invalid", ""), (None, None),
                                   ("username@example.com", "example_password")):
            with self.subTest(username=username, password_present=bool(password)):
                self.driver.current_url = "https://www.linkedin.com/login"
                self.manual_login.reset_mock()
                with patch.object(linkedin_login, "submit_credentials") as submit:
                    self.assertTrue(self.login(username, password))

                submit.assert_not_called()
                self.manual_login.assert_called_once_with()

    def test_missing_fields_fall_back_without_logging_credentials(self):
        with patch.object(
            linkedin_login, "submit_credentials",
            side_effect=TimeoutException("Rejected test@example.invalid / test-password")
        ) as submit:
            self.assertTrue(self.login())

        self.assertEqual(submit.call_count, 1)
        self.manual_login.assert_called_once_with()
        logged = " ".join(str(call) for call in self.log.call_args_list)
        self.assertNotIn("test@example.invalid", logged)
        self.assertNotIn("test-password", logged)

    def test_challenge_after_submission_is_handed_to_manual_login(self):
        def submit(*args, **kwargs):
            self.driver.current_url = "https://www.linkedin.com/checkpoint/challenge/123"
            return True

        with patch.object(
            linkedin_login, "submit_credentials", side_effect=submit
        ) as fill:
            self.assertTrue(self.login())

        self.assertEqual(fill.call_count, 1)
        self.manual_login.assert_called_once_with()

    def test_failed_manual_login_returns_false(self):
        self.manual_login.side_effect = None
        self.manual_login.return_value = False
        with patch.object(
            linkedin_login, "submit_credentials", side_effect=TimeoutException("No usable fields")
        ):
            self.assertFalse(self.login())

    def test_manual_confirmation_without_authenticated_session_returns_false(self):
        self.manual_login.side_effect = None
        self.manual_login.return_value = True
        with patch.object(linkedin_login, "submit_credentials", side_effect=TimeoutException("No usable fields")):
            self.assertFalse(self.login())


if __name__ == "__main__":
    unittest.main()

"""LinkedIn authentication without browser-launch or personal-config side effects."""

from collections.abc import Callable
from urllib.parse import urlparse

from selenium.common.exceptions import (
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait


LOGIN_URL = "https://www.linkedin.com/login"
USERNAME_LOCATORS = (
    (By.CSS_SELECTOR, 'input#username, input[name="session_key"], input[name="username"]'),
    (By.CSS_SELECTOR, 'input[autocomplete="username"], input[autocomplete="email"], input[type="email"]'),
    (By.XPATH, '//input[@id = //label[contains(translate(normalize-space(.), '
     '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "email")]/@for]'),
)
PASSWORD_LOCATORS = (
    (By.CSS_SELECTOR, 'input#password, input[name="session_password"], input[name="password"]'),
    (By.CSS_SELECTOR, 'input[autocomplete="current-password"], input[type="password"]'),
)
SUBMIT_LOCATORS = (
    (By.CSS_SELECTOR, 'button[data-litms-control-urn="login-submit"]'),
    (By.XPATH, './/button[@type="submit" and normalize-space(.)="Sign in"]'),
    (By.XPATH, './/button[normalize-space(.)="Sign in"]'),
    (By.CSS_SELECTOR, 'input[type="submit"][value="Sign in"]'),
)
AUTHENTICATED_LOCATORS = (
    (By.CSS_SELECTOR, '#global-nav, nav.global-nav, .global-nav__me'),
    (By.CSS_SELECTOR, 'a[href*="/mynetwork/"][data-test-global-nav-link], '
     'button[data-control-name="nav.settings"]'),
)
PROFILE_LOCATORS = ((By.CSS_SELECTOR, '.profile__details'),)


def _is_linkedin(url: str) -> bool:
    """Only recognize LinkedIn HTTPS pages as credential/session destinations."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "linkedin.com" or host.endswith(".linkedin.com"))


def _visible_element(scope: WebDriver | WebElement, locators: tuple, enabled: bool = True) -> WebElement | None:
    """Try all locator candidates per poll, ignoring hidden duplicates and stale nodes."""
    for by, value in locators:
        for element in scope.find_elements(by, value):
            try:
                if element.is_displayed() and (not enabled or element.is_enabled()):
                    return element
            except StaleElementReferenceException:
                continue
    return None


def is_logged_in(driver: WebDriver) -> bool:
    """Read session evidence without clicking links or submitting the sign-in form."""
    url = driver.current_url
    if not _is_linkedin(url):
        return False
    path = urlparse(url).path.lower().rstrip("/")
    if any(path == prefix or path.startswith(prefix + "/") for prefix in
           ("/login", "/checkpoint", "/challenge", "/authwall", "/uas", "/signup", "/start")):
        return False
    if _visible_element(driver, PASSWORD_LOCATORS, enabled=False):
        return False
    return (path == "/feed" or path.startswith("/feed/")
            or _visible_element(driver, AUTHENTICATED_LOCATORS, enabled=False) is not None)


def _credential_fields(driver: WebDriver) -> tuple[WebElement, WebElement] | bool:
    """Wait for both editable credential fields, including dynamically assigned IDs."""
    if not _is_linkedin(driver.current_url):
        return False
    user_field = _visible_element(driver, USERNAME_LOCATORS)
    password_field = _visible_element(driver, PASSWORD_LOCATORS)
    return (user_field, password_field) if user_field is not None and password_field is not None else False


def submit_credentials(driver: WebDriver, username: str, password: str, timeout: float = 20) -> bool:
    """Fill both fields before submitting the credential form; never log their values."""
    wait = WebDriverWait(driver, timeout, ignored_exceptions=(StaleElementReferenceException,))
    user_field, password_field = wait.until(_credential_fields)
    for field, value in ((user_field, username.strip()), (password_field, password)):
        field.clear()
        field.send_keys(value)
    if (user_field.get_attribute("value") != username.strip()
            or password_field.get_attribute("value") != password):
        raise ElementNotInteractableException("LinkedIn did not retain both credential fields; sign-in was not submitted.")

    def find_submit(browser: WebDriver) -> WebElement | None:
        """Keep generic submit buttons scoped to the password field's own form."""
        if not _is_linkedin(browser.current_url):
            return None
        field = _visible_element(browser, PASSWORD_LOCATORS)
        if field is None:
            return None
        forms = field.find_elements(By.XPATH, './ancestor::form[1]')
        if forms:
            return (_visible_element(forms[0], SUBMIT_LOCATORS)
                    or _visible_element(forms[0], ((By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]'),)))
        return _visible_element(browser, SUBMIT_LOCATORS)

    wait.until(find_submit).click()
    return True


def login(driver: WebDriver, username: str, password: str,
          manual_login: Callable[[], bool], log: Callable[[str], None] = print,
          timeout: float = 20) -> bool:
    """Attempt one automatic sign-in, then let the user complete login or verification."""
    driver.get(LOGIN_URL)
    if is_logged_in(driver):
        return True
    user = (username or "").strip()
    pwd = password or ""
    if not user or user == "username@example.com" or not pwd.strip() or pwd == "example_password":
        log("LinkedIn credentials are missing in config/secrets.py. Please sign in in the open browser.")
    else:
        try:
            wait = WebDriverWait(driver, timeout, ignored_exceptions=(StaleElementReferenceException,))

            def ready(browser: WebDriver) -> str | bool:
                if is_logged_in(browser):
                    return "authenticated"
                if _credential_fields(browser):
                    return "form"
                if _is_linkedin(browser.current_url) and _visible_element(browser, PROFILE_LOCATORS):
                    return "profile"
                return False

            state = wait.until(ready)
            if state == "authenticated":
                return True
            if state == "profile":
                _visible_element(driver, PROFILE_LOCATORS).click()
                state = wait.until(lambda browser: "authenticated" if is_logged_in(browser)
                                   else "form" if _credential_fields(browser) else False)
                if state == "authenticated":
                    return True
            submit_credentials(driver, user, pwd, timeout)
            wait.until(is_logged_in)
            log("LinkedIn login successful!")
            return True
        except (TimeoutException, WebDriverException) as error:
            # Selenium exception text/page sources can contain entered values.
            log(f"LinkedIn automatic sign-in could not be completed ({type(error).__name__}).")

    log("Complete LinkedIn sign-in, including any CAPTCHA or verification code, in the open browser.")
    return bool(manual_login()) and is_logged_in(driver)

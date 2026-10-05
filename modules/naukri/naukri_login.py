'''
Naukri login detection and login flow.

Mirrors the user experience of `is_logged_in_LN()` / `login_LN()` in
`runAiBot.py`: try to log in with the configured credentials, and if that
fails for any reason hand control to the human via `manual_login_retry()`
and continue automatically once they are done.
'''

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from modules.helpers import print_lg, buffer, manual_login_retry, sleep
from modules.clickers_and_finders import try_xp
from modules.naukri import naukri_dialogs
from modules.naukri.naukri_config import get_credentials, credentials_are_placeholders


NAUKRI_HOME = "https://www.naukri.com/"
NAUKRI_LOGIN_URL = "https://www.naukri.com/nlogin/login"

# Any one of these present means we are logged in. Multiple variants are listed
# because Naukri ships different headers to different accounts/experiments.
LOGGED_IN_XPATHS = [
    '//div[contains(@class, "nI-gNb-drawer__bars")]',
    '//div[contains(@class, "view-profile-wrapper")]',
    '//a[contains(@href, "/mnjuser/profile")]',
    '//div[contains(@class, "nI-gNb-info")]',
    '//*[contains(@class, "nI-gNb-menuItems")]',
]

# Any one of these present means we are logged out.
LOGGED_OUT_XPATHS = [
    '//*[@id="login_Layer"]',
    '//a[normalize-space()="Login"]',
    '//div[normalize-space()="Login" and contains(@class, "nI-gNb-lg-rg__login")]',
    '//button[normalize-space()="Login"]',
]

# Cookies Naukri sets once a session is authenticated.
SESSION_COOKIES = ("nauk_at", "nauk_rt", "ni_user", "NKWAP")

# How long to wait for a human to finish logging in when dialogs are unavailable.
MANUAL_LOGIN_WAIT_SECS = 300
POLL_INTERVAL_SECS = 5


def _has_session_cookie(driver: WebDriver) -> bool:
    try:
        names = {cookie.get('name') for cookie in driver.get_cookies()}
    except Exception:
        return False
    return any(name in names for name in SESSION_COOKIES)


def is_logged_in_NK(driver: WebDriver) -> bool:
    '''
    Checks whether the user is logged in to Naukri.
    * Returns `True` if logged in, `False` otherwise.
    * Deliberately layered: URL check -> logged-out markers -> logged-in markers
      -> session cookie, so a single markup change can't break detection.
    '''
    try:
        current_url = (driver.current_url or "").lower()
    except Exception:
        return False

    if "nlogin/login" in current_url or "/registration/" in current_url:
        return False

    # Logged-in only pages redirect away when the session is gone.
    if "/mnjuser/" in current_url:
        return True

    for xpath in LOGGED_OUT_XPATHS:
        if try_xp(driver, xpath, False):
            return False

    for xpath in LOGGED_IN_XPATHS:
        if try_xp(driver, xpath, False):
            return True

    if _has_session_cookie(driver):
        print_lg("Found a Naukri session cookie, assuming user is logged in!")
        return True

    print_lg("Couldn't confirm Naukri login state from the page, assuming NOT logged in.")
    return False


def _is_logged_in_after_navigation(driver: WebDriver) -> bool:
    '''
    Wrapper handed to `manual_login_retry()`. Navigates home first, because the
    user may have finished logging in on a completely different Naukri page.
    '''
    try:
        driver.get(NAUKRI_HOME)
        buffer(2)
    except Exception as e:
        print_lg("Failed to reload Naukri home while confirming login.", e)
    return is_logged_in_NK(driver)


def _await_manual_login(driver: WebDriver, limit: int = 2) -> None:
    '''
    Hands control to the human to finish logging in.

    Uses the shared `manual_login_retry()` so the experience matches LinkedIn's.
    That helper shows a Tk dialog, which is unavailable on some machines, so we
    fall back to polling the page and logging progress instead of failing.
    '''
    try:
        manual_login_retry(lambda: _is_logged_in_after_navigation(driver), limit)
        return
    except Exception as e:
        print_lg("Couldn't show the login dialog "
                 f"({type(e).__name__}). Falling back to waiting for you to log in.", e)

    print_lg(f"\n>>> Please log in to Naukri in the open browser window. "
             f"Waiting up to {MANUAL_LOGIN_WAIT_SECS // 60} minutes... <<<\n")
    waited = 0
    while waited < MANUAL_LOGIN_WAIT_SECS:
        sleep(POLL_INTERVAL_SECS)
        waited += POLL_INTERVAL_SECS
        if is_logged_in_NK(driver):
            return print_lg("Detected a Naukri login, continuing!")
        if waited % 60 == 0:
            print_lg(f"  ...still waiting for the Naukri login ({waited // 60} min).")
    print_lg("Gave up waiting for a manual Naukri login, continuing anyway.")


def _fill_login_form(driver: WebDriver, wait: WebDriverWait, user: str, pwd: str) -> bool:
    '''
    Fills and submits Naukri's login form. Returns `True` if the form was submitted.
    Tries several field locators since Naukri has shipped a few login layouts.
    '''
    username_locators = [
        (By.ID, "usernameField"),
        (By.XPATH, '//input[@placeholder="Enter your active Email ID / Username"]'),
        (By.XPATH, '//input[@type="text" and contains(@class, "login")]'),
        (By.NAME, "email"),
    ]
    password_locators = [
        (By.ID, "passwordField"),
        (By.XPATH, '//input[@placeholder="Enter your password"]'),
        (By.XPATH, '//input[@type="password"]'),
        (By.NAME, "password"),
    ]
    submit_locators = [
        (By.XPATH, '//button[@type="submit" and normalize-space()="Login"]'),
        (By.XPATH, '//button[normalize-space()="Login"]'),
        (By.XPATH, '//button[@type="submit"]'),
    ]

    def _first(locators, timeout=5.0):
        for by, value in locators:
            try:
                return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
            except Exception:
                continue
        return None

    username_field = _first(username_locators, 8.0)
    if not username_field:
        print_lg("Couldn't find the Naukri username field.")
        return False
    password_field = _first(password_locators, 3.0)
    if not password_field:
        print_lg("Couldn't find the Naukri password field.")
        return False

    try:
        username_field.clear()
        username_field.send_keys(user)
        password_field.clear()
        password_field.send_keys(pwd)
    except Exception as e:
        print_lg("Failed to type Naukri credentials.", e)
        return False

    submit = _first(submit_locators, 3.0)
    if not submit:
        print_lg("Couldn't find the Naukri login submit button.")
        return False
    try:
        submit.click()
        return True
    except Exception as e:
        print_lg("Failed to click the Naukri login button.", e)
        return False


def login_NK(driver: WebDriver, wait: WebDriverWait) -> None:
    '''
    Logs in to Naukri.
    * Uses `naukri_username` / `naukri_password` from `secrets.py`, falling back
      to the shared `username` / `password`.
    * If credentials are missing or the automatic attempt fails, pauses and lets
      the human log in, then continues automatically.
    '''
    user, pwd = get_credentials()

    if credentials_are_placeholders():
        message = ("Naukri credentials are not configured in config/secrets.py, "
                   "so the bot can't login automatically. Please login manually!")
        print_lg(message)
        naukri_dialogs.alert(message, "Login Manually", "Okay")
        driver.get(NAUKRI_LOGIN_URL)
        _await_manual_login(driver)
        return

    try:
        driver.get(NAUKRI_LOGIN_URL)
        buffer(2)
        submitted = _fill_login_form(driver, wait, user, pwd)
        if submitted:
            # Naukri lands on the dashboard/homepage after a successful login.
            for _ in range(10):
                sleep(1)
                if is_logged_in_NK(driver):
                    return print_lg("Naukri login successful!")
    except Exception as e:
        print_lg("Naukri automatic login attempt failed.", e)

    print_lg("Seems like the Naukri login attempt failed! Possibly wrong credentials, "
             "a captcha/OTP challenge, or you're already logged in. Please login manually!")
    _await_manual_login(driver)


def ensure_logged_in(driver: WebDriver, wait: WebDriverWait) -> bool:
    '''
    Opens Naukri, checks the login state and logs in if needed.
    * Returns `True` when we end up logged in.
    '''
    driver.get(NAUKRI_HOME)
    buffer(2)
    if is_logged_in_NK(driver):
        print_lg("Already logged in to Naukri!")
        return True
    print_lg("Not logged in to Naukri, attempting login...")
    login_NK(driver, wait)
    logged_in = _is_logged_in_after_navigation(driver)
    print_lg("Logged in to Naukri!" if logged_in
             else "Continuing without a confirmed Naukri login, some steps may fail.")
    return logged_in

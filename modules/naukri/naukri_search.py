'''
Naukri job search: URL building, result-card scraping and pagination.

Naukri changes its result markup fairly often and ships different variants to
different accounts, so every lookup here goes through an ordered list of
selectors and falls back to a text-based strategy rather than depending on one
rigid structure.
'''

import re
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from config.search import search_location
from config.settings import click_gap

from modules.helpers import print_lg, buffer, sleep
from modules.clickers_and_finders import try_xp, scroll_to_view
from modules.naukri import naukri_config


NAUKRI_BASE = "https://www.naukri.com"

# Ordered candidates for the container of a single job result.
JOB_CARD_SELECTORS = [
    (By.CSS_SELECTOR, "div.srp-jobtuple-wrapper"),
    (By.CSS_SELECTOR, "article.jobTuple"),
    (By.CSS_SELECTOR, "div.jobTuple"),
    (By.CSS_SELECTOR, "div[data-job-id]"),
    (By.XPATH, "//div[contains(@class,'cust-job-tuple')]"),
]

# Ordered candidates for fields inside a job card.
TITLE_SELECTORS = ["a.title", "a.jobTupleHeader", "a[title]"]
COMPANY_SELECTORS = ["a.comp-name", "a.subTitle", "span.comp-name", "a[class*='comp']"]
EXPERIENCE_SELECTORS = ["span.expwdth", "li.experience span.ellipsis", "li.experience", "span[title*='Yrs']"]
SALARY_SELECTORS = ["span.sal-wrap span", "span.sal", "li.salary span.ellipsis", "li.salary"]
LOCATION_SELECTORS = ["span.locWdth", "li.location span.ellipsis", "li.location"]
DESCRIPTION_SELECTORS = ["span.job-desc", "div.job-description", "li.job-description"]
POSTED_SELECTORS = ["span.job-post-day", "div.type span.job-post-day", "span[class*='post-day']"]


def _slugify(text: str) -> str:
    '''Converts a search term or location into Naukri's URL slug form.'''
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"[\s-]+", "-", text).strip("-")
    return text


def build_search_url(keyword: str, page: int = 1,
                     sort_by: str | None = None, date_posted: str | None = None) -> str:
    '''
    Builds a Naukri search results URL from the shared configuration.

    * `keyword` comes from `search_terms` in `config/search.py`.
    * `sort_by` / `date_posted` are passed explicitly so the non-stop run loop
      can cycle them exactly like the LinkedIn bot does.
    '''
    keyword = (keyword or "").strip()
    location = (search_location or "").strip()

    slug = _slugify(keyword) or "jobs"
    path = f"{slug}-jobs"
    if location:
        path += f"-in-{_slugify(location)}"
    if page > 1:
        path += f"-{page}"

    params = [f"k={quote_plus(keyword)}"]
    if location:
        params.append(f"l={quote_plus(location)}")

    experience = naukri_config.get_experience_years()
    if experience is not None:
        params.append(f"experience={experience}")

    job_age = naukri_config.get_job_age(date_posted)
    if job_age:
        params.append(f"jobAge={job_age}")

    sort_value = naukri_config.get_sort(sort_by)
    if sort_value:
        params.append(f"sort={sort_value}")

    work_modes = naukri_config.get_work_modes()
    if work_modes:
        params.append("wfhType=" + quote_plus(",".join(work_modes)))

    if naukri_config.salary_filter:
        params.append(f"ctcFilter={quote_plus(naukri_config.salary_filter)}")

    return f"{NAUKRI_BASE}/{path}?" + "&".join(params)


def _find_all(driver: WebDriver, selectors) -> list[WebElement]:
    '''Returns the first non-empty match from an ordered list of `(By, value)` selectors.'''
    for by, value in selectors:
        try:
            elements = driver.find_elements(by, value)
            if elements:
                return elements
        except Exception:
            continue
    return []


def _text_of(card: WebElement, css_selectors: list[str]) -> str:
    '''First non-empty text found among the given CSS selectors inside `card`.'''
    for selector in css_selectors:
        try:
            for element in card.find_elements(By.CSS_SELECTOR, selector):
                text = (element.get_attribute("title") or element.text or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def open_search(driver: WebDriver, wait: WebDriverWait, keyword: str, page: int = 1,
                sort_by: str | None = None, date_posted: str | None = None) -> bool:
    '''
    Opens a Naukri search results page and waits for the results to render.
    * Returns `True` if at least one result card was found.
    '''
    url = build_search_url(keyword, page, sort_by, date_posted)
    print_lg(f"Opening Naukri search page {page}: {url}")
    driver.get(url)
    buffer(3)

    for attempt in range(3):
        cards = get_job_cards(driver)
        if cards:
            return True
        # Results are lazy rendered; nudge the page and retry before giving up.
        try:
            driver.execute_script("window.scrollBy(0, 400);")
        except Exception:
            pass
        sleep(2)
        if attempt == 1 and _has_no_results(driver):
            print_lg(f'Naukri reported no results for "{keyword}" on page {page}.')
            return False
    print_lg(f'No job cards found for "{keyword}" on page {page}.')
    return False


def _has_no_results(driver: WebDriver) -> bool:
    '''Detects Naukri's explicit "no jobs found" state.'''
    markers = [
        "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'no jobs found')]",
        "//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'did not match any jobs')]",
        "//*[contains(@class, 'no-result')]",
    ]
    return any(try_xp(driver, marker, False) for marker in markers)


def get_job_cards(driver: WebDriver) -> list[WebElement]:
    '''Returns the job result cards currently rendered on the search page.'''
    return _find_all(driver, JOB_CARD_SELECTORS)


def get_card_details(driver: WebDriver, card: WebElement) -> dict:
    '''
    Extracts everything useful from a search result card.

    Returns a dict with `job_id`, `title`, `company`, `work_location`,
    `experience_text`, `salary`, `snippet`, `posted_text` and `job_link`.
    Missing values come back as empty strings / `Unknown` rather than raising,
    so one odd card never aborts a whole search.
    '''
    details = {
        "job_id": "", "title": "", "company": "", "work_location": "",
        "experience_text": "", "salary": "", "snippet": "", "posted_text": "", "job_link": "",
    }

    try:
        scroll_to_view(driver, card)
    except Exception:
        pass

    # Job id: the card attribute is the most reliable, the URL is the fallback.
    for attribute in ("data-job-id", "data-jobid", "id"):
        try:
            value = card.get_attribute(attribute)
        except Exception:
            value = None
        if value and value.strip():
            details["job_id"] = value.strip()
            break

    # Title + link
    title_element = None
    for selector in TITLE_SELECTORS:
        try:
            candidates = card.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            candidates = []
        for candidate in candidates:
            href = candidate.get_attribute("href") or ""
            if "/job-listings-" in href or "naukri.com" in href:
                title_element = candidate
                break
        if title_element:
            break
    if title_element is None:
        # Last resort: any anchor that looks like a Naukri job listing.
        try:
            for anchor in card.find_elements(By.TAG_NAME, "a"):
                if "/job-listings-" in (anchor.get_attribute("href") or ""):
                    title_element = anchor
                    break
        except Exception:
            pass

    if title_element is not None:
        details["title"] = (title_element.get_attribute("title") or title_element.text or "").strip()
        details["job_link"] = (title_element.get_attribute("href") or "").strip()

    if not details["job_id"] and details["job_link"]:
        details["job_id"] = job_id_from_link(details["job_link"])

    details["company"] = _text_of(card, COMPANY_SELECTORS)
    details["experience_text"] = _text_of(card, EXPERIENCE_SELECTORS)
    details["salary"] = _text_of(card, SALARY_SELECTORS)
    details["work_location"] = _text_of(card, LOCATION_SELECTORS)
    details["snippet"] = _text_of(card, DESCRIPTION_SELECTORS)
    details["posted_text"] = _text_of(card, POSTED_SELECTORS)

    return details


def job_id_from_link(job_link: str) -> str:
    '''
    Derives a stable job id from a Naukri job URL.
    Naukri links look like `.../job-listings-python-developer-acme-bangalore-2-to-5-years-010225500123`.
    '''
    if not job_link:
        return ""
    link = job_link.split("?")[0].rstrip("/")
    tail = link.rsplit("-", 1)[-1]
    if tail.isdigit() and len(tail) >= 6:
        return tail
    return link.rsplit("/", 1)[-1]


def apply_ui_filters(driver: WebDriver) -> None:
    '''
    Best-effort UI filters for preferences that have no reliable URL parameter
    (currently `job_type`, and `sort_by` when the URL parameter was ignored).

    Every step is optional: a failure here only means the results are less
    narrow, never that the run stops.
    '''
    labels = naukri_config.get_job_type_labels()
    for label in labels:
        clicked = _click_filter_label(driver, label)
        print_lg(f'{"Applied" if clicked else "Could not apply"} Naukri employment type filter: "{label}"')
        if clicked:
            buffer(click_gap)


def _click_filter_label(driver: WebDriver, label: str) -> bool:
    '''Finds a checkbox/label with the given visible text in Naukri's filter rail and clicks it.'''
    xpaths = [
        f'//div[contains(@class,"filter")]//label[normalize-space()="{label}"]',
        f'//div[contains(@class,"filter")]//span[normalize-space()="{label}"]',
        f'//label[normalize-space()="{label}"]',
        f'//span[normalize-space()="{label}"]/ancestor::label[1]',
    ]
    for xpath in xpaths:
        element = try_xp(driver, xpath, False)
        if not element:
            continue
        try:
            scroll_to_view(driver, element)
            element.click()
            return True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                continue
    return False


def go_to_next_page(driver: WebDriver) -> bool:
    '''
    Clicks Naukri's "Next" pagination control.
    * Returns `True` when the click worked. Callers that get `False` should fall
      back to navigating to the next page URL directly.
    '''
    xpaths = [
        '//a[normalize-space()="Next"]',
        '//span[normalize-space()="Next"]/ancestor::a[1]',
        '//div[contains(@class,"pagination")]//a[contains(@class,"next")]',
    ]
    for xpath in xpaths:
        element = try_xp(driver, xpath, False)
        if not element:
            continue
        try:
            scroll_to_view(driver, element)
            element.click()
            buffer(3)
            return True
        except Exception:
            continue
    return False

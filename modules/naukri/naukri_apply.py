'''
Naukri application flow.

The Naukri counterpart of `apply_to_jobs()` in `runAiBot.py`. It keeps the same
shape (search -> filter -> per job: screen, apply, log) and reuses the same
configuration, helpers and AI providers, but every selector and page
interaction here is Naukri-specific so the LinkedIn flow stays untouched.
'''

import csv
from datetime import datetime
from random import shuffle

from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from config.search import (
    switch_number, randomize_search_order, easy_apply_only,
    pause_after_filters, about_company_bad_words, about_company_good_words,
    bad_words, security_clearance, did_masters, current_experience,
)
import config.settings as _settings_module
from config.settings import (
    click_gap, close_tabs, keep_screen_awake, logs_folder_path, run_in_background,
)
from config.secrets import use_AI, ai_provider
from config.questions import pause_before_submit, pause_at_failed_question

from modules import answers, relevance
from modules.helpers import print_lg, buffer, sleep, calculate_date_posted, critical_error_log, truncate_for_csv
from modules.clickers_and_finders import try_xp, scroll_to_view
from modules.naukri import naukri_config, naukri_search, naukri_questions, naukri_dialogs
from modules.naukri.naukri_config import _opt as _setting

# Optional, backward compatible: fail closed when a job description can't be read.
skip_if_no_description = bool(_setting(_settings_module, 'naukri_skip_if_no_description', True))


#< Run statistics, reported by `runNaukriBot.py` at the end of a run
stats = {
    "applied": 0,          # applications submitted on Naukri
    "external": 0,         # "Apply on company site" links collected
    "failed": 0,
    "skipped": 0,
}

# How many jobs each rule rejected, printed at the end of a run so you can see
# which filter is actually doing the skipping and tune it.
skip_reasons: dict[str, int] = {}


def _note_skip(rejected_jobs: dict, job_id: str, reason: str) -> None:
    '''
    Records why a job was rejected.

    The reason is kept per job id so that re-encountering the same job under a
    later search term can say *why* it was rejected the first time, instead of
    just "previously rejected".
    '''
    rejected_jobs[job_id] = reason
    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
    stats["skipped"] += 1
#>

# Mutable copies, so the in-run "Disable Pause" choice behaves like LinkedIn's.
# `run_in_background` disables every dialog, same rule as runAiBot.py.
_pause_before_submit = False if run_in_background else pause_before_submit
_pause_after_filters = False if run_in_background else pause_after_filters
_pause_at_failed_question = False if run_in_background else pause_at_failed_question

randomly_answered_questions: set = set()


#< ------ Job page selectors (ordered, first match wins) ------
DESCRIPTION_SELECTORS = [
    "div.styles_JDC__dang-inner-html__h0K4t",
    "div.dang-inner-html",
    "section.job-desc",
    "div[class*='job-desc']",
    "div[class*='JDC__dang']",
]

ABOUT_COMPANY_SELECTORS = [
    "div[class*='styles_about-company']",
    "div[class*='about-company']",
    "section[class*='about-company']",
    "div.comp-info",
]

APPLY_BUTTON_XPATHS = [
    '//button[@id="apply-button"]',
    '//span[@id="apply-button"]',
    '//*[@id="apply-button"]',
    '//button[normalize-space()="Apply"]',
    '//span[normalize-space()="Apply"]/ancestor::button[1]',
]

EXTERNAL_APPLY_XPATHS = [
    '//button[@id="company-site-button"]',
    '//*[@id="company-site-button"]',
    '//button[contains(normalize-space(), "Apply on company site")]',
    '//span[contains(normalize-space(), "Apply on company site")]/ancestor::button[1]',
]

ALREADY_APPLIED_XPATHS = [
    '//*[@id="already-applied"]',
    '//span[contains(@class, "already-applied")]',
    '//*[contains(@class,"styles_applied")]',
    '//span[normalize-space()="Applied"]',
]
#>


#< ------ CSV history (separate files, so LinkedIn's history is never touched) ------
def get_applied_job_ids() -> set[str]:
    '''Returns the set of Naukri Job IDs already present in the Naukri history CSV.'''
    job_ids: set[str] = set()
    try:
        with open(naukri_config.naukri_file_name, 'r', encoding='utf-8') as file:
            for row in csv.reader(file):
                if row:
                    job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The Naukri CSV file '{naukri_config.naukri_file_name}' does not exist yet, starting fresh.")
    except Exception as e:
        print_lg("Failed to read the Naukri applied jobs history!", e)
    return job_ids


def submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required,
                   skills, resume, date_listed, date_applied, job_link, application_link,
                   questions_list) -> None:
    '''Appends a successful application to the Naukri history CSV.'''
    fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'About Job',
                  'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume',
                  'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link',
                  'Questions Found', 'Connect Request']
    try:
        with open(naukri_config.naukri_file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0:
                writer.writeheader()
            writer.writerow({
                'Job ID': truncate_for_csv(job_id), 'Title': truncate_for_csv(title),
                'Company': truncate_for_csv(company), 'Work Location': truncate_for_csv(work_location),
                'Work Style': truncate_for_csv(work_style), 'About Job': truncate_for_csv(description),
                'Experience required': truncate_for_csv(experience_required),
                'Skills required': truncate_for_csv(skills), 'HR Name': 'Unknown', 'HR Link': 'Unknown',
                'Resume': truncate_for_csv(resume), 'Re-posted': False,
                'Date Posted': truncate_for_csv(date_listed), 'Date Applied': truncate_for_csv(date_applied),
                'Job Link': truncate_for_csv(job_link), 'External Job link': truncate_for_csv(application_link),
                'Questions Found': truncate_for_csv(questions_list), 'Connect Request': 'Not Applicable',
            })
    except Exception as e:
        print_lg("Failed to update the Naukri submitted jobs list!", e)
        naukri_dialogs.alert("Failed to update the excel of applied Naukri jobs!\nProbably because of 1 of the following reasons:\n"
                        "1. The file is currently open or in use by another program\n"
                        "2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")


def failed_job(job_id, job_link, resume, date_listed, error, exception, application_link, screenshot_name) -> None:
    '''Appends a failed/skipped application to the Naukri failures CSV.'''
    fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried',
                  'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name']
    try:
        with open(naukri_config.naukri_failed_file_name, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0:
                writer.writeheader()
            writer.writerow({
                'Job ID': truncate_for_csv(job_id), 'Job Link': truncate_for_csv(job_link),
                'Resume Tried': truncate_for_csv(resume), 'Date listed': truncate_for_csv(date_listed),
                'Date Tried': datetime.now(), 'Assumed Reason': truncate_for_csv(error),
                'Stack Trace': truncate_for_csv(exception), 'External Job link': truncate_for_csv(application_link),
                'Screenshot Name': truncate_for_csv(screenshot_name),
            })
    except Exception as e:
        print_lg("Failed to update the Naukri failed jobs list!", e)


def screenshot(driver: WebDriver, job_id: str, failed_at: str) -> str:
    '''Saves a debugging screenshot and returns its file name.'''
    screenshot_name = "naukri - {} - {} - {}.png".format(job_id, failed_at, str(datetime.now()))
    path = (logs_folder_path + "/screenshots/" + screenshot_name.replace(":", ".")).replace("//", "/")
    try:
        driver.save_screenshot(path)
    except Exception as e:
        print_lg("Failed to save a screenshot.", e)
        return "Not Available"
    return screenshot_name
#>


#< ------ Job page helpers ------
def _text_of(driver: WebDriver, css_selectors: list[str]) -> str:
    '''First non-empty text found among the given CSS selectors on the current page.'''
    for selector in css_selectors:
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                text = (element.text or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def _find_first(driver: WebDriver, xpaths: list[str]) -> WebElement | None:
    '''Returns the first *visible* element matching any of the xpaths.'''
    for xpath in xpaths:
        element = try_xp(driver, xpath, False)
        if not element:
            continue
        try:
            if element.is_displayed():
                return element
        except Exception:
            return element
    return None


def is_already_applied(driver: WebDriver) -> bool:
    '''`True` when Naukri's job page shows this job as already applied.'''
    return _find_first(driver, ALREADY_APPLIED_XPATHS) is not None


def get_job_description(driver: WebDriver, company: str) -> tuple[str, int | str, bool, str | None, str | None]:
    '''
    Reads the Naukri job description and screens it against the shared config.

    Applies exactly the same rules as LinkedIn's `get_job_description()`:
    `bad_words`, `security_clearance`, `did_masters` and the
    `current_experience` ceiling.

    ### Returns `(description, experience_required, skip, skip_reason, skip_message)`
    '''
    description = _text_of(driver, DESCRIPTION_SELECTORS) or "Unknown"
    experience_required: int | str = "Unknown"

    if description == "Unknown":
        # Fail closed. Applying to a job whose description could not be read means
        # applying blind: none of the bad-word, clearance or experience rules ran.
        print_lg(f'Unable to extract the job description for "{company}"!')
        if skip_if_no_description:
            return (description, experience_required, True, "Job description could not be read",
                    'Skipping this job because its description could not be read, so it could not '
                    'be screened. Set `naukri_skip_if_no_description = False` in config/settings.py '
                    'to apply to these anyway.')
        return description, experience_required, False, None, None

    lowered = description.lower()

    for word in bad_words:
        if word.lower() in lowered:
            return (description, experience_required, True, "Found a Bad Word in About Job",
                    f'\n{description}\n\nContains bad word "{word}". Skipping this job!\n')

    if not security_clearance and ('polygraph' in lowered or 'clearance' in lowered or 'secret' in lowered):
        return (description, experience_required, True, "Asking for Security clearance",
                f'\n{description}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n')

    found_masters = 0
    if did_masters and 'master' in lowered:
        print_lg('Found the word "master" in the job description.')
        found_masters = 2

    try:
        experience_required = answers.extract_years_of_experience(description)
    except Exception as e:
        experience_required = "Error in extraction"
        print_lg("Unable to extract years of experience required!", e)
        return description, experience_required, False, None, None

    if current_experience > -1 and isinstance(experience_required, int) \
            and experience_required > current_experience + found_masters:
        return (description, experience_required, True, "Required experience is high",
                f'\nExperience required {experience_required} > Current Experience '
                f'{current_experience + found_masters}. Skipping this job!\n')

    return description, experience_required, False, None, None


def check_blacklist(driver: WebDriver, company: str) -> str | None:
    '''
    Checks the company name and its "About company" section for blacklisted words.
    * Returns the offending word, or `None` when the company is acceptable.
    '''
    about_company = (_text_of(driver, ABOUT_COMPANY_SELECTORS) + " " + (company or "")).lower()
    if not about_company.strip():
        return None

    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            return None

    for word in about_company_bad_words:
        if word.lower() in about_company:
            return word
    return None


def _company_name_blacklisted(company: str) -> str | None:
    '''Cheap pre-check on the search card, so blacklisted companies never get opened.'''
    if not company:
        return None
    lowered = company.lower()
    if any(word.lower() in lowered for word in about_company_good_words):
        return None
    for word in about_company_bad_words:
        if word.lower() in lowered:
            return word
    return None


def _extract_skills_with_ai(ai_client, description: str) -> str | list:
    '''Reuses the existing AI providers to extract skills, exactly like the LinkedIn flow does.'''
    if not (use_AI and ai_client and description and description != "Unknown"):
        return "Needs an AI"
    try:
        provider = ai_provider.lower()
        if provider == "openai":
            from modules.ai.openaiConnections import ai_extract_skills
            skills = ai_extract_skills(ai_client, description)
        elif provider == "deepseek":
            from modules.ai.deepseekConnections import deepseek_extract_skills
            skills = deepseek_extract_skills(ai_client, description)
        elif provider == "gemini":
            from modules.ai.geminiConnections import gemini_extract_skills
            skills = gemini_extract_skills(ai_client, description)
        else:
            return "In Development"
        print_lg(f"Extracted skills using {ai_provider} AI")
        return skills
    except Exception as e:
        print_lg("Failed to extract skills:", e)
        return "Error extracting skills"


def _collect_external_link(driver: WebDriver, naukri_tab: str, button: WebElement) -> str:
    '''
    Clicks "Apply on company site" and captures the external application URL,
    the same way LinkedIn's `external_apply()` does.
    '''
    tabs_before = list(driver.window_handles)
    try:
        button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", button)
    buffer(3)

    application_link = "Unknown"
    tabs_after = driver.window_handles
    new_tabs = [handle for handle in tabs_after if handle not in tabs_before]
    if new_tabs:
        driver.switch_to.window(new_tabs[-1])
        sleep(2)
        application_link = driver.current_url
        if close_tabs:
            try:
                driver.close()
            except Exception:
                pass
        driver.switch_to.window(naukri_tab)
    else:
        # Naukri sometimes navigates in place instead of opening a tab.
        application_link = driver.current_url
    print_lg(f'Got the external application link "{application_link}"')
    return application_link
#>


def _confirm_before_submit(title: str, company: str) -> str:
    '''
    The Naukri version of LinkedIn's "pause before submit" dialog.
    Returns one of `"submit"`, `"discard"`.
    '''
    global _pause_before_submit
    decision = naukri_dialogs.confirm(
        f'About to apply on Naukri to:\n\n"{title}" at "{company}"\n\n'
        '1. Please verify the job page.\n'
        '2. Do NOT click Apply yourself, the bot will do it.\n\n'
        'You can turn off "pause_before_submit" in config/questions.py\n'
        'To TEMPORARILY disable pausing, click "Disable Pause"',
        "Confirm your application",
        ["Disable Pause", "Discard Application", "Submit Application"],
        default="Submit Application")
    if decision == "Discard Application":
        return "discard"
    if decision == "Disable Pause":
        _pause_before_submit = False
    return "submit"


def process_job(driver: WebDriver, naukri_tab: str, details: dict, applied_jobs: set,
                rejected_jobs: dict, blacklisted_companies: set, ai_client=None) -> bool:
    '''
    Screens and applies to a single Naukri job.
    * Returns `True` when the job counted towards `switch_number`
      (i.e. it was applied to, or its external link was collected).
    '''
    job_id = details.get("job_id") or ""
    title = details.get("title") or "Unknown"
    company = details.get("company") or "Unknown"
    work_location = details.get("work_location") or ""
    job_link = details.get("job_link") or ""

    application_link = "Applied on Naukri"
    date_applied = "Pending"
    resume = "Naukri profile resume"
    screenshot_name = "Not Available"
    skills = "Needs an AI"
    questions_list = None

    date_listed = "Unknown"
    if details.get("posted_text"):
        try:
            date_listed = calculate_date_posted(details["posted_text"]) or "Unknown"
        except Exception:
            date_listed = "Unknown"

    work_style = ""
    for mode in ("Remote", "Hybrid"):
        if mode.lower() in (details.get("snippet", "") + " " + work_location).lower():
            work_style = mode
            break

    print_lg("\n-@-\n")

    if not job_link:
        print_lg(f'Skipping "{title} | {company}": could not read its job link from the search card.')
        stats["skipped"] += 1
        return False

    if job_id in applied_jobs:
        print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
        return False
    if job_id in rejected_jobs:
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}! '
                 f'(original reason: {rejected_jobs[job_id]})')
        return False
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        return False

    bad_word = _company_name_blacklisted(company)
    if bad_word:
        print_lg(f'Skipping "{title} | {company}": company name contains blacklisted word "{bad_word}".')
        blacklisted_companies.add(company)
        _note_skip(rejected_jobs, job_id, f'Blacklisted company name ("{bad_word}")')
        failed_job(job_id, job_link, resume, date_listed,
                   "Found Blacklisted words in Company name", bad_word, "Skipped", screenshot_name)
        return False

    # Relevance gate on the title alone, straight off the card. Naukri's keyword
    # search returns plenty of unrelated roles, so reject them before spending a
    # page load on them.
    relevant, irrelevance_reason = relevance.check_title_only(title)
    if not relevant:
        print_lg(f'Skipping "{title} | {company}" (not relevant): {irrelevance_reason}')
        _note_skip(rejected_jobs, job_id, f'Irrelevant job title - {irrelevance_reason}')
        failed_job(job_id, job_link, resume, date_listed, "Irrelevant job title",
                   irrelevance_reason, "Skipped", screenshot_name)
        return False

    # Cheap experience gate straight off the card, before we spend a page load.
    min_years = answers.extract_min_years_from_range(details.get("experience_text", ""))
    if current_experience > -1 and min_years is not None and min_years > current_experience:
        print_lg(f'Skipping "{title} | {company}": needs {min_years}+ yrs '
                 f'(card says "{details.get("experience_text")}") > your {current_experience} yrs.')
        _note_skip(rejected_jobs, job_id,
                   f'Required experience too high (card says "{details.get("experience_text")}")')
        failed_job(job_id, job_link, resume, date_listed, "Required experience is high",
                   details.get("experience_text", ""), "Skipped", screenshot_name)
        return False

    print_lg(f'Trying to apply to "{title} | {company}" job. Job ID: {job_id}')
    driver.get(job_link)
    buffer(3)

    if is_already_applied(driver):
        print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
        applied_jobs.add(job_id)
        return False

    bad_word = check_blacklist(driver, company)
    if bad_word:
        print_lg(f'Skipping "{title} | {company}": About Company contains "{bad_word}".')
        blacklisted_companies.add(company)
        _note_skip(rejected_jobs, job_id, f'Blacklisted word in About Company ("{bad_word}")')
        failed_job(job_id, job_link, resume, date_listed,
                   "Found Blacklisted words in About Company", bad_word, "Skipped", screenshot_name)
        return False

    description, experience_required, skip, reason, message = get_job_description(driver, company)
    if skip:
        print_lg(message)
        _note_skip(rejected_jobs, job_id, str(reason))
        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
        return False

    # Full relevance gate, now that the job description is available. This is what
    # catches a plausible-looking title whose actual content is unrelated to you.
    relevant, irrelevance_reason = relevance.check_relevance(title, description, company)
    if not relevant:
        print_lg(f'Skipping "{title} | {company}" (not relevant): {irrelevance_reason}')
        _note_skip(rejected_jobs, job_id, f'Irrelevant job - {irrelevance_reason}')
        failed_job(job_id, job_link, resume, date_listed, "Irrelevant job",
                   irrelevance_reason, "Skipped", screenshot_name)
        return False

    skills = _extract_skills_with_ai(ai_client, description)

    apply_button = _find_first(driver, APPLY_BUTTON_XPATHS)
    external_button = _find_first(driver, EXTERNAL_APPLY_XPATHS)

    if apply_button is None and external_button is None:
        print_lg(f'Found no Apply button for "{title} | {company}". Job ID: {job_id}!')
        screenshot_name = screenshot(driver, job_id, "No apply button")
        failed_job(job_id, job_link, resume, date_listed, "No Apply button found on the job page",
                   "Neither 'Apply' nor 'Apply on company site' was present", application_link, screenshot_name)
        stats["failed"] += 1
        return False

    # Case 2 (LinkedIn parity): only an external application is offered.
    if apply_button is None:
        if easy_apply_only:
            print_lg(f'Skipping "{title} | {company}": only "Apply on company site" is available '
                     f'and easy_apply_only is True.')
            _note_skip(rejected_jobs, job_id,
                       'Only "Apply on company site" available and easy_apply_only is True')
            return False
        try:
            application_link = _collect_external_link(driver, naukri_tab, external_button)
        except Exception as e:
            print_lg(f'Failed to collect the external application link for "{title} | {company}".', e)
            screenshot_name = screenshot(driver, job_id, "Failed external apply")
            failed_job(job_id, job_link, resume, date_listed, "Failed to open the external application",
                       e, "Unknown", screenshot_name)
            stats["failed"] += 1
            return False
        submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required,
                       skills, resume, date_listed, date_applied, job_link, application_link, questions_list)
        applied_jobs.add(job_id)
        stats["external"] += 1
        print_lg(f'Successfully saved external link for "{title} | {company}". Job ID: {job_id}')
        return True

    # Case 1: apply on Naukri.
    if _pause_before_submit and _confirm_before_submit(title, company) == "discard":
        print_lg(f'Application to "{title} | {company}" discarded by user!')
        _note_skip(rejected_jobs, job_id, 'Discarded by user')
        return False

    try:
        scroll_to_view(driver, apply_button)
        try:
            apply_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", apply_button)
        buffer(click_gap)
    except Exception as e:
        print_lg(f'Failed to click Apply for "{title} | {company}".', e)
        screenshot_name = screenshot(driver, job_id, "Failed to click Apply")
        failed_job(job_id, job_link, resume, date_listed, "Failed to click the Apply button",
                   e, application_link, screenshot_name)
        stats["failed"] += 1
        return False

    try:
        completed, questions_list, failure_reason = naukri_questions.handle_chatbot(
            driver,
            {"title": title, "company": company, "work_location": work_location, "description": description},
            ai_client, randomly_answered_questions)
    except Exception as e:
        print_lg(f'Failed while answering the Naukri chatbot for "{title} | {company}".', e)
        critical_error_log("In Naukri chatbot", e)
        screenshot_name = screenshot(driver, job_id, "Failed in chatbot")
        failed_job(job_id, job_link, resume, date_listed, "Problem in the Naukri chatbot",
                   e, application_link, screenshot_name)
        stats["failed"] += 1
        return False

    if questions_list:
        print_lg("Answered the following Naukri questions...", questions_list)

    if not completed:
        # Give the human the same final say LinkedIn offers when submit detection fails.
        if _pause_at_failed_question and "Yes" == naukri_dialogs.confirm(
                f'Could not confirm the Naukri application for:\n\n"{title}" at "{company}"\n\n'
                f'Reason: {failure_reason}\n\nDid you complete it manually?',
                "Failed to confirm the application!", ["Yes", "No"], default="No"):
            completed = True

    if not completed:
        print_lg(f'Failed to apply to "{title} | {company}". Reason: {failure_reason}')
        screenshot_name = screenshot(driver, job_id, "Failed to confirm application")
        failed_job(job_id, job_link, resume, date_listed, failure_reason or "Application not confirmed",
                   failure_reason, application_link, screenshot_name)
        stats["failed"] += 1
        return False

    date_applied = datetime.now()
    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required,
                   skills, resume, date_listed, date_applied, job_link, application_link, questions_list)
    applied_jobs.add(job_id)
    stats["applied"] += 1
    print_lg(f'Successfully applied to "{title} | {company}" job. Job ID: {job_id}')
    return True


def apply_to_jobs(driver: WebDriver, wait, search_terms: list[str], ai_client=None,
                  sort_by: str | None = None, date_posted: str | None = None) -> None:
    '''
    Walks every configured search term on Naukri and applies to matching jobs.
    Honours `switch_number`, `randomize_search_order` and `naukri_max_pages_per_search`.
    '''
    global _pause_after_filters

    applied_jobs = get_applied_job_ids()
    rejected_jobs: dict[str, str] = {}
    blacklisted_companies: set = set()
    naukri_tab = driver.current_window_handle

    terms = list(search_terms)
    if randomize_search_order:
        shuffle(terms)

    for search_term in terms:
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching Naukri for "{search_term}" <<<<\n\n')

        current_count = 0
        try:
            for page in range(1, naukri_config.max_pages_per_search + 1):
                if current_count >= switch_number:
                    break

                if not naukri_search.open_search(driver, wait, search_term, page, sort_by, date_posted):
                    break

                if page == 1:
                    naukri_search.apply_ui_filters(driver)
                    if _pause_after_filters and "Turn off Pause after search" == naukri_dialogs.confirm(
                            "These are your configured Naukri search results and filters. It is safe to change "
                            "them while this dialog is open, any changes later could result in errors and "
                            "skipping this search run.",
                            "Please check your results",
                            ["Turn off Pause after search", "Look's good, Continue"],
                            default="Look's good, Continue"):
                        _pause_after_filters = False

                cards = naukri_search.get_job_cards(driver)
                # Snapshot every card before navigating away, the elements go stale otherwise.
                page_jobs = []
                for card in cards:
                    try:
                        page_jobs.append(naukri_search.get_card_details(driver, card))
                    except Exception as e:
                        print_lg("Failed to read a Naukri job card, skipping it.", e)
                print_lg(f"Found {len(page_jobs)} job(s) on page {page} for \"{search_term}\".")

                for details in page_jobs:
                    if keep_screen_awake:
                        naukri_dialogs.keep_awake()
                    if current_count >= switch_number:
                        print_lg(f'Reached switch_number ({switch_number}) for "{search_term}", '
                                 f'moving to the next search term.')
                        break
                    try:
                        if process_job(driver, naukri_tab, details, applied_jobs,
                                       rejected_jobs, blacklisted_companies, ai_client):
                            current_count += 1
                    except (NoSuchWindowException, WebDriverException):
                        raise
                    except Exception as e:
                        print_lg(f'Unexpected failure while processing "{details.get("title")}".', e)
                        critical_error_log("In Naukri job processing", e)
                        failed_job(details.get("job_id", ""), details.get("job_link", ""),
                                   "Naukri profile resume", "Unknown", "Unexpected error", e,
                                   "Unknown", "Not Available")
                        stats["failed"] += 1

        except (NoSuchWindowException, WebDriverException) as e:
            print_lg("Browser window closed or session is invalid. Ending the Naukri application process.", e)
            raise
        except Exception as e:
            print_lg(f'Failed while searching Naukri for "{search_term}"!')
            critical_error_log("In Naukri Applier", e)

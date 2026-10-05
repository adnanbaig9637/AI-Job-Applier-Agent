'''
Naukri chatbot handling.

After clicking Apply, Naukri either applies straight away or opens a chatbot
drawer that asks one question at a time (notice period, expected CTC, a
skill rating, a yes/no screener, ...).

This is the Naukri counterpart of `answer_questions()` in `runAiBot.py`, and it
follows the same escalation ladder:

  1. answer from the existing config (`modules/answers.py`),
  2. ask the configured AI provider when `use_AI` is on,
  3. pause and ask the human when `pause_at_failed_question` is on,
  4. otherwise record the question as randomly/blank answered and move on.
'''

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from config.secrets import use_AI, ai_provider
from config.questions import pause_at_failed_question, user_information_all
from config.settings import click_gap, run_in_background

from modules import answers
from modules.helpers import print_lg, buffer, sleep
from modules.clickers_and_finders import try_xp, scroll_to_view
from modules.naukri import naukri_config, naukri_dialogs


# The chatbot drawer, in order of preference.
CHATBOT_SELECTORS = [
    (By.CSS_SELECTOR, "div.chatbot_DrawerContentWrapper"),
    (By.CSS_SELECTOR, "div.chatbot_Drawer"),
    (By.CSS_SELECTOR, "div._chatBotContainer"),
    (By.CSS_SELECTOR, "div[class*='chatbot']"),
]

# Bot messages (the questions), oldest first.
BOT_MESSAGE_SELECTORS = [
    "div.botMsg", "li.botItem div.msg", "div.botItem span", "div[class*='botMsg']",
]

# Free-text input.
TEXT_INPUT_SELECTORS = [
    "div.textArea[contenteditable='true']",
    "div[contenteditable='true']",
    "textarea",
    "input[type='text']",
    "input[type='number']",
]

# Choice inputs (radio / checkbox).
CHOICE_CONTAINER_SELECTORS = [
    "div.ssrc__radio-btn-container",
    "div.singleselect-radiobutton-container",
    "div.chatbot_MultipleSelection div.ssrc__label",
    "div[class*='radio-btn-container']",
    "div[class*='checkbox-container']",
]

# Send / save controls.
SEND_XPATHS = [
    './/div[contains(@class,"sendMsg")]',
    './/span[contains(@class,"sendMsg")]',
    './/div[contains(@class,"send-msg")]',
    './/button[normalize-space()="Save"]',
    './/div[normalize-space()="Save"]',
    './/button[normalize-space()="Submit"]',
    './/div[contains(@class,"botMsg")]/following::div[contains(@class,"send")][1]',
]

# `run_in_background` cannot show dialogs, so it never pauses for a human.
_pause_at_failed_question = False if run_in_background else pause_at_failed_question

SUCCESS_PHRASES = (
    "successfully applied",
    "application sent",
    "you have applied",
    "applied to this job",
    "your application has been",
    "thank you for applying",
)


def find_chatbot(driver: WebDriver, timeout: float = 6.0) -> WebElement | None:
    '''Waits briefly for the Naukri chatbot drawer and returns it, or `None`.'''
    deadline = timeout
    while deadline > 0:
        for by, value in CHATBOT_SELECTORS:
            try:
                for element in driver.find_elements(by, value):
                    if element.is_displayed():
                        return element
            except Exception:
                continue
        sleep(1)
        deadline -= 1
    return None


def _current_question(chatbot: WebElement) -> str:
    '''Returns the text of the most recent bot message (the question being asked).'''
    for selector in BOT_MESSAGE_SELECTORS:
        try:
            messages = [m for m in chatbot.find_elements(By.CSS_SELECTOR, selector) if m.text.strip()]
        except Exception:
            messages = []
        if messages:
            return messages[-1].text.strip()
    return ""


def _visible(elements: list[WebElement]) -> list[WebElement]:
    result = []
    for element in elements:
        try:
            if element.is_displayed():
                result.append(element)
        except Exception:
            continue
    return result


def _find_choices(chatbot: WebElement) -> list[tuple[WebElement, str]]:
    '''
    Returns the currently offered choices as `(clickable_element, visible_text)`.
    Handles both radio-style and checkbox-style question widgets.
    '''
    for selector in CHOICE_CONTAINER_SELECTORS:
        try:
            containers = _visible(chatbot.find_elements(By.CSS_SELECTOR, selector))
        except Exception:
            containers = []
        if not containers:
            continue
        choices: list[tuple[WebElement, str]] = []
        for container in containers:
            text = ""
            clickable = container
            try:
                labels = container.find_elements(By.TAG_NAME, "label")
                if labels:
                    clickable = labels[0]
                    text = labels[0].text.strip()
            except Exception:
                pass
            if not text:
                text = (container.text or "").strip()
            if text:
                choices.append((clickable, text))
        if choices:
            return choices
    return []


def _find_text_input(chatbot: WebElement) -> WebElement | None:
    '''Returns the visible free-text input of the chatbot, if any.'''
    for selector in TEXT_INPUT_SELECTORS:
        try:
            candidates = _visible(chatbot.find_elements(By.CSS_SELECTOR, selector))
        except Exception:
            candidates = []
        if candidates:
            return candidates[-1]
    return None


def _click(driver: WebDriver, element: WebElement) -> bool:
    '''Clicks an element, falling back to a JS click when Naukri overlays intercept it.'''
    try:
        scroll_to_view(driver, element)
    except Exception:
        pass
    try:
        element.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False


def _send(driver: WebDriver, chatbot: WebElement, text_input: WebElement | None) -> bool:
    '''Submits the current chatbot answer via the send/save control, or Enter as a fallback.'''
    for xpath in SEND_XPATHS:
        element = try_xp(chatbot, xpath, False)
        if element and _click(driver, element):
            buffer(click_gap)
            return True
    if text_input is not None:
        try:
            text_input.send_keys(Keys.ENTER)
            buffer(click_gap)
            return True
        except Exception:
            pass
    return False


def _fill_text(driver: WebDriver, text_input: WebElement, value: str) -> bool:
    '''Types `value` into a chatbot text field (plain input or contenteditable div).'''
    try:
        text_input.click()
    except Exception:
        pass
    try:
        text_input.send_keys(Keys.CONTROL, "a")
        text_input.send_keys(Keys.DELETE)
    except Exception:
        pass
    try:
        text_input.send_keys(value)
        return True
    except Exception:
        pass
    # contenteditable divs sometimes reject send_keys; set the text directly.
    try:
        driver.execute_script(
            "arguments[0].innerText = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            text_input, value)
        return True
    except Exception as e:
        print_lg("Failed to type the chatbot answer.", e)
        return False


def _ai_answer(ai_client, question: str, options: list[str] | None,
               question_type: str, job_description: str | None) -> str:
    '''Asks the configured AI provider to answer a chatbot question. Returns "" on any failure.'''
    if not (use_AI and ai_client):
        return ""
    try:
        provider = ai_provider.lower()
        if provider == "openai":
            from modules.ai.openaiConnections import ai_answer_question
            answer = ai_answer_question(ai_client, question, options=options, question_type=question_type,
                                        job_description=job_description, user_information_all=user_information_all)
        elif provider == "deepseek":
            from modules.ai.deepseekConnections import deepseek_answer_question
            answer = deepseek_answer_question(ai_client, question, options=options, question_type=question_type,
                                              job_description=job_description, about_company=None,
                                              user_information_all=user_information_all)
        elif provider == "gemini":
            from modules.ai.geminiConnections import gemini_answer_question
            answer = gemini_answer_question(ai_client, question, options=options, question_type=question_type,
                                            job_description=job_description, about_company=None,
                                            user_information_all=user_information_all)
        else:
            return ""
        if answer and isinstance(answer, str) and answer.strip():
            print_lg(f'AI answered Naukri question "{question}" with: "{answer.strip()}"')
            return answer.strip()
    except Exception as e:
        print_lg("Failed to get an AI answer for a Naukri chatbot question!", e)
    return ""


def _custom_rule_hint(question: str) -> str:
    '''
    Suggests a short, lowercase `custom_question_answers` key for a question the
    bot could not answer, so the log line can be copy-pasted into the config.
    '''
    words = [w for w in "".join(c if c.isalnum() or c.isspace() else " "
                                for c in (question or "").lower()).split() if len(w) > 2]
    skip = {"the", "your", "you", "are", "for", "with", "and", "what", "how", "many",
            "much", "this", "that", "have", "any", "please", "kindly", "will"}
    keep = [w for w in words if w not in skip][:4]
    return " ".join(keep) if keep else (question or "").lower()[:40]


def _log_unanswerable(question: str) -> None:
    '''
    Explains why a job is being skipped and prints a ready-to-paste config line,
    so every question the bot meets only needs teaching once.
    '''
    print_lg("  -> no rule matched and nothing safe to guess, skipping this job.")
    print_lg("     To answer it from now on, add this to custom_question_answers "
             "in config/questions.py:")
    print_lg(f'       "{_custom_rule_hint(question)}": "your answer",')


def _ask_human(question: str, options: list[str] | None) -> str:
    '''
    Asks the human for an answer. Returns "" if they skip or cannot be reached.

    Tries the pop-up dialog first, then falls back to a terminal prompt. The
    pop-up relies on pyautogui's Tk dialogs, which raise `TclError` on machines
    with a broken Tk install - there the bot used to silently fall through to its
    own guess, which is why `pause_at_failed_question = True` never actually
    stopped the wrong answers.
    '''
    if _pause_at_failed_question:
        prompt = (f'The Naukri chatbot asked a question the bot could not answer:\n\n"{question}"\n\n')
        if options:
            prompt += "Available options:\n  - " + "\n  - ".join(options) + "\n\n"
            prompt += "Type the option text exactly, or leave empty to skip this job.\n"
        else:
            prompt += "Type the answer to fill in, or leave empty to skip this job.\n"
        prompt += '\nYou can turn off "pause_at_failed_question" in config/questions.py'
        reply = naukri_dialogs.prompt(prompt, "Help Needed - Naukri")
        if reply:
            return reply

    # Works wherever the bot was launched from a terminal, Tk or no Tk.
    return answers.ask_in_terminal(question, options)


def is_application_successful(driver: WebDriver) -> bool:
    '''Detects Naukri's post-application confirmation, in any of its wordings.'''
    for phrase in SUCCESS_PHRASES:
        xpath = ("//*[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                 f"'abcdefghijklmnopqrstuvwxyz'), '{phrase}')]")
        element = try_xp(driver, xpath, False)
        if element:
            try:
                if element.is_displayed():
                    return True
            except Exception:
                return True
    return False


def handle_chatbot(driver: WebDriver, job_context: dict, ai_client=None,
                   randomly_answered_questions: set | None = None) -> tuple[bool, set, str | None]:
    '''
    Drives Naukri's chatbot to completion.

    ### Returns `(completed, questions_answered, failure_reason)`
    - `completed`: `True` when the chatbot finished (or was never shown).
    - `questions_answered`: set of `(question, answer, type)` tuples, logged to the CSV.
    - `failure_reason`: `None` on success, otherwise why we gave up.
    '''
    questions_list: set = set()
    if randomly_answered_questions is None:
        randomly_answered_questions = set()

    chatbot = find_chatbot(driver)
    if chatbot is None:
        # No chatbot at all: either applied instantly, or the click did nothing.
        return is_application_successful(driver), questions_list, None

    print_lg("Naukri chatbot opened, answering its questions...")
    work_location = job_context.get("work_location", "")
    job_description = job_context.get("description")

    last_question = None
    repeat_count = 0
    greeting_waits = 0

    for round_number in range(1, naukri_config.max_chatbot_rounds + 1):
        if is_application_successful(driver):
            return True, questions_list, None

        # The drawer is re-rendered between questions, so re-acquire it each round.
        chatbot = find_chatbot(driver, timeout=3.0)
        if chatbot is None:
            # Drawer closed: treat a visible confirmation as success, silence as failure.
            return is_application_successful(driver), questions_list, None

        question = _current_question(chatbot)

        # Naukri's opening banner ("Hi <name>, thank you for showing interest...")
        # renders in the same slot as the questions but is not one. It used to be
        # answered like a question, which typed junk into the chat and burned a round.
        if question and answers.looks_like_greeting(question):
            greeting_waits += 1
            if greeting_waits <= 3:
                print_lg("Naukri chatbot opened with its greeting banner, "
                         "waiting for the first real question...")
                sleep(2)
                continue
            # The banner is not advancing by itself, so nudge the chat forward.
            print_lg("Greeting banner did not advance, nudging the chatbot forward.")
            _send(driver, chatbot, None)
            sleep(1)
            continue

        if question and question == last_question:
            repeat_count += 1
            if repeat_count >= 3:
                return False, questions_list, "Chatbot kept repeating the same question"
        else:
            repeat_count = 0
        last_question = question

        choices = _find_choices(chatbot)
        text_input = _find_text_input(chatbot)

        if not choices and text_input is None:
            # Nothing to answer. Either it is done, or it is still rendering.
            sleep(2)
            if is_application_successful(driver):
                return True, questions_list, None
            if _send(driver, chatbot, None):
                continue
            return False, questions_list, "Chatbot showed no answerable input"

        if choices:
            option_texts = [text for _, text in choices]
            print_lg(f'Naukri chatbot Q{round_number}: "{question}" (options: {option_texts})')
            answer = answers.resolve_choice_answer(question, option_texts, work_location)
            source = "config"
            if not answer:
                ai_raw = _ai_answer(ai_client, question, option_texts, "single_select", job_description)
                answer = answers.match_option(ai_raw, option_texts) if ai_raw else None
                source = "ai"
            if not answer:
                # Shape-based answer, but only where one is defensible (a years
                # band, or a yes/no pair). Returns None otherwise so we ask you
                # rather than taking option_texts[0], which answered "No"
                # whenever a recruiter happened to list No before Yes.
                answer = answers.fallback_choice_answer(question, option_texts)
                if answer:
                    source = f"{answers.classify_question(question)} fallback"
                    randomly_answered_questions.add((question, "choice"))
            if not answer:
                human_raw = _ask_human(question, option_texts)
                answer = answers.match_option(human_raw, option_texts) if human_raw else None
                source = "human"
            if not answer:
                if answers.skip_job_on_unanswerable_question:
                    _log_unanswerable(question)
                    return False, questions_list, f'Could not answer the question "{question}"'
                answer = answers.last_resort_choice(option_texts)
                source = "last-resort option (guess)"
                randomly_answered_questions.add((question, "choice"))

            print_lg(f'  -> answering "{answer}" (from {source})')
            target = next((element for element, text in choices if text == answer), None)
            if target is None or not _click(driver, target):
                return False, questions_list, f'Failed to select chatbot option "{answer}"'
            questions_list.add((question, answer, "choice"))
            buffer(click_gap)
            _send(driver, chatbot, None)
            continue

        # Free-text question
        print_lg(f'Naukri chatbot Q{round_number}: "{question}" (free text)')
        answer = answers.resolve_text_answer(question, work_location, default="")
        source = "config"
        if not answer:
            answer = _ai_answer(ai_client, question, None, "text", job_description)
            source = "ai"
        if not answer:
            # Shape-based fallback: a yes/no screener gets a yes/no, a years
            # question gets the configured years. Everything else gets nothing,
            # because defaulting to `years_of_experience` here is what answered
            # every unrecognised question - email included - with "2".
            answer = answers.fallback_text_answer(question)
            if answer:
                source = f"{answers.classify_question(question)} fallback"
                randomly_answered_questions.add((question, "text"))
        if not answer:
            answer = _ask_human(question, None)
            source = "human"
        if not answer:
            if answers.skip_job_on_unanswerable_question:
                _log_unanswerable(question)
                return False, questions_list, f'Could not answer the question "{question}"'
            print_lg('  -> no rule matched, leaving this question blank.')
            randomly_answered_questions.add((question, "text"))

        print_lg(f'  -> answering "{answer}" (from {source})')
        if not _fill_text(driver, text_input, str(answer)):
            return False, questions_list, "Failed to type an answer into the chatbot"
        questions_list.add((question, str(answer), "text"))
        if not _send(driver, chatbot, text_input):
            return False, questions_list, "Failed to submit a chatbot answer"

    # Ran out of rounds. Mirror LinkedIn's behaviour and offer the human a chance to finish.
    if _pause_at_failed_question:
        naukri_dialogs.alert(
            "The Naukri chatbot asked more questions than the bot could handle "
            f"({naukri_config.max_chatbot_rounds} rounds).\n"
            'Please finish this application manually, then click "Continue".\n\n'
            'You can raise "naukri_max_chatbot_rounds" in config/settings.py.',
            "Help Needed - Naukri", "Continue")
        if is_application_successful(driver):
            return True, questions_list, None
    return False, questions_list, "Exceeded the maximum number of chatbot rounds"

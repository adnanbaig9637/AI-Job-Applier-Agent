'''
Shared, platform-neutral answer resolution.

Added alongside the existing LinkedIn automation (which keeps its own inline
answering logic in `runAiBot.py` untouched). This module turns a question
*label* into an answer using only `config/personals.py` and
`config/questions.py`, with no Selenium/WebElement dependency, so any platform
(currently Naukri) can reuse the exact same answer vocabulary.

The keyword -> config mapping intentionally mirrors `answer_questions()` in
`runAiBot.py` so both platforms answer consistently.
'''

import re

from config import personals as _personals
from config import questions as _questions

from config.personals import (
    first_name, middle_name, last_name, phone_number, current_city,
    street, state, zipcode, country, gender, disability_status, veteran_status,
)
from config.questions import (
    years_of_experience, require_visa, website, linkedIn, us_citizenship,
    desired_salary, current_ctc, notice_period, linkedin_headline,
    linkedin_summary, cover_letter, recent_employer, confidence_level,
)


def _opt(module, name: str, default):
    '''
    Reads an optional config value, falling back to `default` when it is absent
    or None. Mirrors `naukri_config._opt()` so a user config that predates these
    fields keeps working instead of raising ImportError.
    '''
    value = getattr(module, name, None)
    return default if value is None else value


#< Optional config (added for the rules-only Naukri chatbot; all backward compatible)
email = str(_opt(_personals, 'email', "")).strip()

highest_qualification = str(_opt(_questions, 'highest_qualification', "")).strip()
graduation_year = str(_opt(_questions, 'graduation_year', "")).strip()
graduation_percentage = str(_opt(_questions, 'graduation_percentage', "")).strip()
current_company = str(_opt(_questions, 'current_company', "")).strip()
current_designation = str(_opt(_questions, 'current_designation', "")).strip()
willing_to_relocate = str(_opt(_questions, 'willing_to_relocate', "Yes")).strip()
default_yes_no_answer = str(_opt(_questions, 'default_yes_no_answer', "Yes")).strip()
custom_question_answers: dict = _opt(_questions, 'custom_question_answers', {}) or {}
skip_job_on_unanswerable_question = bool(_opt(_questions, 'skip_job_on_unanswerable_question', True))
ask_in_terminal_on_failed_question = bool(_opt(_questions, 'ask_in_terminal_on_failed_question', True))

# `custom_question_answers` is matched longest-key-first so a specific phrase
# ("total years of experience") always beats a broad one ("experience").
_custom_rules: list[tuple[str, str]] = sorted(
    ((str(k).lower().strip(), str(v)) for k, v in custom_question_answers.items() if str(k).strip()),
    key=lambda item: len(item[0]), reverse=True)
#>


#< Derived values (same derivations as runAiBot.py)
_first_name = first_name.strip()
_middle_name = middle_name.strip()
_last_name = last_name.strip()
full_name = f"{_first_name} {_middle_name} {_last_name}" if _middle_name else f"{_first_name} {_last_name}"

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary / 12, 2))
desired_salary_str = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc / 12, 2))
current_ctc_str = str(current_ctc)

notice_period_months = str(notice_period // 30)
notice_period_weeks = str(notice_period // 7)
notice_period_str = str(notice_period)
#>


# Matches '10+ years', '5 years', '3-5 years', '2 to 4 yrs' etc.
re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)
# Naukri renders experience on cards as '2-5 Yrs', '0-1 Yrs', '5+ Yrs'
re_experience_short = re.compile(r'(\d+)\s*(?:-|to|–)?\s*(\d+)?\s*\+?\s*(?:yr|yrs|year|years)', re.IGNORECASE)


#< ------ Question shape classification ------
# Used to pick a *sane* fallback. Answering an unknown question with
# `years_of_experience` is what made every unrecognised question come back "2".

# Openers that mean "give me a value", so the question is never a yes/no.
_QUANTITY_OPENERS = (
    "how many", "how much", "what is", "what's", "what are", "which", "where",
    "when", "why", "who", "whats", "state your", "mention your", "specify",
    "enter your", "provide your", "share your", "tell us your",
)

# Markers of a yes/no screener.
_YES_NO_MARKERS = (
    "y/n", "yes/no", "yes / no", "(y/n)",
    "willing to", "willing for", "comfortable", "ready to", "ready for",
    "open to", "able to", "do you have", "are you ok", "are you okay",
    "interested in", "agree to", "acceptable",
)
_YES_NO_OPENERS = (
    "are you", "is your", "do you", "does your", "did you", "have you", "has your",
    "can you", "could you", "will you", "would you", "shall you", "any ",
)

# Markers that the answer must be a number of years.
_YEARS_MARKERS = (
    "years of experience", "year of experience", "yrs of experience",
    "years experience", "total experience", "overall experience",
    "relevant experience", "work experience", "experience in years",
    "exp in years", "experience (in years", "years in",
)

# Markers that the answer is a plain number / percentage.
_NUMBER_MARKERS = (
    "cgpa", "percentage", "percentile", "marks", "score", "gpa",
    "how many", "how much", "number of", "no of", "no. of",
)


def looks_like_greeting(text: str) -> bool:
    '''
    `True` for Naukri's opening chatbot banner, e.g.
    "Hi Adnan Baig, thank you for showing interest. Kindly answer all the
    recruiter's questions to successfully apply for the job."

    It is a statement, not a question, but the chatbot renders it in the same
    bot-message slot, so without this check the bot types an answer at it.
    '''
    if not text:
        return False
    lowered = text.lower()
    banners = (
        "thank you for showing interest",
        "kindly answer all the recruiter",
        "answer all the recruiter's question",
        "to successfully apply for the job",
        "thanks for showing interest",
    )
    if any(phrase in lowered for phrase in banners):
        return True
    # A greeting with no question mark and no imperative ask is not answerable.
    return "?" not in text and lowered.startswith(("hi ", "hello ", "hey ", "welcome"))


def classify_question(label: str) -> str:
    '''
    Classifies a question by the *shape of answer it wants*, independent of topic.
    Returns one of `'yes_no'`, `'years'`, `'number'`, `'text'`.
    '''
    if not label:
        return "text"
    lowered = label.lower().strip()

    # Years beats everything: "How many years of experience..." opens like a
    # quantity question and contains "do you have", so check it first.
    if any(marker in lowered for marker in _YEARS_MARKERS):
        return "years"

    explicit_yes_no = any(marker in lowered for marker in ("y/n", "yes/no", "yes / no"))
    starts_quantity = lowered.startswith(_QUANTITY_OPENERS)

    if explicit_yes_no:
        return "yes_no"
    if not starts_quantity:
        if lowered.startswith(_YES_NO_OPENERS) or any(m in lowered for m in _YES_NO_MARKERS):
            return "yes_no"

    if any(marker in lowered for marker in _NUMBER_MARKERS):
        return "number"
    return "text"


def custom_answer(label: str) -> str:
    '''
    Returns the user's own answer for this question from
    `custom_question_answers`, or `""`. Longest matching key wins.
    '''
    if not label or not _custom_rules:
        return ""
    lowered = label.lower()
    for phrase, answer in _custom_rules:
        if phrase in lowered:
            return answer
    return ""
#>


def extract_years_of_experience(text: str, max_sane_value: int = 12) -> int:
    '''
    Extracts the highest sane "years of experience" number from a block of text.
    Returns `0` when nothing could be found (same fallback as LinkedIn's version).
    '''
    if not text:
        return 0
    matches = re.findall(re_experience, text)
    sane = [int(m) for m in matches if int(m) <= max_sane_value]
    if not sane:
        return 0
    return max(sane)


def extract_min_years_from_range(text: str) -> int | None:
    '''
    Parses Naukri's compact card experience label (e.g. `'2-5 Yrs'`, `'5+ Yrs'`)
    and returns the *minimum* required years, or `None` if unparseable.
    '''
    if not text:
        return None
    match = re_experience_short.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _first_index(label: str, markers: tuple[str, ...]) -> int | None:
    '''
    Returns the position of the earliest of `markers` in `label`, or `None` when
    none appear. Used to tell what a mixed question is really asking for: in
    "CGPA in your Graduation degree" the score comes first, in "qualification
    with year and percentage" the qualification does.
    '''
    positions = [label.find(m) for m in markers]
    found = [p for p in positions if p >= 0]
    return min(found) if found else None


def _education_summary() -> str:
    '''Builds the "qualification, year, percentage" answer Naukri recruiters ask for.'''
    parts = [p for p in (highest_qualification, graduation_year) if p]
    summary = ", ".join(parts)
    if graduation_percentage:
        percent = graduation_percentage
        suffix = "" if "%" in percent else "%"
        summary = f"{summary}, {percent}{suffix}" if summary else f"{percent}{suffix}"
    return summary


def resolve_text_answer(label: str, work_location: str = "", default: str = "") -> str:
    '''
    Resolves a free-text / textarea question `label` to an answer from config.
    * Returns `default` (empty string by default) when no rule matches, which is
      the caller's cue to ask the human or to skip the job.

    Rules are ordered most-specific-first. The broad "experience / years" rule
    deliberately sits near the *end*: when it ran early it swallowed every
    question containing the word "years" and answered it with
    `years_of_experience`.
    '''
    if not label:
        return default

    # 0. The user's own overrides always win.
    own = custom_answer(label)
    if own:
        return own

    label = label.lower().strip()

    #< 1. Identity and contact - these must beat every broader rule below.
    if 'email' in label or 'e-mail' in label or 'mail id' in label:
        return email or default
    if 'phone' in label or 'mobile' in label or 'contact number' in label \
            or 'contact no' in label or 'whatsapp' in label or 'alternate number' in label:
        return phone_number
    if 'signature' in label:
        return full_name
    if 'aadhaar' in label or 'aadhar' in label or 'pan card' in label or 'passport' in label:
        return default  # never volunteer identity documents
    #>

    #< 2. Education
    # These questions mix topics ("CGPA in your Graduation degree", "qualification
    # with passed out year and percentage"), so decide by which part the question
    # leads with: the first marker to appear is the value actually being asked for.
    _qualification_at = _first_index(label, ('qualification', 'education', 'degree',
                                            'graduation', 'college', 'university'))
    _score_at = _first_index(label, ('cgpa', 'gpa', 'percentage', 'percentile',
                                     'marks', 'aggregate'))
    _year_at = _first_index(label, ('passout', 'pass out', 'passing year',
                                    'year of passing', 'graduation year'))

    if _qualification_at is not None and (_score_at is not None or _year_at is not None):
        others = [i for i in (_score_at, _year_at) if i is not None]
        # "Highest educational qualification with passed out year and percentage"
        # leads with the qualification, so it wants all three parts at once.
        if _qualification_at < min(others):
            return _education_summary() or default
    if _score_at is not None and (_qualification_at is None or _score_at < _qualification_at):
        return graduation_percentage or default
    if _year_at is not None and (_qualification_at is None or _year_at < _qualification_at):
        return graduation_year or default
    if _score_at is not None:
        return graduation_percentage or default
    if _year_at is not None:
        return graduation_year or default
    if _qualification_at is not None:
        return highest_qualification or default
    #>

    #< 3. Visa / authorization
    if 'sponsorship' in label or 'visa' in label or 'work authorization' in label \
            or 'work permit' in label:
        return require_visa
    #>

    #< 4. Notice period and joining
    if 'notice' in label or 'joining' in label or 'join' in label or 'lwd' in label \
            or 'last working day' in label or 'serving' in label:
        if 'month' in label:
            return notice_period_months
        if 'week' in label:
            return notice_period_weeks
        return notice_period_str
    #>

    #< 5. Money
    if 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label \
            or 'lpa' in label or 'package' in label or 'remuneration' in label:
        is_current = 'current' in label or 'present' in label or 'existing' in label
        if is_current:
            if 'month' in label:
                return current_ctc_monthly
            if 'lakh' in label or 'lpa' in label:
                return current_ctc_lakhs
            return current_ctc_str
        if 'month' in label:
            return desired_salary_monthly
        if 'lakh' in label or 'lpa' in label:
            return desired_salary_lakhs
        return desired_salary_str
    #>

    #< 6. Employment
    if 'designation' in label or 'job title' in label or 'current role' in label \
            or 'current position' in label:
        return current_designation or default
    if 'current company' in label or 'present company' in label \
            or 'current employer' in label or 'organization' in label \
            or 'organisation' in label or 'present employer' in label:
        return current_company or recent_employer or default
    #>

    #< 7. Links
    if 'linkedin' in label:
        return linkedIn
    if 'website' in label or 'blog' in label or 'portfolio' in label \
            or 'github' in label or 'link' in label:
        return website
    #>

    #< 8. Location
    if 'street' in label:
        return street
    if 'state' in label or 'province' in label:
        return state
    if 'zip' in label or 'postal' in label or 'pincode' in label or 'pin code' in label:
        return zipcode
    if 'country' in label:
        return country
    if 'relocat' in label:
        # "Are you currently residing in X or willing to relocate to X?" is a
        # yes/no screener, not a request for a city name.
        if classify_question(label) == 'yes_no':
            return willing_to_relocate
        return current_city if current_city else work_location
    if 'city' in label or 'location' in label or 'address' in label \
            or 'residing' in label or 'hometown' in label or 'native' in label:
        return current_city if current_city else work_location
    #>

    #< 9. Free-text blobs
    if 'scale of 1-10' in label or 'scale of 1 to 10' in label:
        return confidence_level
    if 'headline' in label:
        return linkedin_headline
    if 'summary' in label or 'about yourself' in label or 'about you' in label:
        return linkedin_summary
    if 'cover' in label:
        return cover_letter
    #>

    #< 10. Names - narrow, so "company name" does not become the candidate's name.
    if 'name' in label:
        if 'employer' in label or 'company' in label or 'organization' in label \
                or 'organisation' in label or 'college' in label or 'institute' in label:
            return current_company or recent_employer or default
        if 'full' in label:
            return full_name
        if 'first' in label and 'last' not in label:
            return _first_name
        if 'middle' in label and 'last' not in label:
            return _middle_name
        if 'last' in label and 'first' not in label:
            return _last_name
        if 'your name' in label or label in ('name', 'candidate name'):
            return full_name
        return default
    #>

    #< 11. Broad experience rule LAST, and only when the question really wants years.
    if classify_question(label) == 'years':
        return years_of_experience
    if 'experience' in label and ('year' in label or 'yrs' in label or 'total' in label
                                  or 'overall' in label or 'relevant' in label):
        return years_of_experience
    #>

    return default


def fallback_text_answer(label: str) -> str:
    '''
    Last-resort answer for a free-text question no rule matched, chosen from the
    *shape* of the question rather than from one hard-coded value.

    Returns `""` when there is no defensible answer, which tells the caller to
    ask the human or skip the job. This replaces the old behaviour of answering
    every unknown question with `years_of_experience` (i.e. "2").
    '''
    kind = classify_question(label)
    if kind == 'yes_no':
        return default_yes_no_answer
    if kind == 'years':
        return years_of_experience
    return ""


def resolve_choice_answer(label: str, options: list[str], work_location: str = "") -> str | None:
    '''
    Resolves a single/multi choice question to one of the given `options`.
    * `options` are the visible option texts.
    * Returns the matched option text, or `None` when no confident match exists.
    '''
    if not label or not options:
        return None
    lowered = label.lower().strip()

    # The user's own overrides win here too.
    own = custom_answer(label)
    if own:
        matched = match_option(own, options)
        if matched:
            return matched

    preferred: str | None = None
    if 'gender' in lowered or 'sex' in lowered:
        preferred = gender
    elif 'disability' in lowered or 'handicap' in lowered:
        preferred = disability_status
    elif 'veteran' in lowered or 'protected' in lowered:
        preferred = veteran_status
    elif 'citizenship' in lowered or 'employment eligibility' in lowered:
        preferred = us_citizenship
    elif 'sponsorship' in lowered or 'visa' in lowered or 'work authorization' in lowered:
        preferred = require_visa
    elif 'relocat' in lowered:
        preferred = willing_to_relocate
    elif 'proficiency' in lowered:
        preferred = 'Professional'
    elif 'country' in lowered:
        preferred = country
    elif 'state' in lowered:
        preferred = state
    elif 'city' in lowered or 'location' in lowered or 'residing' in lowered:
        preferred = current_city if current_city else work_location
    else:
        # Fall back to the text vocabulary; useful for notice period / CTC pickers.
        preferred = resolve_text_answer(label, work_location, default="") or None

    if not preferred:
        return None

    # A years question with range options ("2-3 years") needs numeric banding,
    # not substring matching: matching "2" as a substring picks "<2 years".
    if classify_question(label) == 'years':
        banded = match_numeric_band(preferred, options)
        if banded:
            return banded
    return match_option(preferred, options)


def fallback_choice_answer(label: str, options: list[str]) -> str | None:
    '''
    Answer for a choice question no config rule matched, but only when the
    question's shape makes one defensible:
      * a years question with range options -> the band containing your experience,
      * a yes/no pair -> your configured `default_yes_no_answer`.

    Returns `None` for anything else, so the caller asks the human instead of
    guessing. That is deliberately different from the old `options[0]`, which
    answered "No" whenever a recruiter listed No before Yes and could pick
    "Skip this question" purely because of its position.
    '''
    if not options:
        return None

    pool = [o for o in options if not _is_skip_option(o)] or options

    if classify_question(label) == 'years':
        banded = match_numeric_band(years_of_experience, pool)
        if banded:
            return banded

    if _looks_like_yes_no_options(pool):
        return match_option(default_yes_no_answer, pool)

    return None


def last_resort_choice(options: list[str]) -> str | None:
    '''
    The final guess when a choice question cannot be answered any other way and
    the job is being submitted regardless. Skips Naukri's "Skip this question"
    style opt-outs so position alone cannot decide the answer.
    '''
    if not options:
        return None
    pool = [o for o in options if not _is_skip_option(o)] or options
    return pool[0]


def _is_skip_option(option: str) -> bool:
    '''`True` for Naukri's "Skip this question" style opt-out choices.'''
    lowered = (option or "").strip().lower()
    return any(phrase in lowered for phrase in
               ("skip this question", "skip question", "prefer not", "not disclose", "decline to"))


def _looks_like_yes_no_options(options: list[str]) -> bool:
    '''`True` when the options are a yes/no pair, in any order.'''
    lowered = {(o or "").strip().lower() for o in options}
    return bool(lowered & {"yes", "y"}) and bool(lowered & {"no", "n"})


# Range options as Naukri writes them: 'No experience', '<2 years', '2-3 years',
# '3-4 years', '>4 years', '5+ years', 'Less than 1 year', 'More than 10 years'.
_re_band_between = re.compile(r'(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)')
_re_band_plus = re.compile(r'(\d+(?:\.\d+)?)\s*\+')
_re_band_number = re.compile(r'(\d+(?:\.\d+)?)')


def _parse_band(option: str) -> tuple[float, float] | None:
    '''
    Parses one option into the inclusive `(low, high)` range of values it covers.
    Returns `None` when the option carries no number at all.
    '''
    text = (option or "").strip().lower()
    if not text:
        return None

    if 'fresher' in text or 'no experience' in text or 'none' in text or 'not applicable' in text:
        return (0.0, 0.0)

    between = _re_band_between.search(text)
    if between:
        low, high = float(between.group(1)), float(between.group(2))
        return (min(low, high), max(low, high))

    plus = _re_band_plus.search(text)
    if plus:
        return (float(plus.group(1)), float('inf'))

    number = _re_band_number.search(text)
    if not number:
        return None
    value = float(number.group(1))

    is_less = any(m in text for m in ('<', 'less than', 'under', 'below', 'upto', 'up to', 'fewer'))
    is_more = any(m in text for m in ('>', 'more than', 'over', 'above', 'at least', 'greater'))
    if is_less:
        # '<2 years' covers everything strictly below 2.
        return (0.0, value - 0.01)
    if is_more:
        return (value + 0.01, float('inf'))
    return (value, value)


def match_numeric_band(answer: str, options: list[str]) -> str | None:
    '''
    Picks the option whose numeric range contains `answer`.

    This is what makes "2" choose "2-3 years" instead of "<2 years" out of
    `['No experience', '<2 years', '2-3 years', '3-4 years', '>4 years']`.
    When bands overlap, the lowest matching band wins, so the answer never
    overstates experience.
    '''
    if not options:
        return None
    try:
        value = float(str(answer).strip())
    except (TypeError, ValueError):
        return None

    bands: list[tuple[float, float, str]] = []
    for option in options:
        band = _parse_band(option)
        if band:
            bands.append((band[0], band[1], option))
    if not bands:
        return None

    containing = [b for b in bands if b[0] <= value <= b[1]]
    if containing:
        # Bands touch at their edges ('1-2 Yrs' and '2-5 Yrs' both contain 2).
        # Prefer the band the value *starts*, so 2 years reads as '2-5 Yrs'
        # instead of being understated as '1-2 Yrs'; otherwise take the lowest
        # band, so the answer never overstates experience.
        return min(containing, key=lambda b: (0 if b[0] == value else 1, b[0], b[1]))[2]

    # Value sits outside every band: take the closest band instead of guessing.
    def distance(band: tuple[float, float, str]) -> float:
        low, high, _ = band
        if value < low:
            return low - value
        return value - high if high != float('inf') else 0.0

    return min(bands, key=distance)[2]


def match_option(answer: str, options: list[str]) -> str | None:
    '''
    Finds the option that best represents `answer`.
    Mirrors the phrase-matching fallbacks used by LinkedIn's `answer_questions()`.
    '''
    if not answer or not options:
        return None
    answer = str(answer).strip()

    # 1. Exact (case-insensitive) match
    for option in options:
        if option.strip().lower() == answer.lower():
            return option

    # 2. A bare number against range options is a banding question, not a
    #    substring search ("2" must not match "<2 years").
    if re.fullmatch(r'\d+(?:\.\d+)?', answer):
        banded = match_numeric_band(answer, options)
        if banded:
            return banded

    # 3. Known synonym phrases
    if answer.lower() == 'decline':
        phrases = ["decline", "not wish", "don't wish", "prefer not", "not want", "not disclose"]
    elif answer.lower() in ('yes', 'y'):
        phrases = ["yes", "agree", "i do", "i have"]
    elif answer.lower() in ('no', 'n'):
        phrases = ["no", "disagree", "i don't", "i do not", "none"]
    else:
        phrases = [answer.lower(), ''.join(c for c in answer if c.isalnum()).lower()]

    for phrase in phrases:
        if not phrase:
            continue
        for option in options:
            option_low = option.strip().lower()
            if phrase in option_low or option_low in phrase:
                return option

    return None


def ask_in_terminal(question: str, options: list[str] | None = None) -> str:
    '''
    Asks the user for an answer on stdin.

    `pause_at_failed_question` relies on pyautogui's Tk dialogs, which raise
    `TclError` on machines with a broken Tk install - there the bot silently fell
    through to its guess. The terminal is always available when the bot is run by
    hand, so this is the dependable version of the same prompt.

    Returns `""` when the user skips, or when there is no interactive terminal.
    '''
    import sys

    if not ask_in_terminal_on_failed_question:
        return ""
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return ""
    except Exception:
        return ""

    print("\n" + "=" * 70)
    print("The bot could not answer this application question:")
    print(f'  "{question}"')
    if options:
        print("\nOptions:")
        for index, option in enumerate(options, start=1):
            print(f"  {index}. {option}")
        print("\nType the option number or its exact text. Press Enter alone to skip this job.")
    else:
        print("\nType the answer to fill in. Press Enter alone to skip this job.")
    print("=" * 70)

    try:
        reply = input("Your answer: ").strip()
    except (EOFError, KeyboardInterrupt, OSError):
        return ""

    if not reply:
        return ""
    if options and reply.isdigit():
        index = int(reply) - 1
        if 0 <= index < len(options):
            return options[index]
    return reply

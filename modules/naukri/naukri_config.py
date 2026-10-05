'''
Naukri configuration adapter.

Reads the *existing* project configuration (`config/search.py`,
`config/settings.py`, `config/secrets.py`) and translates it into the values
Naukri's search understands. Every Naukri-only setting is read through
`_opt()` with a default, so the bot keeps working even if a user's config
files predate the Naukri feature.

Nothing here is imported by `runAiBot.py`; LinkedIn is unaffected.
'''

from config import search as _search
from config import settings as _settings
from config import secrets as _secrets

from modules.helpers import print_lg


def _opt(module, name: str, default):
    '''Reads an optional config value, falling back to `default` when absent or None.'''
    value = getattr(module, name, None)
    return default if value is None else value


#< ------ Naukri-only settings (all optional, backward compatible) ------
naukri_file_name: str = _opt(_settings, 'naukri_file_name', "all excels/all_applied_applications_history_naukri.csv")
naukri_failed_file_name: str = _opt(_settings, 'naukri_failed_file_name', "all excels/all_failed_applications_history_naukri.csv")
max_pages_per_search: int = int(_opt(_settings, 'naukri_max_pages_per_search', 5))
max_chatbot_rounds: int = int(_opt(_settings, 'naukri_max_chatbot_rounds', 15))
salary_filter: str = str(_opt(_settings, 'naukri_salary_filter', "")).strip()
_experience_override = getattr(_settings, 'naukri_experience_years', None)
#>


#< ------ Credentials: Naukri-specific if given, else reuse the shared ones ------
def get_credentials() -> tuple[str, str]:
    '''
    Returns `(username, password)` for Naukri.
    Falls back to the shared `username` / `password` from `config/secrets.py`.
    '''
    user = str(_opt(_secrets, 'naukri_username', "")).strip()
    pwd = str(_opt(_secrets, 'naukri_password', "")).strip()
    if not user:
        user = str(_opt(_secrets, 'username', "")).strip()
    if not pwd:
        pwd = str(_opt(_secrets, 'password', "")).strip()
    return user, pwd


def credentials_are_placeholders() -> bool:
    '''`True` when credentials are still the shipped placeholders, so we must ask the human.'''
    user, pwd = get_credentials()
    placeholders = {"", "username@example.com", "example_password"}
    return user in placeholders or pwd in placeholders
#>


#< ------ Translation of shared LinkedIn-flavoured config into Naukri params ------

# `date_posted` (config/search.py) -> Naukri's `jobAge` in days
JOB_AGE_MAP = {
    "Past 24 hours": 1,
    "Past week": 7,
    "Past month": 30,
    "Any time": None,
    "": None,
}

# `sort_by` (config/search.py) -> Naukri's `sort` query value
SORT_MAP = {
    "Most recent": "f",     # freshness / date
    "Most relevant": "r",   # relevance
    "": None,
}

# `sort_by` -> visible label in Naukri's sort dropdown (UI fallback)
SORT_UI_LABEL_MAP = {
    "Most recent": "Date",
    "Most relevant": "Relevance",
}

# `on_site` (config/search.py) -> Naukri's `wfhType`
WORK_MODE_MAP = {
    "On-site": "0",
    "Remote": "2",
    "Hybrid": "3",
}

# `job_type` (config/search.py) -> visible label in Naukri's "Employment type" filter (UI fallback)
JOB_TYPE_UI_LABEL_MAP = {
    "Full-time": "Full Time",
    "Part-time": "Part Time",
    "Contract": "Contractual",
    "Temporary": "Temporary",
    "Internship": "Internship",
    "Volunteer": "Volunteer",
    "Other": "Other",
}

# `experience_level` (config/search.py) -> approximate years, used only when
# `current_experience` is unusable (-1) and no explicit override is given.
EXPERIENCE_LEVEL_YEARS_MAP = {
    "Internship": 0,
    "Entry level": 0,
    "Associate": 2,
    "Mid-Senior level": 5,
    "Director": 10,
    "Executive": 15,
}


def get_experience_years() -> int | None:
    '''
    Years of experience to send to Naukri's search.
    Priority: `naukri_experience_years` -> `current_experience` -> lowest matching
    `experience_level`. Returns `None` when experience should not be filtered on.
    '''
    if _experience_override is not None:
        try:
            return max(0, int(_experience_override))
        except (TypeError, ValueError):
            print_lg(f'Invalid `naukri_experience_years` value "{_experience_override}", ignoring it.')

    current = getattr(_search, 'current_experience', -1)
    if isinstance(current, int) and current > -1:
        return current

    levels = getattr(_search, 'experience_level', []) or []
    years = [EXPERIENCE_LEVEL_YEARS_MAP[level] for level in levels if level in EXPERIENCE_LEVEL_YEARS_MAP]
    return min(years) if years else None


def get_job_age(date_posted: str | None = None) -> int | None:
    '''Naukri `jobAge` (in days) derived from `date_posted`. `None` means no filter.'''
    value = getattr(_search, 'date_posted', "") if date_posted is None else date_posted
    return JOB_AGE_MAP.get(value)


def get_sort(sort_by: str | None = None) -> str | None:
    '''Naukri `sort` query value derived from `sort_by`. `None` means no explicit sort.'''
    value = getattr(_search, 'sort_by', "") if sort_by is None else sort_by
    return SORT_MAP.get(value)


def get_sort_ui_label(sort_by: str | None = None) -> str | None:
    '''Visible sort-dropdown label, used when the URL parameter did not take effect.'''
    value = getattr(_search, 'sort_by', "") if sort_by is None else sort_by
    return SORT_UI_LABEL_MAP.get(value)


def get_work_modes() -> list[str]:
    '''Naukri `wfhType` values derived from `on_site`. Empty list means no filter.'''
    modes = getattr(_search, 'on_site', []) or []
    values = [WORK_MODE_MAP[mode] for mode in modes if mode in WORK_MODE_MAP]
    # Selecting every mode is the same as selecting none, and a shorter URL is safer.
    if len(values) >= len(WORK_MODE_MAP):
        return []
    return values


def get_job_type_labels() -> list[str]:
    '''Visible "Employment type" filter labels derived from `job_type`.'''
    types = getattr(_search, 'job_type', []) or []
    return [JOB_TYPE_UI_LABEL_MAP[t] for t in types if t in JOB_TYPE_UI_LABEL_MAP]


def describe() -> str:
    '''Human readable summary of the resolved Naukri search configuration, for the logs.'''
    return (
        f"  Search terms      : {getattr(_search, 'search_terms', [])}\n"
        f"  Search location   : '{getattr(_search, 'search_location', '')}'\n"
        f"  Experience (yrs)  : {get_experience_years()}\n"
        f"  Job age (days)    : {get_job_age()}\n"
        f"  Sort              : {getattr(_search, 'sort_by', '')} -> '{get_sort()}'\n"
        f"  Work modes        : {getattr(_search, 'on_site', [])} -> {get_work_modes()}\n"
        f"  Employment types  : {get_job_type_labels()}\n"
        f"  Salary filter     : '{salary_filter}'\n"
        f"  Apply on Naukri only (easy_apply_only): {getattr(_search, 'easy_apply_only', False)}\n"
        f"  Applications per search term (switch_number): {getattr(_search, 'switch_number', 0)}\n"
        f"  Max pages per search term: {max_pages_per_search}"
    )
#>

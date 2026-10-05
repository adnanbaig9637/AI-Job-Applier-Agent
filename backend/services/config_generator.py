"""
Config generator: builds a temporary `config/` Python package per agent run
from the user's DB data, so runAiBot.py's `from config.* import *` resolves to
the temp package (via PYTHONPATH) without touching the original config files.

Generated files mirror the originals:
  - config/personals.py
  - config/questions.py
  - config/search.py
  - config/secrets.py
  - config/settings.py
  - config/__init__.py
"""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import (
    AgentConfig, JobPreference, LinkedInSession, Resume, UserProfile, User,
)


def _py_list(items) -> str:
    """Render a Python list literal from an iterable."""
    return "[" + ", ".join(repr(str(i)) for i in (items or [])) + "]"


def _py_str(value) -> str:
    """Render a Python string literal (triple-quoted for multiline)."""
    if value is None:
        return '""'
    s = str(value)
    if "\n" in s:
        # triple-quoted; escape any existing triple quotes
        s = s.replace('"""', '\\"\\"\\"')
        return f'"""\n{s}\n"""'
    return repr(s)


async def build_temp_config(
    db: AsyncSession,
    user_id,
    run_id,
    cdp_port: Optional[int] = None,
) -> Path:
    """
    Build a temp config/ package for one run. Returns the temp directory path
    (the PARENT dir containing the `config/` package, to be prepended to PYTHONPATH).
    """
    # Load all user data
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalar_one_or_none()
    prefs = (await db.execute(select(JobPreference).where(JobPreference.user_id == user_id))).scalar_one_or_none()
    agent_cfg = (await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == user_id, AgentConfig.is_active == True)
    )).scalar_one_or_none()
    linkedin = (await db.execute(select(LinkedInSession).where(LinkedInSession.user_id == user_id))).scalar_one_or_none()
    default_resume = (await db.execute(
        select(Resume).where(Resume.user_id == user_id, Resume.is_default == True)
    )).scalar_one_or_none()
    if default_resume is None:
        # fall back to most recent
        default_resume = (await db.execute(
            select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        )).scalars().first()

    # Create temp dir
    temp_root = Path(tempfile.mkdtemp(prefix=f"jp_run_{run_id}_"))
    config_pkg = temp_root / "config"
    config_pkg.mkdir(parents=True, exist_ok=True)

    # ---- config/__init__.py ----
    (config_pkg / "__init__.py").write_text('"""Auto-generated temp config package for JobPilot run."""\n')

    # ---- config/personals.py ----
    p = profile or UserProfile(user_id=user_id)
    (config_pkg / "personals.py").write_text(_personals_py(p))

    # ---- config/questions.py ----
    (config_pkg / "questions.py").write_text(_questions_py(p, default_resume))

    # ---- config/search.py ----
    j = prefs or JobPreference(user_id=user_id)
    (config_pkg / "search.py").write_text(_search_py(j))

    # ---- config/secrets.py ----
    from core.security import decrypt_secret
    linkedin_username = linkedin.username if linkedin else "username@example.com"
    linkedin_password = "example_password"
    if linkedin and linkedin.password_enc:
        try:
            linkedin_password = decrypt_secret(linkedin.password_enc)
        except Exception:
            linkedin_password = "example_password"

    ai_settings = (agent_cfg.ai_settings_json if agent_cfg else {}) or {}
    (config_pkg / "secrets.py").write_text(_secrets_py(
        username=linkedin_username,
        password=linkedin_password,
        ai_settings=ai_settings,
    ))

    # ---- config/settings.py ----
    s_settings = (agent_cfg.settings_json if agent_cfg else {}) or {}
    (config_pkg / "settings.py").write_text(_settings_py(
        run_id=run_id,
        settings_overrides=s_settings,
        cdp_port=cdp_port,
    ))

    return temp_root


# ---------------------------------------------------------------------------
# File template functions
# ---------------------------------------------------------------------------

def _personals_py(p: UserProfile) -> str:
    return f'''"""Auto-generated personals config (JobPilot). Do not edit by hand."""
first_name = {_py_str(p.first_name)}
middle_name = {_py_str(p.middle_name)}
last_name = {_py_str(p.last_name)}
phone_number = {_py_str(p.phone_number)}
current_city = {_py_str(p.current_city)}
street = {_py_str(p.street)}
state = {_py_str(p.state)}
zipcode = {_py_str(p.zipcode)}
country = {_py_str(p.country)}
ethnicity = {_py_str(p.ethnicity)}
gender = {_py_str(p.gender)}
disability_status = {_py_str(p.disability_status)}
veteran_status = {_py_str(p.veteran_status)}
'''


def _questions_py(p: UserProfile, resume) -> str:
    resume_path = ""
    if resume:
        resume_path = resume.stored_path
    return f'''"""Auto-generated questions config (JobPilot). Do not edit by hand."""
default_resume_path = {_py_str(resume_path)}
years_of_experience = {_py_str(p.years_of_experience)}
require_visa = {_py_str(p.require_visa)}
website = {_py_str(p.website)}
linkedIn = {_py_str(p.linkedin_url)}
us_citizenship = {_py_str(p.us_citizenship)}
desired_salary = {int(p.desired_salary or 0)}
current_ctc = {int(p.current_ctc or 0)}
currency = {_py_str(p.currency)}
notice_period = {int(p.notice_period or 30)}
linkedin_headline = {_py_str(p.linkedin_headline)}
linkedin_summary = {_py_str(p.linkedin_summary)}
cover_letter = {_py_str(p.cover_letter)}
user_information_all = {_py_str(p.user_information_all)}
recent_employer = {_py_str(p.recent_employer)}
confidence_level = {_py_str(p.confidence_level)}
pause_before_submit = {bool(p.pause_before_submit)}
pause_at_failed_question = {bool(p.pause_at_failed_question)}
overwrite_previous_answers = {bool(p.overwrite_previous_answers)}
'''


def _search_py(j: JobPreference) -> str:
    return f'''"""Auto-generated search config (JobPilot). Do not edit by hand."""
search_terms = {_py_list(j.search_terms)}
search_location = {_py_str(j.search_location)}
switch_number = {int(j.switch_number or 30)}
randomize_search_order = {bool(j.randomize_search_order)}
sort_by = {_py_str(j.sort_by)}
date_posted = {_py_str(j.date_posted)}
salary = {_py_str(j.salary)}
easy_apply_only = {bool(j.easy_apply_only)}
experience_level = {_py_list(j.experience_level)}
job_type = {_py_list(j.job_type)}
on_site = {_py_list(j.on_site)}
companies = {_py_list(j.companies)}
location = {_py_list(j.location)}
industry = {_py_list(j.industry)}
job_function = {_py_list(j.job_function)}
job_titles = {_py_list(j.job_titles)}
benefits = {_py_list(j.benefits)}
commitments = {_py_list(j.commitments)}
under_10_applicants = {bool(j.under_10_applicants)}
in_your_network = {bool(j.in_your_network)}
fair_chance_employer = {bool(j.fair_chance_employer)}
pause_after_filters = {bool(j.pause_after_filters)}
about_company_bad_words = {_py_list(j.about_company_bad_words)}
about_company_good_words = {_py_list(j.about_company_good_words)}
bad_words = {_py_list(j.bad_words)}
security_clearance = {bool(j.security_clearance)}
did_masters = {bool(j.did_masters)}
current_experience = {int(j.current_experience if j.current_experience is not None else -1)}
'''


def _secrets_py(username: str, password: str, ai_settings: dict) -> str:
    use_ai = bool(ai_settings.get("use_AI", False))
    ai_provider = ai_settings.get("ai_provider", "openai")
    llm_api_url = ai_settings.get("llm_api_url", "https://api.openai.com/v1/")
    llm_api_key = ai_settings.get("llm_api_key", "not-needed")
    llm_model = ai_settings.get("llm_model", "gpt-4o-mini")
    llm_spec = ai_settings.get("llm_spec", "openai")
    stream_output = bool(ai_settings.get("stream_output", False))
    return f'''"""Auto-generated secrets config (JobPilot). Do not edit by hand.
NOTE: This file is generated per-run from the encrypted DB store and lives in a
temporary directory. It is deleted after the run completes.
"""
username = {_py_str(username)}
password = {_py_str(password)}
use_AI = {use_ai}
ai_provider = {_py_str(ai_provider)}
llm_api_url = {_py_str(llm_api_url)}
llm_api_key = {_py_str(llm_api_key)}
llm_model = {_py_str(llm_model)}
llm_spec = {_py_str(llm_spec)}
stream_output = {stream_output}
'''


def _settings_py(run_id, settings_overrides: dict, cdp_port: Optional[int]) -> str:
    """Generate settings.py with per-run CSV paths + optional CDP port env hint."""
    # Per-run CSV paths so the agent writes to temp files (not shared CSVs)
    temp_csv_dir = Path(tempfile.gettempdir()) / f"jp_csv_{run_id}"
    temp_csv_dir.mkdir(parents=True, exist_ok=True)
    applied_csv = str(temp_csv_dir / "applied.csv")
    failed_csv = str(temp_csv_dir / "failed.csv")
    logs_dir = str(temp_csv_dir / "logs")
    Path(logs_dir).mkdir(parents=True, exist_ok=True)

    # Defaults mirror the original config/settings.py
    defaults = {
        "close_tabs": True,
        "follow_companies": False,
        "run_non_stop": False,        # backend controls re-runs, not the agent
        "alternate_sortby": False,
        "cycle_date_posted": False,
        "stop_date_cycle_at_24hr": True,
        "generated_resume_path": "all resumes/",
        "file_name": applied_csv,
        "failed_file_name": failed_csv,
        "logs_folder_path": logs_dir,
        "click_gap": 1,
        "run_in_background": False,    # headed so user can see / HITL
        "disable_extensions": False,
        "safe_mode": True,            # guest profile for isolation
        "smooth_scroll": False,
        "keep_screen_awake": True,
        "stealth_mode": True,
        "showAiErrorAlerts": False,
    }
    # Apply user overrides
    defaults.update({k: v for k, v in (settings_overrides or {}).items() if k in defaults})

    lines = ['"""Auto-generated settings config (JobPilot). Do not edit by hand."""']
    for k, v in defaults.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {v}")
        elif isinstance(v, int):
            lines.append(f"{k} = {v}")
        elif isinstance(v, str):
            lines.append(f"{k} = {_py_str(v)}")
        else:
            lines.append(f"{k} = {v!r}")
    # CDP port hint (read by our minimal open_chrome.py patch via env var)
    if cdp_port:
        lines.append(f"\n# CDP remote debugging port (set by backend for screenshot streaming)")
    return "\n".join(lines) + "\n"


def cleanup_temp_config(temp_root: Path) -> None:
    """Remove the temp config dir after a run."""
    try:
        shutil.rmtree(temp_root, ignore_errors=True)
    except Exception:
        pass

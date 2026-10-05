'''
Job relevance filtering.

The existing screening in this project is entirely *negative*: reject a job if
it contains a bad word, asks for clearance, or wants too much experience.
That is enough on LinkedIn, whose search is already tight and whose Easy Apply
filter narrows things further.

Naukri's keyword search is much looser -- a search for "AI Engineer" genuinely
returns .NET, QA and support roles -- so it also needs a *positive* gate:
a job must look like something you actually want before it is applied to.

This module is platform-neutral and config-driven. It is currently wired into
the Naukri bot only; `runAiBot.py` (LinkedIn) is untouched and keeps its
existing behaviour.
'''

import re

from config import search as _search
from config.search import bad_words


def _opt(name: str, default):
    '''Reads an optional config value, falling back to `default` when absent or None.'''
    value = getattr(_search, name, None)
    return default if value is None else value


#< ------ Relevance configuration (all optional, empty list = rule disabled) ------
required_title_words: list[str] = _opt('naukri_required_title_words', [])
excluded_title_words: list[str] = _opt('naukri_excluded_title_words', [])
required_skills: list[str] = _opt('naukri_required_skills', [])
min_skill_matches: int = int(_opt('naukri_min_skill_matches', 0))
#>


def _normalise(text: str) -> str:
    '''Lowercases and collapses whitespace so multi-word terms match reliably.'''
    return re.sub(r'\s+', ' ', (text or '').lower()).strip()


def _contains_term(haystack: str, term: str) -> bool:
    '''
    Whole-term containment check.

    Plain substring matching is unusable here: "AI" would match "chair" and
    "maintain", and ".NET" would match "subnetting". So a term only counts when
    it is not glued to another letter or digit on either side. This keeps
    "AI/ML", "AI-driven" and "(.NET)" matching while rejecting "chair".
    '''
    if not term:
        return False
    pattern = r'(?<![a-z0-9])' + re.escape(_normalise(term)) + r'(?![a-z0-9])'
    return re.search(pattern, haystack) is not None


def matched_terms(text: str, terms: list[str]) -> list[str]:
    '''Returns every term from `terms` that appears in `text` as a whole term.'''
    haystack = _normalise(text)
    return [term for term in terms if _contains_term(haystack, term)]


def check_relevance(title: str, description: str = "", company: str = "") -> tuple[bool, str | None]:
    '''
    Decides whether a job is worth applying to.

    Rules are applied in order, strongest first. Every rule is skipped when its
    config list is empty, so an unconfigured setup behaves exactly as before.

    ### Returns `(relevant, reason)`
    - `relevant`: `True` when the job passes every configured rule.
    - `reason`: `None` when relevant, otherwise why it was rejected.
    '''
    title = title or ""

    # 1. Explicitly unwanted role in the title. Strongest signal, checked first.
    hits = matched_terms(title, excluded_title_words)
    if hits:
        return False, f'Title contains excluded word(s) {hits}'

    # 2. The existing `bad_words` list also applies to the title, not just the
    #    job description. This is what catches ".NET Developer" when the
    #    description fails to load.
    hits = matched_terms(title, bad_words)
    if hits:
        return False, f'Title contains bad word(s) {hits}'

    # 3. The title must positively look like a role you want.
    if required_title_words:
        hits = matched_terms(title, required_title_words)
        if not hits:
            return False, (f'Title "{title}" matched none of the required title words')

    # 4. The job must mention enough of your actual skills.
    if required_skills and min_skill_matches > 0:
        # Search the title too, so a well-named role with a thin description passes.
        hits = matched_terms(f"{title} {description}", required_skills)
        if len(hits) < min_skill_matches:
            return False, (f'Only {len(hits)} of your skills found ({hits}), '
                           f'need at least {min_skill_matches}')

    return True, None


def check_title_only(title: str) -> tuple[bool, str | None]:
    '''
    Title-only relevance pre-check, safe to run straight off a search result card.

    Lets the bot reject obviously wrong roles before spending a page load on
    them. Skill matching is deliberately skipped here because the card has no
    job description yet.
    '''
    title = title or ""

    hits = matched_terms(title, excluded_title_words)
    if hits:
        return False, f'Title contains excluded word(s) {hits}'

    hits = matched_terms(title, bad_words)
    if hits:
        return False, f'Title contains bad word(s) {hits}'

    if required_title_words:
        hits = matched_terms(title, required_title_words)
        if not hits:
            return False, f'Title "{title}" matched none of the required title words'

    return True, None


def describe() -> str:
    '''Human readable summary of the active relevance rules, for the logs.'''
    if not (required_title_words or excluded_title_words or (required_skills and min_skill_matches)):
        return "  Relevance filter  : DISABLED (no naukri_required_title_words / " \
               "naukri_excluded_title_words / naukri_required_skills configured)"
    return (
        f"  Required title words : {len(required_title_words)} configured "
        f"-> {required_title_words[:6]}{' ...' if len(required_title_words) > 6 else ''}\n"
        f"  Excluded title words : {len(excluded_title_words)} configured "
        f"-> {excluded_title_words[:6]}{' ...' if len(excluded_title_words) > 6 else ''}\n"
        f"  Required skills      : {len(required_skills)} configured, "
        f"need at least {min_skill_matches} match(es) per job"
    )

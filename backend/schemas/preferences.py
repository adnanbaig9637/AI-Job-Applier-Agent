"""Job preferences schemas (maps config/search.py)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel


class JobPreferenceIn(BaseModel):
    search_terms: List[str] = []
    search_location: str = ""
    switch_number: int = 30
    randomize_search_order: bool = False
    sort_by: str = "Most recent"
    date_posted: str = "Past week"
    salary: str = ""
    easy_apply_only: bool = True
    experience_level: List[str] = []
    job_type: List[str] = []
    on_site: List[str] = []
    companies: List[str] = []
    location: List[str] = []
    industry: List[str] = []
    job_function: List[str] = []
    job_titles: List[str] = []
    benefits: List[str] = []
    commitments: List[str] = []
    under_10_applicants: bool = False
    in_your_network: bool = False
    fair_chance_employer: bool = False
    pause_after_filters: bool = False
    about_company_bad_words: List[str] = []
    about_company_good_words: List[str] = []
    bad_words: List[str] = []
    security_clearance: bool = False
    did_masters: bool = False
    current_experience: int = -1


class JobPreferenceOut(JobPreferenceIn):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

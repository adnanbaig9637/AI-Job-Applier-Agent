"""Profile schemas (maps config/personals.py + questions.py profile fields)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserProfileIn(BaseModel):
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    phone_number: str = ""
    current_city: str = ""
    street: str = ""
    state: str = ""
    zipcode: str = ""
    country: str = ""
    ethnicity: str = "Decline"
    gender: str = ""
    disability_status: str = "No"
    veteran_status: str = "Decline"
    years_of_experience: str = "0"
    require_visa: str = "No"
    website: str = ""
    linkedin_url: str = ""
    us_citizenship: str = ""
    desired_salary: int = 0
    current_ctc: int = 0
    currency: str = "INR"
    notice_period: int = 30
    linkedin_headline: str = ""
    linkedin_summary: str = ""
    cover_letter: str = ""
    user_information_all: str = ""
    recent_employer: str = ""
    confidence_level: str = "5"
    pause_before_submit: bool = False
    pause_at_failed_question: bool = True
    overwrite_previous_answers: bool = False


class UserProfileOut(UserProfileIn):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

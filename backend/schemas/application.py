"""Job application schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class JobApplicationOut(BaseModel):
    id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    job_id: str
    title: Optional[str] = None
    company: Optional[str] = None
    work_location: Optional[str] = None
    work_style: Optional[str] = None
    experience_required: Optional[str] = None
    hr_name: Optional[str] = None
    hr_link: Optional[str] = None
    resume_filename: Optional[str] = None
    reposted: bool = False
    date_posted: Optional[str] = None
    date_applied: Optional[str] = None
    job_link: Optional[str] = None
    external_job_link: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobApplicationList(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[JobApplicationOut]


class ApplicationSummary(BaseModel):
    total: int
    applied: int
    external: int
    skipped: int
    failed: int
    rejected: int

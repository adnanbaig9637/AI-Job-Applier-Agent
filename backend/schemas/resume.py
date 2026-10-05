"""Resume schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResumeOut(BaseModel):
    id: uuid.UUID
    filename: str
    size_bytes: int
    mime_type: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeSetDefault(BaseModel):
    resume_id: uuid.UUID

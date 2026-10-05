"""Agent run + HITL schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AgentRunOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    easy_applied_count: int = 0
    external_jobs_count: int = 0
    failed_count: int = 0
    skip_count: int = 0
    total_runs: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunLogOut(BaseModel):
    id: int
    seq: int
    level: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunLogList(BaseModel):
    total: int
    items: List[AgentRunLogOut]


class StartRunRequest(BaseModel):
    agent_config_id: Optional[uuid.UUID] = None


class HitlOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    type: str
    prompt_text: str
    options: List[str] = []
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class HitlResolveRequest(BaseModel):
    resolution: str = "continue"


class RunSummaryOut(BaseModel):
    run_id: uuid.UUID
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    easy_applied_count: int = 0
    external_jobs_count: int = 0
    failed_count: int = 0
    skip_count: int = 0
    total_runs: int = 0
    total_scanned: int = 0

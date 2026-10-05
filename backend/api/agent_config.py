"""Agent config API: GET / POST /api/agent-config (settings + AI settings overrides)."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.database import get_db
from db.models import AgentConfig, User
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent-config", tags=["agent-config"])


class AgentConfigIn(BaseModel):
    name: str = "default"
    settings_json: dict[str, Any] = {}
    ai_settings_json: dict[str, Any] = {}
    is_active: bool = True


class AgentConfigOut(AgentConfigIn):
    id: uuid.UUID
    user_id: uuid.UUID

    model_config = {"from_attributes": True}


async def _get_active_config(db: AsyncSession, user_id) -> AgentConfig:
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == user_id, AgentConfig.is_active == True)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        # Create default
        cfg = AgentConfig(user_id=user_id, name="default", is_active=True)
        db.add(cfg)
        await db.flush()
    return cfg


@router.get("", response_model=AgentConfigOut)
async def get_agent_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_active_config(db, current_user.id)
    await db.commit()
    return cfg


@router.post("", response_model=AgentConfigOut)
async def set_agent_config(
    payload: AgentConfigIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_active_config(db, current_user.id)
    cfg.name = payload.name
    cfg.settings_json = payload.settings_json
    cfg.ai_settings_json = payload.ai_settings_json
    cfg.is_active = payload.is_active
    await db.commit()
    await db.refresh(cfg)
    return cfg

"""Job preferences API: GET / POST /api/job-preferences."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.database import get_db
from db.models import JobPreference, User
from schemas.preferences import JobPreferenceIn, JobPreferenceOut

router = APIRouter(prefix="/api", tags=["job-preferences"])


async def _get_or_create_prefs(db: AsyncSession, user_id) -> JobPreference:
    result = await db.execute(select(JobPreference).where(JobPreference.user_id == user_id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        prefs = JobPreference(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


@router.get("/job-preferences", response_model=JobPreferenceOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_or_create_prefs(db, current_user.id)
    await db.commit()
    return prefs


@router.post("/job-preferences", response_model=JobPreferenceOut)
async def set_preferences(
    payload: JobPreferenceIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _get_or_create_prefs(db, current_user.id)
    for field, value in payload.model_dump().items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs

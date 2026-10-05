"""Applications API: GET /api/job-applications (paginated, filtered)."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.database import get_db
from db.models import JobApplication, User
from schemas.application import ApplicationSummary, JobApplicationList, JobApplicationOut

router = APIRouter(prefix="/api", tags=["applications"])


@router.get("/job-applications", response_model=JobApplicationList)
async def list_applications(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(JobApplication).where(JobApplication.user_id == current_user.id)
    count_q = select(func.count()).select_from(JobApplication).where(JobApplication.user_id == current_user.id)

    if status_filter and status_filter != "all":
        q = q.where(JobApplication.status == status_filter)
        count_q = count_q.where(JobApplication.status == status_filter)

    if search:
        q = q.where(
            (JobApplication.title.ilike(f"%{search}%"))
            | (JobApplication.company.ilike(f"%{search}%"))
        )
        count_q = count_q.where(
            (JobApplication.title.ilike(f"%{search}%"))
            | (JobApplication.company.ilike(f"%{search}%"))
        )

    total = (await db.execute(count_q)).scalar_one()
    q = q.order_by(JobApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return JobApplicationList(total=total, page=page, page_size=page_size, items=items)


@router.get("/job-applications/summary", response_model=ApplicationSummary)
async def applications_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(func.count()).select_from(JobApplication).where(JobApplication.user_id == current_user.id)
    total = (await db.execute(base)).scalar_one()
    applied = (await db.execute(base.where(JobApplication.status == "applied"))).scalar_one()
    external = (await db.execute(base.where(JobApplication.status == "external"))).scalar_one()
    skipped = (await db.execute(base.where(JobApplication.status == "skipped"))).scalar_one()
    failed = (await db.execute(base.where(JobApplication.status == "failed"))).scalar_one()
    rejected = (await db.execute(base.where(JobApplication.status == "rejected"))).scalar_one()
    return ApplicationSummary(
        total=total, applied=applied, external=external,
        skipped=skipped, failed=failed, rejected=rejected,
    )


@router.get("/job-applications/recent", response_model=list[JobApplicationOut])
async def recent_applications(
    limit: int = Query(6, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(JobApplication)
        .where(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.created_at.desc())
        .limit(limit)
    )
    return (await db.execute(q)).scalars().all()

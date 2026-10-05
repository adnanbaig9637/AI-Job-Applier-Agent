"""Resumes API: upload, list, set-default, delete. Files on disk + DB metadata."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_user
from db.database import get_db
from db.models import Resume, User
from schemas.resume import ResumeOut, ResumeSetDefault

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _user_dir(user_id: uuid.UUID) -> Path:
    d = settings.uploads_path / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("", response_model=list[ResumeOut])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    is_default: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate size
    contents = await file.read()
    max_bytes = settings.MAX_RESUME_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Resume exceeds {settings.MAX_RESUME_SIZE_MB}MB limit")

    # Sanitize filename
    safe_name = Path(file.filename or "resume.pdf").name
    stored_path = _user_dir(current_user.id) / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(contents)

    # If is_default, unset other defaults
    if is_default:
        await db.execute(
            update(Resume).where(Resume.user_id == current_user.id).values(is_default=False)
        )

    resume = Resume(
        user_id=current_user.id,
        filename=safe_name,
        stored_path=str(stored_path),
        size_bytes=len(contents),
        mime_type=file.content_type or "application/pdf",
        is_default=is_default,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.post("/set-default", response_model=dict)
async def set_default_resume(
    payload: ResumeSetDefault,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Unset others
    await db.execute(
        update(Resume).where(Resume.user_id == current_user.id).values(is_default=False)
    )
    result = await db.execute(
        select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.is_default = True
    await db.commit()
    return {"message": "Default resume updated", "resume_id": str(resume.id)}


@router.delete("/{resume_id}", response_model=dict)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    # Remove file from disk
    try:
        Path(resume.stored_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(resume)
    await db.commit()
    return {"message": "Resume deleted"}

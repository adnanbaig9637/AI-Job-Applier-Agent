"""Auth API: register, login, OTP (mock), users/me."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.security import create_access_token, hash_password, verify_password
from db.database import get_db
from db.models import User, UserProfile, JobPreference
from schemas.auth import (
    LoginRequest, OtpSendRequest, OtpVerifyRequest, RegisterRequest,
    TokenResponse, UserOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()  # get user.id

    # Create empty profile + preferences rows
    db.add(UserProfile(user_id=user.id))
    db.add(JobPreference(user_id=user.id))
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        is_new_user=True,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Determine if user has completed onboarding (profile first_name set)
    prof = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = prof.scalar_one_or_none()
    is_new = profile is None or not profile.first_name

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        is_new_user=bool(is_new),
    )


# ---- OTP (mock / stub for phone auth) ----
# In production this would integrate an SMS gateway. For local dev we accept any 6-digit code.
@router.post("/otp/send")
async def otp_send(payload: OtpSendRequest):
    # Mock: pretend we sent an OTP. Real implementation would call SMS provider.
    return {"message": f"OTP sent to {payload.phone}", "demo_code": "123456"}


@router.post("/otp/verify")
async def otp_verify(payload: OtpVerifyRequest, db: AsyncSession = Depends(get_db)):
    # Mock: accept "123456" or any code for local dev.
    if payload.code != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP code (demo code is 123456)")
    # Look up user by phone; if none, return a flag so UI can prompt registration.
    result = await db.execute(select(User).where(User.phone == payload.phone))
    user = result.scalar_one_or_none()
    if not user:
        return {"registered": False, "message": "Phone not registered. Please register with email."}
    token = create_access_token(str(user.id))
    return {"registered": True, "access_token": token, "user_id": str(user.id)}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

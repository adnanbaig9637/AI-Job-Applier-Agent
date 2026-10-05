"""Auth + user schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    email: str
    is_new_user: bool = False


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    phone: Optional[str] = None
    is_active: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OtpSendRequest(BaseModel):
    phone: str = Field(min_length=6)


class OtpVerifyRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)

"""SQLAlchemy ORM models — mirror the SQL schema in migrations/001_init.sql."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Integer, LargeBinary, String, Text, TIMESTAMP, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base


# ---------------------------------------------------------------------------
# Enum-like string columns (kept as VARCHAR for simplicity; DB enforces via ENUM)
# We use String + server_default to stay compatible with async inserts.
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    preferences: Mapped[Optional["JobPreference"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    resumes: Mapped[List["Resume"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    agent_configs: Mapped[List["AgentConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    linkedin_session: Mapped[Optional["LinkedInSession"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    runs: Mapped[List["AgentRun"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    # personals
    first_name: Mapped[str] = mapped_column(String(100), default="")
    middle_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    phone_number: Mapped[str] = mapped_column(String(20), default="")
    current_city: Mapped[str] = mapped_column(String(100), default="", server_default="")
    street: Mapped[str] = mapped_column(String(255), default="", server_default="")
    state: Mapped[str] = mapped_column(String(100), default="", server_default="")
    zipcode: Mapped[str] = mapped_column(String(20), default="", server_default="")
    country: Mapped[str] = mapped_column(String(100), default="", server_default="")
    ethnicity: Mapped[str] = mapped_column(String(50), default="Decline", server_default="Decline")
    gender: Mapped[str] = mapped_column(String(50), default="", server_default="")
    disability_status: Mapped[str] = mapped_column(String(20), default="No", server_default="No")
    veteran_status: Mapped[str] = mapped_column(String(20), default="Decline", server_default="Decline")
    # questions (profile-level)
    years_of_experience: Mapped[str] = mapped_column(String(10), default="0")
    require_visa: Mapped[str] = mapped_column(String(5), default="No", server_default="No")
    website: Mapped[str] = mapped_column(Text, default="", server_default="")
    linkedin_url: Mapped[str] = mapped_column(Text, default="", server_default="")
    us_citizenship: Mapped[str] = mapped_column(String(100), default="", server_default="")
    desired_salary: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_ctc: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(10), default="INR", server_default="INR")
    notice_period: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    linkedin_headline: Mapped[str] = mapped_column(Text, default="", server_default="")
    linkedin_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    cover_letter: Mapped[str] = mapped_column(Text, default="", server_default="")
    user_information_all: Mapped[str] = mapped_column(Text, default="", server_default="")
    recent_employer: Mapped[str] = mapped_column(String(255), default="", server_default="")
    confidence_level: Mapped[str] = mapped_column(String(5), default="5")
    pause_before_submit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    pause_at_failed_question: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    overwrite_previous_answers: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")


class JobPreference(Base):
    __tablename__ = "job_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    search_terms: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    search_location: Mapped[str] = mapped_column(String(255), default="", server_default="")
    switch_number: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    randomize_search_order: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort_by: Mapped[str] = mapped_column(String(50), default="Most recent", server_default="Most recent")
    date_posted: Mapped[str] = mapped_column(String(50), default="Past week", server_default="Past week")
    salary: Mapped[str] = mapped_column(String(50), default="", server_default="")
    easy_apply_only: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    experience_level: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    job_type: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    on_site: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    companies: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    location: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    industry: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    job_function: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    job_titles: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    benefits: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    commitments: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    under_10_applicants: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    in_your_network: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    fair_chance_employer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    pause_after_filters: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    about_company_bad_words: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    about_company_good_words: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    bad_words: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    security_clearance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    did_masters: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    current_experience: Mapped[int] = mapped_column(Integer, default=-1, server_default="-1")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="preferences")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="resumes")


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), default="default", server_default="default")
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    ai_settings_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="agent_configs")
    runs: Mapped[List["AgentRun"]] = relationship(back_populates="agent_config")


class LinkedInSession(Base):
    __tablename__ = "linkedin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255))
    password_enc: Mapped[bytes] = mapped_column(LargeBinary)
    cookies_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    profile_dir: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="linkedin_session")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent_config_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True)
    pid: Mapped[Optional[int]] = mapped_column(Integer)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    easy_applied_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    external_jobs_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    skip_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    temp_config_dir: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="runs")
    agent_config: Mapped[Optional["AgentConfig"]] = relationship(back_populates="runs")
    logs: Mapped[List["AgentRunLog"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    applications: Mapped[List["JobApplication"]] = relationship(back_populates="run")
    interventions: Mapped[List["HumanInterventionRequest"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    browser_session: Mapped[Optional["BrowserSession"]] = relationship(back_populates="run", uselist=False, cascade="all, delete-orphan")


class AgentRunLog(Base):
    __tablename__ = "agent_run_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="info", server_default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_line: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    run: Mapped["AgentRun"] = relationship(back_populates="logs")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    company: Mapped[Optional[str]] = mapped_column(Text)
    work_location: Mapped[Optional[str]] = mapped_column(Text)
    work_style: Mapped[Optional[str]] = mapped_column(Text)
    about_job: Mapped[Optional[str]] = mapped_column(Text)
    experience_required: Mapped[Optional[str]] = mapped_column(Text)
    skills_required: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    hr_name: Mapped[Optional[str]] = mapped_column(Text)
    hr_link: Mapped[Optional[str]] = mapped_column(Text)
    resume_filename: Mapped[Optional[str]] = mapped_column(Text)
    reposted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    date_posted: Mapped[Optional[str]] = mapped_column(Text)
    date_applied: Mapped[Optional[str]] = mapped_column(Text)
    job_link: Mapped[Optional[str]] = mapped_column(Text)
    external_job_link: Mapped[Optional[str]] = mapped_column(Text)
    questions_found: Mapped[Optional[dict]] = mapped_column(JSONB)
    connect_request: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="applied", server_default="applied")
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    screenshot_name: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    run: Mapped[Optional["AgentRun"]] = relationship(back_populates="applications")


class HumanInterventionRequest(Base):
    __tablename__ = "human_intervention_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), default="other", server_default="other")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    run: Mapped["AgentRun"] = relationship(back_populates="interventions")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="none", server_default="none")
    cdp_url: Mapped[Optional[str]] = mapped_column(Text)
    debugging_port: Mapped[Optional[int]] = mapped_column(Integer)
    last_screenshot_path: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    run: Mapped["AgentRun"] = relationship(back_populates="browser_session")

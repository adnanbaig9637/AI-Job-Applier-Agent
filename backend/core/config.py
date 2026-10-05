"""Application settings loaded from environment variables / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/ is one level below repo root
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_auto_pilot"
    DATABASE_URL_SYNC: str = "postgresql+postgres:postgres@localhost:5432/job_auto_pilot"

    # JWT
    JWT_SECRET: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Encryption
    AES_KEY: str = "change-me-to-a-fernet-key"

    # Server
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Uploads
    UPLOADS_DIR: str = "backend/uploads"
    MAX_RESUME_SIZE_MB: int = 10

    # Agent
    REPO_ROOT: str = "."
    CDP_PORT_START: int = 9223

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def uploads_path(self) -> Path:
        p = Path(self.UPLOADS_DIR)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p

    @property
    def resolved_repo_root(self) -> Path:
        r = Path(self.REPO_ROOT)
        return r.resolve() if r.is_absolute() else (REPO_ROOT / r).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

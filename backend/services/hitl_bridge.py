"""
HITL bridge: in-process event bus for human-in-the-loop requests.

The agent subprocess (via the pyautogui shim) writes HITL requests to the DB
and then blocks on a threading.Event. The backend's resolve endpoint sets the
resolution and signals the event so the agent continues.

Since the agent runs in a separate subprocess, the shim communicates with the
backend via the shared database (poll the human_intervention_requests row).
This avoids any IPC complexity and works across process boundaries.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.models import HumanInterventionRequest


async def create_hitl(
    run_id,
    user_id,
    type_: str,
    prompt_text: str,
    options: Optional[list[str]] = None,
) -> str:
    """Create a HITL request row and return its id (as string)."""
    async with AsyncSessionLocal() as db:
        hitl = HumanInterventionRequest(
            run_id=run_id,
            user_id=user_id,
            type=type_,
            prompt_text=prompt_text,
            options=options or [],
            status="pending",
        )
        db.add(hitl)
        await db.commit()
        await db.refresh(hitl)
        return str(hitl.id)


async def resolve_hitl(hitl_id: str, resolution: str = "continue") -> bool:
    """Mark a HITL request as resolved. Returns True if found."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(HumanInterventionRequest).where(HumanInterventionRequest.id == uuid.UUID(hitl_id))
        )
        hitl = result.scalar_one_or_none()
        if hitl is None:
            return False
        hitl.resolution = resolution
        hitl.status = "resolved"
        from datetime import datetime, timezone
        hitl.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        return True


async def get_pending_hitl_for_run(run_id) -> Optional[dict]:
    """Get the most recent pending HITL for a run (for SSE polling)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(HumanInterventionRequest)
            .where(HumanInterventionRequest.run_id == run_id, HumanInterventionRequest.status == "pending")
            .order_by(HumanInterventionRequest.created_at.desc())
            .limit(1)
        )
        hitl = result.scalar_one_or_none()
        if hitl is None:
            return None
        return {
            "id": str(hitl.id),
            "run_id": str(hitl.run_id),
            "type": hitl.type,
            "prompt_text": hitl.prompt_text,
            "options": hitl.options,
            "status": hitl.status,
            "created_at": hitl.created_at.isoformat() if hitl.created_at else None,
        }

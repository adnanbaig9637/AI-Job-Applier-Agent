"""
Agent runner: spawns runAiBot.py as a subprocess with a temp config injected
via PYTHONPATH, captures stdout/stderr line-by-line into the DB, and supports
stop via process termination.

Key design:
- runAiBot.py is NOT modified. It's launched as `python runAiBot.py`.
- PYTHONPATH = <temp_config_root>;<repo_root> so `from config.* import *`
  resolves to the temp config package first.
- The pyautogui shim + sitecustomize.py live in <temp_config_root> so they're
  auto-imported at interpreter startup (before the agent imports pyautogui).
- stdout/stderr are read asynchronously and stored as agent_run_logs rows.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.database import AsyncSessionLocal
from db.models import AgentRun, AgentRunLog, BrowserSession
from services.config_generator import build_temp_config, cleanup_temp_config
from services.csv_importer import import_run_csvs


# In-memory registry of active runs (run_id -> Process + log queue)
_active_runs: dict[str, dict] = {}


def _build_dsn() -> str:
    """Build a psycopg2-style DSN from the async DATABASE_URL for the shim."""
    # asyncpg URL: postgresql+asyncpg://user:pass@host:port/db
    url = settings.DATABASE_URL.replace("+asyncpg", "")
    return url  # psycopg2 accepts postgresql:// URLs


async def start_run(
    db: AsyncSession,
    user_id,
    run_id,
    agent_config_id: Optional[uuid.UUID] = None,
) -> Path:
    """Generate temp config, spawn the agent subprocess, begin log capture."""
    # Allocate a CDP port for this run
    cdp_port = settings.CDP_PORT_START + (len(_active_runs) % 100)

    # Build temp config (returns the root dir containing config/ package)
    temp_root = await build_temp_config(db, user_id, run_id, cdp_port=cdp_port)

    # Copy the pyautogui shim + sitecustomize into temp_root so they're importable
    import shutil
    services_dir = Path(__file__).resolve().parent
    shutil.copy(services_dir / "pyautogui_shim.py", temp_root / "pyautogui_shim.py")
    shutil.copy(services_dir / "sitecustomize.py", temp_root / "sitecustomize.py")

    # Set up environment for the subprocess
    env = os.environ.copy()
    # PYTHONPATH: temp_root first (so config/ + sitecustomize resolve), then repo root
    sep = ";" if sys.platform == "win32" else ":"
    env["PYTHONPATH"] = sep.join([str(temp_root), str(settings.resolved_repo_root)])
    env["JP_RUN_ID"] = str(run_id)
    env["JP_USER_ID"] = str(user_id)
    env["JP_DATABASE_URL_DSN"] = _build_dsn()
    env["JP_HITL_TIMEOUT"] = "3600"
    # CDP port hint for our minimal open_chrome.py patch
    env["JP_REMOTE_DEBUG_PORT"] = str(cdp_port)

    # Launch the agent
    repo_root = settings.resolved_repo_root
    cmd = [sys.executable, "runAiBot.py"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(repo_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    # Update run record
    await db.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id)
        .values(
            status="running",
            pid=proc.pid,
            started_at=datetime.now(timezone.utc),
            temp_config_dir=str(temp_root),
        )
    )
    await db.commit()

    # Create browser_session row
    db.add(BrowserSession(
        run_id=run_id,
        provider="cdp_windows" if sys.platform == "win32" else "cdp_linux_xvfb",
        cdp_url=f"http://127.0.0.1:{cdp_port}",
        debugging_port=cdp_port,
    ))
    await db.commit()

    # Register + start log capture task
    _active_runs[str(run_id)] = {"proc": proc, "temp_root": temp_root}
    asyncio.create_task(_capture_logs(run_id, proc))

    return temp_root


async def _capture_logs(run_id, proc: asyncio.subprocess.Process):
    """Read subprocess stdout line-by-line, store in DB."""
    seq = 0
    assert proc.stdout is not None
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n\r")
            if not text:
                continue
            seq += 1
            level = _classify_log_level(text)
            await _store_log(run_id, seq, level, text)
    except Exception as e:
        await _store_log(run_id, seq + 1, "error", f"[log capture error] {e}")
    finally:
        # Wait for process exit
        exit_code = await proc.wait()
        await _finalize_run(run_id, exit_code)


def _classify_log_level(text: str) -> str:
    t = text.lower()
    if "critical" in t or "traceback" in t or "error" in t and "failed" in t:
        if "critical" in t:
            return "critical"
        return "error"
    if "failed" in t or "error" in t or "exception" in t:
        return "error"
    if "warn" in t or "skip" in t:
        return "warn"
    return "info"


async def _store_log(run_id, seq: int, level: str, message: str):
    try:
        async with AsyncSessionLocal() as db:
            db.add(AgentRunLog(
                run_id=uuid.UUID(run_id) if isinstance(run_id, str) else run_id,
                seq=seq,
                level=level,
                message=message,
                raw_line=message,
            ))
            await db.commit()
    except Exception:
        pass  # don't let log storage crash the capture loop


async def _finalize_run(run_id, exit_code: int):
    """Update run status + import CSVs when the subprocess exits."""
    run_uuid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
    status = "completed" if exit_code == 0 else ("stopped" if exit_code in (-15, 1) and _was_stopped(run_id) else "failed")

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id == run_uuid)
            .values(
                status=status,
                ended_at=datetime.now(timezone.utc),
                error_message=None if status == "completed" else f"Agent exited with code {exit_code}",
            )
        )
        await db.commit()

    # Import CSV outputs into DB
    try:
        await import_run_csvs(run_uuid)
    except Exception as e:
        await _store_log(run_id, 99999, "error", f"[CSV import error] {e}")

    # Cleanup temp config
    info = _active_runs.pop(str(run_id), None)
    if info:
        cleanup_temp_config(info["temp_root"])


def _was_stopped(run_id) -> bool:
    """Check if this run was explicitly stopped by the user."""
    info = _active_runs.get(str(run_id))
    return bool(info and info.get("stopped", False))


async def stop_run(run_id) -> bool:
    """Terminate the agent subprocess gracefully."""
    info = _active_runs.get(str(run_id))
    if not info:
        return False
    proc: asyncio.subprocess.Process = info["proc"]
    info["stopped"] = True
    try:
        if sys.platform == "win32":
            # Windows: terminate the process tree
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True


def is_run_active(run_id) -> bool:
    return str(run_id) in _active_runs

"""
pyautogui shim: monkeypatches pyautogui.alert/confirm/prompt inside the agent
subprocess so that HITL prompts surface as UI events instead of desktop popups.

This file is placed in a directory that is prepended to PYTHONPATH BEFORE the
agent runs, via a `sitecustomize.py` that imports this shim at interpreter
startup. The shim imports the real pyautogui, then replaces its alert/confirm/
prompt functions with versions that:
  1. Write a human_intervention_requests row to the DB (via asyncpg sync call).
  2. Poll the DB until the row is resolved (or timeout).
  3. Return the user's choice to the agent (mimicking pyautogui's return value).

The shim reads connection info and run/user IDs from environment variables:
  JP_DATABASE_URL_DSN  — psycopg2-style DSN (e.g. "postgresql://user:pass@host:port/db")
  JP_RUN_ID            — UUID of the current agent run
  JP_USER_ID           — UUID of the current user
  JP_HITL_TIMEOUT      — seconds to wait before auto-resolving (default 3600)
"""
from __future__ import annotations

import os
import sys
import time
import uuid

# Only patch if we're running under JobPilot control
_JP_ENABLED = bool(os.environ.get("JP_RUN_ID") and os.environ.get("JP_USER_ID"))

if _JP_ENABLED:
    import pyautogui as _real_pyautogui

    _JP_DSN = os.environ.get("JP_DATABASE_URL_DSN", "")
    _JP_RUN_ID = os.environ.get("JP_RUN_ID")
    _JP_USER_ID = os.environ.get("JP_USER_ID")
    _JP_TIMEOUT = int(os.environ.get("JP_HITL_TIMEOUT", "3600"))

    # Use psycopg2 (sync) for the subprocess — simpler than async in a blocking shim
    try:
        import psycopg2
        _HAS_PSYCOPG2 = True
    except ImportError:
        _HAS_PSYCOPG2 = False
        # Fallback: if psycopg2 not available, fall back to real pyautogui
        sys.stderr.write("[JobPilot shim] psycopg2 not available; HITL disabled, using desktop popups.\n")

    if _HAS_PSYCOPG2 and _JP_DSN:
        def _db_conn():
            return psycopg2.connect(_JP_DSN)

        def _create_hitl(type_: str, prompt_text: str, options=None) -> str:
            opts = options or []
            hid = str(uuid.uuid4())
            with _db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO human_intervention_requests
                           (id, run_id, user_id, type, prompt_text, options, status, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, 'pending', now())""",
                        (hid, _JP_RUN_ID, _JP_USER_ID, type_, prompt_text, opts),
                    )
                conn.commit()
            return hid

        def _wait_for_resolution(hitl_id: str, timeout: int) -> str:
            start = time.time()
            while time.time() - start < timeout:
                with _db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT resolution, status FROM human_intervention_requests WHERE id = %s",
                            (hitl_id,),
                        )
                        row = cur.fetchone()
                if row and row[1] == "resolved":
                    return row[0] or "continue"
                time.sleep(1.0)
            # Timeout: auto-resolve
            with _db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE human_intervention_requests SET status='timeout', resolved_at=now() WHERE id=%s",
                        (hitl_id,),
                    )
                conn.commit()
            return "continue"

        def _jp_alert(text, title="Alert", button="OK", **kwargs):
            """Replacement for pyautogui.alert. Returns the button text."""
            sys.stdout.write(f"[JobPilot HITL][alert] {title}: {text}\n")
            sys.stdout.flush()
            hitl_id = _create_hitl("manual_confirm", f"{title}\n\n{text}", [button])
            _wait_for_resolution(hitl_id, _JP_TIMEOUT)
            return button

        def _jp_confirm(text, title="Confirm", buttons=None, **kwargs):
            """Replacement for pyautogui.confirm. Returns the chosen button text."""
            if buttons is None:
                buttons = ["OK", "Cancel"]
            sys.stdout.write(f"[JobPilot HITL][confirm] {title}: {text}\n")
            sys.stdout.flush()
            hitl_id = _create_hitl("manual_confirm", f"{title}\n\n{text}", list(buttons))
            resolution = _wait_for_resolution(hitl_id, _JP_TIMEOUT)
            # Match resolution to a button; default to first if no match
            for b in buttons:
                if b.lower() in (resolution or "").lower():
                    return b
            return buttons[0] if buttons else "OK"

        def _jp_prompt(text, title="Prompt", default="", **kwargs):
            """Replacement for pyautogui.prompt. Returns user input string."""
            sys.stdout.write(f"[JobPilot HITL][prompt] {title}: {text}\n")
            sys.stdout.flush()
            hitl_id = _create_hitl("manual_confirm", f"{title}\n\n{text} (default: {default})", [])
            resolution = _wait_for_resolution(hitl_id, _JP_TIMEOUT)
            return resolution if resolution and resolution != "continue" else default

        # Patch the real pyautogui module's attributes
        _real_pyautogui.alert = _jp_alert
        _real_pyautogui.confirm = _jp_confirm
        _real_pyautogui.prompt = _jp_prompt
        # Also patch pyautogui.press (used for keep_screen_awake) — pass through, no HITL
        # (press is not a HITL action; leave it as the real implementation)
        sys.stderr.write("[JobPilot shim] pyautogui HITL patching active.\n")
    else:
        sys.stderr.write("[JobPilot shim] HITL disabled (no DSN/psycopg2); using desktop popups.\n")

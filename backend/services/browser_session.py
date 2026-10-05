"""
Browser session service: takes screenshots of the agent's Chrome via CDP
(Chrome DevTools Protocol) for streaming to the UI.

The agent's Chrome is launched with --remote-debugging-port=<port> (injected
via the JP_REMOTE_DEBUG_PORT env var read by our minimal open_chrome.py patch).
This service connects to that CDP endpoint and captures screenshots using raw
CDP WebSocket calls — no Playwright dependency needed.
"""
from __future__ import annotations

import asyncio
import base64
import json
import urllib.request
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.models import BrowserSession


async def get_cdp_url(run_id) -> Optional[str]:
    """Get the CDP URL for a run's browser session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BrowserSession).where(BrowserSession.run_id == run_id))
        bs = result.scalar_one_or_none()
        return bs.cdp_url if bs else None


def _cdp_http_get(url: str) -> dict:
    """Synchronous GET to a CDP HTTP endpoint (used in thread executor)."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def take_screenshot(cdp_url: str) -> Optional[bytes]:
    """
    Connect to Chrome via CDP and capture a screenshot as JPEG bytes.

    Uses the CDP HTTP API to find the page target, then a WebSocket to call
    Page.captureScreenshot. Runs blocking I/O in a thread executor.
    """
    try:
        loop = asyncio.get_event_loop()
        # 1. Get the list of browser targets
        tabs = await loop.run_in_executor(None, _cdp_http_get, f"{cdp_url}/json")
        if not tabs:
            return None
        # Find the first page-type target
        page_target = next((t for t in tabs if t.get("type") == "page"), None)
        if not page_target:
            return None
        ws_url = page_target.get("webSocketDebuggerUrl")
        if not ws_url:
            return None

        # 2. Connect via WebSocket and call Page.captureScreenshot
        import websockets
        async with websockets.connect(ws_url, max_size=None) as ws:
            # Enable Page domain
            await ws.send(json.dumps({"id": 1, "method": "Page.enable", "params": {}}))
            await ws.recv()
            # Capture screenshot
            await ws.send(json.dumps({
                "id": 2,
                "method": "Page.captureScreenshot",
                "params": {"format": "jpeg", "quality": 60},
            }))
            resp = json.loads(await ws.recv())
            data = resp.get("result", {}).get("data")
            if data:
                return base64.b64decode(data)
    except Exception:
        return None
    return None


async def screenshot_loop(cdp_url: str, interval: float = 1.5):
    """Async generator yielding base64 JPEG strings for SSE streaming."""
    while True:
        img_bytes = await take_screenshot(cdp_url)
        if img_bytes:
            yield base64.b64encode(img_bytes).decode("ascii")
        await asyncio.sleep(interval)

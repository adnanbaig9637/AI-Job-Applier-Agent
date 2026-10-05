"""
sitecustomize.py — auto-imported by Python at interpreter startup.

This file is placed in the temp config root dir (prepended to PYTHONPATH) so
that when the agent subprocess starts, Python auto-imports it BEFORE the agent
imports pyautogui. The shim then patches pyautogui's alert/confirm/prompt.

This is the most reliable way to monkeypatch pyautogui in a subprocess without
editing runAiBot.py: sitecustomize.py is guaranteed to run at startup.
"""
# Import the shim which conditionally patches pyautogui if JP_RUN_ID is set.
try:
    import pyautogui_shim  # noqa: F401
except Exception as _e:
    import sys
    sys.stderr.write(f"[sitecustomize] pyautogui_shim import failed: {_e}\n")

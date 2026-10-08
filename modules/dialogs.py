"""Dialogs that remain safe when Tk/Tcl or the desktop is unavailable.

Informational alerts may fall back to console output. Actions and pauses require
an explicit response, unless the caller supplies a conservative cancel choice.
This module must not import helpers, because helpers uses it while logging.
"""

from importlib import import_module
import sys


class DialogUnavailableError(RuntimeError):
    """A required user decision could not be obtained."""


_dialogs_available = True


def _show_dialog(kind: str, *args):
    global _dialogs_available
    if not _dialogs_available:
        return None
    try:
        return getattr(import_module("pyautogui"), kind)(*args)
    except Exception as exception:
        _dialogs_available = False
        # Exception messages can contain page/form values; only log their type.
        print(f"Pop-up dialogs are unavailable ({type(exception).__name__}). "
              "Instructions will appear in the console instead.", flush=True)
        return None


def alert(text: str, title: str = "", button: str = "OK") -> str | None:
    """Show information; use acknowledge() when continuing requires a human."""
    print(f"[{title}] {text}", flush=True)
    return _show_dialog("alert", text, title, button)


def _terminal_choice(buttons: list[str]) -> str | None:
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return None
        print("Choose an option in this terminal:", flush=True)
        for number, button in enumerate(buttons, start=1):
            print(f"  {number}. {button}", flush=True)
        while True:
            answer = input("Enter the option number (or q to cancel): ").strip()
            if answer.lower() == "q":
                return None
            for number, button in enumerate(buttons, start=1):
                if answer == str(number) or answer.casefold() == button.casefold():
                    return button
            print("Please enter one of the listed options.", flush=True)
    except (EOFError, OSError):
        return None


def confirm(text: str, title: str = "", buttons: list[str] | None = None,
            default: str | None = None) -> str:
    """Get an explicit choice, or a caller-provided conservative cancel default.

Without a default, closing the dialog or losing interactive input stops the
operation with DialogUnavailableError. Never supply an approval as a default.
"""
    buttons = buttons or ["OK", "Cancel"]
    if default is not None and default not in buttons:
        raise ValueError("The dialog default must be one of its buttons.")
    print(f"[{title}] {text}", flush=True)
    response = _show_dialog("confirm", text, title, buttons)
    if response is None and not _dialogs_available:
        response = _terminal_choice(buttons)
    if response in buttons:
        return response
    if default is not None:
        print(f"No confirmation received; choosing '{default}'.", flush=True)
        return default
    raise DialogUnavailableError(
        f"'{title or 'Confirmation'}' requires your response. "
        "Run from an interactive terminal or repair Python's Tcl/Tk installation."
    )


def acknowledge(text: str, title: str = "", button: str = "Continue") -> str:
    """Pause until the user explicitly acknowledges, without auto-continuing."""
    return confirm(text, title, [button])

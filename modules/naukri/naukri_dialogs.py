'''
Safe wrappers around pyautogui's dialog boxes.

pyautogui's `alert` / `confirm` / `prompt` are Tk based, and on machines where
Tk is missing or broken they raise `TclError` instead of showing a dialog.
A human-in-the-loop prompt is a convenience, never a reason to lose a whole
run, so every dialog here degrades to a logged message plus a caller-supplied
default answer.
'''

import pyautogui

from modules.helpers import print_lg


_dialogs_available = True


def _unavailable(exception: Exception) -> None:
    '''Logs the first dialog failure and stops attempting dialogs for the rest of the run.'''
    global _dialogs_available
    if _dialogs_available:
        print_lg("Pop-up dialogs are unavailable on this machine "
                 f"({type(exception).__name__}: {str(exception).splitlines()[0]}). "
                 "The Naukri bot will continue using its configured defaults instead of asking you.")
    _dialogs_available = False


def alert(text: str, title: str = "", button: str = "OK") -> str | None:
    '''Shows an informational dialog. Returns `None` when dialogs are unavailable.'''
    print_lg(f"[{title}] {text}")
    if not _dialogs_available:
        return None
    try:
        return pyautogui.alert(text, title, button)
    except Exception as e:
        _unavailable(e)
        return None


def confirm(text: str, title: str = "", buttons: list[str] | None = None, default: str = "") -> str:
    '''
    Asks the user to pick one of `buttons`.
    * Returns `default` when dialogs are unavailable or the user closes the box.
    '''
    buttons = buttons or ["OK", "Cancel"]
    print_lg(f"[{title}] {text}")
    if not _dialogs_available:
        print_lg(f"  -> dialogs unavailable, assuming \"{default}\"")
        return default
    try:
        response = pyautogui.confirm(text, title, buttons)
    except Exception as e:
        _unavailable(e)
        return default
    return default if response is None else response


def prompt(text: str, title: str = "", default_value: str = "") -> str:
    '''
    Asks the user to type an answer.
    * Returns `""` when dialogs are unavailable or the user cancels.
    '''
    print_lg(f"[{title}] {text}")
    if not _dialogs_available:
        print_lg("  -> dialogs unavailable, skipping the manual answer")
        return ""
    try:
        response = pyautogui.prompt(text, title, default_value)
    except Exception as e:
        _unavailable(e)
        return ""
    return (response or "").strip()


def keep_awake() -> None:
    '''Nudges the keyboard to keep the screen awake, ignoring unsupported environments.'''
    try:
        pyautogui.press('shiftright')
    except Exception:
        pass

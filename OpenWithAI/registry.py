import os
import sys
from contextlib import suppress

import winreg

APP_NAME = "Open with AI"
VERB_NAME = "OpenWithAI"
APP_DIR = os.path.dirname(__file__)
APP_ICON = os.path.join(APP_DIR, "assets", "icon.ico")
APP_EXE = sys.executable.replace("python.exe", "pythonw.exe")
MAIN_PATH = os.path.join(APP_DIR, "main.py")
APP_COMMAND = f'"{APP_EXE}" "{MAIN_PATH}" "%1"'
STARTUP_COMMAND = f'"{APP_EXE}" "{MAIN_PATH}"'
ACTIVE_CONTEXT_MENU_PATHS = [
    rf"Software\Classes\AllFilesystemObjects\shell\{VERB_NAME}",
]
REMOVE_CONTEXT_MENU_PATHS = [
    rf"Software\Classes\AllFilesystemObjects\shell\{VERB_NAME}",
    rf"Software\Classes\*\shell\{VERB_NAME}",
    rf"Software\Classes\Directory\shell\{VERB_NAME}",
]
STARTUP_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _set_string(key, name, value):
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def add_context_menu():
    try:
        for key_path in ACTIVE_CONTEXT_MENU_PATHS:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            _set_string(key, "", APP_NAME)
            _set_string(key, "Icon", APP_ICON)
            _set_string(key, "MultiSelectModel", "Player")
            _set_string(key, "Position", "Top")

            command_key = winreg.CreateKey(key, "command")
            _set_string(command_key, "", APP_COMMAND)
            winreg.CloseKey(command_key)
            winreg.CloseKey(key)
        print("Context menu added successfully.")
        return True
    except Exception as exc:
        print(f"Failed to add context menu: {exc}")
        return False


def remove_context_menu():
    removed_any = False
    for key_path in REMOVE_CONTEXT_MENU_PATHS:
        with suppress(FileNotFoundError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            removed_any = True
    if removed_any:
        print("Context menu removed successfully.")
    return removed_any


def add_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "OpenWithAITray", 0, winreg.REG_SZ, STARTUP_COMMAND)
        winreg.CloseKey(key)
        print("Startup added successfully.")
        return True
    except Exception as exc:
        print(f"Failed to add to startup: {exc}")
        return False


def remove_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        with suppress(FileNotFoundError):
            winreg.DeleteValue(key, "OpenWithAITray")
        winreg.CloseKey(key)
        print("Startup removed successfully.")
        return True
    except Exception:
        return False


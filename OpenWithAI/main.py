import atexit
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

import keyboard
from PIL import Image
from pystray import Icon, Menu, MenuItem

import browser
from app_runtime import configure_exception_logging, log_exception
from history import get_history
from ipc import (
    collect_pending_files,
    enqueue_file_selection,
    get_pending_payload_count,
    release_primary_lock,
    try_acquire_primary_lock,
)
from registry import remove_context_menu, remove_startup
from settings import RUNTIME_DIR, ensure_app_dirs, load_settings, save_settings

logger = configure_exception_logging()
TRAY_LOCK_PATH = os.path.join(RUNTIME_DIR, "tray.lock")

icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
if not os.path.exists(icon_path):
    img = Image.new("RGB", (64, 64), color=(0, 255, 204))
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)
    img.save(icon_path)


def _show_message(title, text, kind="info"):
    root = tk.Tk()
    root.withdraw()
    try:
        if kind == "error":
            messagebox.showerror(title, text, parent=root)
        elif kind == "warning":
            messagebox.showwarning(title, text, parent=root)
        else:
            messagebox.showinfo(title, text, parent=root)
    finally:
        root.destroy()


def _pid_exists(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def release_tray_lock():
    if not os.path.exists(TRAY_LOCK_PATH):
        return
    try:
        with open(TRAY_LOCK_PATH, "r", encoding="utf-8") as file_obj:
            owner_pid = int((file_obj.read() or "0").strip())
    except (OSError, ValueError):
        owner_pid = 0

    if owner_pid not in (0, os.getpid()):
        return

    try:
        os.remove(TRAY_LOCK_PATH)
    except OSError:
        pass


def acquire_tray_lock():
    ensure_app_dirs()
    if os.path.exists(TRAY_LOCK_PATH):
        try:
            with open(TRAY_LOCK_PATH, "r", encoding="utf-8") as file_obj:
                existing_pid = int((file_obj.read() or "0").strip())
        except (OSError, ValueError):
            existing_pid = 0

        if _pid_exists(existing_pid):
            return False
        try:
            os.remove(TRAY_LOCK_PATH)
        except OSError:
            return False

    try:
        with open(TRAY_LOCK_PATH, "x", encoding="utf-8") as file_obj:
            file_obj.write(str(os.getpid()))
        atexit.register(release_tray_lock)
        return True
    except FileExistsError:
        return False


def exit_app(icon, item):
    del item
    release_tray_lock()
    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        logger.debug("Keyboard hotkeys were not active during shutdown.")
    icon.stop()


def _ask_choice(title, prompt, options, current=None):
    if not options:
        _show_message(title, "No options are available right now.", kind="warning")
        return None

    root = tk.Tk()
    root.withdraw()
    initial = current if current in options else options[0]
    text = f"{prompt}\nOptions: {', '.join(options)}"
    value = simpledialog.askstring(title, text, initialvalue=initial, parent=root)
    root.destroy()
    if not value:
        return None

    value = value.strip()
    if value not in options:
        _show_message(title, "Invalid option.", kind="error")
        return None
    return value


def tray_set_default_browser(icon, item):
    del icon, item
    settings = load_settings()
    choices = browser.get_installed_browsers(settings)
    picked = _ask_choice("Open with AI", "Choose default browser", choices, settings.get("default_browser"))
    if picked:
        settings["default_browser"] = picked
        save_settings(settings)


def tray_set_default_ai(icon, item):
    del icon, item
    settings = load_settings()
    ai_choices = browser.get_available_ais(settings)
    picked = _ask_choice("Open with AI", "Choose default AI", ai_choices, settings.get("default_ai"))
    if picked:
        settings["default_ai"] = picked
        save_settings(settings)


def tray_view_history(icon, item):
    del icon, item
    history = get_history()[:10]
    lines = []
    for idx, entry in enumerate(history, start=1):
        files = entry.get("files", [])
        ai_name = entry.get("ai", "Unknown")
        timestamp = entry.get("timestamp", "")
        summary = f"{idx}. {ai_name} -> {len(files)} file(s)"
        if timestamp:
            summary += f" [{timestamp}]"
        lines.append(summary)
        for file_path in files[:3]:
            lines.append(f"   - {file_path}")
    text = "No history yet." if not lines else "\n".join(lines)
    _show_message("Open with AI - History", text)


def tray_uninstall_context(icon, item):
    del icon, item
    remove_context_menu()
    remove_startup()
    _show_message("Open with AI", "Context menu and startup entry removed.")


def main_tray():
    if not acquire_tray_lock():
        logger.info("Tray mode is already running; skipping duplicate launch.")
        return

    image = Image.open(icon_path)
    menu = Menu(
        MenuItem("Set Default Browser", tray_set_default_browser),
        MenuItem("Set Default AI", tray_set_default_ai),
        MenuItem("View History", tray_view_history),
        MenuItem("Uninstall Context Menu", tray_uninstall_context),
        MenuItem("Exit", exit_app),
    )
    icon = Icon("OpenWithAI", image, "Open with AI", menu)

    def hotkey_handler():
        settings = load_settings()
        browser_name = settings.get("default_browser", "System Default")
        ai_name = settings.get("default_ai", "Claude")
        launched = browser.launch_ai(browser_name, ai_name, settings.get("custom_ai_urls", {}), [])
        if not launched:
            _show_message("Open with AI", "The AI page could not be opened in the selected browser.", kind="error")

    try:
        keyboard.add_hotkey("ctrl+shift+a", hotkey_handler)
    except Exception as exc:
        logger.warning("Global hotkey registration failed: %s", exc)

    icon.run()


def _wait_for_queue_to_settle(max_wait=4.0, settle_for=0.6, poll_interval=0.1):
    start = time.time()
    last_count = -1
    stable_since = None

    while time.time() - start < max_wait:
        count = get_pending_payload_count()
        if count == last_count:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= settle_for:
                return
        else:
            last_count = count
            stable_since = None
        time.sleep(poll_interval)


def handle_context_menu(files):
    if not files:
        return

    enqueue_file_selection(files)
    if not try_acquire_primary_lock():
        return

    try:
        _wait_for_queue_to_settle()
        unique_files = collect_pending_files()
        if unique_files:
            import popup

            popup.show_popup(unique_files)
    except Exception as exc:
        log_exception("Failed to display the file-selection popup.", exc)
        _show_message("Open with AI", "Something went wrong while opening the file picker popup.", kind="error")
    finally:
        release_primary_lock()


if __name__ == "__main__":
    ensure_app_dirs()
    if len(sys.argv) > 1:
        handle_context_menu(sys.argv[1:])
    else:
        main_tray()

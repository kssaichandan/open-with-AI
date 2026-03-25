import copy
import json
import os
import tempfile
from typing import Any, Dict, Iterable, List

APP_DIR_NAME = "OpenWithAI"
LEGACY_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
_DEFAULT_LOCAL_APPDATA = os.path.join(os.path.expanduser("~"), "AppData", "Local")
APP_DIR = os.environ.get("OPENWITHAI_APP_DIR") or os.path.join(
    os.environ.get("LOCALAPPDATA", _DEFAULT_LOCAL_APPDATA),
    APP_DIR_NAME,
)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
RUNTIME_DIR = os.path.join(APP_DIR, "runtime")
QUEUE_DIR = os.path.join(RUNTIME_DIR, "queue")
LOG_DIR = os.path.join(APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

DEFAULT_SETTINGS = {
    "default_browser": "System Default",
    "default_ai": "Claude",
    "custom_ai_urls": {},
    "custom_browsers": {},
    "history": [],
}


def ensure_app_dirs() -> None:
    for path in (APP_DIR, RUNTIME_DIR, QUEUE_DIR, LOG_DIR):
        os.makedirs(path, exist_ok=True)


def _default_settings() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_SETTINGS)


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    return data if isinstance(data, dict) else {}


def _sanitize_string_map(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}

    cleaned: Dict[str, str] = {}
    for raw_key, raw_item in value.items():
        if not isinstance(raw_key, str) or not isinstance(raw_item, str):
            continue
        key = raw_key.strip()
        item = raw_item.strip()
        if key and item:
            cleaned[key] = item
    return cleaned


def _sanitize_history(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    for entry in value[:10]:
        if not isinstance(entry, dict):
            continue

        ai_name = entry.get("ai") if isinstance(entry.get("ai"), str) else DEFAULT_SETTINGS["default_ai"]
        files = entry.get("files") if isinstance(entry.get("files"), list) else []
        safe_files = [item for item in files if isinstance(item, str) and item.strip()]
        if not safe_files:
            continue

        safe_entry: Dict[str, Any] = {"files": safe_files, "ai": ai_name.strip() or DEFAULT_SETTINGS["default_ai"]}
        timestamp = entry.get("timestamp")
        if isinstance(timestamp, str) and timestamp.strip():
            safe_entry["timestamp"] = timestamp.strip()
        cleaned.append(safe_entry)

    return cleaned


def sanitize_settings(data: Any) -> Dict[str, Any]:
    merged = _default_settings()
    if isinstance(data, dict):
        merged.update(data)

    browser_name = merged.get("default_browser")
    ai_name = merged.get("default_ai")
    merged["default_browser"] = browser_name.strip() if isinstance(browser_name, str) and browser_name.strip() else DEFAULT_SETTINGS["default_browser"]
    merged["default_ai"] = ai_name.strip() if isinstance(ai_name, str) and ai_name.strip() else DEFAULT_SETTINGS["default_ai"]
    merged["custom_ai_urls"] = _sanitize_string_map(merged.get("custom_ai_urls"))
    merged["custom_browsers"] = _sanitize_string_map(merged.get("custom_browsers"))
    merged["history"] = _sanitize_history(merged.get("history"))
    return merged


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    ensure_app_dirs()
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=4)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _load_raw_settings() -> Dict[str, Any]:
    ensure_app_dirs()
    if os.path.exists(CONFIG_FILE):
        return _read_json(CONFIG_FILE)

    if os.path.exists(LEGACY_CONFIG_FILE):
        legacy_data = _read_json(LEGACY_CONFIG_FILE)
        sanitized = sanitize_settings(legacy_data)
        _atomic_write_json(CONFIG_FILE, sanitized)
        return sanitized

    return _default_settings()


def load_settings() -> Dict[str, Any]:
    try:
        settings = sanitize_settings(_load_raw_settings())
    except Exception:
        settings = _default_settings()

    return settings


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = sanitize_settings(settings)
    _atomic_write_json(CONFIG_FILE, sanitized)
    return sanitized

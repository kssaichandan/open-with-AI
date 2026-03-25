from datetime import datetime, timezone

from settings import load_settings, save_settings


def add_to_history(files, ai_used):
    clean_files = [path for path in files if isinstance(path, str) and path.strip()]
    if not clean_files:
        return

    settings = load_settings()
    entry = {
        "files": clean_files,
        "ai": ai_used if isinstance(ai_used, str) and ai_used.strip() else "Claude",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    history = settings.get("history", [])
    history.insert(0, entry)
    settings["history"] = history[:10]
    save_settings(settings)


def get_history():
    settings = load_settings()
    return settings.get("history", [])

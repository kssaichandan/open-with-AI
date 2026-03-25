import os
import subprocess
import webbrowser
from urllib.parse import urlparse

from settings import load_settings

BROWSERS = {
    "Chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "Firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "Edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "Brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
}

AI_URLS = {
    "Claude": "https://claude.ai/",
    "ChatGPT": "https://chatgpt.com/",
    "DeepSeek": "https://chat.deepseek.com/",
    "Gemini": "https://gemini.google.com/app",
}

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def normalize_choice_name(value: str, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.strip().split())
    return cleaned[:80] if cleaned else fallback


def is_safe_ai_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in _LOCAL_HOSTS


def is_valid_browser_path(path: str) -> bool:
    return isinstance(path, str) and path.lower().endswith(".exe") and os.path.isfile(path)


def _candidate_paths(path: str):
    if not isinstance(path, str) or not path.strip():
        return []

    path = os.path.expandvars(path.strip())
    candidates = [path]
    if "Program Files (x86)" not in path and "Program Files" in path:
        candidates.append(path.replace("Program Files", "Program Files (x86)"))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _resolve_existing_path(path: str) -> str:
    for candidate in _candidate_paths(path):
        if os.path.isfile(candidate):
            return candidate
    return ""


def get_custom_ai_urls(settings=None):
    current = settings or load_settings()
    custom = current.get("custom_ai_urls", {})
    return {name: url for name, url in custom.items() if is_safe_ai_url(url)}


def get_all_browsers(settings=None):
    current = settings or load_settings()
    custom_browsers = current.get("custom_browsers", {})
    valid_custom = {name: path for name, path in custom_browsers.items() if isinstance(name, str) and isinstance(path, str)}
    return {**BROWSERS, **valid_custom}


def get_installed_browsers(settings=None):
    installed = ["System Default"]
    for name, path in get_all_browsers(settings).items():
        if _resolve_existing_path(path) and name not in installed:
            installed.append(name)
    return installed


def get_available_ais(settings=None):
    current = settings or load_settings()
    ai_names = list(AI_URLS.keys())
    for name in get_custom_ai_urls(current).keys():
        if name not in ai_names:
            ai_names.append(name)
    return ai_names


def resolve_ai_url(ai_name: str, custom_urls=None) -> str:
    chosen_name = normalize_choice_name(ai_name, "Claude")
    safe_custom_urls = {name: url for name, url in (custom_urls or {}).items() if is_safe_ai_url(url)}
    url = safe_custom_urls.get(chosen_name, AI_URLS.get(chosen_name, AI_URLS["Claude"]))
    return url if is_safe_ai_url(url) else AI_URLS["Claude"]


def launch_ai(browser_name, ai_name, custom_urls, file_paths=None):
    del file_paths  # Reserved for future native upload support.

    settings = load_settings()
    all_browsers = get_all_browsers(settings)
    url = resolve_ai_url(ai_name, custom_urls)
    chosen_browser = normalize_choice_name(browser_name, "System Default")

    if chosen_browser != "System Default":
        path = _resolve_existing_path(all_browsers.get(chosen_browser, ""))
        if path:
            try:
                subprocess.Popen([path, url], close_fds=True)
                return True
            except OSError:
                pass

    try:
        os.startfile(url)
        return True
    except OSError:
        return bool(webbrowser.open_new_tab(url))

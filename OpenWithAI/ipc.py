import json
import os
import time
import uuid
from contextlib import suppress
from typing import Iterable, List

from settings import QUEUE_DIR, ensure_app_dirs

LOCK_STALE_SECONDS = 120
PAYLOAD_STALE_SECONDS = 300


def _lock_path() -> str:
    return os.path.join(QUEUE_DIR, "aggregator.lock")


def _payload_path() -> str:
    filename = f"payload-{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex}.json"
    return os.path.join(QUEUE_DIR, filename)


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock_owner() -> int:
    try:
        with open(_lock_path(), "r", encoding="utf-8") as file_obj:
            return int((file_obj.read() or "0").strip())
    except (OSError, ValueError):
        return 0


def _cleanup_stale_files() -> None:
    ensure_app_dirs()
    now = time.time()
    lock_path = _lock_path()
    if os.path.exists(lock_path):
        owner_pid = _read_lock_owner()
        lock_age = now - os.path.getmtime(lock_path)
        if lock_age > LOCK_STALE_SECONDS or not _pid_exists(owner_pid):
            with suppress(FileNotFoundError, PermissionError):
                os.remove(lock_path)

    queue_names = []
    with suppress(FileNotFoundError):
        queue_names = list(os.listdir(QUEUE_DIR))

    for name in queue_names:
        if not name.startswith("payload-") or not name.endswith(".json"):
            continue
        payload_path = os.path.join(QUEUE_DIR, name)
        try:
            is_stale = now - os.path.getmtime(payload_path) > PAYLOAD_STALE_SECONDS
        except FileNotFoundError:
            continue
        if is_stale:
            with suppress(FileNotFoundError, PermissionError):
                os.remove(payload_path)


def enqueue_file_selection(files: Iterable[str]) -> str:
    ensure_app_dirs()
    _cleanup_stale_files()

    payload = {
        "created_at": time.time(),
        "files": [str(path) for path in files if isinstance(path, str) and path.strip()],
    }

    final_path = _payload_path()
    temp_path = f"{final_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj)
        file_obj.flush()
        os.fsync(file_obj.fileno())
    os.replace(temp_path, final_path)
    return final_path


def try_acquire_primary_lock() -> bool:
    ensure_app_dirs()
    _cleanup_stale_files()
    try:
        with open(_lock_path(), "x", encoding="utf-8") as file_obj:
            file_obj.write(str(os.getpid()))
        return True
    except FileExistsError:
        owner_pid = _read_lock_owner()
        if not _pid_exists(owner_pid):
            with suppress(FileNotFoundError, PermissionError):
                os.remove(_lock_path())
            try:
                with open(_lock_path(), "x", encoding="utf-8") as file_obj:
                    file_obj.write(str(os.getpid()))
                return True
            except FileExistsError:
                return False
        return False


def release_primary_lock() -> None:
    lock_path = _lock_path()
    if not os.path.exists(lock_path):
        return

    owner_pid = _read_lock_owner()
    if owner_pid not in (0, os.getpid()):
        return

    with suppress(FileNotFoundError, PermissionError):
        os.remove(lock_path)


def get_pending_payload_count() -> int:
    ensure_app_dirs()
    _cleanup_stale_files()
    try:
        return sum(1 for name in os.listdir(QUEUE_DIR) if name.startswith("payload-") and name.endswith(".json"))
    except FileNotFoundError:
        return 0


def collect_pending_files() -> List[str]:
    ensure_app_dirs()
    _cleanup_stale_files()

    collected: List[str] = []
    seen = set()
    try:
        queue_names = sorted(os.listdir(QUEUE_DIR))
    except FileNotFoundError:
        return collected

    for name in queue_names:
        if not name.startswith("payload-") or not name.endswith(".json"):
            continue

        payload_path = os.path.join(QUEUE_DIR, name)
        try:
            with open(payload_path, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
        except (OSError, json.JSONDecodeError):
            payload = {}
        finally:
            with suppress(FileNotFoundError, PermissionError):
                os.remove(payload_path)

        for path in payload.get("files", []):
            if isinstance(path, str) and path.strip() and path not in seen:
                seen.add(path)
                collected.append(path)

    return collected

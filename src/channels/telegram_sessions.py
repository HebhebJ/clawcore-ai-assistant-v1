import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import WORKSPACES_DIR


class TelegramSessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _path(self, workspace_id: str) -> Path:
        return WORKSPACES_DIR / workspace_id / "channels" / "telegram_sessions.json"

    def _load(self, workspace_id: str) -> dict[str, str]:
        path = self._path(workspace_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                out[key] = value
        return out

    def _save(self, workspace_id: str, data: dict[str, str]) -> None:
        path = self._path(workspace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def _new_session_id(self, chat_id: int) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"tg-{chat_id}-{stamp}"

    def get_or_create_current(self, workspace_id: str, chat_id: int) -> str:
        key = str(chat_id)
        with self._lock:
            data = self._load(workspace_id)
            current = data.get(key, "").strip()
            if current:
                return current

            if key not in data:
                # Keep backward-compatible default for existing users.
                current = f"tg-{chat_id}"
            else:
                # Key exists but is empty (closed session): start fresh.
                current = self._new_session_id(chat_id)
            data[key] = current
            self._save(workspace_id, data)
            return current

    def start_new(self, workspace_id: str, chat_id: int) -> str:
        key = str(chat_id)
        with self._lock:
            data = self._load(workspace_id)
            session_id = self._new_session_id(chat_id)
            data[key] = session_id
            self._save(workspace_id, data)
            return session_id

    def close_current(self, workspace_id: str, chat_id: int) -> str:
        key = str(chat_id)
        with self._lock:
            data = self._load(workspace_id)
            current = data.get(key, "").strip()
            data[key] = ""
            self._save(workspace_id, data)
            return current


import logging
from collections import deque
import threading

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from src.api.chat import get_runtime
from src.channels.telegram_sessions import TelegramSessionStore
from src.core.config import TelegramSettings, load_telegram_settings

logger = logging.getLogger(__name__)

router = APIRouter()

_PROCESSED_UPDATE_IDS: set[int] = set()
_PROCESSED_ORDER: deque[int] = deque()
_PROCESSED_LOCK = threading.Lock()
_PROCESSED_MAX = 5000
_SESSION_STORE = TelegramSessionStore()


def _extract_command(text: str) -> str:
    if not text:
        return ""
    first = text.split(maxsplit=1)[0].strip()
    if not first.startswith("/"):
        return ""
    return first.split("@", 1)[0].lower()


def _mark_update_processed(update_id: int) -> bool:
    with _PROCESSED_LOCK:
        if update_id in _PROCESSED_UPDATE_IDS:
            return False
        _PROCESSED_UPDATE_IDS.add(update_id)
        _PROCESSED_ORDER.append(update_id)
        while len(_PROCESSED_ORDER) > _PROCESSED_MAX:
            old = _PROCESSED_ORDER.popleft()
            _PROCESSED_UPDATE_IDS.discard(old)
        return True


def _extract_message(update: dict) -> tuple[int | None, str]:
    message = update.get("message") or update.get("edited_message") or {}
    if not isinstance(message, dict):
        return None, ""

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return None, ""

    text = message.get("text", "")
    if not isinstance(text, str):
        return chat_id, ""
    return chat_id, text.strip()


def _split_message(text: str, max_len: int = 3500) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _send_telegram_messages(settings: TelegramSettings, chat_id: int, text: str) -> None:
    chunks = _split_message(text)
    if not chunks:
        return
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    with httpx.Client(timeout=settings.timeout_seconds) as client:
        for chunk in chunks:
            response = client.post(url, json={"chat_id": chat_id, "text": chunk})
            response.raise_for_status()


def _process_update(update: dict, settings: TelegramSettings) -> None:
    chat_id, text = _extract_message(update)
    if chat_id is None or not text:
        return

    runtime = get_runtime()
    try:
        command = _extract_command(text)
        if command == "/new":
            current_session = _SESSION_STORE.get_or_create_current(settings.workspace_id, chat_id)
            flush = runtime.flush_memory(settings.workspace_id, current_session)
            new_session = _SESSION_STORE.start_new(settings.workspace_id, chat_id)
            reply = (
                f"Started new session: {new_session}\n"
                f"Flushed memory: saved={int(flush.get('saved', 0))} mode={flush.get('mode', 'unknown')}"
            )
            _send_telegram_messages(settings=settings, chat_id=chat_id, text=reply)
            return

        if command == "/exit":
            current_session = _SESSION_STORE.get_or_create_current(settings.workspace_id, chat_id)
            flush = runtime.flush_memory(settings.workspace_id, current_session)
            _SESSION_STORE.close_current(settings.workspace_id, chat_id)
            reply = (
                "Session closed.\n"
                f"Flushed memory: saved={int(flush.get('saved', 0))} mode={flush.get('mode', 'unknown')}\n"
                "Send any message (or /new) to start a fresh session."
            )
            _send_telegram_messages(settings=settings, chat_id=chat_id, text=reply)
            return

        if command == "/session":
            current_session = _SESSION_STORE.get_or_create_current(settings.workspace_id, chat_id)
            _send_telegram_messages(settings=settings, chat_id=chat_id, text=f"Current session: {current_session}")
            return

        if command == "/help":
            _send_telegram_messages(
                settings=settings,
                chat_id=chat_id,
                text="Commands: /new, /exit, /session, /help",
            )
            return

        session_id = _SESSION_STORE.get_or_create_current(settings.workspace_id, chat_id)
        result = runtime.handle_message(
            workspace_id=settings.workspace_id,
            session_id=session_id,
            message=text,
        )
        answer = str(result.get("answer", "")).strip()
        if not answer:
            return
        _send_telegram_messages(settings=settings, chat_id=chat_id, text=answer)
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram update processing failed chat_id=%s error=%s", chat_id, exc)


@router.post("/webhook/telegram")
def telegram_webhook(
    update: dict,
    background_tasks: BackgroundTasks,
    x_telegram_secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    settings = load_telegram_settings()
    if not settings.bot_token:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured")

    if settings.webhook_secret and x_telegram_secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    update_id_raw = update.get("update_id")
    if isinstance(update_id_raw, int):
        if not _mark_update_processed(update_id_raw):
            return {"ok": True, "duplicate": True}

    background_tasks.add_task(_process_update, update, settings)
    return {"ok": True, "queued": True}


def _clear_processed_updates_for_tests() -> None:
    with _PROCESSED_LOCK:
        _PROCESSED_UPDATE_IDS.clear()
        _PROCESSED_ORDER.clear()

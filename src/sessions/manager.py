import logging
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from src.core.config import WORKSPACES_DIR, load_summary_settings
from src.sessions.summary import update_summary
from src.sessions.transcript import append_jsonl, tail_jsonl

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self) -> None:
        self._summary_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="summary-updater")
        self._summary_locks: dict[tuple[str, str], threading.Lock] = {}
        self._summary_locks_guard = threading.Lock()

    def _session_dir(self, workspace_id: str, session_id: str) -> Path:
        return WORKSPACES_DIR / workspace_id / "sessions" / session_id

    def load_or_create(self, workspace_id: str, session_id: str) -> dict:
        sdir = self._session_dir(workspace_id, session_id)
        sdir.mkdir(parents=True, exist_ok=True)

        summary_path = sdir / "summary.md"
        state_path = sdir / "state.json"
        transcript_path = sdir / "transcript.jsonl"

        is_new = not transcript_path.exists()
        if not state_path.exists():
            state_path.write_text(
                json.dumps(
                    {
                        "goal": "",
                        "plan": [],
                        "completed": [],
                        "pending": [],
                        "turn_count": 0,
                        "token_totals": {"input": 0, "output": 0},
                    }
                ),
                encoding="utf-8",
            )
        if not summary_path.exists():
            summary_path.write_text("", encoding="utf-8")

        state = json.loads(state_path.read_text(encoding="utf-8"))
        if "turn_count" not in state:
            state["turn_count"] = 0
        if "token_totals" not in state:
            state["token_totals"] = {"input": 0, "output": 0}
        if "input" not in state["token_totals"]:
            state["token_totals"]["input"] = 0
        if "output" not in state["token_totals"]:
            state["token_totals"]["output"] = 0
        state_path.write_text(json.dumps(state), encoding="utf-8")

        return {
            "is_new": is_new,
            "summary": summary_path.read_text(encoding="utf-8"),
            "state": state,
            "recent": tail_jsonl(transcript_path, limit=12),
        }

    def append_transcript(self, workspace_id: str, session_id: str, event: dict) -> None:
        path = self._session_dir(workspace_id, session_id) / "transcript.jsonl"
        append_jsonl(path, event)

    def append_tool_call(self, workspace_id: str, session_id: str, tool_event: dict) -> None:
        path = self._session_dir(workspace_id, session_id) / "tool_calls.jsonl"
        append_jsonl(path, tool_event)

    def update_summary(
        self,
        workspace_id: str,
        session_id: str,
        assistant_reply: str,
        user_message: str = "",
    ) -> dict:
        path = self._session_dir(workspace_id, session_id) / "summary.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        next_summary, info = update_summary(existing, assistant_reply, user_message=user_message)
        path.write_text(next_summary, encoding="utf-8")
        return info

    def schedule_summary_update(
        self,
        workspace_id: str,
        session_id: str,
        assistant_reply: str,
        user_message: str = "",
    ) -> dict:
        settings = load_summary_settings()
        key = (workspace_id, session_id)

        with self._summary_locks_guard:
            lock = self._summary_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._summary_locks[key] = lock

        def _worker() -> None:
            with lock:
                self.update_summary(
                    workspace_id=workspace_id,
                    session_id=session_id,
                    assistant_reply=assistant_reply,
                    user_message=user_message,
                )

        future = self._summary_executor.submit(_worker)

        def _on_done(done) -> None:
            exc = done.exception()
            if exc is not None:
                logger.warning(
                    "summary background update failed workspace=%s session=%s error=%s",
                    workspace_id,
                    session_id,
                    exc,
                )

        future.add_done_callback(_on_done)
        return {
            "queued": True,
            "background": True,
            "provider_configured": settings.summary_updater_provider,
            "token_cap": settings.summary_token_cap,
        }

    def read_summary(self, workspace_id: str, session_id: str) -> str:
        path = self._session_dir(workspace_id, session_id) / "summary.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def load_recent_transcript(self, workspace_id: str, session_id: str, limit: int = 30) -> list[dict]:
        path = self._session_dir(workspace_id, session_id) / "transcript.jsonl"
        return tail_jsonl(path, limit=limit)

    def increment_turn_count(self, workspace_id: str, session_id: str) -> int:
        path = self._session_dir(workspace_id, session_id) / "state.json"
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        turns = int(state.get("turn_count", 0)) + 1
        state["turn_count"] = turns
        if "token_totals" not in state:
            state["token_totals"] = {"input": 0, "output": 0}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
        return turns

    def add_token_usage(self, workspace_id: str, session_id: str, prompt_tokens: int, completion_tokens: int) -> dict:
        path = self._session_dir(workspace_id, session_id) / "state.json"
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        totals = state.get("token_totals", {"input": 0, "output": 0})
        totals["input"] = int(totals.get("input", 0)) + int(prompt_tokens)
        totals["output"] = int(totals.get("output", 0)) + int(completion_tokens)
        state["token_totals"] = totals
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
        return {"input": totals["input"], "output": totals["output"]}

import json
from pathlib import Path

from src.core.config import WORKSPACES_DIR
from src.sessions.summary import update_summary_text
from src.sessions.transcript import append_jsonl, tail_jsonl


class SessionManager:
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

    def update_summary(self, workspace_id: str, session_id: str, assistant_reply: str) -> None:
        path = self._session_dir(workspace_id, session_id) / "summary.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(update_summary_text(existing, assistant_reply), encoding="utf-8")

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

import json
from pathlib import Path

from src.core.config import WORKSPACES_DIR


class MemoryStore:
    def _memory_dir(self, workspace_id: str) -> Path:
        return WORKSPACES_DIR / workspace_id / "memory"

    def _facts_path(self, workspace_id: str) -> Path:
        return self._memory_dir(workspace_id) / "facts.jsonl"

    def _notes_path(self, workspace_id: str) -> Path:
        return self._memory_dir(workspace_id) / "notes.jsonl"

    def _append_row(self, path: Path, row: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    def append_fact(self, workspace_id: str, fact: dict) -> None:
        self._append_row(self._facts_path(workspace_id), fact)

    def append_note(self, workspace_id: str, note: dict) -> None:
        self._append_row(self._notes_path(workspace_id), note)

    def _load_rows(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def load_facts(self, workspace_id: str) -> list[dict]:
        return self._load_rows(self._facts_path(workspace_id))

    def load_notes(self, workspace_id: str) -> list[dict]:
        return self._load_rows(self._notes_path(workspace_id))

    def load_all(self, workspace_id: str) -> list[dict]:
        return self.load_facts(workspace_id) + self.load_notes(workspace_id)

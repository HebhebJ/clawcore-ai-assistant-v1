import re
from datetime import datetime, timezone

from src.memory.store import MemoryStore
from src.memory.vector_index import VectorMemoryIndex

DURABLE_TYPES = {
    "user_preference",
    "project_fact",
    "workflow_rule",
    "open_task",
    "environment_fact",
}


class MemoryWriter:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.vector_index = VectorMemoryIndex()

    def maybe_store(
        self,
        workspace_id: str,
        user_message: str,
        assistant_reply: str,
        source: str = "memory_classifier_v2",
    ) -> bool:
        memory = self._classify(user_message.strip())
        if not memory:
            return False

        memory["created_at"] = datetime.now(timezone.utc).isoformat()
        memory["source"] = source

        if self._is_duplicate(workspace_id, memory):
            return False

        if memory["type"] == "open_task":
            self.store.append_note(workspace_id, memory)
        else:
            self.store.append_fact(workspace_id, memory)
        self.vector_index.append_memory(workspace_id, memory)
        return True

    def maybe_store_many(self, workspace_id: str, messages: list[str], source: str = "memory_distill_v1") -> int:
        stored = 0
        for msg in messages:
            if self.maybe_store(workspace_id, msg, assistant_reply="", source=source):
                stored += 1
        return stored

    def maybe_store_candidates(self, workspace_id: str, candidates: list[dict], source: str = "memory_distill_llm_v1") -> int:
        stored = 0
        for candidate in candidates:
            if self.maybe_store_candidate(workspace_id, candidate, source=source):
                stored += 1
        return stored

    def maybe_store_candidate(self, workspace_id: str, candidate: dict, source: str = "memory_distill_llm_v1") -> bool:
        ctype = str(candidate.get("type", "")).strip()
        content = str(candidate.get("content", "")).strip()
        if ctype not in DURABLE_TYPES:
            return False
        if not content or len(content) < 3 or len(content) > 300:
            return False

        tags = candidate.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        clean_tags = [str(tag).strip() for tag in tags if str(tag).strip()][:8]

        importance_raw = candidate.get("importance", 0.6)
        try:
            importance = float(importance_raw)
        except (ValueError, TypeError):
            importance = 0.6
        importance = max(0.0, min(1.0, importance))

        memory = {
            "type": ctype,
            "content": content,
            "tags": clean_tags,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }
        if self._is_duplicate(workspace_id, memory):
            return False

        if ctype == "open_task":
            self.store.append_note(workspace_id, memory)
        else:
            self.store.append_fact(workspace_id, memory)
        self.vector_index.append_memory(workspace_id, memory)
        return True

    def _classify(self, msg: str) -> dict | None:
        if len(msg) < 3:
            return None

        lower = msg.lower()
        if lower.endswith("?"):
            return None

        age_match = re.match(
            r"^i\s*(?:am|'m)\s+(\d{1,3})\s*(?:yo|y/o|years?\s*old|yrs?\s*old)?$",
            msg,
            flags=re.IGNORECASE,
        )
        if age_match:
            age = age_match.group(1).strip()
            return {
                "type": "environment_fact",
                "content": f"User age: {age}",
                "tags": ["user", "age"],
                "importance": 0.8,
            }

        from_match = re.match(
            r"^(?:i\s*(?:am|'m)\s+from|am\s+from)\s+(.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if from_match:
            place = from_match.group(1).strip(" .!")
            if place:
                return {
                    "type": "environment_fact",
                    "content": f"User is from: {place}",
                    "tags": ["user", "location"],
                    "importance": 0.8,
                }

        live_match = re.match(
            r"^i\s*(?:live|am\s+living|'m\s+living)\s+in\s+(.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if live_match:
            place = live_match.group(1).strip(" .!")
            if place:
                return {
                    "type": "environment_fact",
                    "content": f"User lives in: {place}",
                    "tags": ["user", "location"],
                    "importance": 0.8,
                }

        name_match = re.match(r"^my\s+name\s+is\s+(.+)$", msg, flags=re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip(" .!")
            if name:
                return {
                    "type": "environment_fact",
                    "content": f"User name: {name}",
                    "tags": ["user", "identity"],
                    "importance": 0.9,
                }

        preference_match = re.match(
            r"^i\s+(love|like|prefer|enjoy)\s+(.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if preference_match:
            item = preference_match.group(2).strip(" .!")
            if item:
                return {
                    "type": "user_preference",
                    "content": f"User preference: {item}",
                    "tags": ["user", "preference"],
                    "importance": 0.7,
                }

        if "i'm " in lower or "i am " in lower:
            if any(term in lower for term in ["student", "engineer", "developer", "founder"]):
                return {
                    "type": "environment_fact",
                    "content": msg,
                    "tags": ["user", "background"],
                    "importance": 0.7,
                }

        if any(phrase in lower for phrase in ["my project", "project is", "we are building", "we're building"]):
            return {
                "type": "project_fact",
                "content": msg,
                "tags": ["project"],
                "importance": 0.7,
            }

        if "building" in lower and any(term in lower for term in ["agent", "ai", "system"]):
            return {
                "type": "project_fact",
                "content": msg,
                "tags": ["project", "build"],
                "importance": 0.7,
            }

        if any(phrase in lower for phrase in ["always", "never", "must", "should always"]):
            return {
                "type": "workflow_rule",
                "content": msg,
                "tags": ["workflow"],
                "importance": 0.8,
            }

        if any(phrase in lower for phrase in ["todo", "to do", "next step", "i need to", "remember to"]):
            return {
                "type": "open_task",
                "content": msg,
                "tags": ["task"],
                "importance": 0.6,
            }

        if any(phrase in lower for phrase in ["i use", "my os", "my machine", "i am on", "timezone"]):
            return {
                "type": "environment_fact",
                "content": msg,
                "tags": ["environment"],
                "importance": 0.5,
            }

        return None

    def _is_duplicate(self, workspace_id: str, candidate: dict) -> bool:
        ctype = str(candidate.get("type", "")).strip()
        ccontent = str(candidate.get("content", "")).strip().lower()
        if not ctype or not ccontent or ctype not in DURABLE_TYPES:
            return True

        for row in self.store.load_all(workspace_id):
            if str(row.get("type", "")).strip() != ctype:
                continue
            existing = str(row.get("content", "")).strip().lower()
            if existing == ccontent:
                return True
        return False

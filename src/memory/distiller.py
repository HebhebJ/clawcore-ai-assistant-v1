import json
import logging
import re

import httpx

from src.core.config import LLMSettings
from src.sessions.manager import SessionManager

logger = logging.getLogger(__name__)

_MEMORY_TYPES = {"user_preference", "project_fact", "workflow_rule", "open_task", "environment_fact"}

MEMORY_DISTILL_SYSTEM = """Extract durable memory candidates from conversation context.
Return strict JSON only in this schema:
{"memories":[{"type":"user_preference|project_fact|workflow_rule|open_task|environment_fact","content":"...","tags":["..."],"importance":0.0}]}
Rules:
- Include only durable, reusable facts.
- Ignore chit-chat/noise.
- Max 12 memories.
- Keep content concise and factual.
"""


class MemoryDistiller:
    def __init__(self, session_manager: SessionManager, memory_writer, settings: LLMSettings, llm_extract_fn=None) -> None:
        self.session_manager = session_manager
        self.memory_writer = memory_writer
        self.settings = settings
        self.llm_extract_fn = llm_extract_fn

    def distill_session(self, workspace_id: str, session_id: str, limit: int = 40) -> dict:
        events = self.session_manager.load_recent_transcript(workspace_id, session_id, limit=limit)
        summary = self.session_manager.read_summary(workspace_id, session_id)
        existing = self.memory_writer.store.load_all(workspace_id)

        user_turns = [str(e.get("content", "")).strip() for e in events if str(e.get("role", "")).strip() == "user"]
        user_turns = [u for u in user_turns if u]
        if not user_turns and not summary.strip():
            return {"ran": False, "saved": 0, "prompt_tokens": 0, "completion_tokens": 0, "mode": "none"}

        try:
            memories, prompt_tokens, completion_tokens = self._extract_with_llm(user_turns, summary, existing)
            saved = self.memory_writer.maybe_store_candidates(
                workspace_id=workspace_id,
                candidates=memories,
                source="memory_distill_llm_v1",
            )
            return {
                "ran": True,
                "saved": saved,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "mode": "llm",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory distill llm failed, fallback to rules: %s", exc)
            candidates = list(user_turns)
            for line in summary.splitlines():
                cleaned = line.strip().lstrip("-").strip()
                if cleaned:
                    candidates.append(cleaned)
            saved = self.memory_writer.maybe_store_many(
                workspace_id=workspace_id,
                messages=candidates,
                source="memory_distill_fallback_v1",
            )
            return {
                "ran": True,
                "saved": saved,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "mode": "fallback",
            }

    def _extract_with_llm(self, user_turns: list[str], summary: str, existing: list[dict]) -> tuple[list[dict], int, int]:
        if self.llm_extract_fn is not None:
            return self.llm_extract_fn(user_turns, summary, existing)

        if self.settings.llm_provider != "kimi" or not self.settings.kimi_api_key or not self.settings.kimi_model:
            raise RuntimeError("LLM memory distill unavailable for current provider configuration")

        payload = {
            "model": self.settings.kimi_model,
            "messages": [
                {"role": "system", "content": MEMORY_DISTILL_SYSTEM},
                {
                    "role": "user",
                    "content": self._build_distill_input(user_turns, summary, existing),
                },
            ],
            "temperature": 0.1,
            "max_tokens": min(1200, self.settings.kimi_max_tokens),
        }
        headers = {
            "Authorization": f"Bearer {self.settings.kimi_api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.settings.kimi_base_url.rstrip('/')}/chat/completions"

        with httpx.Client(timeout=self.settings.kimi_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = str(data["choices"][0]["message"]["content"])
        parsed = self._parse_memories_json(content)
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        return parsed, prompt_tokens, completion_tokens

    def _build_distill_input(self, user_turns: list[str], summary: str, existing: list[dict]) -> str:
        existing_compact = []
        for row in existing[-80:]:
            ctype = str(row.get("type", "")).strip()
            content = str(row.get("content", "")).strip()
            if ctype and content:
                existing_compact.append(f"[{ctype}] {content}")

        parts = [
            "Session summary:",
            summary.strip() or "(empty)",
            "",
            "Recent user turns:",
            "\n".join(f"- {t}" for t in user_turns[-40:]) or "(none)",
            "",
            "Existing memory:",
            "\n".join(f"- {e}" for e in existing_compact[-40:]) or "(none)",
        ]
        return "\n".join(parts)

    def _parse_memories_json(self, text: str) -> list[dict]:
        cleaned = text.strip()
        cleaned = self._strip_fences(cleaned)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            payload = self._extract_first_json_object(cleaned)

        memories = payload.get("memories", []) if isinstance(payload, dict) else []
        if not isinstance(memories, list):
            return []

        out: list[dict] = []
        for item in memories[:12]:
            if not isinstance(item, dict):
                continue
            ctype = str(item.get("type", "")).strip()
            content = str(item.get("content", "")).strip()
            if ctype not in _MEMORY_TYPES or not content:
                continue
            tags = item.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            importance = item.get("importance", 0.6)
            out.append(
                {
                    "type": ctype,
                    "content": content,
                    "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:8],
                    "importance": importance,
                }
            )
        return out

    def _strip_fences(self, value: str) -> str:
        if not value.startswith("```"):
            return value
        lines = value.splitlines()
        if len(lines) < 2:
            return value
        if lines[-1].strip() == "```":
            body = "\n".join(lines[1:-1]).strip()
            return re.sub(r"^json\s*", "", body, flags=re.IGNORECASE)
        return value

    def _extract_first_json_object(self, text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}

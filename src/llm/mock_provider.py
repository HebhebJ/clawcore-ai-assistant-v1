import json

from src.llm.base import LLMProvider
from src.llm.token_counter import estimate_tokens


class MockProvider(LLMProvider):
    async def generate(self, messages: list[dict], tools: dict) -> dict:
        all_content = " ".join(m.get("content", "") for m in messages).lower()
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        ).lower()

        if "tool result" in last_user:
            snippet = last_user[:500]
            decision = {
                "action": "final_answer",
                "final_answer": f"Tool result processed. {snippet}",
            }
            return self._with_meta(messages, decision)

        if "list" in all_content and "file" in all_content:
            decision = {
                "action": "tool_call",
                "tool_name": "list_files",
                "tool_input": {"path": "."},
            }
            return self._with_meta(messages, decision)

        if "read" in all_content and "plan.md" in all_content:
            decision = {
                "action": "tool_call",
                "tool_name": "read_file",
                "tool_input": {"path": "plan.md", "max_chars": 2000},
            }
            return self._with_meta(messages, decision)

        if "time" in all_content or "date" in all_content:
            decision = {
                "action": "tool_call",
                "tool_name": "get_datetime",
                "tool_input": {},
            }
            return self._with_meta(messages, decision)

        decision = {
            "action": "final_answer",
            "final_answer": "I can help with planning, files, and basic project operations in this workspace.",
        }
        return self._with_meta(messages, decision)

    async def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:  # noqa: ARG002
        return '{"memories":[]}', 0, 0

    def _with_meta(self, messages: list[dict], decision: dict) -> dict:
        all_content = " ".join(m.get("content", "") for m in messages)
        raw = json.dumps({k: v for k, v in decision.items()}, ensure_ascii=True)
        decision["_meta"] = {
            "provider": "mock",
            "model": "mock-static",
            "prompt_tokens": estimate_tokens(all_content),
            "completion_tokens": estimate_tokens(raw),
            "stop_reason": "stop",
            "raw_content": raw,
        }
        return decision

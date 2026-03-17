import json

from src.llm.base import LLMProvider
from src.llm.token_counter import estimate_tokens


class MockProvider(LLMProvider):
    def generate(self, context: str, tools: dict) -> dict:
        lower = context.lower()

        if "tool observation" in lower:
            snippet = context.split("Tool observation")[-1].strip()
            decision = {
                "action": "final_answer",
                "final_answer": f"Tool result processed. {snippet[:500]}",
            }
            return self._with_meta(context, decision)

        if "list" in lower and "file" in lower:
            decision = {
                "action": "tool_call",
                "tool_name": "list_files",
                "tool_input": {"path": "."},
            }
            return self._with_meta(context, decision)

        if "read" in lower and "plan.md" in lower:
            decision = {
                "action": "tool_call",
                "tool_name": "read_file",
                "tool_input": {"path": "plan.md", "max_chars": 2000},
            }
            return self._with_meta(context, decision)

        if "time" in lower or "date" in lower:
            decision = {
                "action": "tool_call",
                "tool_name": "get_datetime",
                "tool_input": {},
            }
            return self._with_meta(context, decision)

        decision = {
            "action": "final_answer",
            "final_answer": "I can help with planning, files, and basic project operations in this workspace.",
        }
        return self._with_meta(context, decision)

    def _with_meta(self, context: str, decision: dict) -> dict:
        decision["_meta"] = {
            "provider": "mock",
            "model": "mock-static",
            "prompt_tokens": estimate_tokens(context),
            "completion_tokens": estimate_tokens(json.dumps(decision, ensure_ascii=True)),
            "stop_reason": "stop",
        }
        return decision

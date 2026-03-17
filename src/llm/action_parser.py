import json
import re


def _strip_markdown_fences(text: str) -> str:
    body = text.strip()
    if not body.startswith("```"):
        return body

    lines = body.splitlines()
    if len(lines) < 2:
        return body

    first = lines[0].strip()
    last = lines[-1].strip()
    if not first.startswith("```") or last != "```":
        return body

    return "\n".join(lines[1:-1]).strip()


def parse_action_response(text: str) -> dict:
    cleaned = _strip_markdown_fences(text)
    cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"action": "unsupported"}

    action = payload.get("action")
    if action == "final_answer":
        final_answer = payload.get("final_answer")
        if isinstance(final_answer, str):
            return {"action": "final_answer", "final_answer": final_answer}
        return {"action": "unsupported"}

    if action == "tool_call":
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input", {})
        if isinstance(tool_name, str) and isinstance(tool_input, dict):
            return {
                "action": "tool_call",
                "tool_name": tool_name,
                "tool_input": tool_input,
            }
        return {"action": "unsupported"}

    if action == "reasoning":
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, str):
            return {"action": "reasoning", "reasoning": reasoning}
        return {"action": "unsupported"}

    return {"action": "unsupported"}

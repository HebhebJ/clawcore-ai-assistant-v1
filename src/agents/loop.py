from src.core.config import MAX_REASONING_ACTIONS, MAX_STEPS, MAX_TOOL_CALLS

_UNSUPPORTED_ACTION_RETRY_HINT = (
    "Repair instruction: your previous output did not match the required action schema. "
    "Return only one JSON object with exactly one action: "
    "tool_call, reasoning, or final_answer."
)


class AgentLoop:
    def run(self, provider, context: str, tools: dict, execute_tool):
        steps = 0
        tool_calls = 0
        reasoning_actions = 0
        unsupported_action_retried = False
        prompt_tokens_total = 0
        completion_tokens_total = 0
        model_calls = 0

        while steps < MAX_STEPS:
            steps += 1
            decision = provider.generate(context=context, tools=tools)
            model_calls += 1
            meta = decision.get("_meta", {})
            prompt_tokens_total += int(meta.get("prompt_tokens", 0) or 0)
            completion_tokens_total += int(meta.get("completion_tokens", 0) or 0)
            action = decision.get("action")

            if action == "final_answer":
                return {
                    "answer": decision.get("final_answer", ""),
                    "steps": steps,
                    "tool_calls": tool_calls,
                    "prompt_tokens": prompt_tokens_total,
                    "completion_tokens": completion_tokens_total,
                    "model_calls": model_calls,
                }

            if action == "reasoning":
                if reasoning_actions >= MAX_REASONING_ACTIONS:
                    return {
                        "answer": "Stopped safely: max reasoning actions reached.",
                        "steps": steps,
                        "tool_calls": tool_calls,
                        "prompt_tokens": prompt_tokens_total,
                        "completion_tokens": completion_tokens_total,
                        "model_calls": model_calls,
                    }
                reasoning_actions += 1
                note = str(decision.get("reasoning", "")).strip()
                if note:
                    context += f"\n\nReasoning note:\n{note[:300]}"
                continue

            if action != "tool_call":
                if not unsupported_action_retried:
                    unsupported_action_retried = True
                    context += f"\n\n{_UNSUPPORTED_ACTION_RETRY_HINT}"
                    continue
                return {
                    "answer": "Stopped safely: model returned unsupported action.",
                    "steps": steps,
                    "tool_calls": tool_calls,
                    "prompt_tokens": prompt_tokens_total,
                    "completion_tokens": completion_tokens_total,
                    "model_calls": model_calls,
                }

            if tool_calls >= MAX_TOOL_CALLS:
                return {
                    "answer": "Stopped safely: max tool calls reached.",
                    "steps": steps,
                    "tool_calls": tool_calls,
                    "prompt_tokens": prompt_tokens_total,
                    "completion_tokens": completion_tokens_total,
                    "model_calls": model_calls,
                }

            tool_name = decision.get("tool_name", "")
            tool_input = decision.get("tool_input", {})
            try:
                observation = execute_tool(tool_name, tool_input)
            except ValueError as exc:
                observation = f"Tool error: {exc}"
            except RuntimeError as exc:
                observation = f"Tool runtime error: {exc}"
            tool_calls += 1
            context += f"\n\nTool observation ({tool_name}):\n{observation}"

        return {
            "answer": "Stopped safely: max reasoning steps reached.",
            "steps": steps,
            "tool_calls": tool_calls,
            "prompt_tokens": prompt_tokens_total,
            "completion_tokens": completion_tokens_total,
            "model_calls": model_calls,
        }

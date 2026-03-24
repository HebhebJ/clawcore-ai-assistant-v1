from src.context.prompt_layers import ACTION_INSTRUCTIONS, BASE_SYSTEM_PROMPT
from src.context.tool_prompt import render_tools


class ContextBuilder:
    def build(
        self,
        workspace: dict,
        session: dict,
        memories: list[str],
        tools: dict,
        user_message: str,
        skill_instructions: str = "",
    ) -> list[dict]:
        memory_text = "\n".join(memories)

        system_parts = [
            BASE_SYSTEM_PROMPT,
            ACTION_INSTRUCTIONS,
            "[AGENT.md]\n" + workspace.get("AGENT.md", ""),
            "[SOUL.md]\n" + workspace.get("SOUL.md", ""),
            "[TOOLS.md]\n" + workspace.get("TOOLS.md", ""),
            "[USER.md]\n" + workspace.get("USER.md", ""),
            "[BOOTSTRAP.md]\n" + (workspace.get("BOOTSTRAP.md", "") if session.get("is_new") else ""),
            "[Active Skills]\n" + skill_instructions,
            "[Retrieved Memories]\n" + memory_text,
            "[Session Summary]\n" + session.get("summary", ""),
            "[Tool Descriptions]\n" + render_tools(tools),
        ]
        messages: list[dict] = [{"role": "system", "content": "\n\n".join(system_parts)}]

        for event in session.get("recent", []):
            role = str(event.get("role", "")).strip()
            content = str(event.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})
        return messages

from src.context.prompt_layers import BASE_SYSTEM_PROMPT
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
    ) -> str:
        recent = "\n".join([f"{e['role']}: {e['content']}" for e in session.get("recent", [])])
        memory_text = "\n".join(memories)

        parts = [
            BASE_SYSTEM_PROMPT,
            "[AGENT.md]\n" + workspace.get("AGENT.md", ""),
            "[SOUL.md]\n" + workspace.get("SOUL.md", ""),
            "[TOOLS.md]\n" + workspace.get("TOOLS.md", ""),
            "[USER.md]\n" + workspace.get("USER.md", ""),
            "[BOOTSTRAP.md]\n" + (workspace.get("BOOTSTRAP.md", "") if session.get("is_new") else ""),
            "[Active Skills]\n" + skill_instructions,
            "[Retrieved Memories]\n" + memory_text,
            "[Session Summary]\n" + session.get("summary", ""),
            "[Recent Conversation]\n" + recent,
            "[Tool Descriptions]\n" + render_tools(tools),
            "[Current User Message]\n" + user_message,
        ]
        return "\n\n".join(parts)

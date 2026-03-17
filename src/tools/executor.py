from src.core.config import WORKSPACES_DIR


class ToolExecutor:
    def __init__(self, tools: dict):
        self.tools = tools

    def execute(self, workspace_id: str, tool_name: str, tool_input: dict) -> str:
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        workspace_path = str((WORKSPACES_DIR / workspace_id).resolve())
        tool = self.tools[tool_name]
        return str(tool.handler(workspace_path, tool_input))

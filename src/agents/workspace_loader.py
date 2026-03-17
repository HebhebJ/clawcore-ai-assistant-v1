from pathlib import Path

from src.core.config import WORKSPACES_DIR

WORKSPACE_FILES = ["AGENT.md", "SOUL.md", "TOOLS.md", "USER.md", "BOOTSTRAP.md"]


class WorkspaceLoader:
    def load(self, workspace_id: str) -> dict[str, str]:
        workspace_path = WORKSPACES_DIR / workspace_id
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace '{workspace_id}' does not exist")

        data: dict[str, str] = {"workspace_path": str(workspace_path)}
        for name in WORKSPACE_FILES:
            file_path = workspace_path / name
            data[name] = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        return data

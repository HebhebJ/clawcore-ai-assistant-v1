import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agents.runtime import AgentRuntime
from src.core.config import LLMSettings


class RuntimeToolPolicyIntegrationTests(unittest.TestCase):
    def test_runtime_respects_workspace_tool_restrictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "default-agent"
            (workspace / "skills").mkdir(parents=True, exist_ok=True)
            (workspace / "memory").mkdir(parents=True, exist_ok=True)
            (workspace / "sessions").mkdir(parents=True, exist_ok=True)

            for name, content in {
                "AGENT.md": "# Agent",
                "SOUL.md": "# Soul",
                "TOOLS.md": "allow: get_datetime\ndeny: list_files, read_file",
                "USER.md": "# User",
                "BOOTSTRAP.md": "# Bootstrap",
            }.items():
                (workspace / name).write_text(content, encoding="utf-8")

            (workspace / "skills" / "enabled.json").write_text(
                json.dumps(
                    {
                        "enabled_tools": ["list_files", "read_file", "get_datetime"],
                        "disabled_tools": ["list_files", "read_file"],
                        "enabled_skills": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch("src.agents.workspace_loader.WORKSPACES_DIR", base), patch(
                "src.tools.executor.WORKSPACES_DIR", base
            ):
                runtime = AgentRuntime(settings=LLMSettings(llm_provider="mock"))
                result = runtime.handle_message(
                    workspace_id="default-agent",
                    session_id="tool-policy-session",
                    message="tell me date time",
                )
                self.assertEqual(result["tool_calls"], 1)
                self.assertIn("tool result processed", result["answer"].lower())

    def test_runtime_safe_message_when_effective_tools_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "default-agent"
            (workspace / "skills").mkdir(parents=True, exist_ok=True)
            (workspace / "memory").mkdir(parents=True, exist_ok=True)
            (workspace / "sessions").mkdir(parents=True, exist_ok=True)

            for name, content in {
                "AGENT.md": "# Agent",
                "SOUL.md": "# Soul",
                "TOOLS.md": "deny: list_files, read_file, get_datetime",
                "USER.md": "# User",
                "BOOTSTRAP.md": "# Bootstrap",
            }.items():
                (workspace / name).write_text(content, encoding="utf-8")

            (workspace / "skills" / "enabled.json").write_text(
                json.dumps(
                    {
                        "enabled_tools": ["list_files", "read_file", "get_datetime"],
                        "disabled_tools": [],
                        "enabled_skills": [],
                    }
                ),
                encoding="utf-8",
            )

            with patch("src.agents.workspace_loader.WORKSPACES_DIR", base), patch(
                "src.tools.executor.WORKSPACES_DIR", base
            ):
                runtime = AgentRuntime(settings=LLMSettings(llm_provider="mock"))
                result = runtime.handle_message(
                    workspace_id="default-agent",
                    session_id="tool-policy-empty",
                    message="what time is it",
                )
                self.assertEqual(result["tool_calls"], 0)
                self.assertIn("no tools are enabled", result["answer"].lower())


if __name__ == "__main__":
    unittest.main()

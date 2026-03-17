import json
import tempfile
import unittest
from pathlib import Path

from src.tools.policy import load_workspace_tool_config


class WorkspaceToolConfigTests(unittest.TestCase):
    def test_missing_enabled_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_workspace_tool_config(tmp)
            self.assertIsNone(cfg)

    def test_load_valid_enabled_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir(parents=True, exist_ok=True)
            (skills / "enabled.json").write_text(
                json.dumps({"enabled_tools": ["list_files"], "disabled_tools": ["read_file"]}),
                encoding="utf-8",
            )
            cfg = load_workspace_tool_config(tmp)
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg.enabled_tools, ["list_files"])
            self.assertEqual(cfg.disabled_tools, ["read_file"])
            self.assertEqual(cfg.enabled_skills, [])

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir(parents=True, exist_ok=True)
            (skills / "enabled.json").write_text("not-json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workspace_tool_config(tmp)


if __name__ == "__main__":
    unittest.main()

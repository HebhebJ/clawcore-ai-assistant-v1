import json
import tempfile
import unittest
from pathlib import Path

from src.skills.loader import collect_skill_tool_overrides, load_active_skills, render_skill_instructions


class SkillLoaderTests(unittest.TestCase):
    def test_load_active_skills_and_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "research"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "skill.json").write_text(
                json.dumps(
                    {
                        "name": "research",
                        "description": "desc",
                        "enabled_tools": ["read_file"],
                        "disabled_tools": ["list_files"],
                        "allow_tools": ["read_file"],
                        "deny_tools": ["get_datetime"],
                    }
                ),
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text("Use sources", encoding="utf-8")

            skills = load_active_skills(str(root), ["research"])
            self.assertEqual(len(skills), 1)
            self.assertEqual(skills[0].name, "research")
            text = render_skill_instructions(skills)
            self.assertIn("Use sources", text)

    def test_collect_skill_tool_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "skills" / "a"
            b = root / "skills" / "b"
            a.mkdir(parents=True, exist_ok=True)
            b.mkdir(parents=True, exist_ok=True)
            (a / "skill.json").write_text(
                json.dumps({"name": "a", "enabled_tools": ["read_file"], "allow_tools": ["read_file"]}),
                encoding="utf-8",
            )
            (b / "skill.json").write_text(
                json.dumps({"name": "b", "disabled_tools": ["list_files"], "deny_tools": ["get_datetime"]}),
                encoding="utf-8",
            )

            skills = load_active_skills(str(root), ["a", "b"])
            merged = collect_skill_tool_overrides(skills)
            self.assertEqual(merged["enabled_tools"], ["read_file"])
            self.assertEqual(merged["disabled_tools"], ["list_files"])
            self.assertEqual(merged["allow_tools"], ["read_file"])
            self.assertEqual(merged["deny_tools"], ["get_datetime"])


if __name__ == "__main__":
    unittest.main()

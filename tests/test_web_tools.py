import json
import unittest

from src.tools.builtins.web import read_url, search_web
from src.tools.registry import default_registry


class WebToolTests(unittest.TestCase):
    def test_registry_contains_web_tools(self):
        tools = default_registry()
        self.assertIn("search_web", tools)
        self.assertIn("read_url", tools)

    def test_read_url_rejects_invalid_url(self):
        with self.assertRaises(ValueError):
            read_url("", {"url": "not-a-url"})

    def test_read_url_rejects_blocked_host(self):
        with self.assertRaises(ValueError):
            read_url("", {"url": "http://127.0.0.1"})

    def test_search_web_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            search_web("", {"query": ""})

    def test_search_web_rejects_bad_max_results(self):
        with self.assertRaises(ValueError):
            search_web("", {"query": "openclaw", "max_results": 0})

    def test_web_skill_manifest_present(self):
        with open("workspaces/default-agent/skills/web-research/skill.json", "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["name"], "web-research")
        self.assertIn("search_web", payload["enabled_tools"])
        self.assertIn("read_url", payload["enabled_tools"])


if __name__ == "__main__":
    unittest.main()

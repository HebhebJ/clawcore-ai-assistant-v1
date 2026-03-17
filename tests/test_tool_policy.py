import unittest

from src.tools.policy import ToolPolicy, WorkspaceToolConfig, parse_tools_policy, resolve_effective_tools


class _Tool:
    def __init__(self, name: str):
        self.name = name
        self.description = name


class ToolPolicyTests(unittest.TestCase):
    def setUp(self):
        self.global_tools = {
            "list_files": _Tool("list_files"),
            "read_file": _Tool("read_file"),
            "get_datetime": _Tool("get_datetime"),
        }

    def test_parse_allow_and_deny(self):
        policy = parse_tools_policy("allow: list_files, read_file\ndeny: read_file")
        self.assertEqual(policy.allow_tools, ["list_files", "read_file"])
        self.assertEqual(policy.deny_tools, ["read_file"])

    def test_parse_ignores_non_directive_lines(self):
        policy = parse_tools_policy("- Use tools\nrandom text\nallow: get_datetime")
        self.assertEqual(policy.allow_tools, ["get_datetime"])
        self.assertEqual(policy.deny_tools, [])

    def test_resolve_missing_workspace_config_uses_all(self):
        policy = ToolPolicy()
        eff = resolve_effective_tools(self.global_tools, None, policy)
        self.assertEqual(set(eff.keys()), set(self.global_tools.keys()))

    def test_resolve_with_enabled_and_disabled(self):
        cfg = WorkspaceToolConfig(enabled_tools=["list_files", "read_file"], disabled_tools=["read_file"])
        policy = ToolPolicy()
        eff = resolve_effective_tools(self.global_tools, cfg, policy)
        self.assertEqual(set(eff.keys()), {"list_files"})

    def test_resolve_allow_then_deny(self):
        cfg = WorkspaceToolConfig(enabled_tools=["list_files", "read_file", "get_datetime"], disabled_tools=[])
        policy = ToolPolicy(allow_tools=["list_files", "read_file"], deny_tools=["read_file"])
        eff = resolve_effective_tools(self.global_tools, cfg, policy)
        self.assertEqual(set(eff.keys()), {"list_files"})

    def test_unknown_tool_names_are_skipped(self):
        cfg = WorkspaceToolConfig(enabled_tools=["list_files", "unknown_tool"], disabled_tools=[])
        policy = ToolPolicy(allow_tools=["list_files", "missing"], deny_tools=["nope"])
        eff = resolve_effective_tools(self.global_tools, cfg, policy)
        self.assertEqual(set(eff.keys()), {"list_files"})


if __name__ == "__main__":
    unittest.main()

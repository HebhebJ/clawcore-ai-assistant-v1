import unittest

from src.llm.action_parser import parse_action_response


class ActionParserTests(unittest.TestCase):
    def test_parse_final_answer(self):
        payload = '{"action":"final_answer","final_answer":"ok"}'
        self.assertEqual(parse_action_response(payload), {"action": "final_answer", "final_answer": "ok"})

    def test_parse_tool_call(self):
        payload = '{"action":"tool_call","tool_name":"list_files","tool_input":{"path":"."}}'
        self.assertEqual(
            parse_action_response(payload),
            {"action": "tool_call", "tool_name": "list_files", "tool_input": {"path": "."}},
        )

    def test_parse_markdown_wrapped_json(self):
        payload = "```json\n{\"action\":\"final_answer\",\"final_answer\":\"done\"}\n```"
        self.assertEqual(parse_action_response(payload), {"action": "final_answer", "final_answer": "done"})

    def test_parse_malformed_json(self):
        self.assertEqual(parse_action_response("not json"), {"action": "unsupported"})

    def test_parse_missing_fields(self):
        payload = '{"action":"tool_call","tool_name":123}'
        self.assertEqual(parse_action_response(payload), {"action": "unsupported"})

    def test_parse_reasoning(self):
        payload = '{"action":"reasoning","reasoning":"Need to inspect one source first."}'
        self.assertEqual(
            parse_action_response(payload),
            {"action": "reasoning", "reasoning": "Need to inspect one source first."},
        )


if __name__ == "__main__":
    unittest.main()

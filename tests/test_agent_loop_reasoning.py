import unittest

from src.agents.loop import AgentLoop


class _SeqProvider:
    def __init__(self, decisions):
        self._decisions = list(decisions)

    async def generate(self, messages: list[dict], tools: dict) -> dict:
        if not self._decisions:
            return {"action": "final_answer", "final_answer": "fallback", "_meta": {}}
        return self._decisions.pop(0)


class AgentLoopReasoningTests(unittest.IsolatedAsyncioTestCase):
    def _msgs(self) -> list[dict]:
        return [{"role": "user", "content": "ctx"}]

    async def test_reasoning_then_final_answer(self):
        loop = AgentLoop()
        provider = _SeqProvider(
            [
                {"action": "reasoning", "reasoning": "Need a quick check.", "_meta": {}},
                {"action": "final_answer", "final_answer": "done", "_meta": {}},
            ]
        )
        result = await loop.run(provider=provider, messages=self._msgs(), tools={}, execute_tool=lambda n, i: "")
        self.assertEqual(result["answer"], "done")
        self.assertEqual(result["tool_calls"], 0)

    async def test_reasoning_cap_stops_safely(self):
        loop = AgentLoop()
        provider = _SeqProvider(
            [
                {"action": "reasoning", "reasoning": "r1", "_meta": {}},
                {"action": "reasoning", "reasoning": "r2", "_meta": {}},
                {"action": "reasoning", "reasoning": "r3", "_meta": {}},
                {"action": "reasoning", "reasoning": "r4", "_meta": {}},
                {"action": "reasoning", "reasoning": "r5", "_meta": {}},
                {"action": "reasoning", "reasoning": "r6", "_meta": {}},
            ]
        )
        result = await loop.run(provider=provider, messages=self._msgs(), tools={}, execute_tool=lambda n, i: "")
        self.assertIn("max reasoning actions", result["answer"].lower())
        self.assertEqual(result["tool_calls"], 0)

    async def test_tool_error_does_not_crash_loop(self):
        loop = AgentLoop()
        provider = _SeqProvider(
            [
                {"action": "tool_call", "tool_name": "read_file", "tool_input": {"path": ""}, "_meta": {}},
                {"action": "final_answer", "final_answer": "recovered", "_meta": {}},
            ]
        )

        def _fail_tool(_name, _input):
            raise ValueError("File not found")

        result = await loop.run(provider=provider, messages=self._msgs(), tools={}, execute_tool=_fail_tool)
        self.assertEqual(result["answer"], "recovered")
        self.assertEqual(result["tool_calls"], 1)

    async def test_unsupported_action_gets_one_retry(self):
        loop = AgentLoop()
        provider = _SeqProvider(
            [
                {"action": "unsupported", "_meta": {}},
                {"action": "final_answer", "final_answer": "fixed_after_retry", "_meta": {}},
            ]
        )
        result = await loop.run(provider=provider, messages=self._msgs(), tools={}, execute_tool=lambda n, i: "")
        self.assertEqual(result["answer"], "fixed_after_retry")
        self.assertEqual(result["tool_calls"], 0)


if __name__ == "__main__":
    unittest.main()

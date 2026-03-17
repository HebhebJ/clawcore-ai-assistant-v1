import unittest

from src.agents.runtime import AgentRuntime
from src.core.config import LLMSettings


class TokenUsageTests(unittest.TestCase):
    def test_runtime_returns_and_accumulates_token_usage(self):
        runtime = AgentRuntime(settings=LLMSettings(llm_provider="mock"))
        session_id = "token-usage-test-session"

        r1 = runtime.handle_message(
            workspace_id="default-agent",
            session_id=session_id,
            message="What tools do you have",
        )
        self.assertGreater(r1.get("prompt_tokens", 0), 0)
        self.assertGreater(r1.get("completion_tokens", 0), 0)
        self.assertGreaterEqual(r1.get("session_prompt_tokens_total", 0), r1.get("prompt_tokens", 0))
        self.assertGreaterEqual(r1.get("session_completion_tokens_total", 0), r1.get("completion_tokens", 0))

        r2 = runtime.handle_message(
            workspace_id="default-agent",
            session_id=session_id,
            message="Tell me date time",
        )
        self.assertGreaterEqual(r2.get("session_prompt_tokens_total", 0), r1.get("session_prompt_tokens_total", 0))
        self.assertGreaterEqual(r2.get("session_completion_tokens_total", 0), r1.get("session_completion_tokens_total", 0))
        self.assertGreaterEqual(r2.get("context_tokens_estimate", 0), 1)

    def test_distill_tokens_are_added_to_session_totals(self):
        runtime = AgentRuntime(settings=LLMSettings(llm_provider="mock"))
        runtime.memory_distill_every_turns = 1
        runtime.memory_distiller.distill_session = lambda workspace_id, session_id: {
            "ran": True,
            "saved": 1,
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "mode": "llm",
        }

        result = runtime.handle_message(
            workspace_id="default-agent",
            session_id="token-distill-test-session",
            message="What tools do you have",
        )
        self.assertIsNotNone(result.get("memory_distill"))
        self.assertEqual(result["memory_distill"]["saved"], 1)
        self.assertGreaterEqual(result.get("session_prompt_tokens_total", 0), result.get("prompt_tokens", 0) + 50)
        self.assertGreaterEqual(result.get("session_completion_tokens_total", 0), result.get("completion_tokens", 0) + 20)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from src.agents.runtime import AgentRuntime
from src.core.config import LLMSettings


class SummaryBackgroundTests(unittest.TestCase):
    def test_runtime_queues_summary_update(self):
        runtime = AgentRuntime(settings=LLMSettings(llm_provider="mock"))
        runtime.session_manager.schedule_summary_update = lambda *args, **kwargs: {
            "queued": True,
            "background": True,
            "provider_configured": "ollama",
            "token_cap": 1000,
        }
        runtime.memory_distiller.distill_session = lambda workspace_id, session_id: {
            "ran": False,
            "saved": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "mode": "none",
        }
        with patch.object(runtime.session_manager, "increment_turn_count", return_value=1):
            result = runtime.handle_message(
                workspace_id="default-agent",
                session_id="summary-background-test",
                message="hello there",
            )
        self.assertTrue(result.get("summary_update", {}).get("queued"))
        self.assertTrue(result.get("summary_update", {}).get("background"))


if __name__ == "__main__":
    unittest.main()


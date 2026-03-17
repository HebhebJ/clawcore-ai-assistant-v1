import unittest
from unittest.mock import patch

import httpx

from src.core.config import SummarySettings
from src.llm.token_counter import estimate_tokens
from src.sessions import summary as summary_module
from src.sessions.summary import update_summary_text


class SummaryUpdaterTests(unittest.TestCase):
    def setUp(self):
        summary_module._OLLAMA_CONSECUTIVE_FAILURES = 0
        summary_module._OLLAMA_COOLDOWN_UNTIL = 0.0

    def _heuristic_settings(self, token_cap: int = 1000) -> SummarySettings:
        return SummarySettings(
            summary_updater_provider="heuristic",
            summary_token_cap=token_cap,
            summary_delta_max_lines=3,
            summary_compact_target_tokens=120,
            summary_timeout_seconds=1.0,
            summary_temperature=0.1,
            summary_ollama_max_failures=3,
            summary_ollama_cooldown_seconds=60.0,
            ollama_base_url="http://127.0.0.1:11434",
            ollama_summary_model="gpt-oss:20b",
        )

    def _ollama_settings(self, max_failures: int = 3, cooldown_seconds: float = 60.0) -> SummarySettings:
        return SummarySettings(
            summary_updater_provider="ollama",
            summary_token_cap=1000,
            summary_delta_max_lines=3,
            summary_compact_target_tokens=120,
            summary_timeout_seconds=1.0,
            summary_temperature=0.1,
            summary_ollama_max_failures=max_failures,
            summary_ollama_cooldown_seconds=cooldown_seconds,
            ollama_base_url="http://127.0.0.1:11434",
            ollama_summary_model="gpt-oss:20b",
        )

    def test_turn_delta_is_capped_to_three_lines(self):
        with patch("src.sessions.summary.load_summary_settings", return_value=self._heuristic_settings()):
            summary = update_summary_text(
                existing="",
                assistant_reply="You should build phase one first, then test the routing layer.",
                user_message="Can we plan all modules today?",
            )
        lines = [line for line in summary.splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 3)
        self.assertTrue(all(line.strip().startswith("- ") for line in lines))

    def test_summary_auto_compacts_under_token_cap(self):
        with patch("src.sessions.summary.load_summary_settings", return_value=self._heuristic_settings(token_cap=60)):
            summary = ""
            for i in range(20):
                summary = update_summary_text(
                    existing=summary,
                    assistant_reply=f"Assistant response {i}: keep implementation practical and verifiable.",
                    user_message=f"User asks long planning question number {i}?",
                )
        self.assertLessEqual(estimate_tokens(summary), 60)

    def test_ollama_recovers_before_failure_threshold(self):
        events = [
            httpx.TimeoutException("timed out"),
            httpx.TimeoutException("timed out"),
            {"response": "short stable summary"},
        ]
        post_calls = {"count": 0}

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class _Client:
            def __init__(self, *args, **kwargs):  # noqa: ARG002
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
                return False

            def post(self, *args, **kwargs):  # noqa: ARG002
                post_calls["count"] += 1
                event = events.pop(0)
                if isinstance(event, Exception):
                    raise event
                return _Resp(event)

        with patch("src.sessions.summary.httpx.Client", _Client):
            settings = self._ollama_settings(max_failures=3, cooldown_seconds=60.0)
            first = summary_module._try_ollama("prompt-1", settings)
            second = summary_module._try_ollama("prompt-2", settings)
            third = summary_module._try_ollama("prompt-3", settings)

        self.assertEqual(first, ("", "timeout"))
        self.assertEqual(second, ("", "timeout"))
        self.assertEqual(third, ("short stable summary", ""))
        self.assertEqual(post_calls["count"], 3)
        self.assertEqual(summary_module._OLLAMA_CONSECUTIVE_FAILURES, 0)

    def test_ollama_enters_cooldown_after_three_failures(self):
        post_calls = {"count": 0}

        class _Client:
            def __init__(self, *args, **kwargs):  # noqa: ARG002
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):  # noqa: ARG002
                return False

            def post(self, *args, **kwargs):  # noqa: ARG002
                post_calls["count"] += 1
                raise httpx.TimeoutException("timed out")

        with patch("src.sessions.summary.httpx.Client", _Client):
            settings = self._ollama_settings(max_failures=3, cooldown_seconds=120.0)
            one = summary_module._try_ollama("prompt-1", settings)
            two = summary_module._try_ollama("prompt-2", settings)
            three = summary_module._try_ollama("prompt-3", settings)
            four = summary_module._try_ollama("prompt-4", settings)

        self.assertEqual(one, ("", "timeout"))
        self.assertEqual(two, ("", "timeout"))
        self.assertEqual(three, ("", "timeout"))
        self.assertEqual(four, ("", "cooldown"))
        self.assertEqual(post_calls["count"], 3)

    def test_compact_summary_handles_try_ollama_tuple(self):
        settings = self._ollama_settings(max_failures=3, cooldown_seconds=60.0)
        with patch("src.sessions.summary._try_ollama", return_value=("line a\nline b", "")):
            compacted = summary_module._compact_summary("old summary text", settings)
        self.assertIn("- line a", compacted)


if __name__ == "__main__":
    unittest.main()

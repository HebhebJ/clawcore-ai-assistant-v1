import unittest

import httpx

from src.core.config import LLMSettings
from src.core.errors import ProviderUpstreamError
from src.llm.kimi_provider import KimiProvider


class _SequenceClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def post(self, url: str, headers: dict, json: dict):  # noqa: ARG002
        self.calls += 1
        if not self._responses:
            raise RuntimeError("no more responses configured")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        status_code, payload = next_item
        request = httpx.Request("POST", url)
        return httpx.Response(status_code=status_code, json=payload, request=request)


class KimiProviderTests(unittest.TestCase):
    def _settings(self) -> LLMSettings:
        return LLMSettings(
            llm_provider="kimi",
            kimi_api_key="k",
            kimi_model="m",
            kimi_base_url="https://api.moonshot.ai/v1",
            kimi_timeout_seconds=30.0,
            kimi_temperature=1.0,
            kimi_max_tokens=800,
        )

    def test_retries_once_on_retryable_http_status(self):
        success_payload = {
            "choices": [
                {
                    "message": {"content": '{"action":"final_answer","final_answer":"ok"}'},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        client = _SequenceClient(
            [
                (503, {"error": {"message": "unavailable"}}),
                (200, success_payload),
            ]
        )
        provider = KimiProvider(settings=self._settings(), client=client)

        result = provider.generate("hello", {})
        self.assertEqual(result.get("action"), "final_answer")
        self.assertEqual(client.calls, 2)

    def test_does_not_retry_on_non_retryable_http_status(self):
        client = _SequenceClient([(400, {"error": {"message": "bad request"}})])
        provider = KimiProvider(settings=self._settings(), client=client)

        with self.assertRaises(ProviderUpstreamError):
            provider.generate("hello", {})
        self.assertEqual(client.calls, 1)


if __name__ == "__main__":
    unittest.main()


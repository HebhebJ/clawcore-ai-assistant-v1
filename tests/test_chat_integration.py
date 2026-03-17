import os
import unittest
import uuid
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from src.core.app import app
from src.llm.factory import create_provider


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.moonshot.ai/v1/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("upstream error", request=request, response=response)

    def json(self):
        return self._data


class FakeHTTPClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def post(self, url, headers, json):
        if not self._responses:
            raise AssertionError("No more fake responses available")
        return self._responses.pop(0)


class ChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _clear_runtime_cache(self):
        from src.api.chat import get_runtime

        get_runtime.cache_clear()

    def test_chat_with_mock_provider(self):
        self._clear_runtime_cache()
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False):
            session_id = f"test-mock-{uuid.uuid4().hex[:8]}"
            response = self.client.post(
                "/chat",
                json={
                    "workspace_id": "default-agent",
                    "session_id": session_id,
                    "message": "List workspace files",
                },
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("answer", body)
            self.assertGreaterEqual(body["steps"], 1)

    def test_chat_with_kimi_mocked_http_tool_then_final(self):
        self._clear_runtime_cache()
        env = {
            "LLM_PROVIDER": "kimi",
            "KIMI_API_KEY": "test-key",
            "KIMI_MODEL": "kimi-k2",
        }
        fake_client = FakeHTTPClient(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"action":"tool_call","tool_name":"list_files","tool_input":{"path":"."}}'
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 8},
                    }
                ),
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"action":"final_answer","final_answer":"done"}'
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 15, "completion_tokens": 5},
                    }
                ),
            ]
        )

        with patch.dict(os.environ, env, clear=False):
            with patch("src.agents.runtime.create_provider", side_effect=lambda settings: create_provider(settings, client=fake_client)):
                session_id = f"test-kimi-{uuid.uuid4().hex[:8]}"
                response = self.client.post(
                    "/chat",
                    json={
                        "workspace_id": "default-agent",
                        "session_id": session_id,
                        "message": "List workspace files",
                    },
                )
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["answer"], "done")
                self.assertGreaterEqual(body["tool_calls"], 1)

    def test_chat_with_kimi_upstream_error_maps_502(self):
        self._clear_runtime_cache()
        env = {
            "LLM_PROVIDER": "kimi",
            "KIMI_API_KEY": "test-key",
            "KIMI_MODEL": "kimi-k2",
        }
        fake_client = FakeHTTPClient([FakeResponse({}, status_code=502)])
        with patch.dict(os.environ, env, clear=False):
            with patch("src.agents.runtime.create_provider", side_effect=lambda settings: create_provider(settings, client=fake_client)):
                session_id = f"test-kimi-err-{uuid.uuid4().hex[:8]}"
                response = self.client.post(
                    "/chat",
                    json={
                        "workspace_id": "default-agent",
                        "session_id": session_id,
                        "message": "hello",
                    },
                )
                self.assertEqual(response.status_code, 502)

    def test_chat_with_kimi_malformed_action_stops_safely(self):
        self._clear_runtime_cache()
        env = {
            "LLM_PROVIDER": "kimi",
            "KIMI_API_KEY": "test-key",
            "KIMI_MODEL": "kimi-k2",
        }
        fake_client = FakeHTTPClient(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {"content": "not-json"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                    }
                )
            ]
        )
        with patch.dict(os.environ, env, clear=False):
            with patch("src.agents.runtime.create_provider", side_effect=lambda settings: create_provider(settings, client=fake_client)):
                session_id = f"test-kimi-bad-{uuid.uuid4().hex[:8]}"
                response = self.client.post(
                    "/chat",
                    json={
                        "workspace_id": "default-agent",
                        "session_id": session_id,
                        "message": "hello",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("unsupported action", response.json()["answer"].lower())


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.telegram import _clear_processed_updates_for_tests
from src.core.app import app
from src.core.config import TelegramSettings


class _FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.flush_calls: list[dict] = []

    def handle_message(self, workspace_id: str, session_id: str, message: str) -> dict:
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "session_id": session_id,
                "message": message,
            }
        )
        return {"answer": "telegram-ok"}

    def flush_memory(self, workspace_id: str, session_id: str) -> dict:
        self.flush_calls.append({"workspace_id": workspace_id, "session_id": session_id})
        return {"ran": True, "saved": 2, "mode": "vector", "prompt_tokens": 0, "completion_tokens": 0}


class _FakeSessionStore:
    def __init__(self) -> None:
        self.current: dict[tuple[str, int], str] = {}
        self.new_counter = 0

    def get_or_create_current(self, workspace_id: str, chat_id: int) -> str:
        key = (workspace_id, chat_id)
        if key in self.current and self.current[key]:
            return self.current[key]
        if key not in self.current:
            self.current[key] = f"tg-{chat_id}"
        else:
            self.new_counter += 1
            self.current[key] = f"tg-{chat_id}-new-{self.new_counter}"
        return self.current[key]

    def start_new(self, workspace_id: str, chat_id: int) -> str:
        self.new_counter += 1
        value = f"tg-{chat_id}-new-{self.new_counter}"
        self.current[(workspace_id, chat_id)] = value
        return value

    def close_current(self, workspace_id: str, chat_id: int) -> str:
        key = (workspace_id, chat_id)
        existing = self.current.get(key, "")
        self.current[key] = ""
        return existing


class TelegramWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_processed_updates_for_tests()
        self.client = TestClient(app)

    def test_webhook_requires_configuration(self):
        with patch("src.api.telegram.load_telegram_settings", return_value=TelegramSettings(bot_token="")):
            response = self.client.post("/webhook/telegram", json={"update_id": 1})
        self.assertEqual(response.status_code, 503)

    def test_webhook_secret_is_validated(self):
        settings = TelegramSettings(bot_token="test-token", webhook_secret="expected-secret")
        with patch("src.api.telegram.load_telegram_settings", return_value=settings):
            response = self.client.post("/webhook/telegram", json={"update_id": 1})
        self.assertEqual(response.status_code, 403)

    def test_duplicate_update_is_ignored(self):
        settings = TelegramSettings(bot_token="test-token")
        with patch("src.api.telegram.load_telegram_settings", return_value=settings):
            with patch("src.api.telegram._process_update", return_value=None):
                payload = {"update_id": 22, "message": {"chat": {"id": 123}, "text": "hello"}}
                first = self.client.post("/webhook/telegram", json=payload)
                second = self.client.post("/webhook/telegram", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json().get("queued"), True)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json().get("duplicate"), True)

    def test_valid_text_message_routes_to_runtime(self):
        fake_runtime = _FakeRuntime()
        fake_store = _FakeSessionStore()
        settings = TelegramSettings(bot_token="test-token", workspace_id="default-agent")
        sent: list[dict] = []

        def _capture_send(settings, chat_id: int, text: str) -> None:
            sent.append({"chat_id": chat_id, "text": text})

        payload = {
            "update_id": 77,
            "message": {
                "chat": {"id": 987654},
                "text": "hi from telegram",
            },
        }

        with patch("src.api.telegram.load_telegram_settings", return_value=settings):
            with patch("src.api.telegram.get_runtime", return_value=fake_runtime):
                with patch("src.api.telegram._SESSION_STORE", fake_store):
                    with patch("src.api.telegram._send_telegram_messages", side_effect=_capture_send):
                        response = self.client.post("/webhook/telegram", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("queued"), True)
        self.assertEqual(len(fake_runtime.calls), 1)
        self.assertEqual(fake_runtime.calls[0]["session_id"], "tg-987654")
        self.assertEqual(fake_runtime.calls[0]["workspace_id"], "default-agent")
        self.assertEqual(fake_runtime.calls[0]["message"], "hi from telegram")
        self.assertEqual(sent, [{"chat_id": 987654, "text": "telegram-ok"}])

    def test_new_command_starts_fresh_session(self):
        fake_runtime = _FakeRuntime()
        fake_store = _FakeSessionStore()
        settings = TelegramSettings(bot_token="test-token", workspace_id="default-agent")
        sent: list[dict] = []

        def _capture_send(settings, chat_id: int, text: str) -> None:
            sent.append({"chat_id": chat_id, "text": text})

        payload = {"update_id": 90, "message": {"chat": {"id": 1234}, "text": "/new"}}
        with patch("src.api.telegram.load_telegram_settings", return_value=settings):
            with patch("src.api.telegram.get_runtime", return_value=fake_runtime):
                with patch("src.api.telegram._SESSION_STORE", fake_store):
                    with patch("src.api.telegram._send_telegram_messages", side_effect=_capture_send):
                        response = self.client.post("/webhook/telegram", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(fake_runtime.flush_calls), 1)
        self.assertEqual(fake_runtime.flush_calls[0]["session_id"], "tg-1234")
        self.assertEqual(fake_store.current[("default-agent", 1234)], "tg-1234-new-1")
        self.assertIn("Started new session: tg-1234-new-1", sent[0]["text"])

    def test_exit_command_closes_session_and_next_message_starts_new(self):
        fake_runtime = _FakeRuntime()
        fake_store = _FakeSessionStore()
        settings = TelegramSettings(bot_token="test-token", workspace_id="default-agent")
        sent: list[dict] = []

        def _capture_send(settings, chat_id: int, text: str) -> None:
            sent.append({"chat_id": chat_id, "text": text})

        exit_payload = {"update_id": 91, "message": {"chat": {"id": 1234}, "text": "/exit"}}
        msg_payload = {"update_id": 92, "message": {"chat": {"id": 1234}, "text": "hello again"}}
        with patch("src.api.telegram.load_telegram_settings", return_value=settings):
            with patch("src.api.telegram.get_runtime", return_value=fake_runtime):
                with patch("src.api.telegram._SESSION_STORE", fake_store):
                    with patch("src.api.telegram._send_telegram_messages", side_effect=_capture_send):
                        self.client.post("/webhook/telegram", json=exit_payload)
                        self.client.post("/webhook/telegram", json=msg_payload)

        self.assertEqual(len(fake_runtime.flush_calls), 1)
        self.assertEqual(fake_runtime.flush_calls[0]["session_id"], "tg-1234")
        self.assertEqual(len(fake_runtime.calls), 1)
        self.assertEqual(fake_runtime.calls[0]["session_id"], "tg-1234-new-1")
        self.assertIn("Session closed.", sent[0]["text"])
        self.assertEqual(sent[1]["text"], "telegram-ok")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.config import LLMSettings
from src.memory.distiller import MemoryDistiller
from src.memory.store import MemoryStore
from src.memory.writer import MemoryWriter
from src.sessions.manager import SessionManager


class MemoryDistillTests(unittest.IsolatedAsyncioTestCase):
    async def test_distill_from_transcript_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)
            (base / "default-agent" / "sessions").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base), patch("src.sessions.manager.WORKSPACES_DIR", base):
                manager = SessionManager()
                writer = MemoryWriter()
                distiller = MemoryDistiller(
                    manager,
                    writer,
                    settings=LLMSettings(llm_provider="mock"),
                    llm_extract_fn=lambda user_turns, summary, existing: (
                        [
                            {
                                "type": "environment_fact",
                                "content": "User name: iheb",
                                "tags": ["user", "identity"],
                                "importance": 0.9,
                            },
                            {
                                "type": "project_fact",
                                "content": "User is building ai agentic systems",
                                "tags": ["project"],
                                "importance": 0.7,
                            },
                        ],
                        123,
                        45,
                    ),
                )

                manager.load_or_create("default-agent", "s1")
                manager.append_transcript(
                    "default-agent",
                    "s1",
                    {"role": "user", "content": "my name is iheb", "timestamp": "2026-03-16T00:00:00Z"},
                )
                manager.append_transcript(
                    "default-agent",
                    "s1",
                    {
                        "role": "user",
                        "content": "i am a software engineering student who loves building ai agentic systems",
                        "timestamp": "2026-03-16T00:00:01Z",
                    },
                )
                manager.update_summary(
                    "default-agent",
                    "s1",
                    "User said they love apples and are building AI agentic systems.",
                )

                info = await distiller.distill_session("default-agent", "s1")
                self.assertEqual(info["mode"], "llm")
                self.assertGreaterEqual(info["saved"], 2)
                self.assertEqual(info["prompt_tokens"], 123)
                self.assertEqual(info["completion_tokens"], 45)

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                text = "\n".join(str(f.get("content", "")) for f in facts).lower()
                self.assertIn("user name: iheb", text)
                self.assertIn("building ai agentic systems", text)

    async def test_kimi_distill_uses_configured_temperature(self):
        """Provider.complete() is called with the configured temperature."""
        import httpx
        from src.llm.http_provider import HttpProvider

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {
                    "choices": [{"message": {"content": '{"memories": []}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }

        captured: dict = {}

        class _Client:
            async def post(self, url: str, headers: dict, json: dict):
                captured["url"] = url
                captured["json"] = json
                return _Response()

        settings = LLMSettings(
            llm_provider="kimi",
            llm_api_key="k",
            llm_model="m",
            llm_base_url="https://api.moonshot.ai/v1",
            llm_timeout_seconds=30.0,
            llm_temperature=1.0,
            llm_max_tokens=800,
        )
        provider = HttpProvider(settings=settings, base_url="https://api.moonshot.ai/v1", client=_Client())

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)
            (base / "default-agent" / "sessions").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base), patch("src.sessions.manager.WORKSPACES_DIR", base):
                manager = SessionManager()
                writer = MemoryWriter()
                distiller = MemoryDistiller(manager, writer, settings=settings, provider=provider)

                manager.load_or_create("default-agent", "s1")
                manager.append_transcript(
                    "default-agent",
                    "s1",
                    {"role": "user", "content": "my name is iheb", "timestamp": "2026-03-16T00:00:00Z"},
                )

                info = await distiller.distill_session("default-agent", "s1")

        self.assertEqual(info["mode"], "llm")
        self.assertEqual(captured["json"]["temperature"], 1.0)


if __name__ == "__main__":
    unittest.main()

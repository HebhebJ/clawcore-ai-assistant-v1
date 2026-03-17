import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.memory.retrieval import MemoryRetrieval
from src.memory.store import MemoryStore
from src.memory.writer import MemoryWriter


class MemoryTests(unittest.TestCase):
    def test_user_preference_is_stored_and_retrieved(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "I love apples", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0]["type"], "user_preference")
                self.assertIn("apples", facts[0]["content"].lower())

                retrieval = MemoryRetrieval()
                items = retrieval.retrieve("default-agent", "apples")
                self.assertTrue(items)
                self.assertIn("apples", items[0].lower())

    def test_open_task_is_stored_in_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "Next step: add write_file tool", "ok")

                store = MemoryStore()
                notes = store.load_notes("default-agent")
                self.assertEqual(len(notes), 1)
                self.assertEqual(notes[0]["type"], "open_task")

    def test_duplicate_memory_is_not_stored_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "I love apples", "ok")
                writer.maybe_store("default-agent", "I love apples", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                self.assertEqual(len(facts), 1)

    def test_age_and_location_are_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "I am 25 yo", "ok")
                writer.maybe_store("default-agent", "Am from tunisia", "ok")
                writer.maybe_store("default-agent", "I live in tunisia", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                text = "\n".join(str(f.get("content", "")).lower() for f in facts)
                self.assertIn("user age: 25", text)
                self.assertIn("user is from: tunisia", text)
                self.assertIn("user lives in: tunisia", text)

    def test_languages_are_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "I speak Arabic, French and English", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0]["type"], "environment_fact")
                self.assertIn("languages", str(facts[0]["content"]).lower())
                self.assertIn("arabic", str(facts[0]["content"]).lower())

    def test_explicit_memory_command_save_to_your_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "save to your memory: i speak arabic and french", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                self.assertEqual(len(facts), 1)
                self.assertIn("languages", str(facts[0]["content"]).lower())
                self.assertIn("arabic", str(facts[0]["content"]).lower())

    def test_explicit_memory_command_memorize_that(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "memorize that my timezone is Africa/Tunis", "ok")

                store = MemoryStore()
                facts = store.load_facts("default-agent")
                self.assertEqual(len(facts), 1)
                self.assertIn("timezone", str(facts[0]["content"]).lower())


if __name__ == "__main__":
    unittest.main()

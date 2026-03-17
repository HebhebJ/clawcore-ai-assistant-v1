import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.memory.retrieval import MemoryRetrieval
from src.memory.writer import MemoryWriter


class VectorMemoryTests(unittest.TestCase):
    def test_embeddings_file_is_created_on_memory_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch("src.memory.store.WORKSPACES_DIR", base), patch("src.memory.vector_index.WORKSPACES_DIR", base):
                writer = MemoryWriter()
                writer.maybe_store("default-agent", "I love python programming", "ok")

                embeddings_path = base / "default-agent" / "memory" / "embeddings.jsonl"
                self.assertTrue(embeddings_path.exists())
                rows = [line for line in embeddings_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(len(rows), 1)

    def test_vector_mode_retrieves_nearby_word_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "default-agent" / "memory").mkdir(parents=True, exist_ok=True)

            with patch.dict("os.environ", {"MEMORY_RETRIEVAL_MODE": "vector"}):
                with patch("src.memory.store.WORKSPACES_DIR", base), patch("src.memory.vector_index.WORKSPACES_DIR", base):
                    writer = MemoryWriter()
                    writer.maybe_store("default-agent", "I love python programming", "ok")

                    retrieval = MemoryRetrieval()
                    items = retrieval.retrieve("default-agent", "I enjoy pythonic coding")
                    self.assertTrue(items)
                    self.assertIn("python", items[0].lower())

    def test_retrieval_mode_can_load_from_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / ".env").write_text("MEMORY_RETRIEVAL_MODE=vector\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                with patch("src.core.config.BASE_DIR", base):
                    retrieval = MemoryRetrieval()
                    self.assertEqual(retrieval.mode, "vector")


if __name__ == "__main__":
    unittest.main()

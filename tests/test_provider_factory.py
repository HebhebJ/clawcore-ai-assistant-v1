import os
import unittest
from unittest.mock import patch

from src.core.config import load_llm_settings
from src.core.errors import RuntimeConfigError
from src.llm.factory import create_provider
from src.llm.kimi_provider import KimiProvider
from src.llm.mock_provider import MockProvider


class ProviderFactoryTests(unittest.TestCase):
    def test_create_provider_mock(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, MockProvider)

    def test_kimi_missing_required_env(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "kimi", "KIMI_API_KEY": "", "KIMI_MODEL": ""}, clear=False):
            with self.assertRaises(RuntimeConfigError):
                load_llm_settings()

    def test_create_provider_kimi(self):
        env = {
            "LLM_PROVIDER": "kimi",
            "KIMI_API_KEY": "test-key",
            "KIMI_MODEL": "kimi-k2",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, KimiProvider)


if __name__ == "__main__":
    unittest.main()

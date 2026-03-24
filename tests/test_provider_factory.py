import os
import unittest
from unittest.mock import patch

from src.core.config import load_llm_settings
from src.core.errors import RuntimeConfigError
from src.llm.factory import create_provider
from src.llm.http_provider import HttpProvider
from src.llm.mock_provider import MockProvider


class ProviderFactoryTests(unittest.TestCase):
    def test_create_provider_mock(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, MockProvider)

    def test_kimi_missing_required_env(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "kimi", "LLM_API_KEY": "", "LLM_MODEL": ""}, clear=False):
            with self.assertRaises(RuntimeConfigError):
                load_llm_settings()

    def test_create_provider_kimi(self):
        env = {
            "LLM_PROVIDER": "kimi",
            "LLM_API_KEY": "test-key",
            "LLM_MODEL": "kimi-k2",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, HttpProvider)

    def test_create_provider_openai(self):
        env = {
            "LLM_PROVIDER": "openai",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "gpt-4o-mini",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, HttpProvider)

    def test_create_provider_openrouter(self):
        env = {
            "LLM_PROVIDER": "openrouter",
            "LLM_API_KEY": "sk-or-test",
            "LLM_MODEL": "mistralai/mistral-7b-instruct",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = load_llm_settings()
            provider = create_provider(settings)
            self.assertIsInstance(provider, HttpProvider)
            self.assertEqual(settings.llm_base_url, "https://openrouter.ai/api/v1")

    def test_openai_missing_required_env(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "LLM_API_KEY": "", "LLM_MODEL": ""}, clear=False):
            with self.assertRaises(RuntimeConfigError):
                load_llm_settings()


if __name__ == "__main__":
    unittest.main()

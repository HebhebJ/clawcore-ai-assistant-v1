from src.core.config import LLMSettings
from src.core.errors import RuntimeConfigError
from src.llm.kimi_provider import KimiProvider
from src.llm.mock_provider import MockProvider


def create_provider(settings: LLMSettings, client=None):
    if settings.llm_provider == "mock":
        return MockProvider()
    if settings.llm_provider == "kimi":
        return KimiProvider(settings, client=client)
    raise RuntimeConfigError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

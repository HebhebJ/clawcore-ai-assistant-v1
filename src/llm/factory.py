from src.core.config import LLMSettings
from src.core.errors import RuntimeConfigError
from src.llm.http_provider import HttpProvider
from src.llm.mock_provider import MockProvider

_DEFAULT_BASE_URLS: dict[str, str] = {
    "kimi": "https://api.moonshot.ai/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def create_provider(settings: LLMSettings, client=None):
    if settings.llm_provider == "mock":
        return MockProvider()
    base_url = settings.llm_base_url or _DEFAULT_BASE_URLS.get(settings.llm_provider, "")
    if not base_url:
        raise RuntimeConfigError(
            f"No base URL known for LLM_PROVIDER={settings.llm_provider!r}. Set LLM_BASE_URL."
        )
    return HttpProvider(settings, base_url=base_url, client=client)

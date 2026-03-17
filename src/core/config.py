import os
from dataclasses import dataclass
from pathlib import Path

from src.core.errors import RuntimeConfigError

BASE_DIR = Path(__file__).resolve().parents[2]
WORKSPACES_DIR = BASE_DIR / "workspaces"
DEFAULT_WORKSPACE_ID = "default-agent"
MAX_STEPS = 10
MAX_TOOL_CALLS = 5
MAX_REASONING_ACTIONS = 5


@dataclass(frozen=True)
class LLMSettings:
    llm_provider: str = "kimi"
    kimi_api_key: str = ""
    kimi_model: str = ""
    kimi_base_url: str = "https://api.moonshot.ai/v1"
    kimi_timeout_seconds: float = 30.0
    kimi_temperature: float = 0.2
    kimi_max_tokens: int = 800


def _load_dotenv_file() -> None:
    dotenv_path = BASE_DIR / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RuntimeConfigError(f"{name} must be a float") from exc


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeConfigError(f"{name} must be an integer") from exc


def load_llm_settings() -> LLMSettings:
    _load_dotenv_file()

    settings = LLMSettings(
        llm_provider=os.getenv("LLM_PROVIDER", "kimi").strip().lower(),
        kimi_api_key=os.getenv("KIMI_API_KEY", "").strip(),
        kimi_model=os.getenv("KIMI_MODEL", "").strip(),
        kimi_base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1").strip(),
        kimi_timeout_seconds=_get_env_float("KIMI_TIMEOUT_SECONDS", 30.0),
        kimi_temperature=_get_env_float("KIMI_TEMPERATURE", 0.2),
        kimi_max_tokens=_get_env_int("KIMI_MAX_TOKENS", 800),
    )

    if settings.llm_provider == "kimi":
        if not settings.kimi_api_key:
            raise RuntimeConfigError("Missing required env var: KIMI_API_KEY")
        if not settings.kimi_model:
            raise RuntimeConfigError("Missing required env var: KIMI_MODEL")

    return settings


def load_memory_distill_every_turns() -> int:
    _load_dotenv_file()
    value = _get_env_int("MEMORY_DISTILL_EVERY_TURNS", 6)
    if value < 1:
        raise RuntimeConfigError("MEMORY_DISTILL_EVERY_TURNS must be >= 1")
    return value


def load_memory_retrieval_mode() -> str:
    _load_dotenv_file()
    mode = os.getenv("MEMORY_RETRIEVAL_MODE", "hybrid").strip().lower()
    if mode not in {"hybrid", "vector", "keyword"}:
        raise RuntimeConfigError("MEMORY_RETRIEVAL_MODE must be one of: hybrid, vector, keyword")
    return mode

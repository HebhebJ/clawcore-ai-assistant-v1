import os
from dataclasses import dataclass
from pathlib import Path

from src.core.errors import RuntimeConfigError

BASE_DIR = Path(__file__).resolve().parents[2]
WORKSPACES_DIR = BASE_DIR / "workspaces"
DEFAULT_WORKSPACE_ID = "default-agent"


@dataclass(frozen=True)
class AgentLimits:
    max_steps: int = 10
    max_tool_calls: int = 5
    max_reasoning_actions: int = 5


@dataclass(frozen=True)
class LLMSettings:
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_seconds: float = 30.0
    llm_temperature: float = 0.2
    llm_max_tokens: int = 800
    llm_max_retries: int = 1


@dataclass(frozen=True)
class SummarySettings:
    summary_updater_provider: str = "heuristic"
    summary_token_cap: int = 1000
    summary_delta_max_lines: int = 3
    summary_compact_target_tokens: int = 350
    summary_timeout_seconds: float = 30.0
    summary_temperature: float = 0.1
    summary_max_failures: int = 3
    summary_cooldown_seconds: float = 60.0
    summary_api_key: str = ""
    summary_model: str = ""
    summary_base_url: str = ""


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = ""
    webhook_secret: str = ""
    workspace_id: str = DEFAULT_WORKSPACE_ID
    timeout_seconds: float = 20.0


@dataclass(frozen=True)
class TelegramAutoSetupSettings:
    enabled: bool = False
    public_base_url: str = ""
    auto_ngrok: bool = False
    local_port: int = 8000
    startup_timeout_seconds: float = 20.0
    ngrok_path: str = "ngrok"
    ngrok_authtoken: str = ""


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


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    norm = value.strip().lower()
    if norm in {"1", "true", "yes", "on"}:
        return True
    if norm in {"0", "false", "no", "off"}:
        return False
    raise RuntimeConfigError(f"{name} must be a boolean (true/false)")


def load_agent_limits() -> AgentLimits:
    _load_dotenv_file()
    max_steps = _get_env_int("MAX_STEPS", 10)
    max_tool_calls = _get_env_int("MAX_TOOL_CALLS", 5)
    max_reasoning_actions = _get_env_int("MAX_REASONING_ACTIONS", 5)
    if max_steps < 1:
        raise RuntimeConfigError("MAX_STEPS must be >= 1")
    if max_tool_calls < 1:
        raise RuntimeConfigError("MAX_TOOL_CALLS must be >= 1")
    if max_reasoning_actions < 1:
        raise RuntimeConfigError("MAX_REASONING_ACTIONS must be >= 1")
    return AgentLimits(
        max_steps=max_steps,
        max_tool_calls=max_tool_calls,
        max_reasoning_actions=max_reasoning_actions,
    )


def load_llm_settings() -> LLMSettings:
    _load_dotenv_file()

    settings = LLMSettings(
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "").strip(),
        llm_timeout_seconds=_get_env_float("LLM_TIMEOUT_SECONDS", 30.0),
        llm_temperature=_get_env_float("LLM_TEMPERATURE", 0.2),
        llm_max_tokens=_get_env_int("LLM_MAX_TOKENS", 800),
        llm_max_retries=_get_env_int("LLM_MAX_RETRIES", 1),
    )

    if settings.llm_provider != "mock":
        if not settings.llm_api_key:
            raise RuntimeConfigError("Missing required env var: LLM_API_KEY")
        if not settings.llm_model:
            raise RuntimeConfigError("Missing required env var: LLM_MODEL")

    return settings


def load_memory_distill_every_turns() -> int:
    _load_dotenv_file()
    value = _get_env_int("MEMORY_DISTILL_EVERY_TURNS", 6)
    if value < 1:
        raise RuntimeConfigError("MEMORY_DISTILL_EVERY_TURNS must be >= 1")
    return value


def load_session_max_age_days() -> int:
    _load_dotenv_file()
    value = _get_env_int("SESSION_MAX_AGE_DAYS", 30)
    if value < 1:
        raise RuntimeConfigError("SESSION_MAX_AGE_DAYS must be >= 1")
    return value


def load_summary_every_turns() -> int:
    _load_dotenv_file()
    value = _get_env_int("SUMMARY_EVERY_TURNS", 3)
    if value < 1:
        raise RuntimeConfigError("SUMMARY_EVERY_TURNS must be >= 1")
    return value


def load_memory_retrieval_mode() -> str:
    _load_dotenv_file()
    mode = os.getenv("MEMORY_RETRIEVAL_MODE", "hybrid").strip().lower()
    if mode not in {"hybrid", "vector", "keyword"}:
        raise RuntimeConfigError("MEMORY_RETRIEVAL_MODE must be one of: hybrid, vector, keyword")
    return mode


_SUMMARY_DEFAULT_BASE_URLS: dict[str, str] = {
    "ollama": "http://127.0.0.1:11434",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "kimi": "https://api.moonshot.ai/v1",
}
_SUMMARY_DEFAULT_MODELS: dict[str, str] = {
    "ollama": "gpt-oss:20b",
}


def load_summary_settings() -> SummarySettings:
    _load_dotenv_file()
    provider = os.getenv("SUMMARY_UPDATER_PROVIDER", "heuristic").strip().lower()
    valid_providers = {"ollama", "openrouter", "openai", "kimi", "heuristic"}
    if provider not in valid_providers:
        raise RuntimeConfigError(f"SUMMARY_UPDATER_PROVIDER must be one of: {', '.join(sorted(valid_providers))}")

    token_cap = _get_env_int("SUMMARY_TOKEN_CAP", 1000)
    if token_cap < 200:
        raise RuntimeConfigError("SUMMARY_TOKEN_CAP must be >= 200")

    delta_lines = _get_env_int("SUMMARY_DELTA_MAX_LINES", 3)
    if delta_lines < 1 or delta_lines > 8:
        raise RuntimeConfigError("SUMMARY_DELTA_MAX_LINES must be between 1 and 8")

    compact_target = _get_env_int("SUMMARY_COMPACT_TARGET_TOKENS", 350)
    if compact_target < 100:
        raise RuntimeConfigError("SUMMARY_COMPACT_TARGET_TOKENS must be >= 100")

    timeout_seconds = _get_env_float("SUMMARY_TIMEOUT_SECONDS", 30.0)
    if timeout_seconds <= 0:
        raise RuntimeConfigError("SUMMARY_TIMEOUT_SECONDS must be > 0")

    temperature = _get_env_float("SUMMARY_TEMPERATURE", 0.1)
    if temperature < 0 or temperature > 2:
        raise RuntimeConfigError("SUMMARY_TEMPERATURE must be between 0 and 2")

    max_failures = _get_env_int("SUMMARY_MAX_FAILURES", 3)
    if max_failures < 1:
        raise RuntimeConfigError("SUMMARY_MAX_FAILURES must be >= 1")

    cooldown_seconds = _get_env_float("SUMMARY_COOLDOWN_SECONDS", 60.0)
    if cooldown_seconds < 0:
        raise RuntimeConfigError("SUMMARY_COOLDOWN_SECONDS must be >= 0")

    base_url = os.getenv("SUMMARY_BASE_URL", "").strip() or _SUMMARY_DEFAULT_BASE_URLS.get(provider, "")
    model = os.getenv("SUMMARY_MODEL", "").strip() or _SUMMARY_DEFAULT_MODELS.get(provider, "")

    return SummarySettings(
        summary_updater_provider=provider,
        summary_token_cap=token_cap,
        summary_delta_max_lines=delta_lines,
        summary_compact_target_tokens=compact_target,
        summary_timeout_seconds=timeout_seconds,
        summary_temperature=temperature,
        summary_max_failures=max_failures,
        summary_cooldown_seconds=cooldown_seconds,
        summary_api_key=os.getenv("SUMMARY_API_KEY", "").strip(),
        summary_model=model,
        summary_base_url=base_url,
    )


def load_telegram_settings() -> TelegramSettings:
    _load_dotenv_file()
    workspace_id = os.getenv("TELEGRAM_WORKSPACE_ID", DEFAULT_WORKSPACE_ID).strip() or DEFAULT_WORKSPACE_ID
    timeout_seconds = _get_env_float("TELEGRAM_TIMEOUT_SECONDS", 20.0)
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise RuntimeConfigError("TELEGRAM_TIMEOUT_SECONDS must be between 0 and 120")

    return TelegramSettings(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip(),
        workspace_id=workspace_id,
        timeout_seconds=timeout_seconds,
    )


def load_telegram_auto_setup_settings() -> TelegramAutoSetupSettings:
    _load_dotenv_file()
    enabled = _get_env_bool("TELEGRAM_AUTO_SETUP", False)
    auto_ngrok = _get_env_bool("TELEGRAM_AUTO_NGROK", False)
    local_port = _get_env_int("TELEGRAM_LOCAL_PORT", 8000)
    if local_port < 1 or local_port > 65535:
        raise RuntimeConfigError("TELEGRAM_LOCAL_PORT must be between 1 and 65535")
    startup_timeout_seconds = _get_env_float("TELEGRAM_STARTUP_TIMEOUT_SECONDS", 20.0)
    if startup_timeout_seconds <= 0 or startup_timeout_seconds > 120:
        raise RuntimeConfigError("TELEGRAM_STARTUP_TIMEOUT_SECONDS must be between 0 and 120")

    return TelegramAutoSetupSettings(
        enabled=enabled,
        public_base_url=os.getenv("TELEGRAM_PUBLIC_BASE_URL", "").strip(),
        auto_ngrok=auto_ngrok,
        local_port=local_port,
        startup_timeout_seconds=startup_timeout_seconds,
        ngrok_path=os.getenv("NGROK_PATH", "ngrok").strip() or "ngrok",
        ngrok_authtoken=os.getenv("NGROK_AUTHTOKEN", "").strip(),
    )

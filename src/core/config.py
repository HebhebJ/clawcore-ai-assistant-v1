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


@dataclass(frozen=True)
class SummarySettings:
    summary_updater_provider: str = "ollama"
    summary_token_cap: int = 1000
    summary_delta_max_lines: int = 3
    summary_compact_target_tokens: int = 350
    summary_timeout_seconds: float = 30.0
    summary_temperature: float = 0.1
    summary_ollama_max_failures: int = 3
    summary_ollama_cooldown_seconds: float = 60.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_summary_model: str = "gpt-oss:20b"


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


def load_summary_settings() -> SummarySettings:
    _load_dotenv_file()
    provider = os.getenv("SUMMARY_UPDATER_PROVIDER", "ollama").strip().lower()
    if provider not in {"ollama", "heuristic"}:
        raise RuntimeConfigError("SUMMARY_UPDATER_PROVIDER must be one of: ollama, heuristic")

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

    max_failures = _get_env_int("SUMMARY_OLLAMA_MAX_FAILURES", 3)
    if max_failures < 1:
        raise RuntimeConfigError("SUMMARY_OLLAMA_MAX_FAILURES must be >= 1")

    cooldown_seconds = _get_env_float("SUMMARY_OLLAMA_COOLDOWN_SECONDS", 60.0)
    if cooldown_seconds < 0:
        raise RuntimeConfigError("SUMMARY_OLLAMA_COOLDOWN_SECONDS must be >= 0")

    return SummarySettings(
        summary_updater_provider=provider,
        summary_token_cap=token_cap,
        summary_delta_max_lines=delta_lines,
        summary_compact_target_tokens=compact_target,
        summary_timeout_seconds=timeout_seconds,
        summary_temperature=temperature,
        summary_ollama_max_failures=max_failures,
        summary_ollama_cooldown_seconds=cooldown_seconds,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip(),
        ollama_summary_model=os.getenv("OLLAMA_SUMMARY_MODEL", "gpt-oss:20b").strip(),
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

import logging
import time

import httpx

from src.core.config import LLMSettings
from src.core.errors import ProviderUpstreamError
from src.llm.action_parser import parse_action_response
from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)

ACTION_INSTRUCTIONS = """Return only JSON object with one of three shapes.
1) Tool call:
{"action":"tool_call","tool_name":"<tool>","tool_input":{...}}
2) Reasoning:
{"action":"reasoning","reasoning":"<short next step note>"}
3) Final:
{"action":"final_answer","final_answer":"<answer>"}
No markdown fences. No additional keys.
"""


class KimiProvider(LLMProvider):
    def __init__(self, settings: LLMSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.kimi_timeout_seconds)

    def generate(self, context: str, tools: dict) -> dict:
        url = f"{self.settings.kimi_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.kimi_model,
            "messages": [
                {"role": "system", "content": ACTION_INSTRUCTIONS},
                {"role": "user", "content": context},
            ],
            "temperature": self.settings.kimi_temperature,
            "max_tokens": self.settings.kimi_max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.kimi_api_key}",
            "Content-Type": "application/json",
        }

        start = time.perf_counter()
        try:
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("provider=kimi upstream_error request_failed error=%s", exc.__class__.__name__)
            raise ProviderUpstreamError("Kimi upstream request failed") from exc
        except ValueError as exc:
            logger.warning("provider=kimi upstream_error invalid_json")
            raise ProviderUpstreamError("Kimi upstream returned invalid JSON") from exc

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        try:
            choice = data["choices"][0]
            message_content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "unknown")
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("provider=kimi upstream_error invalid_shape")
            raise ProviderUpstreamError("Kimi upstream response shape invalid") from exc

        parsed = parse_action_response(message_content)
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        logger.info(
            "provider=kimi model=%s latency_ms=%s prompt_tokens=%s completion_tokens=%s stop_reason=%s action=%s",
            self.settings.kimi_model,
            elapsed_ms,
            prompt_tokens if prompt_tokens else "na",
            completion_tokens if completion_tokens else "na",
            finish_reason,
            parsed.get("action", "unknown"),
        )
        parsed["_meta"] = {
            "provider": "kimi",
            "model": self.settings.kimi_model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "stop_reason": finish_reason,
            "latency_ms": elapsed_ms,
        }
        return parsed

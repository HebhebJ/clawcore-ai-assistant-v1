import asyncio
import logging
import time

import httpx

from src.core.config import LLMSettings
from src.core.errors import ProviderUpstreamError
from src.llm.action_parser import parse_action_response
from src.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class HttpProvider(LLMProvider):
    """OpenAI-compatible HTTP provider.

    Works with any OpenAI-compatible endpoint: OpenAI, OpenRouter, Kimi, etc.
    The caller (factory) is responsible for resolving the base_url.
    """

    def __init__(self, settings: LLMSettings, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.base_url = base_url
        self.client = client or httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    async def generate(self, messages: list[dict], tools: dict) -> dict:
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }

        start = time.perf_counter()
        data = await self._post_with_retry(payload)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        try:
            choice = data["choices"][0]
            message_content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "unknown")
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("provider=%s upstream_error invalid_shape", self.settings.llm_provider)
            raise ProviderUpstreamError("Upstream response shape invalid") from exc

        parsed = parse_action_response(message_content)
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        logger.info(
            "provider=%s model=%s latency_ms=%s prompt_tokens=%s completion_tokens=%s stop_reason=%s action=%s",
            self.settings.llm_provider,
            self.settings.llm_model,
            elapsed_ms,
            prompt_tokens if prompt_tokens else "na",
            completion_tokens if completion_tokens else "na",
            finish_reason,
            parsed.get("action", "unknown"),
        )
        parsed["_meta"] = {
            "provider": self.settings.llm_provider,
            "model": self.settings.llm_model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "stop_reason": finish_reason,
            "latency_ms": elapsed_ms,
            "raw_content": message_content,
        }
        return parsed

    async def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.llm_temperature,
            "max_tokens": min(1200, self.settings.llm_max_tokens),
        }
        data = await self._post_with_retry(payload)
        content = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return content, int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)

    async def _post_with_retry(self, payload: dict) -> dict:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        retries = self.settings.llm_max_retries
        data = None
        for attempt in range(retries + 1):
            try:
                response = await self.client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else -1
                body = ""
                if exc.response is not None:
                    body = (exc.response.text or "").replace("\n", " ").strip()[:220]
                retryable = status in {429, 500, 502, 503, 504}
                logger.warning(
                    "provider=%s upstream_error status=%s retryable=%s attempt=%s body=%s",
                    self.settings.llm_provider,
                    status,
                    retryable,
                    attempt + 1,
                    body or "(empty)",
                )
                if retryable and attempt < retries:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                raise ProviderUpstreamError("Upstream request failed") from exc
            except httpx.TimeoutException as exc:
                logger.warning(
                    "provider=%s upstream_error timeout attempt=%s",
                    self.settings.llm_provider,
                    attempt + 1,
                )
                if attempt < retries:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                raise ProviderUpstreamError("Upstream request timed out") from exc
            except httpx.HTTPError as exc:
                logger.warning(
                    "provider=%s upstream_error request_failed error=%s",
                    self.settings.llm_provider,
                    exc.__class__.__name__,
                )
                raise ProviderUpstreamError("Upstream request failed") from exc
            except ValueError as exc:
                logger.warning("provider=%s upstream_error invalid_json", self.settings.llm_provider)
                raise ProviderUpstreamError("Upstream returned invalid JSON") from exc

        if data is None:
            raise ProviderUpstreamError("Upstream request failed")
        return data

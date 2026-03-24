from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict], tools: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        """Simple text completion, bypassing action schema.

        Returns (text, prompt_tokens, completion_tokens).
        """
        raise NotImplementedError

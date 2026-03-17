from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, context: str, tools: dict) -> dict:
        raise NotImplementedError

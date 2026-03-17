from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[str, dict[str, Any]], str]
    category: str = "safe"
    risk_level: str = "low"
    requires_confirmation: bool = False

from dataclasses import dataclass


@dataclass
class RunMetrics:
    steps: int
    tool_calls: int
    stop_reason: str

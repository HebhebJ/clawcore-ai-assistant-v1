import math


def estimate_tokens(text: str) -> int:
    # Lightweight fallback estimate for providers that do not return usage.
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))

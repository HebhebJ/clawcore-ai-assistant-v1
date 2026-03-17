import logging
import time

import httpx

from src.core.config import SummarySettings, load_summary_settings
from src.llm.token_counter import estimate_tokens

logger = logging.getLogger(__name__)

_OLLAMA_CONSECUTIVE_FAILURES = 0
_OLLAMA_COOLDOWN_UNTIL = 0.0


def update_summary_text(existing: str, assistant_reply: str, user_message: str = "") -> str:
    text, _ = update_summary(existing, assistant_reply, user_message=user_message)
    return text


def update_summary(existing: str, assistant_reply: str, user_message: str = "") -> tuple[str, dict]:
    settings = load_summary_settings()
    prior = existing.strip()
    user = user_message.strip()
    assistant = assistant_reply.strip()
    meta = {
        "configured_provider": settings.summary_updater_provider,
        "provider_used": "heuristic",
        "fallback_reason": "",
        "compacted": False,
        "token_cap": settings.summary_token_cap,
        "tokens_before": estimate_tokens(prior),
        "tokens_after": estimate_tokens(prior),
    }

    if not user and not assistant:
        return prior, meta

    turn_delta, delta_meta = _build_turn_delta(user, assistant, settings)
    meta["provider_used"] = delta_meta.get("provider_used", "heuristic")
    meta["fallback_reason"] = delta_meta.get("fallback_reason", "")
    updated = _append_delta(prior, turn_delta)

    if estimate_tokens(updated) <= settings.summary_token_cap:
        meta["tokens_after"] = estimate_tokens(updated)
        return updated, meta

    compacted = _compact_summary(updated, settings)
    if not compacted:
        compacted = _heuristic_compact(updated, settings.summary_compact_target_tokens)
    meta["compacted"] = True

    if estimate_tokens(compacted) > settings.summary_token_cap:
        compacted = _hard_trim_to_tokens(compacted, settings.summary_token_cap)
    meta["tokens_after"] = estimate_tokens(compacted)
    return compacted, meta


def _build_turn_delta(user_message: str, assistant_reply: str, settings: SummarySettings) -> tuple[str, dict]:
    reason = ""
    if settings.summary_updater_provider == "ollama":
        prompt = (
            f"Summarize this turn in at most {settings.summary_delta_max_lines} short lines.\n"
            "Keep only durable context: goal, constraints, decisions, open tasks.\n"
            "Output plain lines only.\n\n"
            f"user said: {user_message or '(none)'}\n"
            f"agent answered: {assistant_reply or '(none)'}\n"
        )
        ai, reason = _try_ollama(prompt, settings)
        if ai:
            return _normalize_lines(ai, max_lines=settings.summary_delta_max_lines), {
                "provider_used": "ollama",
                "fallback_reason": "",
            }

    return (
        _heuristic_turn_delta(
            user_message=user_message,
            assistant_reply=assistant_reply,
            max_lines=settings.summary_delta_max_lines,
        ),
        {
            "provider_used": "heuristic",
            "fallback_reason": reason if settings.summary_updater_provider == "ollama" else "",
        },
    )


def _append_delta(existing: str, delta: str) -> str:
    if not delta.strip():
        return existing
    if not existing:
        return delta.strip()
    return (existing.rstrip() + "\n" + delta.strip()).strip()


def _compact_summary(summary_text: str, settings: SummarySettings) -> str:
    if settings.summary_updater_provider != "ollama":
        return ""
    prompt = (
        "Rewrite this running summary to be shorter while preserving durable context.\n"
        "Keep goals, constraints, decisions, open tasks, and stable user/project facts.\n"
        "Drop repetition and chatter.\n"
        f"Target around {settings.summary_compact_target_tokens} tokens.\n"
        "Output plain lines only.\n\n"
        f"current summary:\n{summary_text}\n"
    )
    ai, _reason = _try_ollama(prompt, settings)
    if not ai:
        return ""
    # Keep enough room under cap for subsequent appended turns.
    target = max(120, min(settings.summary_compact_target_tokens, settings.summary_token_cap - 120))
    compacted = _normalize_lines(ai, max_lines=18)
    if estimate_tokens(compacted) > target:
        compacted = _hard_trim_to_tokens(compacted, target)
    return compacted


def _try_ollama(prompt: str, settings: SummarySettings) -> tuple[str, str]:
    global _OLLAMA_CONSECUTIVE_FAILURES
    global _OLLAMA_COOLDOWN_UNTIL
    now = time.monotonic()
    if now < _OLLAMA_COOLDOWN_UNTIL:
        return "", "cooldown"

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": settings.ollama_summary_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": settings.summary_temperature},
    }

    try:
        with httpx.Client(timeout=settings.summary_timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        _OLLAMA_CONSECUTIVE_FAILURES += 1
        logger.warning("summary updater ollama unavailable, using heuristic fallback: %s", exc)
        if _OLLAMA_CONSECUTIVE_FAILURES >= settings.summary_ollama_max_failures:
            _OLLAMA_COOLDOWN_UNTIL = now + settings.summary_ollama_cooldown_seconds
            logger.warning(
                "summary updater entering cooldown for %.1fs after %d consecutive failures",
                settings.summary_ollama_cooldown_seconds,
                _OLLAMA_CONSECUTIVE_FAILURES,
            )
        return "", "timeout"
    except httpx.HTTPStatusError as exc:
        _OLLAMA_CONSECUTIVE_FAILURES += 1
        logger.warning("summary updater ollama unavailable, using heuristic fallback: %s", exc)
        if _OLLAMA_CONSECUTIVE_FAILURES >= settings.summary_ollama_max_failures:
            _OLLAMA_COOLDOWN_UNTIL = now + settings.summary_ollama_cooldown_seconds
            logger.warning(
                "summary updater entering cooldown for %.1fs after %d consecutive failures",
                settings.summary_ollama_cooldown_seconds,
                _OLLAMA_CONSECUTIVE_FAILURES,
            )
        return "", f"http_{exc.response.status_code}"
    except Exception as exc:  # noqa: BLE001
        _OLLAMA_CONSECUTIVE_FAILURES += 1
        logger.warning("summary updater ollama unavailable, using heuristic fallback: %s", exc)
        if _OLLAMA_CONSECUTIVE_FAILURES >= settings.summary_ollama_max_failures:
            _OLLAMA_COOLDOWN_UNTIL = now + settings.summary_ollama_cooldown_seconds
            logger.warning(
                "summary updater entering cooldown for %.1fs after %d consecutive failures",
                settings.summary_ollama_cooldown_seconds,
                _OLLAMA_CONSECUTIVE_FAILURES,
            )
        return "", "error"

    content = data.get("response", "")
    _OLLAMA_CONSECUTIVE_FAILURES = 0
    _OLLAMA_COOLDOWN_UNTIL = 0.0
    return str(content).strip(), ""


def _heuristic_turn_delta(user_message: str, assistant_reply: str, max_lines: int) -> str:
    lines: list[str] = []
    if user_message:
        lines.append(f"- User asked: {_clip_line(user_message, 180)}")
    if assistant_reply:
        lines.append(f"- Assistant answer: {_clip_line(assistant_reply, 180)}")

    if user_message and "?" in user_message and assistant_reply:
        lines.append("- Open item reviewed in this turn.")

    return "\n".join(lines[:max_lines])


def _heuristic_compact(text: str, target_tokens: int) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""

    # Keep recency bias while removing duplicates by normalized content.
    seen: set[str] = set()
    deduped: list[str] = []
    for line in reversed(lines):
        normalized = line.lower().lstrip("-").strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(line)
    deduped.reverse()

    compacted = "\n".join(deduped)
    if estimate_tokens(compacted) > target_tokens:
        compacted = _hard_trim_to_tokens(compacted, target_tokens)
    return compacted


def _normalize_lines(text: str, max_lines: int) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line:
            continue
        out.append(f"- {_clip_line(line, 180)}")
        if len(out) >= max_lines:
            break
    return "\n".join(out)


def _clip_line(text: str, max_chars: int) -> str:
    value = " ".join(text.strip().split())
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def _hard_trim_to_tokens(text: str, token_limit: int) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""

    selected: list[str] = []
    for line in reversed(lines):
        candidate = "\n".join(reversed([line] + selected))
        if estimate_tokens(candidate) > token_limit and selected:
            break
        selected.append(line)
    return "\n".join(reversed(selected))

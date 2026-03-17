import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class WorkspaceToolConfig:
    def __init__(
        self,
        enabled_tools: list[str] | None = None,
        disabled_tools: list[str] | None = None,
        enabled_skills: list[str] | None = None,
    ) -> None:
        self.enabled_tools = enabled_tools or []
        self.disabled_tools = disabled_tools or []
        self.enabled_skills = enabled_skills or []


class ToolPolicy:
    def __init__(self, allow_tools: list[str] | None = None, deny_tools: list[str] | None = None) -> None:
        self.allow_tools = allow_tools or []
        self.deny_tools = deny_tools or []


def load_workspace_tool_config(workspace_path: str) -> WorkspaceToolConfig | None:
    config_path = Path(workspace_path) / "skills" / "enabled.json"
    if not config_path.exists():
        return None

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}") from exc

    enabled = payload.get("enabled_tools", [])
    disabled = payload.get("disabled_tools", [])
    enabled_skills = payload.get("enabled_skills", [])

    if not isinstance(enabled, list) or not all(isinstance(x, str) for x in enabled):
        raise ValueError("skills/enabled.json: enabled_tools must be a list of strings")
    if not isinstance(disabled, list) or not all(isinstance(x, str) for x in disabled):
        raise ValueError("skills/enabled.json: disabled_tools must be a list of strings")
    if not isinstance(enabled_skills, list) or not all(isinstance(x, str) for x in enabled_skills):
        raise ValueError("skills/enabled.json: enabled_skills must be a list of strings")

    return WorkspaceToolConfig(
        enabled_tools=enabled,
        disabled_tools=disabled,
        enabled_skills=enabled_skills,
    )


def parse_tools_policy(tools_md: str) -> ToolPolicy:
    allow: list[str] = []
    deny: list[str] = []

    for raw in tools_md.splitlines():
        line = raw.strip()
        if not line:
            continue

        lower = line.lower()
        if lower.startswith("allow:"):
            values = line.split(":", 1)[1]
            allow.extend(_parse_tool_list(values))
        elif lower.startswith("deny:"):
            values = line.split(":", 1)[1]
            deny.extend(_parse_tool_list(values))

    return ToolPolicy(allow_tools=_dedupe(allow), deny_tools=_dedupe(deny))


def resolve_effective_tools(global_tools: dict, workspace_config: WorkspaceToolConfig | None, policy: ToolPolicy) -> dict:
    available_names = set(global_tools.keys())

    if workspace_config is None:
        current = set(available_names)
    else:
        if workspace_config.enabled_tools:
            current = set(_known_or_warn(workspace_config.enabled_tools, available_names, "enabled.json enabled_tools"))
        else:
            current = set(available_names)

        disabled = set(_known_or_warn(workspace_config.disabled_tools, available_names, "enabled.json disabled_tools"))
        current -= disabled

    if policy.allow_tools:
        allowed = set(_known_or_warn(policy.allow_tools, available_names, "TOOLS.md allow"))
        current &= allowed

    if policy.deny_tools:
        denied = set(_known_or_warn(policy.deny_tools, available_names, "TOOLS.md deny"))
        current -= denied

    return {name: global_tools[name] for name in global_tools.keys() if name in current}


def merge_tool_policies(*policies: ToolPolicy) -> ToolPolicy:
    allow: list[str] = []
    deny: list[str] = []
    for policy in policies:
        allow.extend(policy.allow_tools)
        deny.extend(policy.deny_tools)
    return ToolPolicy(allow_tools=_dedupe(allow), deny_tools=_dedupe(deny))


def _parse_tool_list(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _known_or_warn(names: list[str], available: set[str], source: str) -> list[str]:
    out: list[str] = []
    for name in names:
        if name in available:
            out.append(name)
        else:
            logger.warning("Skipping unknown tool '%s' from %s", name, source)
    return out

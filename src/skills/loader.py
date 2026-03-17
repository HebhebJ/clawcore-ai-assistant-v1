import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillDefinition:
    name: str
    description: str
    instructions: str
    enabled_tools: list[str]
    disabled_tools: list[str]
    allow_tools: list[str]
    deny_tools: list[str]


def load_active_skills(workspace_path: str, enabled_skills: list[str]) -> list[SkillDefinition]:
    if not enabled_skills:
        return []

    skills_root = Path(workspace_path) / "skills"
    active: list[SkillDefinition] = []
    for skill_name in enabled_skills:
        skill_dir = skills_root / skill_name
        if not skill_dir.exists() or not skill_dir.is_dir():
            logger.warning("Enabled skill '%s' not found at %s", skill_name, skill_dir)
            continue

        try:
            active.append(_load_skill(skill_dir))
        except ValueError as exc:
            logger.warning("Skipping invalid skill '%s': %s", skill_name, exc)

    return active


def render_skill_instructions(skills: list[SkillDefinition]) -> str:
    if not skills:
        return ""

    lines: list[str] = []
    for skill in skills:
        lines.append(f"## {skill.name}")
        if skill.description:
            lines.append(skill.description)
        if skill.instructions:
            lines.append(skill.instructions)
    return "\n".join(lines).strip()


def collect_skill_tool_overrides(skills: list[SkillDefinition]) -> dict[str, list[str]]:
    enabled: list[str] = []
    disabled: list[str] = []
    allow: list[str] = []
    deny: list[str] = []

    for skill in skills:
        enabled.extend(skill.enabled_tools)
        disabled.extend(skill.disabled_tools)
        allow.extend(skill.allow_tools)
        deny.extend(skill.deny_tools)

    return {
        "enabled_tools": _dedupe(enabled),
        "disabled_tools": _dedupe(disabled),
        "allow_tools": _dedupe(allow),
        "deny_tools": _dedupe(deny),
    }


def _load_skill(skill_dir: Path) -> SkillDefinition:
    manifest_path = skill_dir / "skill.json"
    if not manifest_path.exists():
        raise ValueError("missing skill.json")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid skill.json") from exc

    name = str(payload.get("name") or skill_dir.name).strip()
    description = str(payload.get("description") or "").strip()

    enabled_tools = _read_str_list(payload, "enabled_tools")
    disabled_tools = _read_str_list(payload, "disabled_tools")
    allow_tools = _read_str_list(payload, "allow_tools")
    deny_tools = _read_str_list(payload, "deny_tools")

    skill_md = skill_dir / "SKILL.md"
    instructions = skill_md.read_text(encoding="utf-8").strip() if skill_md.exists() else ""

    return SkillDefinition(
        name=name,
        description=description,
        instructions=instructions,
        enabled_tools=enabled_tools,
        disabled_tools=disabled_tools,
        allow_tools=allow_tools,
        deny_tools=deny_tools,
    )


def _read_str_list(payload: dict, key: str) -> list[str]:
    values = payload.get(key, [])
    if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
        raise ValueError(f"skill.json {key} must be a list of strings")
    return [v.strip() for v in values if v.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

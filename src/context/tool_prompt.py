def render_tools(tools: dict) -> str:
    lines = []
    for name, tool in tools.items():
        lines.append(f"- {name}: {tool.description}")
    return "\n".join(lines)

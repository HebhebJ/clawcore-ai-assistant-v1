from pathlib import Path


def _safe_path(workspace_path: str, user_path: str) -> Path:
    base = Path(workspace_path).resolve()
    candidate = (base / user_path).resolve()
    if not str(candidate).startswith(str(base)):
        raise ValueError("Path escapes workspace")
    return candidate


def list_files(workspace_path: str, params: dict) -> str:
    target = _safe_path(workspace_path, params.get("path", "."))
    if not target.exists() or not target.is_dir():
        raise ValueError("Directory not found")
    return "\n".join(sorted([p.name for p in target.iterdir()]))


def read_file(workspace_path: str, params: dict) -> str:
    target = _safe_path(workspace_path, params.get("path", ""))
    max_chars = int(params.get("max_chars", 4000))
    if not target.exists() or not target.is_file():
        raise ValueError("File not found")
    return target.read_text(encoding="utf-8")[:max_chars]

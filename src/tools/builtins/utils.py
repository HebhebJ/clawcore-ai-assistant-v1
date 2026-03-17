from datetime import datetime, timezone


def get_datetime(_workspace_path: str, _params: dict) -> str:
    return datetime.now(timezone.utc).isoformat()

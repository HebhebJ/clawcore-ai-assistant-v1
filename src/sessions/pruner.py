import logging
import shutil
from datetime import datetime, timedelta, timezone

from src.core.config import WORKSPACES_DIR

logger = logging.getLogger(__name__)


def prune_sessions(workspace_id: str, max_age_days: int) -> dict:
    sessions_dir = WORKSPACES_DIR / workspace_id / "sessions"
    if not sessions_dir.exists():
        return {"pruned": 0, "kept": 0, "workspace_id": workspace_id}

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    pruned = 0
    kept = 0

    for session_dir in sorted(sessions_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        # Use transcript mtime as the activity timestamp; fall back to dir mtime
        transcript = session_dir / "transcript.jsonl"
        check = transcript if transcript.exists() else session_dir
        mtime = datetime.fromtimestamp(check.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            shutil.rmtree(session_dir)
            logger.info("pruned session workspace=%s session=%s last_active=%s", workspace_id, session_dir.name, mtime.date())
            pruned += 1
        else:
            kept += 1

    return {"pruned": pruned, "kept": kept, "workspace_id": workspace_id}

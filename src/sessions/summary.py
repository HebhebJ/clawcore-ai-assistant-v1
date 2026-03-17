def update_summary_text(existing: str, assistant_reply: str) -> str:
    existing = existing.strip()
    addition = assistant_reply.strip()
    if not addition:
        return existing
    if not existing:
        return addition[:2000]
    return (existing + "\n- " + addition)[:4000]

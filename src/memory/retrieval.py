from src.core.config import load_memory_retrieval_mode
from src.memory.store import MemoryStore
from src.memory.vector_index import VectorMemoryIndex


class MemoryRetrieval:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.vector_index = VectorMemoryIndex()
        self.mode = load_memory_retrieval_mode()

    def retrieve(self, workspace_id: str, query: str) -> list[str]:
        rows = self.store.load_all(workspace_id)
        if not rows:
            return []

        keyword_items = self._retrieve_keyword(rows, query)
        if self.mode == "keyword":
            return keyword_items

        vector_items = self.vector_index.search(workspace_id=workspace_id, query=query, rows=rows, top_k=6)
        if self.mode == "vector":
            return vector_items or keyword_items

        # Hybrid mode: prefer semantic vector ordering then fill with keyword hits.
        if not vector_items:
            return keyword_items
        merged: list[str] = []
        seen: set[str] = set()
        for item in vector_items + keyword_items:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
            if len(merged) >= 6:
                break
        return merged

    def _retrieve_keyword(self, rows: list[dict], query: str) -> list[str]:
        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[int, str]] = []
        for row in rows:
            content = str(row.get("content", ""))
            if not content:
                continue
            low = content.lower()

            if not tokens:
                score = 1
            else:
                score = sum(1 for token in tokens if token in low)
                if score == 0:
                    continue

            category = str(row.get("type", ""))
            if category == "user_preference":
                score += 1

            scored.append((score, f"[{category}] {content}" if category else content))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:6]]

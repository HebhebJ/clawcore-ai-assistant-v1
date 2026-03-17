import hashlib
import json
import math
import re
from pathlib import Path

from src.core.config import WORKSPACES_DIR

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_EMBED_DIM = 192


def _tokenize_for_embedding(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    features: list[str] = []
    for token in tokens:
        features.append(token)
        # Add character trigrams so close forms (python/pythonic) remain similar.
        if len(token) >= 4:
            for idx in range(len(token) - 2):
                features.append(token[idx : idx + 3])
    return features


def _embed_text(text: str, dim: int = _EMBED_DIM) -> list[float]:
    vector = [0.0] * dim
    for feature in _tokenize_for_embedding(text):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        slot = int.from_bytes(digest[:4], byteorder="little", signed=False) % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[slot] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 1e-12:
        return vector
    return [value / norm for value in vector]


def _dot(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class VectorMemoryIndex:
    def _memory_dir(self, workspace_id: str) -> Path:
        return WORKSPACES_DIR / workspace_id / "memory"

    def _index_path(self, workspace_id: str) -> Path:
        return self._memory_dir(workspace_id) / "embeddings.jsonl"

    def memory_key(self, row: dict) -> str:
        category = str(row.get("type", "")).strip()
        content = str(row.get("content", "")).strip()
        raw = f"{category}|{content}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()

    def append_memory(self, workspace_id: str, row: dict) -> None:
        content = str(row.get("content", "")).strip()
        if not content:
            return
        path = self._index_path(workspace_id)
        existing = self._load_index(workspace_id)
        key = self.memory_key(row)
        if key in existing:
            return

        payload = {
            "key": key,
            "type": str(row.get("type", "")).strip(),
            "content": content,
            "vector": _embed_text(content),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    def ensure_index(self, workspace_id: str, rows: list[dict]) -> dict[str, dict]:
        existing = self._load_index(workspace_id)
        for row in rows:
            key = self.memory_key(row)
            if key in existing:
                continue
            self.append_memory(workspace_id, row)
            existing[key] = {
                "type": str(row.get("type", "")).strip(),
                "content": str(row.get("content", "")).strip(),
                "vector": _embed_text(str(row.get("content", ""))),
            }
        return existing

    def search(self, workspace_id: str, query: str, rows: list[dict], top_k: int = 6) -> list[str]:
        if not rows or not query.strip():
            return []
        query_vector = _embed_text(query)
        if max((abs(v) for v in query_vector), default=0.0) <= 1e-12:
            return []

        indexed = self.ensure_index(workspace_id, rows)
        scored: list[tuple[float, str]] = []
        for row in rows:
            content = str(row.get("content", "")).strip()
            if not content:
                continue

            key = self.memory_key(row)
            vector = indexed.get(key, {}).get("vector", [])
            if not isinstance(vector, list):
                continue

            similarity = _dot(query_vector, vector)
            if similarity < 0.12:
                continue

            importance_raw = row.get("importance", 0.6)
            try:
                importance = float(importance_raw)
            except (TypeError, ValueError):
                importance = 0.6
            importance = max(0.0, min(1.0, importance))
            score = similarity + (0.06 * importance)

            category = str(row.get("type", "")).strip()
            if category == "user_preference":
                score += 0.03
            label = f"[{category}] {content}" if category else content
            scored.append((score, label))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def _load_index(self, workspace_id: str) -> dict[str, dict]:
        path = self._index_path(workspace_id)
        if not path.exists():
            return {}

        items: dict[str, dict] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(row.get("key", "")).strip()
            vector = row.get("vector", [])
            if not key or not isinstance(vector, list):
                continue
            items[key] = row
        return items


import json
import time
from pathlib import Path


class Memory:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def remember(self, text: str):
        items = json.loads(self.path.read_text(encoding="utf-8"))
        items.append({"text": text, "time": time.time()})
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def search(self, query: str, limit=8):
        query_lower = query.lower()
        items = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            item for item in reversed(items) if query_lower in item["text"].lower()
        ][:limit]

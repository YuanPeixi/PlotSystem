from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class JsonStorage:
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.file_path.exists():
            self.save({"projects": {}, "meta": {}})

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.file_path.exists():
                return {"projects": {}, "meta": {}}
            return json.loads(self.file_path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

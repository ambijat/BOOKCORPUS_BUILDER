from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ..models import RunRecord
from .common import atomic_write_json, read_json


class HistoryService:
    def __init__(self, history_dir: Path):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: RunRecord) -> None:
        atomic_write_json(self.history_dir / f"{record.run_id}.json", asdict(record))

    def records(self, book_id: str | None = None) -> list[RunRecord]:
        result = []
        for path in self.history_dir.glob("*.json"):
            value = read_json(path)
            if value and (book_id is None or value.get("book_id") == book_id):
                result.append(RunRecord(**value))
        return sorted(result, key=lambda item: item.started_at, reverse=True)

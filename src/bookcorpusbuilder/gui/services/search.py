from __future__ import annotations

import json
from pathlib import Path


class CorpusSearchService:
    def __init__(self, output_root: Path):
        self.output_root = output_root

    def search(self, query: str, book_id: str | None = None, run_id: str | None = None,
               kind: str | None = None, printed_from: int | None = None,
               printed_to: int | None = None) -> list[dict]:
        needle = query.casefold().strip()
        results = []
        pattern = f"runs/{run_id}/jsonl/*.jsonl" if run_id else "runs/*/jsonl/*.jsonl"
        for path in self.output_root.glob(pattern):
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if book_id and item.get("book_id") != book_id:
                    continue
                if kind and item.get("kind") != kind:
                    continue
                printed = item.get("printed_start")
                if printed_from is not None and (printed is None or printed < printed_from):
                    continue
                if printed_to is not None and (printed is None or printed > printed_to):
                    continue
                haystack = f"{item.get('title', '')}\n{item.get('text', '')}"
                position = haystack.casefold().find(needle) if needle else 0
                if position < 0:
                    continue
                start = max(0, position - 80)
                item["snippet"] = haystack[start:position + max(len(query), 1) + 120].replace("\n", " ")
                item["jsonl_path"] = str(path)
                section_dir = path.parents[1] / "sections" / item.get("book_id", "")
                matches = list(section_dir.glob(f"{int(item.get('sno', 0)):03d}_*.txt"))
                item["txt_path"] = str(matches[0]) if matches else ""
                results.append(item)
        return results

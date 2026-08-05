from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from threading import Event
from typing import Callable

from ... import __version__
from ...extract import slugify
from ..models import BookRecord, ExtractionResult, OutlineEntry, PageMapping, RunRecord, Severity
from .common import sha256_file, sha256_json, utc_now
from .history import HistoryService
from .mapping import MappingService
from .outlines import OutlineService
from .validation import preflight


class ExtractionService:
    def __init__(self, output_root: Path, history: HistoryService, outlines: OutlineService, mappings: MappingService):
        self.output_root = output_root
        self.history = history
        self.outlines = outlines
        self.mappings = mappings

    def dry_run(self, book: BookRecord, entries: list[OutlineEntry], approval: object, mapping: PageMapping):
        return preflight(book, entries, approval, mapping, self.outlines, self.mappings)

    def run(
        self,
        book: BookRecord,
        entries: list[OutlineEntry],
        approval: object,
        mapping: PageMapping,
        min_chars: int = 1,
        cancel: Event | None = None,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> ExtractionResult:
        issues = self.dry_run(book, entries, approval, mapping)
        if any(item.severity == Severity.BLOCKING for item in issues):
            raise ValueError("Extraction blocked: " + "; ".join(item.message for item in issues if item.severity == Severity.BLOCKING))
        cancel = cancel or Event()
        included = [entry for entry in entries if entry.include]
        run_id = f"{utc_now()[:10].replace('-', '')}-{uuid.uuid4().hex[:12]}"
        started = utc_now()
        runs_dir = self.output_root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}-", dir=runs_dir))
        final = runs_dir / run_id
        written = skipped = failed = 0
        status = "running"
        error = ""
        try:
            section_dir = temporary / "sections" / book.book_id
            jsonl_dir = temporary / "jsonl"
            manifest_dir = temporary / "manifests"
            section_dir.mkdir(parents=True)
            jsonl_dir.mkdir()
            manifest_dir.mkdir()
            jsonl_path = jsonl_dir / f"{book.book_id}_sections.jsonl"
            manifest_path = manifest_dir / f"{book.book_id}_manifest.csv"
            mapped = [(entry, mapping.resolve_entry(entry).physical_page) for entry in included]
            rows: list[dict] = []
            import pdfplumber

            with pdfplumber.open(book.path) as pdf, jsonl_path.open("w", encoding="utf-8") as jsonl_handle:
                for index, (entry, start) in enumerate(mapped):
                    if cancel.is_set():
                        status = "cancelled"
                        break
                    next_starts = [value for _, value in mapped[index + 1:] if value and value > (start or 0)]
                    end = (next_starts[0] - 1) if next_starts else len(pdf.pages)
                    texts = []
                    for page_number in range(int(start), end + 1):
                        text = (pdf.pages[page_number - 1].extract_text() or "").strip()
                        if text:
                            texts.append(text)
                    text = "\n\n".join(texts)
                    if len(text) < min_chars:
                        skipped += 1
                        if progress:
                            progress(index + 1, len(included), f"Skipped: {entry.title}")
                        continue
                    txt_path = section_dir / f"{entry.sno:03d}_{slugify(entry.title)}.txt"
                    txt_path.write_text(text + "\n", encoding="utf-8")
                    record = {
                        "book_id": book.book_id, "pdf": book.filename, "sno": entry.sno,
                        "title": entry.title, "kind": entry.kind,
                        "printed_start": entry.printed_start,
                        "printed_end": ((included[index + 1].printed_start - 1) if index + 1 < len(included) and included[index + 1].printed_start and included[index + 1].printed_start > (entry.printed_start or 0) else entry.printed_start + (end - int(start))),
                        "physical_start": start, "physical_end": end,
                        "pdf_page_index": int(start) - 1, "source_pdf_hash": book.source_hash,
                        "run_id": run_id, "text": text,
                    }
                    jsonl_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    rows.append({key: value for key, value in record.items() if key != "text"} | {
                        "txt_path": f"sections/{book.book_id}/{txt_path.name}", "chars": len(text)
                    })
                    written += 1
                    if progress:
                        progress(index + 1, len(included), entry.title)
            if status == "cancelled":
                shutil.rmtree(temporary)
            else:
                with manifest_path.open("w", encoding="utf-8", newline="") as handle:
                    fieldnames = list(rows[0]) if rows else ["book_id", "pdf", "sno", "title", "kind", "printed_start", "printed_end", "physical_start", "physical_end", "pdf_page_index", "source_pdf_hash", "run_id", "txt_path", "chars"]
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                if final.exists():
                    raise FileExistsError(f"Run output already exists: {final}")
                os.replace(temporary, final)
                status = "completed"
        except Exception as exc:
            status = "failed"
            failed += 1
            error = str(exc)
            if temporary.exists():
                shutil.rmtree(temporary)
        completed = utc_now()
        _, clean, _ = self.outlines.paths(book.book_id)
        record = RunRecord(
            run_id, started, completed, status, book.book_id, sha256_file(book.path),
            sha256_file(clean) if clean.exists() else "", sha256_json(mapping.to_dict()),
            __version__, len(included), written, skipped, failed,
            str(final.resolve()) if status == "completed" else "", error,
        )
        self.history.save(record)
        if status == "failed":
            raise RuntimeError(error)
        return ExtractionResult(record, issues)

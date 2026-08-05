from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ...outline import RE_TOC_HEADER, RE_TOC_LINE, normalize_title


@dataclass
class CandidatePage:
    physical_page_number: int
    pdf_page_index: int
    source: str
    confidence: float
    raw_text: str


class TocIndexService:
    def scan(self, pdf_path: Path, early_pages: int = 12, late_pages: int = 12) -> list[CandidatePage]:
        import pdfplumber

        candidates = []
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            indices = list(range(min(early_pages, total))) + list(range(max(0, total - late_pages), total))
            for index in sorted(set(indices)):
                text = pdf.pages[index].extract_text() or ""
                lower = text.casefold()
                source = "toc" if index < early_pages and RE_TOC_HEADER.search(text) else "index" if index >= total - late_pages and ("index" in lower or self._looks_like_index(text)) else ""
                if source:
                    confidence = 0.9 if source == "toc" and RE_TOC_HEADER.search(text) else 0.65
                    candidates.append(CandidatePage(index + 1, index, source, confidence, text))
        return candidates

    def parse_toc(self, pages: list[CandidatePage]):
        rows = []
        for page in pages:
            if page.source != "toc":
                continue
            for line in page.raw_text.splitlines():
                match = RE_TOC_LINE.match(normalize_title(line))
                if match:
                    rows.append({"title": normalize_title(match.group("title")), "printed_start": int(match.group("page")), "source": "toc"})
        return rows

    def parse_index(self, pages: list[CandidatePage]):
        rows = []
        for page in pages:
            if page.source != "index":
                continue
            for line in page.raw_text.splitlines():
                clean = normalize_title(line)
                if "," not in clean or not any(character.isdigit() for character in clean):
                    continue
                term, references = clean.split(",", 1)
                page_numbers = [int(token) for token in references.replace("–", "-").replace("-", " ").replace(",", " ").split() if token.isdigit()]
                if term.strip() and page_numbers:
                    rows.append({"term": term.strip(), "printed_pages": "|".join(map(str, page_numbers)), "source": "index"})
        return rows

    def export_raw(self, pages: list[CandidatePage], destination: Path, source: str) -> None:
        destination.write_text("\n\n".join(f"--- Physical page {p.physical_page_number} ---\n{p.raw_text}" for p in pages if p.source == source), encoding="utf-8")

    def export_entries(self, rows: list[dict], destination: Path) -> None:
        with destination.open("w", encoding="utf-8", newline="") as handle:
            fieldnames = sorted({key for row in rows for key in row}) if rows else ["title", "printed_start", "source"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _looks_like_index(text: str) -> bool:
        lines = [line for line in text.splitlines() if line.strip()]
        comma_pages = sum(1 for line in lines if "," in line and any(char.isdigit() for char in line[-20:]))
        return len(lines) >= 8 and comma_pages / len(lines) >= 0.35

#!/usr/bin/env python3
"""
Stage 2: Extract section chunks from PDF using a clean outline CSV.

Project layout (relative to the repository):
  BOOKCORPUSBUILDER/
    data/input/pdfs/          <- PDFs
    data/work/outlines/       <- outline CSVs (Sno,title,printed_start)
    data/output/sections/     <- per-section TXT outputs
    data/output/jsonl/        <- JSONL outputs
    data/output/manifests/    <- manifest CSV outputs

Default behavior:
- For each row in outline CSV, compute printed_end as (next DISTINCT printed_start - 1).
- Resolve start/end to physical PDF pages through an operator-approved page mapping
  (see gui/models/domain.py::PageMapping) — this stage refuses to run without one.
- Extract text from the resolved physical start..end (inclusive) using pdfplumber.
- Write per-section TXT + one JSONL + manifest CSV.

Notes:
- If multiple rows share the same printed_start (hierarchy), they will extract the same range
  unless the next distinct start differs. This is correct for “structural” headings.
  If you want to skip “structural-only” headings later, you can filter by title patterns.
"""

from __future__ import annotations

import re
import csv
import json
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .gui.models import PageMapping
from .gui.services.common import sha256_file, stable_book_id
from .gui.services.mapping import MappingService
from .paths import INPUT_PDF_DIR, OUTLINE_DIR, OUTPUT_DIR, PROJECT_ROOT


@dataclass
class Row:
    sno: int
    title: str
    start: int
    end: int = 0  # computed later, same coordinate space as `start`
    already_physical: bool = False  # True when `start`/`end` came from a physical_start column
    physical_start: int = 0  # resolved by resolve_physical_pages()
    physical_end: int = 0


@dataclass
class UnresolvedRow:
    row: Row
    reason: str


def ensure_dirs(*directories: Path) -> None:
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)


def slugify(s: str, max_len: int = 80) -> str:
    s = s.strip().lower()
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\[[^\]]+\]\s*", "", s)  # remove [MAP] etc from filename
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "section"
    return s[:max_len]


def read_outline_csv(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        fields = set(rdr.fieldnames or [])
        if "Sno" not in fields or "title" not in fields or not ({"printed_start", "physical_start"} & fields):
            raise ValueError(
                f"CSV must contain 'Sno', 'title', and at least one of 'printed_start'/'physical_start'. "
                f"Found: {rdr.fieldnames}"
            )

        for r in rdr:
            try:
                sno = int(str(r["Sno"]).strip())
                title = str(r["title"]).strip()
                printed_raw = str(r.get("printed_start") or "").strip()
                physical_raw = str(r.get("physical_start") or "").strip()
            except Exception as e:
                raise ValueError(f"Bad row in CSV: {r}") from e

            if printed_raw:
                start, already_physical = int(printed_raw), False
            elif physical_raw:
                start, already_physical = int(physical_raw), True
            else:
                continue

            if title and start >= 1:
                rows.append(Row(sno=sno, title=title, start=start, already_physical=already_physical))

    rows.sort(key=lambda x: x.sno)
    return rows


def resolve_physical_pages(rows: List[Row], mapping: PageMapping) -> List[UnresolvedRow]:
    """Fill in row.physical_start/physical_end via the verified PageMapping.

    Rows sourced from a physical_start column are already physical and pass through
    unchanged. Rows sourced from printed_start are resolved through
    mapping.physical_for(), which returns None when the page cannot be verified
    (see PageMapping.resolve() for the specific reason). Returns the rows that
    could not be resolved instead of silently extracting the wrong page.
    """
    unresolved: List[UnresolvedRow] = []
    for r in rows:
        if r.already_physical:
            r.physical_start, r.physical_end = r.start, r.end
            continue
        start = mapping.physical_for(r.start)
        end = mapping.physical_for(r.end)
        if start is None or end is None:
            bad_page = r.start if start is None else r.end
            unresolved.append(UnresolvedRow(r, mapping.resolve(bad_page).detail))
            continue
        r.physical_start, r.physical_end = start, end
    return unresolved


def compute_page_ranges(rows: List[Row], max_page: int) -> List[Row]:
    """
    printed_end = (next DISTINCT printed_start) - 1
    If no next distinct start, end = max_page.
    """
    starts = [r.start for r in rows]

    for i, r in enumerate(rows):
        nxt_distinct: Optional[int] = None
        for j in range(i + 1, len(rows)):
            if rows[j].start > r.start:
                nxt_distinct = rows[j].start
                break

        if nxt_distinct is None:
            r.end = max_page
        else:
            r.end = max(r.start, nxt_distinct - 1)

    return rows


def extract_text_pages(pdf_path: Path, start_page: int, end_page: int) -> str:
    """
    Extract text from inclusive page range using pdfplumber.
    start_page/end_page must already be resolved *physical* PDF page numbers
    (see resolve_physical_pages) — callers must not pass raw printed page numbers.
    """
    import pdfplumber

    texts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        max_page = len(pdf.pages)
        s = max(1, min(start_page, max_page))
        e = max(1, min(end_page, max_page))
        if e < s:
            e = s

        for p in range(s - 1, e):
            t = pdf.pages[p].extract_text() or ""
            t = t.strip()
            if t:
                texts.append(t)

    return "\n\n".join(texts).strip()


def infer_pdf_from_outline(outline_csv: Path) -> Optional[Path]:
    """
    Try to map 'chapter1_outline_clean.csv' -> 'chapter1.pdf' in PDF_DIR.
    """
    name = outline_csv.stem
    # strip common suffixes
    base = re.sub(r"(_outline(_clean)?|_contents|_toc|_index)$", "", name, flags=re.I)
    candidate = INPUT_PDF_DIR / f"{base}.pdf"
    return candidate if candidate.exists() else None


def main():
    ap = argparse.ArgumentParser(description="Stage 2: Extract section chunks from PDF using clean outline CSV.")
    ap.add_argument(
        "--outline",
        type=Path,
        default=OUTLINE_DIR / "chapter1_outline_clean.csv",
        help=f"Path to outline CSV (default: {OUTLINE_DIR / 'chapter1_outline_clean.csv'})",
    )
    ap.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help=f"Optional PDF path. If omitted, inferred inside {INPUT_PDF_DIR}",
    )
    ap.add_argument(
        "--min_chars",
        type=int,
        default=1,
        help="Drop extracted chunks shorter than this many characters (default: 1).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output root containing sections/jsonl/manifests (default: {OUTPUT_DIR})",
    )

    args = ap.parse_args()
    section_dir = args.out / "sections"
    jsonl_dir = args.out / "jsonl"
    manifest_dir = args.out / "manifests"
    ensure_dirs(OUTLINE_DIR, section_dir, jsonl_dir, manifest_dir)

    import pdfplumber

    outline_csv: Path = args.outline
    if not outline_csv.exists():
        raise FileNotFoundError(f"Outline CSV not found: {outline_csv}")

    pdf_path: Optional[Path] = args.pdf
    if pdf_path is None:
        pdf_path = infer_pdf_from_outline(outline_csv)
    if pdf_path is None or not Path(pdf_path).exists():
        raise FileNotFoundError(
            f"PDF not found. Place it in {INPUT_PDF_DIR} with the same base name as the outline CSV "
            "or pass --pdf /full/path/to/file.pdf"
        )
    pdf_path = Path(pdf_path)

    # Refuse to run without an operator-approved page mapping for this PDF —
    # closes audit finding C1 (printed and physical pages silently treated as
    # identical). See gui/models/domain.py::PageMapping and the Alignment screen.
    book_id = stable_book_id(sha256_file(pdf_path))
    mapping_service = MappingService(OUTLINE_DIR)
    mapping = mapping_service.load(book_id)
    if not mapping.approved:
        raise SystemExit(
            f"Refusing to extract: no approved page mapping for {pdf_path.name} (book_id={book_id}).\n"
            f"Open this book in the GUI's Alignment screen, verify anchors, and approve the mapping first.\n"
            f"Expected mapping file: {mapping_service.path(book_id)}"
        )

    # Read outline
    rows = read_outline_csv(outline_csv)

    # Get max pages
    with pdfplumber.open(str(pdf_path)) as pdf:
        max_page = len(pdf.pages)

    # Compute ranges (still in each row's own printed/physical coordinate space)
    rows = compute_page_ranges(rows, max_page=max_page)

    # Resolve every row to a verified physical page before writing anything —
    # a partial or silently-wrong run must not look like a success.
    unresolved = resolve_physical_pages(rows, mapping)
    if unresolved:
        detail = "\n".join(f"  Sno {u.row.sno} '{u.row.title}': {u.reason}" for u in unresolved)
        raise SystemExit(
            f"Refusing to extract: {len(unresolved)} row(s) have no verified physical page.\n{detail}"
        )

    # Output folders per PDF
    pdf_stem = pdf_path.stem
    txt_out_dir = section_dir / pdf_stem
    txt_out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = jsonl_dir / f"{pdf_stem}_sections.jsonl"
    manifest_path = manifest_dir / f"{pdf_stem}_manifest.csv"

    manifest_rows = []

    with jsonl_path.open("w", encoding="utf-8") as jf:
        for r in rows:
            text = extract_text_pages(pdf_path, r.physical_start, r.physical_end)
            if len(text) < args.min_chars:
                continue

            safe = slugify(r.title)
            txt_path = txt_out_dir / f"{r.sno:03d}_{safe}.txt"

            txt_path.write_text(text + "\n", encoding="utf-8")

            rec = {
                "pdf": pdf_path.name,
                "sno": r.sno,
                "title": r.title,
                "printed_start": r.start,
                "printed_end": r.end,
                "physical_start": r.physical_start,
                "physical_end": r.physical_end,
                "pdf_page_index": r.physical_start - 1,
                "text": text,
            }
            jf.write(json.dumps(rec, ensure_ascii=False) + "\n")

            manifest_rows.append(
                {
                    "pdf": pdf_path.name,
                    "Sno": r.sno,
                    "title": r.title,
                    "printed_start": r.start,
                    "printed_end": r.end,
                    "physical_start": r.physical_start,
                    "physical_end": r.physical_end,
                    "pdf_page_index": r.physical_start - 1,
                    "txt_path": (
                        txt_path.resolve().relative_to(PROJECT_ROOT).as_posix()
                        if txt_path.resolve().is_relative_to(PROJECT_ROOT)
                        else str(txt_path.resolve())
                    ),
                    "chars": len(text),
                }
            )

    # Write manifest
    with manifest_path.open("w", newline="", encoding="utf-8") as mf:
        fieldnames = [
            "pdf", "Sno", "title", "printed_start", "printed_end",
            "physical_start", "physical_end", "pdf_page_index", "txt_path", "chars",
        ]
        w = csv.DictWriter(mf, fieldnames=fieldnames)
        w.writeheader()
        for mr in manifest_rows:
            w.writerow(mr)

    print(f"✅ PDF:      {pdf_path}")
    print(f"✅ Outline:  {outline_csv}")
    print(f"✅ TXT dir:  {txt_out_dir}")
    print(f"✅ JSONL:    {jsonl_path}")
    print(f"✅ Manifest: {manifest_path}")
    print("Done.")


if __name__ == "__main__":
    main()

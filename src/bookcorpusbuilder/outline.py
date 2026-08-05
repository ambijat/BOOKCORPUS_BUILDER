#!/usr/bin/env python3
"""
PDF → Chapter/Section outline → CSV (Sno,title,printed_start) + optional printed_end
Batch processes a folder of PDFs and writes:
  - one CSV per PDF
  - MASTER_outline.csv (all PDFs concatenated)

Key upgrades vs PyPDF2-only:
- Uses pdfplumber (layout-aware: font sizes, bold-ish detection, centering)
- Tries to parse a real Contents/TOC if present (leader dots + trailing page numbers)
- Otherwise falls back to typography + keyword/caption rules
- Captures Maps/Charts/Figures/Tables/Plates robustly
"""

from __future__ import annotations

import re
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Iterable

from .paths import INPUT_PDF_DIR, OUTLINE_DIR

DEFAULT_SOURCE_PDF_DIR = INPUT_PDF_DIR
DEFAULT_OUTPUT_DIR = OUTLINE_DIR


# ========= regex rules =========
RE_TOC_HEADER = re.compile(r"\b(contents|table\s+of\s+contents)\b", re.I)

# Typical TOC line:
# "Chapter 1 Geographic Zones .......... 12"
RE_TOC_LINE = re.compile(
    r"^(?P<title>.+?)\s*(\.{2,}|\s{2,})\s*(?P<page>\d{1,4})\s*$"
)

# Headings/captions
RE_PART = re.compile(r"^\s*PART\s+([IVXLC]+|\d+)\b[:\-]?\s*(.*)$", re.I)
RE_CHAPTER = re.compile(r"^\s*CHAPTER\s+(\d+|[IVXLC]+)\b[:\-]?\s*(.*)$", re.I)
RE_INTRO = re.compile(r"^\s*INTRODUCTION\b", re.I)
RE_ACK = re.compile(r"^\s*ACKNOWLEDG(E)?MENTS?\b", re.I)

RE_CAPTION = re.compile(
    r"^\s*(MAP|CHART|FIGURE|TABLE|PLATE)\s+([0-9]+[A-Z]?)\b[:\-]?\s*(.*)$",
    re.I
)

# Some PDFs use "Map 2" not "MAP 2"
RE_CAPTION_ALT = re.compile(
    r"^\s*(Map|Chart|Figure|Table|Plate)\s+([0-9]+[A-Z]?)\b[:\-]?\s*(.*)$"
)

# “Zone” lines (optional enrichment)
RE_ZONE = re.compile(r"^\s*(Zone|ZONE)\s+(\d+)\b[:\-]?\s*(.*)$")


@dataclass
class OutlineItem:
    title: str
    printed_start: int
    y: float = 0.0  # vertical position, for stable ordering inside a page
    kind: str = ""  # toc|heading|caption|zone|other


def ensure_dirs(src_dir: Path, out_dir: Path) -> None:
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source PDF directory not found: {src_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)


def normalize_title(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    # Normalize some unicode dashes to em dash style
    s = s.replace("–", "—")
    return s


def is_boldish(fontname: str) -> bool:
    if not fontname:
        return False
    fn = fontname.lower()
    return ("bold" in fn) or ("black" in fn) or ("demi" in fn) or ("heavy" in fn)


def cluster_words_into_lines(words: List[dict], y_tol: float = 3.0) -> List[dict]:
    """
    pdfplumber gives words with x0,x1,top,bottom,text,fontname,size etc.
    We cluster by 'top' into lines.
    Returns list of dict: {text, top, x0, x1, avg_size, bold_ratio, center_ratio}
    """
    if not words:
        return []

    # Sort top-to-bottom then left-to-right
    words = sorted(words, key=lambda w: (w.get("top", 0.0), w.get("x0", 0.0)))

    lines: List[List[dict]] = []
    current: List[dict] = []
    current_top = words[0].get("top", 0.0)

    for w in words:
        top = w.get("top", 0.0)
        if current and abs(top - current_top) > y_tol:
            lines.append(current)
            current = [w]
            current_top = top
        else:
            current.append(w)

    if current:
        lines.append(current)

    out = []
    for lw in lines:
        text = " ".join([normalize_title(w.get("text", "")) for w in lw]).strip()
        text = normalize_title(text)

        if not text:
            continue

        tops = [w.get("top", 0.0) for w in lw]
        x0s = [w.get("x0", 0.0) for w in lw]
        x1s = [w.get("x1", 0.0) for w in lw]
        sizes = [float(w.get("size", 0.0) or 0.0) for w in lw]

        fonts = [w.get("fontname", "") for w in lw]
        bolds = [1.0 if is_boldish(f) else 0.0 for f in fonts]
        bold_ratio = sum(bolds) / max(1, len(bolds))

        out.append(
            {
                "text": text,
                "top": float(sum(tops) / len(tops)),
                "x0": float(min(x0s)),
                "x1": float(max(x1s)),
                "avg_size": float(sum(sizes) / max(1, len(sizes))),
                "bold_ratio": float(bold_ratio),
            }
        )
    return out


def guess_heading_candidates(
    lines: List[dict],
    page_width: float,
    size_threshold: float,
    bold_threshold: float = 0.65,
) -> List[dict]:
    """
    Decide which lines are likely headings/captions using:
    - keyword patterns (PART/CHAPTER/INTRO/ACK/MAP/CHART/FIGURE/TABLE/PLATE)
    - OR typography (larger font size, bold-ish, centered-ish)
    """
    candidates = []
    for ln in lines:
        t = ln["text"]
        avg_size = ln["avg_size"]
        bold_ratio = ln["bold_ratio"]
        center = (ln["x0"] + ln["x1"]) / 2.0
        centeredness = 1.0 - min(1.0, abs(center - (page_width / 2.0)) / (page_width / 2.0))

        # Keyword triggers
        kw = (
            RE_PART.match(t)
            or RE_CHAPTER.match(t)
            or RE_INTRO.match(t)
            or RE_ACK.match(t)
            or RE_CAPTION.match(t)
            or RE_CAPTION_ALT.match(t)
            or RE_ZONE.match(t)
        )

        # Typography triggers
        ty = (avg_size >= size_threshold) or (bold_ratio >= bold_threshold and centeredness >= 0.70)

        if kw or ty:
            candidates.append({**ln, "centeredness": centeredness})
    return candidates


def merge_caption_with_next_line(cands: List[dict]) -> List[dict]:
    """
    If we have a caption marker like "CHART 1" and next line looks like the caption title,
    merge them: "CHART 1: Climatic Charts"
    """
    merged = []
    i = 0
    while i < len(cands):
        cur = cands[i]
        t = cur["text"]

        m1 = RE_CAPTION.match(t) or RE_CAPTION_ALT.match(t)
        if m1 and i + 1 < len(cands):
            nxt = cands[i + 1]
            t2 = nxt["text"]

            # Don't merge if next is another heading/caption marker
            if not (
                RE_PART.match(t2)
                or RE_CHAPTER.match(t2)
                or RE_CAPTION.match(t2)
                or RE_CAPTION_ALT.match(t2)
            ):
                # Only merge if next line isn't just a page number
                if not re.fullmatch(r"\d{1,4}", t2):
                    # Build standardized caption
                    kind = m1.group(1)
                    num = m1.group(2)
                    tail = (m1.group(3) or "").strip()

                    if tail:
                        new_title = f"[{kind.upper()}] {kind.title()} {num}: {tail}"
                    else:
                        new_title = f"[{kind.upper()}] {kind.title()} {num}: {t2}"

                    cur2 = {**cur}
                    cur2["text"] = normalize_title(new_title)
                    merged.append(cur2)
                    i += 2
                    continue

        # Non-merged
        merged.append(cur)
        i += 1
    return merged


def parse_toc_pages(pdf) -> List[OutlineItem]:
    """
    Attempts to find and parse Contents pages.
    Strategy:
      - Search first ~20 pages for a "Contents" header
      - If found, parse that page and the next 1–2 pages for TOC lines with trailing page numbers.
    """
    import pdfplumber

    toc_items: List[OutlineItem] = []
    toc_page_indices = []

    max_scan = min(20, len(pdf.pages))
    for i in range(max_scan):
        page = pdf.pages[i]
        text = page.extract_text() or ""
        if RE_TOC_HEADER.search(text):
            toc_page_indices.append(i)
            break

    if not toc_page_indices:
        return []

    start = toc_page_indices[0]
    for i in range(start, min(start + 3, len(pdf.pages))):
        page = pdf.pages[i]
        text = page.extract_text() or ""
        lines = [normalize_title(x) for x in (text.splitlines() if text else [])]
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            m = RE_TOC_LINE.match(ln)
            if m:
                title = normalize_title(m.group("title"))
                p = int(m.group("page"))
                # Basic cleanup of very short junk titles
                if len(title) >= 3:
                    toc_items.append(OutlineItem(title=title, printed_start=p, y=0.0, kind="toc"))

    # Deduplicate by (title, page)
    uniq = {}
    for it in toc_items:
        key = (it.title.lower(), it.printed_start)
        uniq[key] = it
    return list(uniq.values())


def extract_outline_from_pdf(pdf_path: Path) -> List[OutlineItem]:
    import pdfplumber

    items: List[OutlineItem] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        # 1) Try TOC parsing (best signal)
        toc_items = parse_toc_pages(pdf)
        if toc_items:
            # If TOC found, we still add captions from body to enrich
            items.extend(toc_items)

        # 2) Layout-aware heading/caption extraction across all pages
        for pi, page in enumerate(pdf.pages):
            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
                extra_attrs=["fontname", "size"],
            )
            if not words:
                continue

            lines = cluster_words_into_lines(words, y_tol=3.0)
            if not lines:
                continue

            sizes = sorted([ln["avg_size"] for ln in lines if ln["avg_size"] > 0.0])
            if not sizes:
                continue

            # Heading size threshold = 90th percentile (tune as needed)
            p90 = sizes[int(0.90 * (len(sizes) - 1))]
            size_threshold = max(p90, 12.5)  # avoid too-low thresholds

            cands = guess_heading_candidates(lines, page.width, size_threshold=size_threshold)
            cands = sorted(cands, key=lambda x: x["top"])  # top-to-bottom within page
            cands = merge_caption_with_next_line(cands)

            for c in cands:
                raw = normalize_title(c["text"])
                if not raw:
                    continue

                # Standardize PART/CHAPTER
                mp = RE_PART.match(raw)
                mc = RE_CHAPTER.match(raw)
                mz = RE_ZONE.match(raw)
                cap = RE_CAPTION.match(raw) or RE_CAPTION_ALT.match(raw)

                kind = "heading"
                title = raw

                if mp:
                    roman_or_num = mp.group(1)
                    rest = mp.group(2).strip()
                    title = f"Part {roman_or_num} — {rest}" if rest else f"Part {roman_or_num}"
                    kind = "heading"
                elif mc:
                    chapno = mc.group(1)
                    rest = mc.group(2).strip()
                    title = f"Chapter {chapno} — {rest}" if rest else f"Chapter {chapno}"
                    kind = "heading"
                elif RE_INTRO.match(raw):
                    title = "Introduction"
                    kind = "heading"
                elif RE_ACK.match(raw):
                    title = "Acknowledgments"
                    kind = "heading"
                elif cap:
                    # If already bracketed by merge function, keep as-is
                    if not raw.startswith("["):
                        label = cap.group(1).upper()
                        num = cap.group(2)
                        rest = (cap.group(3) or "").strip()
                        if rest:
                            title = f"[{label}] {label.title()} {num}: {rest}"
                        else:
                            title = f"[{label}] {label.title()} {num}"
                    kind = "caption"
                elif mz:
                    zno = mz.group(2)
                    rest = (mz.group(3) or "").strip()
                    title = f"Zone {zno} — {rest}" if rest else f"Zone {zno}"
                    kind = "zone"

                items.append(
                    OutlineItem(
                        title=normalize_title(title),
                        printed_start=pi + 1,
                        y=float(c["top"]),
                        kind=kind,
                    )
                )

    # 3) Clean + dedupe + order
    # Remove obvious noise lines (pure page numbers, etc.)
    cleaned = []
    for it in items:
        if re.fullmatch(r"\d{1,4}", it.title.strip()):
            continue
        # Avoid very short junk headings
        if len(it.title.strip()) < 3:
            continue
        cleaned.append(it)

    # Deduplicate: keep earliest occurrence by (normalized title)
    seen: Dict[str, OutlineItem] = {}
    for it in sorted(cleaned, key=lambda x: (x.printed_start, x.y)):
        key = it.title.lower()
        if key not in seen:
            seen[key] = it

    final = list(seen.values())
    final = sorted(final, key=lambda x: (x.printed_start, x.y))

    return final


def add_page_ranges(items: List[OutlineItem], max_page: int) -> List[Tuple[OutlineItem, int]]:
    """
    Compute printed_end as (next_item_start_page - 1), else max_page.
    Note: This is coarse (page-level), not position-level.
    """
    out = []
    for idx, it in enumerate(items):
        if idx + 1 < len(items):
            end = items[idx + 1].printed_start - 1
            end = max(it.printed_start, end)
        else:
            end = max_page
        out.append((it, end))
    return out


def write_csv_template(items: List[OutlineItem], out_csv: Path, include_end: bool, max_page: int) -> None:
    """
    Writes printed_start only for TOC-sourced rows (a page number actually printed
    in the table of contents) and physical_start only for everything else (the raw
    PDF page index the heading/caption/zone pass observed it on). The two coordinate
    systems are never placed in the same column — see outline_service.detect() for
    the equivalent split used by the GUI, and audit finding C2 for why this matters.
    """
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if include_end:
        ranged = add_page_ranges(items, max_page=max_page)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Sno", "title", "kind", "printed_start", "printed_end", "physical_start", "physical_end"])
            for i, (it, end) in enumerate(ranged, start=1):
                is_toc = it.kind == "toc"
                w.writerow([
                    i, it.title, it.kind,
                    it.printed_start if is_toc else "", end if is_toc else "",
                    "" if is_toc else it.printed_start, "" if is_toc else end,
                ])
    else:
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Sno", "title", "kind", "printed_start", "physical_start"])
            for i, it in enumerate(items, start=1):
                is_toc = it.kind == "toc"
                w.writerow([i, it.title, it.kind, it.printed_start if is_toc else "", "" if is_toc else it.printed_start])


def main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Extract chapter/section outline from PDFs and export CSVs in template format."
    )
    ap.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SOURCE_PDF_DIR,
        help=f"Source folder containing PDFs (default: {DEFAULT_SOURCE_PDF_DIR})",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output folder for CSVs (default: {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--include_end",
        action="store_true",
        help="Also compute printed_end column (page ranges).",
    )
    ap.add_argument(
        "--only",
        type=str,
        default="",
        help="Process only PDFs whose filename contains this substring (case-insensitive).",
    )

    args = ap.parse_args()

    src_dir: Path = args.src
    out_dir: Path = args.out
    ensure_dirs(src_dir, out_dir)

    pdfs = sorted(src_dir.glob("*.pdf"))
    if args.only:
        needle = args.only.lower()
        pdfs = [p for p in pdfs if needle in p.name.lower()]

    if not pdfs:
        print(f"❌ No PDFs found in: {src_dir}")
        print("Tip: Put your PDFs there, or pass --src /path/to/pdfs")
        sys.exit(1)

    master_rows = []
    for pdf_path in pdfs:
        try:
            # get max page quickly
            import pdfplumber
            with pdfplumber.open(str(pdf_path)) as pdf:
                max_page = len(pdf.pages)

            items = extract_outline_from_pdf(pdf_path)
            if not items:
                print(f"⚠️  No outline extracted (text may be scanned/OCR needed): {pdf_path.name}")
                continue

            out_csv = out_dir / f"{pdf_path.stem}_outline.csv"
            write_csv_template(items, out_csv, include_end=args.include_end, max_page=max_page)
            print(f"✅ {pdf_path.name} → {out_csv}")

            # master rows
            if args.include_end:
                ranged = add_page_ranges(items, max_page=max_page)
                for sno, (it, end) in enumerate(ranged, start=1):
                    is_toc = it.kind == "toc"
                    master_rows.append({
                        "pdf": pdf_path.name, "Sno": sno, "title": it.title, "kind": it.kind,
                        "printed_start": it.printed_start if is_toc else "", "printed_end": end if is_toc else "",
                        "physical_start": "" if is_toc else it.printed_start, "physical_end": "" if is_toc else end,
                    })
            else:
                for sno, it in enumerate(items, start=1):
                    is_toc = it.kind == "toc"
                    master_rows.append({
                        "pdf": pdf_path.name, "Sno": sno, "title": it.title, "kind": it.kind,
                        "printed_start": it.printed_start if is_toc else "",
                        "physical_start": "" if is_toc else it.printed_start,
                    })

        except Exception as e:
            print(f"❌ Failed on {pdf_path.name}: {e}")

    # write master
    if master_rows:
        master_csv = out_dir / "MASTER_outline.csv"
        fieldnames = list(master_rows[0].keys())
        with master_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in master_rows:
                w.writerow(r)
        print(f"📌 MASTER → {master_csv}")

    print("\nDone.")


if __name__ == "__main__":
    main()

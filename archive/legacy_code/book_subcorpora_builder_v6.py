#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Sub‑corpora Builder with Dehyphenation
----------------------------------------------
Build per‑chapter corpora from a book‑length PDF with improved text processing:

Features:
1) Multiple chapter detection methods:
   - CSV chapter list with printed page starts
   - Table of Contents parsed from PDF
   - Regex fallback when no TOC/CSV available

2) Advanced text processing:
   - Automatic dehyphenation of line-wrapped words
   - Preservation of valid hyphenated compounds
   - Optional word frequency checks (if wordfreq installed)

3) Flexible output options:
   - Paragraph handling modes (oneline vs wrapped)
   - Printed page range cropping
   - Printed→Actual page offset inference

Dependencies: PyMuPDF (fitz)
    pip install pymupdf
Optional: wordfreq for better dehyphenation
    pip install wordfreq

Typical usage:
   python book_subcorpora_builder_v6.py \
        --pdf ./local_books/book3.pdf \
        --chapters-csv ./contents/book3_chapters.csv \
        --crop-printed 6:116 \
        --paragraph-mode oneline \
        --outdir ./book3_subcorpora
"""

from __future__ import annotations
import os
import re
import json
import argparse
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set

# ---------------------------
# Dehyphenation Configuration
# ---------------------------
SOFT_HYPHEN = "\u00AD"

# Common hyphenated compounds to preserve (case-insensitive)
DEFAULT_KEEP_HYPHENS = {
    "policy-guided", "state-owned", "rule-based", "policy-making",
    "decision-making", "cost-benefit", "long-term", "short-term",
    "security-related", "socio-economic", "socio-political",
    "geoeconomic-driven", "policy-oriented", "multi-level", "cross-border",
    "well-known", "high-level", "low-cost", "large-scale", "small-scale"
}

# Try to use wordfreq if available
try:
    from wordfreq import zipf_frequency as _zipf


    def is_probable_word(w: str) -> bool:
        return _zipf(w, "en") >= 3.0
except ImportError:
    _zipf = None


    def is_probable_word(w: str) -> bool:
        return bool(re.fullmatch(r"[a-z]+", w)) and len(w) >= 4


# ---------------------------
# Data Structures
# ---------------------------
@dataclass
class ChapterDef:
    title: str
    start_page_idx: int  # 0-based actual PDF index (inclusive)
    end_page_idx: int  # 0-based actual PDF index (inclusive)
    printed_start: Optional[int] = None


# ---------------------------
# Text Processing Utilities
# ---------------------------
def normalize_space(s: str) -> str:
    """Normalize whitespace in a string."""
    return re.sub(r"\s+", " ", s or "").strip()


def dehyphenate_text(text: str, keep_hyphens: Optional[Set[str]] = None) -> str:
    """
    Fix hyphenation artifacts in text while preserving valid compounds.

    Args:
        text: Input text to process
        keep_hyphens: Set of hyphenated compounds to preserve (lowercase)

    Returns:
        Cleaned text with proper word joins
    """
    if keep_hyphens is None:
        keep_hyphens = DEFAULT_KEEP_HYPHENS

    # Remove soft hyphens first
    text = text.replace(SOFT_HYPHEN, "")

    # Pattern for potential line-wrapped hyphens
    pat = re.compile(r"(?i)\b([A-Za-z]{2,})- +([A-Za-z]{2,})\b")

    def process_match(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        compound = f"{left.lower()}-{right.lower()}"

        # Preserve known compounds
        if compound in keep_hyphens:
            return m.group(0)  # return original with hyphen

        # Try joining
        joined = left + right
        if is_probable_word(joined.lower()):
            return joined

        # Not confident - leave as-is
        return m.group(0)

    # Process all potential hyphenation cases
    text = pat.sub(process_match, text)

    # Normalize any odd spacing around hyphens
    text = re.sub(r"-\s+\b", "- ", text)

    return text


def chunk_paragraphs(text: str, width: int, mode: str, dehyphenate: bool = True) -> List[str]:
    """
    Split text into paragraphs with optional dehyphenation and wrapping.

    Args:
        text: Input text to process
        width: Max characters per paragraph in wrap mode
        mode: 'oneline' or 'wrap'
        dehyphenate: Whether to fix hyphenation artifacts

    Returns:
        List of processed paragraphs
    """
    # First split on blank lines to detect paragraphs
    blocks = re.split(r"\n\s*\n", text)
    chunks: List[str] = []

    for b in blocks:
        # Normalize whitespace and handle hyphenation
        b = normalize_space(b.replace("\r", " ").replace("\n", " "))
        if not b:
            continue

        if dehyphenate:
            b = dehyphenate_text(b)

        if mode == "oneline":
            chunks.append(b)
            continue

        # Wrap mode processing
        if len(b) <= width:
            chunks.append(b)
        else:
            # Soft-wrap long paragraphs
            sent_parts = re.split(r"(?<=[.!?])\s+", b)
            carry = ""
            for sp in sent_parts:
                if not sp:
                    continue
                seg = (carry + " " + sp).strip()
                if len(seg) <= width:
                    carry = seg
                else:
                    if carry:
                        chunks.append(carry)
                    # Hard-wrap by words if needed
                    wbuf = []
                    curlen = 0
                    for w in sp.split():
                        add = len(w) + (1 if wbuf else 0)
                        if curlen + add > width:
                            chunks.append(" ".join(wbuf))
                            wbuf = [w]
                            curlen = len(w)
                        else:
                            wbuf.append(w)
                            curlen += add
                    carry = " ".join(wbuf) if wbuf else ""
            if carry:
                chunks.append(carry)

    return chunks


# ---------------------------
# PDF Processing Utilities
# ---------------------------
TOC_HEADING_RE = re.compile(r"^(contents|table of contents)\b", re.I)
TOC_ENTRY_RE = re.compile(r"^(.+?)\s*\.{2,}\s*(\d{1,4})\s*$")  # title ..... 123
TOC_ENTRY_FALLBACK_RE = re.compile(r"^(.*?)\s+(\d{1,4})\s*$")  # title    123 (same line)
CHAPTER_START_RE = re.compile(r"^(chapter\s+\d+\b|\d+\s+[A-Z].+)$", re.I)


def parse_printed_range(spec: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse printed page range specification."""
    if not spec:
        return None
    m = re.fullmatch(r"\s*(\d{1,4})\s*:\s*(\d{1,4})\s*", spec)
    if not m:
        raise ValueError(f"Bad --crop-printed format: {spec}")
    a, b = int(m.group(1)), int(m.group(2))
    if a < 1 or b < a:
        raise ValueError(f"Bad printed range: {a}:{b}")
    return a, b


def printed_to_actual_index(printed_page: int, offset: int) -> int:
    """Convert 1-based printed page to 0-based actual index."""
    return (printed_page + offset) - 1


def detect_contents_pages(doc) -> List[int]:
    """Detect pages containing the table of contents."""
    indices: List[int] = []
    page_limit = min(40, doc.page_count)
    found_anchor = None

    for i in range(page_limit):
        text = doc.load_page(i).get_text("text")
        lines = [normalize_space(l) for l in text.splitlines() if normalize_space(l)]
        if not lines:
            continue
        if any(TOC_HEADING_RE.match(l) for l in lines):
            found_anchor = i
            break

    if found_anchor is not None:
        q = found_anchor
        while q < page_limit:
            t = doc.load_page(q).get_text("text")
            ls = [normalize_space(l) for l in t.splitlines() if normalize_space(l)]
            dotted = sum(1 for l in ls if TOC_ENTRY_RE.match(l))
            tails = sum(1 for l in ls if re.search(r"\s(\d{1,4})$", l))
            numeric_only = sum(1 for l in ls if re.fullmatch(r"\d{1,4}", l))

            if dotted >= 4 or (tails >= 6 and len(ls) >= 12) or numeric_only >= 6:
                indices.append(q)
                q += 1
            else:
                break

    return indices


def parse_toc_entries_from_pages(doc, pages: List[int]) -> List[Tuple[str, int]]:
    """Extract chapter entries from detected TOC pages."""
    entries: List[Tuple[str, int]] = []

    for pno in pages:
        text = doc.load_page(pno).get_text("text")
        lines = [normalize_space(raw) for raw in text.splitlines() if normalize_space(raw)]

        # Pass 1: dotted leaders
        for line in lines:
            m = TOC_ENTRY_RE.match(line)
            if m:
                title = normalize_space(m.group(1))
                page_num = int(m.group(2))
                if title and page_num >= 1:
                    entries.append((title, page_num))

        # Pass 2: same-line tail numbers
        for line in lines:
            if TOC_HEADING_RE.match(line):
                continue
            m2 = TOC_ENTRY_FALLBACK_RE.match(line)
            if m2:
                title = normalize_space(m2.group(1))
                page_num = int(m2.group(2))
                if title and page_num >= 1:
                    entries.append((title, page_num))

        # Pass 3: split-line entries
        if not entries:
            entries.extend(_parse_entries_splitline(lines))

    # Deduplicate while preserving order
    dedup = []
    seen = set()
    for t, p in entries:
        key = (t.lower(), p)
        if key not in seen:
            dedup.append((t, p))
            seen.add(key)

    return dedup


def _parse_entries_splitline(lines: List[str]) -> List[Tuple[str, int]]:
    """Handle TOCs where titles and page numbers are on separate lines."""
    entries: List[Tuple[str, int]] = []
    buf: List[str] = []

    for l in lines:
        if re.fullmatch(r"\d{1,4}", l):
            title = normalize_space(" ".join(buf))
            if title and not TOC_HEADING_RE.match(title):
                entries.append((title, int(l)))
            buf = []
        else:
            if not TOC_HEADING_RE.match(l):
                buf.append(l)

    return entries


def chapters_from_csv(csv_path: str) -> List[Tuple[str, int]]:
    """Load chapter definitions from CSV file."""
    import csv
    out: List[Tuple[str, int]] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            title = normalize_space(row.get("title") or row.get("Title") or "")
            ps = row.get("printed_start") or row.get("PrintedStart")
            if not ps:
                continue
            start = int(ps)
            if title and start >= 1:
                out.append((title, start))

    return out


def infer_printed_offset(doc, seeds: List[Tuple[str, int]]) -> Optional[int]:
    """Infer printed to actual page offset from sample chapters."""
    if not seeds:
        return None

    first_title, first_printed = seeds[0]
    window = range(0, min(40, doc.page_count))
    token = normalize_space(first_title).split()[0:2]
    if not token:
        return None

    needle = " ".join(token).lower()

    for idx in window:
        text = doc.load_page(idx).get_text("text").lower()
        if needle and needle in text:
            return (idx + 1) - first_printed

    return None


def chapters_from_seeds(
        doc,
        seeds: List[Tuple[str, int]],
        printed_offset: int,
        crop_window: Tuple[int, int]
) -> List[ChapterDef]:
    """Build chapter definitions from seed data."""
    actual_starts: List[int] = []
    titles: List[str] = []
    printed_starts: List[int] = []

    for title, printed in seeds:
        ai = printed_to_actual_index(printed, printed_offset)
        ai = max(0, min(ai, doc.page_count - 1))
        actual_starts.append(ai)
        titles.append(title)
        printed_starts.append(printed)

    # Sort by actual start
    zipped = sorted(zip(actual_starts, titles, printed_starts))
    actual_starts = [z[0] for z in zipped]
    titles = [z[1] for z in zipped]
    printed_starts = [z[2] for z in zipped]

    ch_defs: List[ChapterDef] = []

    for i, (a_start, title, p_start) in enumerate(zip(actual_starts, titles, printed_starts)):
        a_end = (actual_starts[i + 1] - 1) if i + 1 < len(actual_starts) else (doc.page_count - 1)

        # Intersect with crop window
        s2 = max(a_start, crop_window[0])
        e2 = min(a_end, crop_window[1])

        if s2 <= e2:
            ch_defs.append(ChapterDef(
                title=title,
                start_page_idx=s2,
                end_page_idx=e2,
                printed_start=p_start
            ))

    return ch_defs


def chapters_by_regex(doc, max_chapters: Optional[int], crop_window: Tuple[int, int]) -> List[ChapterDef]:
    """Fallback chapter detection using heuristics."""
    candidates: List[Tuple[int, str]] = []  # (actual_start_idx, title)

    for i in range(doc.page_count):
        if i < crop_window[0] or i > crop_window[1]:
            continue

        text = doc.load_page(i).get_text("text")
        lines = [normalize_space(l) for l in text.splitlines() if normalize_space(l)]
        if not lines:
            continue

        head = lines[:6]
        for ln in head:
            if CHAPTER_START_RE.match(ln):
                candidates.append((i, ln))
                break

    if not candidates:
        # Fallback: split the crop into equal bins
        s, e = crop_window
        bins = 6 if not max_chapters else max(2, min(12, max_chapters))
        width = max(1, (e - s + 1) // bins)
        starts = [s + k * width for k in range(bins)]
        titles = [f"Chapter {k + 1}" for k in range(len(starts))]
        candidates = list(zip(starts, titles))

    # Build chapter windows
    candidates.sort(key=lambda x: x[0])
    ch_defs: List[ChapterDef] = []

    for i, (a_start, title) in enumerate(candidates):
        a_end = (candidates[i + 1][0] - 1) if i + 1 < len(candidates) else crop_window[1]
        ch_defs.append(ChapterDef(
            title=title,
            start_page_idx=a_start,
            end_page_idx=a_end
        ))
        if max_chapters and len(ch_defs) >= max_chapters:
            break

    return ch_defs


def extract_text_range(doc, start_idx: int, end_idx: int) -> str:
    """Extract text from a range of pages."""
    parts: List[str] = []

    for i in range(start_idx, end_idx + 1):
        t = doc.load_page(i).get_text("text")
        parts.append(t)

    return "\n".join(parts)


def write_chapter(
        outdir: str,
        idx: int,
        ch: ChapterDef,
        text: str,
        para_width: int,
        para_mode: str,
        dehyphenate: bool = True
):
    """Write chapter corpus and metadata to files."""
    ch_dir = os.path.join(outdir, f"chapter_{idx:02d}")
    os.makedirs(ch_dir, exist_ok=True)

    # Process paragraphs
    paras = chunk_paragraphs(text, para_width, para_mode, dehyphenate)

    # Write corpus.txt
    with open(os.path.join(ch_dir, "corpus.txt"), "w", encoding="utf-8") as f:
        if para_mode == "oneline":
            f.write("\n".join(paras) + "\n")
        else:
            f.write("\n\n".join(paras) + ("\n" if paras else ""))

    # Write meta.json
    meta = {
        "title": ch.title,
        "printed_start": ch.printed_start,
        "actual_start_idx": ch.start_page_idx,
        "actual_end_idx": ch.end_page_idx,
        "page_count": ch.end_page_idx - ch.start_page_idx + 1,
        "paragraph_mode": para_mode,
        "paragraph_chars": para_width,
        "dehyphenated": dehyphenate,
    }

    with open(os.path.join(ch_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ---------------------------
# CLI and Main
# ---------------------------
def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Build per-chapter corpora from a PDF with dehyphenation."
    )
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--outdir", required=True, help="Output directory for chapter_XX/")
    parser.add_argument("--max-chapters", type=int, default=None,
                        help="Keep only first N chapters after detection")
    parser.add_argument("--chapters-csv", default=None,
                        help="CSV with columns: title,printed_start (printed page numbers)")
    parser.add_argument("--crop-printed", dest="crop_printed", default=None,
                        help="Printed page crop 'START:END' inclusive, e.g. 8:207")
    parser.add_argument("--printed-offset", type=int, default=None,
                        help="Override printed→actual offset. actual_index=(printed+offset)-1")
    parser.add_argument("--paragraph-chars", type=int, default=220,
                        help="Max characters per paragraph chunk in wrap mode")
    parser.add_argument("--paragraph-mode", choices=["wrap", "oneline"], default="wrap",
                        help="Paragraph handling: wrap or oneline")
    parser.add_argument("--no-dehyphenate", action="store_true",
                        help="Disable automatic dehyphenation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only print resolved chapter windows; do not write files")
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("Error: PyMuPDF (fitz) required. Install with: pip install pymupdf")

    if not os.path.exists(args.pdf):
        raise SystemExit(f"Error: PDF file not found: {args.pdf}")

    os.makedirs(args.outdir, exist_ok=True)
    doc = fitz.open(args.pdf)

    # Gather chapter seeds: CSV → TOC → none
    if args.chapters_csv:
        seeds = chapters_from_csv(args.chapters_csv)
        print(f"[INFO] Loaded {len(seeds)} chapter seeds from CSV")
    else:
        toc_pages = detect_contents_pages(doc)
        seeds = parse_toc_entries_from_pages(doc, toc_pages) if toc_pages else []
        if seeds:
            print(f"[INFO] Parsed {len(seeds)} TOC entries from {len(toc_pages)} TOC page(s)")

    # Determine printed→actual offset
    printed_offset = args.printed_offset
    if printed_offset is None:
        printed_offset = infer_printed_offset(doc, seeds) if seeds else None
    if printed_offset is None:
        printed_offset = 0
    print(f"[INFO] Printed→actual offset: {printed_offset}")

    # Compute crop window in actual indices
    crop_printed = parse_printed_range(args.crop_printed)
    if crop_printed:
        p_start, p_end = crop_printed
        a_start = max(0, printed_to_actual_index(p_start, printed_offset))
        a_end = min(doc.page_count - 1, printed_to_actual_index(p_end, printed_offset))
        if a_end < a_start:
            raise SystemExit(f"Error: Computed crop empty: printed {p_start}:{p_end} → actual {a_start}:{a_end}")
        crop_window = (a_start, a_end)
        print(f"[INFO] Printed crop {p_start}:{p_end} → actual {a_start}–{a_end} (0‑based)")
    else:
        crop_window = (0, doc.page_count - 1)
        print(f"[INFO] No crop; using full document 0–{doc.page_count - 1}")

    # Build chapter definitions
    if seeds:
        ch_defs = chapters_from_seeds(doc, seeds, printed_offset, crop_window)
    else:
        print("[WARN] No CSV/TOC seeds; falling back to regex detection")
        ch_defs = chapters_by_regex(doc, args.max_chapters, crop_window)

    if args.max_chapters:
        ch_defs = ch_defs[:args.max_chapters]

    # Report plan
    print("\n[PLAN] Chapters (actual indices, inclusive):")
    for i, ch in enumerate(ch_defs, 1):
        print(f"  {i:02d}. {ch.title[:60]}{'...' if len(ch.title) > 60 else ''}")
        print(f"       printed_start={ch.printed_start or '?'} | actual {ch.start_page_idx}..{ch.end_page_idx}")

    if args.dry_run:
        print("\n[DRY‑RUN] Exiting before writing files.")
        return

    # Process and write each chapter
    print("\n[INFO] Processing chapters...")
    for i, ch in enumerate(ch_defs, 1):
        text = extract_text_range(doc, ch.start_page_idx, ch.end_page_idx)
        write_chapter(
            args.outdir,
            i,
            ch,
            text,
            args.paragraph_chars,
            args.paragraph_mode,
            dehyphenate=not args.no_dehyphenate
        )
        print(f"[OK] Wrote chapter {i:02d}: {ch.title[:50]}...")

    print(f"\n[DONE] Wrote {len(ch_defs)} chapter corpora → {args.outdir}")


if __name__ == "__main__":
    main()
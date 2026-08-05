from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ...outline import extract_outline_from_pdf
from ..models import ApprovalMetadata, BookRecord, OutlineEntry, Severity, ValidationIssue
from .common import atomic_write_json, read_json, sha256_file, utc_now
from .outline_text_parser import OutlineTextParser


FIELDS = ["Sno", "title", "kind", "printed_start", "physical_start", "pdf_page_index", "confidence", "source", "review_status", "include", "printed_page_label", "level", "edited_by_user", "source_sno", "parent_sno", "raw_import_hash", "entry_id", "parent_entry_id", "provenance_source_type", "analytical_or_verbatim", "boundary_status", "boundary_basis", "allow_extraction", "notes"]
KINDS = {"part", "chapter", "section", "subsection", "analytical_section", "preface", "introduction", "appendix", "bibliography", "notes", "index", "caption", "topic", "glossary", "acknowledgement", "other"}


def parse_pasted_outline(text: str):
    """Compatibility entry point for callers outside the Structure Builder."""
    return OutlineTextParser().parse(text)


def _optional_int(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text else None


class OutlineService:
    def __init__(self, outline_dir: Path):
        self.outline_dir = outline_dir
        self.outline_dir.mkdir(parents=True, exist_ok=True)

    def paths(self, book_id: str) -> tuple[Path, Path, Path]:
        return (
            self.outline_dir / f"{book_id}_outline.csv",
            self.outline_dir / f"{book_id}_outline_clean.csv",
            self.outline_dir / f"{book_id}_approval.json",
        )

    def candidate_provenance_path(self, book_id: str) -> Path:
        return self.outline_dir / f"{book_id}_outline_sources.json"

    def save_candidate_provenance(self, book_id: str, candidates: list, mode: str) -> None:
        path = self.candidate_provenance_path(book_id)
        existing = read_json(path, {"events": []})
        existing.setdefault("events", []).append({
            "recorded_at": utc_now(),
            "mode": mode,
            "candidates": [asdict(candidate) for candidate in candidates],
        })
        atomic_write_json(path, existing)

    def load(self, path: Path) -> list[OutlineEntry]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"Sno", "title", "printed_start"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Outline must contain {sorted(required)}")
            entries = []
            for row in reader:
                entries.append(OutlineEntry(
                    sno=int(row["Sno"]), title=row["title"].strip(),
                    kind=(row.get("kind") or "section").strip().lower(),
                    printed_start=_optional_int(row.get("printed_start")),
                    physical_start=_optional_int(row.get("physical_start")),
                    pdf_page_index=_optional_int(row.get("pdf_page_index")),
                    confidence=float(row["confidence"]) if str(row.get("confidence") or "").strip() else None,
                    source=(row.get("source") or "import").strip(),
                    review_status=(row.get("review_status") or "draft").strip(),
                    include=str(row.get("include", "true")).strip().lower() not in {"0", "false", "no"},
                    printed_page_label=(row.get("printed_page_label") or "").strip(),
                    level=_optional_int(row.get("level")) or 1,
                    edited_by_user=str(row.get("edited_by_user", "false")).strip().lower() in {"1", "true", "yes"},
                    source_sno=(row.get("source_sno") or "").strip(),
                    parent_sno=(row.get("parent_sno") or "").strip(),
                    raw_import_hash=(row.get("raw_import_hash") or "").strip(),
                    entry_id=(row.get("entry_id") or "").strip(),
                    parent_entry_id=(row.get("parent_entry_id") or "").strip(),
                    provenance_source_type=(row.get("provenance_source_type") or "").strip(),
                    analytical_or_verbatim=(row.get("analytical_or_verbatim") or "").strip(),
                    boundary_status=(row.get("boundary_status") or "").strip(),
                    boundary_basis=(row.get("boundary_basis") or "").strip(),
                    allow_extraction=str(row.get("allow_extraction", "true")).strip().lower() not in {"0", "false", "no"},
                    notes=(row.get("notes") or "").strip(),
                ))
        return entries

    def save(self, path: Path, entries: list[OutlineEntry]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(entry.to_csv_row() for entry in entries)
            os.replace(temporary, path)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise

    def generate(self, book: BookRecord) -> list[OutlineEntry]:
        result = self.detect(book)
        draft, _, _ = self.paths(book.book_id)
        self.save(draft, result)
        return result

    def detect(self, book: BookRecord) -> list[OutlineEntry]:
        result = []
        for sno, item in enumerate(extract_outline_from_pdf(book.path), 1):
            is_toc = item.kind == "toc"
            physical = None if is_toc else item.printed_start
            result.append(OutlineEntry(
                sno=sno, title=item.title, kind="caption" if item.kind == "caption" else "section",
                printed_start=item.printed_start if is_toc else None,
                physical_start=physical, pdf_page_index=physical - 1 if physical else None,
                confidence=0.85 if is_toc else 0.55,
                source="toc" if is_toc else "body_heading", review_status="draft",
            ))
        return result

    def validate(self, entries: list[OutlineEntry], page_count: int = 0) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        snos = [entry.sno for entry in entries]
        if len(snos) != len(set(snos)):
            issues.append(ValidationIssue(Severity.BLOCKING, "duplicate_sno", "Section numbers must be unique."))
        included = [entry for entry in entries if entry.include]
        if not included:
            issues.append(ValidationIssue(Severity.BLOCKING, "empty_outline", "At least one included section is required."))
        for entry in included:
            if not entry.title.strip():
                issues.append(ValidationIssue(Severity.BLOCKING, "empty_title", f"Section {entry.sno} has no title."))
            # A missing numeric printed_start is only a real problem when there's no other
            # evidence of this entry's page: a Roman-numeral label (front matter like "ix")
            # or an already-resolved, self-consistent physical_start/pdf_page_index pair
            # (e.g. supplied by JSON import) are each legitimate pagination evidence on
            # their own and must not be forced into a fabricated numeric printed page.
            has_supplied_physical = (
                entry.physical_start is not None and entry.pdf_page_index is not None
                and entry.pdf_page_index == entry.physical_start - 1
            )
            if (
                (entry.printed_start is None or entry.printed_start < 1)
                and not entry.printed_page_label and not has_supplied_physical
            ):
                issues.append(ValidationIssue(
                    Severity.BLOCKING, "invalid_printed_start",
                    f"Section {entry.sno} needs a positive printed page, a Roman-numeral page "
                    "label, or a resolved physical_start/pdf_index pair.",
                ))
            if entry.kind not in KINDS:
                issues.append(ValidationIssue(Severity.WARNING, "unknown_kind", f"Section {entry.sno} has unknown kind '{entry.kind}'."))
            if not entry.allow_extraction:
                issues.append(ValidationIssue(
                    Severity.BLOCKING, "boundary_not_extraction_enabled",
                    f"Section {entry.sno} is analytical metadata or has an unverified boundary.",
                ))
            if page_count and entry.physical_start and entry.physical_start > page_count:
                issues.append(ValidationIssue(Severity.BLOCKING, "physical_out_of_range", f"Section {entry.sno} exceeds the PDF page count."))
        if not issues:
            issues.append(ValidationIssue(Severity.PASSED, "outline_valid", "Outline structure is valid."))
        return issues

    def approve(self, book: BookRecord, entries: list[OutlineEntry], reviewer_note: str = "", revoke: bool = False) -> ApprovalMetadata:
        draft, clean, metadata_path = self.paths(book.book_id)
        prior = read_json(metadata_path)
        if prior and prior.get("approved") and not revoke:
            raise FileExistsError("An approved outline already exists. Revoke approval before replacing it.")
        blocking = [item for item in self.validate(entries, book.page_count) if item.severity == Severity.BLOCKING]
        if blocking:
            raise ValueError("; ".join(item.message for item in blocking))
        approved_entries = [OutlineEntry(**{**asdict(entry), "review_status": "approved"}) for entry in entries]
        self.save(clean, approved_entries)
        metadata = ApprovalMetadata(True, utc_now(), sha256_file(clean), sha256_file(book.path), reviewer_note)
        atomic_write_json(metadata_path, metadata)
        if not draft.exists():
            self.save(draft, entries)
        return metadata

    def approval(self, book_id: str) -> ApprovalMetadata | None:
        _, _, path = self.paths(book_id)
        value = read_json(path)
        return ApprovalMetadata(**value) if value else None

    def revoke(self, book_id: str) -> None:
        _, _, path = self.paths(book_id)
        value = read_json(path)
        if value:
            value["approved"] = False
            atomic_write_json(path, value)

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .domain import OutlineEntry


@dataclass
class OutlineCandidate:
    """A reviewable parser result that is not yet part of the draft outline."""

    raw_text: str
    sno: int | None = None
    title: str = ""
    kind: str = "section"
    printed_page: int | None = None
    printed_page_label: str = ""
    physical_start: int | None = None
    pdf_page_index: int | None = None
    level: int = 1
    parent_candidate_id: str | None = None
    source: str = "pasted_outline"
    confidence: float = 0.0
    include: bool = True
    warning_codes: list[str] = field(default_factory=list)
    parser_rule: str = ""
    edited_by_user: bool = False
    sno_explicit: bool = False
    source_sno: str = ""
    parent_sno: str = ""
    raw_import_hash: str = ""
    entry_id: str = ""
    parent_entry_id: str = ""
    provenance_source_type: str = ""
    analytical_or_verbatim: str = ""
    boundary_status: str = ""
    boundary_basis: str = ""
    allow_extraction: bool = True
    notes: str = ""
    candidate_id: str = field(default_factory=lambda: uuid4().hex)

    def to_outline_entry(self, fallback_sno: int) -> OutlineEntry:
        return OutlineEntry(
            sno=self.sno or fallback_sno,
            title=self.title.strip(),
            kind=self.kind,
            printed_start=self.printed_page,
            physical_start=self.physical_start,
            pdf_page_index=self.pdf_page_index,
            confidence=self.confidence,
            source=self.source,
            review_status="draft",
            include=self.include,
            printed_page_label=self.printed_page_label,
            level=self.level,
            edited_by_user=self.edited_by_user,
            source_sno=self.source_sno,
            parent_sno=self.parent_sno,
            raw_import_hash=self.raw_import_hash,
            entry_id=self.entry_id,
            parent_entry_id=self.parent_entry_id,
            provenance_source_type=self.provenance_source_type,
            analytical_or_verbatim=self.analytical_or_verbatim,
            boundary_status=self.boundary_status,
            boundary_basis=self.boundary_basis,
            allow_extraction=self.allow_extraction,
            notes=self.notes,
        )


@dataclass(frozen=True)
class MergeItem:
    category: str
    candidate: OutlineCandidate
    draft: OutlineEntry | None = None
    reason: str = ""


@dataclass
class MergeAnalysis:
    new_rows: list[MergeItem] = field(default_factory=list)
    matching_rows: list[MergeItem] = field(default_factory=list)
    conflicting_rows: list[MergeItem] = field(default_factory=list)
    ignored_rows: list[MergeItem] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicting_rows)

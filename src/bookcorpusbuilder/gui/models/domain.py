from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str


@dataclass
class BookRecord:
    book_id: str
    filename: str
    pdf_path: str
    source_hash: str
    size_bytes: int
    page_count: int = 0
    text_status: str = "unknown"
    original_source: str = ""
    registered_at: str = ""

    @property
    def path(self) -> Path:
        return Path(self.pdf_path)


@dataclass
class OutlineEntry:
    sno: int
    title: str
    kind: str = "section"
    printed_start: int | None = None
    physical_start: int | None = None
    pdf_page_index: int | None = None
    confidence: float | None = None
    source: str = "manual"
    review_status: str = "draft"
    include: bool = True
    printed_page_label: str = ""
    level: int = 1
    edited_by_user: bool = False
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

    def to_csv_row(self) -> dict[str, str | int | float]:
        return {
            "Sno": self.sno,
            "title": self.title,
            "kind": self.kind,
            "printed_start": "" if self.printed_start is None else self.printed_start,
            "physical_start": "" if self.physical_start is None else self.physical_start,
            "pdf_page_index": "" if self.pdf_page_index is None else self.pdf_page_index,
            "confidence": "" if self.confidence is None else self.confidence,
            "source": self.source,
            "review_status": self.review_status,
            "include": "true" if self.include else "false",
            "printed_page_label": self.printed_page_label,
            "level": self.level,
            "edited_by_user": "true" if self.edited_by_user else "false",
            "source_sno": self.source_sno,
            "parent_sno": self.parent_sno,
            "raw_import_hash": self.raw_import_hash,
            "entry_id": self.entry_id,
            "parent_entry_id": self.parent_entry_id,
            "provenance_source_type": self.provenance_source_type,
            "analytical_or_verbatim": self.analytical_or_verbatim,
            "boundary_status": self.boundary_status,
            "boundary_basis": self.boundary_basis,
            "allow_extraction": "true" if self.allow_extraction else "false",
            "notes": self.notes,
        }


@dataclass
class ApprovalMetadata:
    approved: bool
    approved_at: str
    approved_outline_hash: str
    source_pdf_hash: str
    reviewer_note: str = ""


@dataclass
class MappingAnchor:
    printed_page: int
    physical_page_number: int
    pdf_page_index: int
    label: str = ""
    exception: bool = False


@dataclass
class MappingSegment:
    printed_start: int
    printed_end: int
    offset: int
    anchors: list[MappingAnchor]

    @property
    def confirmed(self) -> bool:
        return len(self.anchors) >= 2


@dataclass
class ResolvedPage:
    physical_page: int | None
    method: str  # "supplied" | "anchor" | "segment" | "extrapolated" | "physical_only" | "unresolved"
    detail: str = ""


@dataclass
class PageMapping:
    book_id: str
    anchors: list[MappingAnchor] = field(default_factory=list)
    exceptions: dict[str, int] = field(default_factory=dict)
    approved: bool = False
    approved_at: str = ""
    reviewer_note: str = ""

    def _normal_anchors(self) -> list[MappingAnchor]:
        return [a for a in self.anchors if not a.exception]

    def conflicting_anchor_pairs(self) -> list[tuple[MappingAnchor, MappingAnchor]]:
        """Anchors that target the same printed page but disagree on the physical page."""
        by_page: dict[int, list[MappingAnchor]] = {}
        for anchor in self._normal_anchors():
            by_page.setdefault(anchor.printed_page, []).append(anchor)
        pairs: list[tuple[MappingAnchor, MappingAnchor]] = []
        for group in by_page.values():
            if len({anchor.physical_page_number for anchor in group}) > 1:
                pairs.extend((group[index], group[index + 1]) for index in range(len(group) - 1))
        return pairs

    def segments(self) -> list[MappingSegment]:
        """Maximal runs of anchors (sorted by printed page) that agree on one offset.

        Anchors involved in a same-page conflict are excluded here; they are
        reported separately via conflicting_anchor_pairs().
        """
        conflicted = {id(anchor) for pair in self.conflicting_anchor_pairs() for anchor in pair}
        ordered = sorted(
            (anchor for anchor in self._normal_anchors() if id(anchor) not in conflicted),
            key=lambda anchor: anchor.printed_page,
        )
        result: list[MappingSegment] = []
        current: list[MappingAnchor] = []
        current_offset: int | None = None
        for anchor in ordered:
            offset = anchor.physical_page_number - anchor.printed_page
            if current and offset != current_offset:
                result.append(MappingSegment(current[0].printed_page, current[-1].printed_page, current_offset, list(current)))
                current = []
            current.append(anchor)
            current_offset = offset
        if current:
            result.append(MappingSegment(current[0].printed_page, current[-1].printed_page, current_offset, list(current)))
        return result

    def confirmed_segments(self) -> list[MappingSegment]:
        return [segment for segment in self.segments() if segment.confirmed]

    def unconfirmed_anchors(self) -> list[MappingAnchor]:
        return [anchor for segment in self.segments() if not segment.confirmed for anchor in segment.anchors]

    @property
    def offset(self) -> int | None:
        """The single offset for simple, single-segment mappings; None otherwise.

        Kept for backward-compatible display of the common case. Multi-segment
        or unresolved mappings should be inspected via segments()/resolve().
        """
        confirmed = self.confirmed_segments()
        if len(confirmed) == 1 and not self.unconfirmed_anchors() and not self.conflicting_anchor_pairs():
            return confirmed[0].offset
        return None

    def resolve(self, printed_page: int) -> ResolvedPage:
        override = self.exceptions.get(str(printed_page))
        if override is not None:
            return ResolvedPage(int(override), "anchor", "explicit exception")

        here = [anchor for anchor in self._normal_anchors() if anchor.printed_page == printed_page]
        if len({anchor.physical_page_number for anchor in here}) > 1:
            return ResolvedPage(None, "unresolved", f"anchors at printed page {printed_page} disagree on the physical page")
        if here:
            return ResolvedPage(here[0].physical_page_number, "anchor", here[0].label)

        confirmed = self.confirmed_segments()
        for segment in confirmed:
            if segment.printed_start <= printed_page <= segment.printed_end:
                return ResolvedPage(
                    printed_page + segment.offset, "segment",
                    f"segment {segment.printed_start}-{segment.printed_end} offset {segment.offset:+d}",
                )

        if len(confirmed) == 1:
            segment = confirmed[0]
            return ResolvedPage(
                printed_page + segment.offset, "extrapolated",
                f"extrapolated from segment {segment.printed_start}-{segment.printed_end} (offset {segment.offset:+d})",
            )
        if not confirmed:
            return ResolvedPage(None, "unresolved", "no confirmed segment covers this page (need at least two agreeing anchors)")
        return ResolvedPage(
            None, "unresolved",
            "page falls between confirmed segments with different offsets — add an anchor near this page",
        )

    def resolve_entry(self, entry: OutlineEntry) -> ResolvedPage:
        """Resolve an outline entry's physical page, preferring its own supplied
        physical_start/pdf_page_index (e.g. from JSON import) over anchor/segment
        inference when the two are internally consistent.

        An operator- or source-supplied, self-consistent physical/PDF-index pair is
        the strongest available evidence for that specific row -- stronger than an
        offset extrapolated or interpolated from anchors elsewhere in the book, which
        is what resolve() alone does. Anchors remain necessary for entries that don't
        carry their own physical_start (heading-detected entries, printed-TOC-only
        imports, manual rows), where they are still the only source of truth.
        """
        if (
            entry.physical_start is not None
            and entry.pdf_page_index is not None
            and entry.pdf_page_index == entry.physical_start - 1
        ):
            return ResolvedPage(entry.physical_start, "supplied", "resolved from imported physical_start/pdf_index")
        if entry.printed_start is None:
            return ResolvedPage(
                entry.physical_start, "physical_only" if entry.physical_start else "no_printed_page",
                "" if entry.physical_start else "no printed page or physical page to resolve",
            )
        return self.resolve(entry.printed_start)

    def physical_for(self, printed_page: int) -> int | None:
        return self.resolve(printed_page).physical_page

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["offset"] = self.offset
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PageMapping":
        value = dict(value)
        value.pop("offset", None)
        value["anchors"] = [MappingAnchor(**item) for item in value.get("anchors", [])]
        return cls(**value)


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    completed_at: str
    status: str
    book_id: str
    source_pdf_hash: str
    outline_hash: str
    page_mapping_hash: str
    tool_version: str
    expected_count: int
    written_count: int
    skipped_count: int
    failed_count: int
    output_location: str
    error_summary: str = ""


@dataclass
class ExtractionResult:
    record: RunRecord
    issues: list[ValidationIssue] = field(default_factory=list)

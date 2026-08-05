from __future__ import annotations

from pathlib import Path

from ..models import MappingAnchor, OutlineEntry, PageMapping, Severity, ValidationIssue
from .common import atomic_write_json, read_json, utc_now

SUGGESTED_ACTION: dict[str, str] = {
    "two_anchors_required": "Add at least two agreeing anchors.",
    "invalid_anchor": "Fix the anchor's printed/physical page — both must be positive.",
    "index_mismatch": "Re-add the anchor from the preview so its PDF index matches physical page minus one.",
    "anchor_out_of_range": "Remove or correct the anchor — its physical page exceeds the PDF length.",
    "offset_conflict": "Remove or mark one of the disagreeing anchors as an exception.",
    "segment_unconfirmed": "Add a second agreeing anchor near this page to confirm the segment.",
    "offset_unresolved": "Add at least two agreeing anchors to establish a confirmed segment.",
    "uncovered_entry": "Add an anchor near this printed page.",
}


def suggested_action(issue: ValidationIssue) -> str:
    return SUGGESTED_ACTION.get(issue.code, "")


class MappingService:
    def __init__(self, outline_dir: Path):
        self.outline_dir = outline_dir

    def path(self, book_id: str) -> Path:
        return self.outline_dir / f"{book_id}_page_mapping.json"

    def load(self, book_id: str) -> PageMapping:
        value = read_json(self.path(book_id))
        return PageMapping.from_dict(value) if value else PageMapping(book_id)

    def validate(
        self, mapping: PageMapping, page_count: int, entries: list[OutlineEntry] | None = None
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        normal_anchors = [anchor for anchor in mapping.anchors if not anchor.exception]
        # Anchors exist to resolve entries that don't already carry their own,
        # internally-consistent physical_start/pdf_page_index (e.g. from JSON import) --
        # requiring two agreeing anchors is pointless busywork for a book whose every
        # entry is already resolved that way. Unknown entries (entries is None) keep the
        # old always-require-anchors behavior rather than guessing.
        entries_need_anchors = entries is None or any(
            entry.include and entry.printed_start and mapping.resolve_entry(entry).method != "supplied"
            for entry in entries
        )
        if entries_need_anchors and len(normal_anchors) < 2:
            issues.append(ValidationIssue(Severity.BLOCKING, "two_anchors_required", "Verify the offset against at least two outline entries."))
        for anchor in mapping.anchors:
            if anchor.printed_page < 1 or anchor.physical_page_number < 1:
                issues.append(ValidationIssue(Severity.BLOCKING, "invalid_anchor", "Printed and physical pages must be positive."))
            if anchor.pdf_page_index != anchor.physical_page_number - 1:
                issues.append(ValidationIssue(Severity.BLOCKING, "index_mismatch", "PDF index must equal physical page minus one."))
            if page_count and anchor.physical_page_number > page_count:
                issues.append(ValidationIssue(Severity.BLOCKING, "anchor_out_of_range", "A mapped physical page exceeds the PDF length."))

        for first, second in mapping.conflicting_anchor_pairs():
            issues.append(ValidationIssue(
                Severity.BLOCKING, "offset_conflict",
                f"Anchors '{first.label}' and '{second.label}' both target printed page {first.printed_page} "
                f"but disagree on the physical page ({first.physical_page_number} vs {second.physical_page_number}).",
            ))

        for anchor in mapping.unconfirmed_anchors():
            issues.append(ValidationIssue(
                Severity.WARNING, "segment_unconfirmed",
                f"Anchor '{anchor.label}' (printed {anchor.printed_page}) is the only anchor at its offset; "
                "add a second agreeing anchor nearby to confirm this segment.",
            ))

        if entries_need_anchors and not mapping.confirmed_segments() and not mapping.exceptions:
            issues.append(ValidationIssue(Severity.BLOCKING, "offset_unresolved", "No confirmed printed-to-physical segment yet. Add at least two agreeing anchors."))

        if entries is not None:
            for entry in entries:
                if not entry.include or not entry.printed_start:
                    continue
                resolution = mapping.resolve_entry(entry)
                if resolution.physical_page is None:
                    issues.append(ValidationIssue(
                        Severity.BLOCKING, "uncovered_entry",
                        f"Section {entry.sno} '{entry.title}' (printed {entry.printed_start}) has no resolvable "
                        f"physical page: {resolution.detail}.",
                    ))

        if not any(item.severity == Severity.BLOCKING for item in issues):
            segments_desc = "; ".join(
                f"{segment.printed_start}-{segment.printed_end}: {segment.offset:+d}"
                for segment in mapping.confirmed_segments()
            ) or "no segments"
            issues.append(ValidationIssue(
                Severity.PASSED, "mapping_valid",
                f"{len(mapping.anchors)} anchor(s), {len(mapping.confirmed_segments())} confirmed segment(s) ({segments_desc}).",
            ))
        return issues

    def approve(
        self, mapping: PageMapping, page_count: int, note: str = "", entries: list[OutlineEntry] | None = None
    ) -> PageMapping:
        blocking = [item for item in self.validate(mapping, page_count, entries) if item.severity == Severity.BLOCKING]
        if blocking:
            raise ValueError("; ".join(item.message for item in blocking))
        mapping.approved = True
        mapping.approved_at = utc_now()
        mapping.reviewer_note = note
        atomic_write_json(self.path(mapping.book_id), mapping.to_dict())
        return mapping

    def save_draft(self, mapping: PageMapping) -> None:
        mapping.approved = False
        atomic_write_json(self.path(mapping.book_id), mapping.to_dict())

    def suggest_next_anchor(self, mapping: PageMapping, entries: list[OutlineEntry]) -> OutlineEntry | None:
        """The best next outline entry for the operator to verify and anchor.

        Pure arithmetic over the already-verified segment model — no PDF text
        search or confidence scoring. Prefers part/chapter-level entries, since
        those anchor the largest surrounding stretch of pages.
        """
        candidates = [
            entry for entry in entries
            if entry.include and entry.printed_start and mapping.resolve_entry(entry).physical_page is None
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda entry: (entry.kind not in {"part", "chapter"}, entry.printed_start))
        return candidates[0]

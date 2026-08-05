from __future__ import annotations

from collections import Counter

from ..models import BookRecord, OutlineEntry, PageMapping, Severity, ValidationIssue
from .common import sha256_file
from .mapping import MappingService
from .outlines import OutlineService


def preflight(
    book: BookRecord,
    entries: list[OutlineEntry],
    approval: object | None,
    mapping: PageMapping,
    outline_service: OutlineService,
    mapping_service: MappingService,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not book.path.exists():
        issues.append(ValidationIssue(Severity.BLOCKING, "pdf_missing", "Source PDF does not exist."))
        return issues
    actual_hash = sha256_file(book.path)
    if actual_hash != book.source_hash:
        issues.append(ValidationIssue(Severity.BLOCKING, "registered_hash_mismatch", "The registered source PDF has changed."))
    if approval is None or not getattr(approval, "approved", False):
        issues.append(ValidationIssue(Severity.BLOCKING, "outline_not_approved", "Outline not approved."))
    else:
        if getattr(approval, "source_pdf_hash", "") != actual_hash:
            issues.append(ValidationIssue(Severity.BLOCKING, "approval_pdf_mismatch", "PDF changed after outline approval."))
        _, clean, _ = outline_service.paths(book.book_id)
        if not clean.exists() or sha256_file(clean) != getattr(approval, "approved_outline_hash", ""):
            issues.append(ValidationIssue(Severity.BLOCKING, "outline_hash_mismatch", "Approved outline changed after approval."))
    issues.extend(item for item in outline_service.validate(entries, book.page_count) if item.severity != Severity.PASSED)
    issues.extend(item for item in mapping_service.validate(mapping, book.page_count, entries) if item.severity != Severity.PASSED)
    if not mapping.approved:
        issues.append(ValidationIssue(Severity.BLOCKING, "mapping_not_approved", "Page mapping unresolved or unapproved."))

    physical: list[int] = []
    filenames: list[str] = []
    from ...extract import slugify

    for entry in [item for item in entries if item.include]:
        page = mapping.resolve_entry(entry).physical_page
        if page is None or page < 1 or page > book.page_count:
            issues.append(ValidationIssue(Severity.BLOCKING, "mapped_page_invalid", f"Section {entry.sno} has no valid physical page."))
        else:
            physical.append(page)
        filenames.append(f"{entry.sno:03d}_{slugify(entry.title)}.txt")
    if any(right < left for left, right in zip(physical, physical[1:])):
        issues.append(ValidationIssue(Severity.BLOCKING, "non_monotonic_physical", "Physical starts must be monotonic unless represented by an explicit mapping exception."))
    collisions = [name for name, count in Counter(filenames).items() if count > 1]
    if collisions:
        issues.append(ValidationIssue(Severity.BLOCKING, "filename_collision", f"Output filenames collide: {', '.join(collisions)}"))
    if not issues:
        issues.append(ValidationIssue(Severity.PASSED, "preflight_passed", "All extraction checks passed."))
    return issues

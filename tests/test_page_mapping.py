import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from bookcorpusbuilder.gui.widgets.page_mapping import RESOLUTION_COLORS, PageMappingPanel
from bookcorpusbuilder.gui.widgets.pdf_preview import PdfTextPreview
from bookcorpusbuilder.gui.models import BookRecord, MappingAnchor, OutlineEntry, PageMapping
from bookcorpusbuilder.gui.services.mapping import MappingService
from bookcorpusbuilder.gui.services.outlines import OutlineService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _panel(window) -> PageMappingPanel:
    """PageMappingPanel now takes Structure Builder's shared PdfTextPreview instance
    instead of owning its own; a standalone preview here mirrors that contract for tests
    that only exercise the panel in isolation."""
    return PageMappingPanel(window, PdfTextPreview())


class FakeWindow:
    def __init__(self, root: Path, book: BookRecord):
        self.selected_book = book
        self.services = SimpleNamespace(
            outlines=OutlineService(root / "outlines"),
            mappings=MappingService(root / "outlines"),
        )

    def show_error(self, title, message, details=""):
        raise AssertionError(f"{title}: {message}\n{details}")


def _book(tmp_path: Path) -> BookRecord:
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"not a real pdf, only used as a path placeholder")
    return BookRecord("book-toc-less", "book.pdf", str(pdf_path), "deadbeef", pdf_path.stat().st_size, 40, "text-extractable")


def test_toc_less_heading_derived_entries_populate_the_entry_picker(app, tmp_path):
    """Regression test for the PageMappingPanel entry picker that used to filter
    out any outline entry lacking printed_start — which left the dropdown (and
    therefore the whole anchor-creation workflow) empty for any PDF whose table
    of contents didn't parse, since OutlineService.detect() gives heading-sourced
    entries physical_start but no printed_start."""
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Chapter One", kind="section", physical_start=5, pdf_page_index=4, source="body_heading"),
        OutlineEntry(sno=2, title="Chapter Two", kind="section", physical_start=20, pdf_page_index=19, source="body_heading"),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    assert screen.entry_combo.count() == 2, "TOC-less, heading-derived entries must still populate the picker"
    assert [screen.entry_combo.itemText(i).split(" · ")[0] for i in range(2)] == ["1. Chapter One", "2. Chapter Two"]


def test_mapping_preview_exposes_a_resolution_column(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Chapter One", kind="section", physical_start=5, pdf_page_index=4)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    headers = [screen.mapping_preview.horizontalHeaderItem(i).text() for i in range(screen.mapping_preview.columnCount())]
    assert "Resolution" in headers


def test_adding_an_anchor_from_a_heading_derived_entry_works(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Chapter One", kind="section", printed_start=1, physical_start=5, pdf_page_index=4)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()
    screen.select_entry(0)
    screen.printed.setValue(1)
    screen.physical.setValue(5)
    screen.add_anchor()

    assert len(screen.mapping.anchors) == 1
    assert screen.table.rowCount() == 1


def test_segments_table_reflects_confirmed_and_unconfirmed_segments(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b"),  # confirmed segment
        MappingAnchor(500, 550, 549, "c"),  # isolated, unconfirmed
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    assert screen.segments_table.rowCount() == 2
    statuses = {screen.segments_table.item(row, 4).text() for row in range(2)}
    assert statuses == {"confirmed", "needs a second anchor"}


def test_unresolved_entry_gets_a_red_resolution_cell(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Nowhere", kind="section", printed_start=500)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    cell = screen.mapping_preview.item(0, 4)
    assert cell.background().color().name() == RESOLUTION_COLORS["unresolved"]


def test_suggest_next_anchor_button_selects_the_recommended_entry(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Covered", kind="chapter", printed_start=1),
        OutlineEntry(sno=2, title="Needs anchor", kind="chapter", printed_start=500),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    # A single, unconfirmed anchor resolves only its own printed page (1) —
    # printed page 500 has no confirmed segment and stays unresolved.
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 3, 2, "a")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    screen.suggest_next()

    assert screen.entry_combo.currentIndex() == 1
    assert "Needs anchor" in screen.suggestion_label.text()


def test_suggested_next_panel_includes_reason_and_next_action(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Needs anchor", kind="chapter", printed_start=500)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.suggestion_label.text()
    assert "Next Recommended Verification" in text
    assert "Printed page" in text and "500" in text
    assert "Reason" in text
    assert "Next action" in text


def test_empty_state_guidance_shown_before_any_anchors_exist(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    assert "Begin by selecting the first chapter" in screen.status.text()


def test_empty_state_guidance_when_no_outline_entries_exist_yet(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)

    screen = _panel(window)
    screen.selection_changed()

    assert "No outline entries yet" in screen.status.text()


def test_completion_guidance_appears_once_everything_is_confirmed_but_not_yet_approved(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.status.text()
    assert "✓ All segments confirmed" in text
    assert "✓ All outline entries resolved" in text
    assert "Next Step" in text
    assert "Verify and approve mapping" in text


def test_segment_guidance_gives_a_bounded_range_when_a_later_segment_exists(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(10, 15, 14, "lone"),  # unconfirmed segment, printed 10-10, offset +5
        MappingAnchor(50, 50, 49, "x"), MappingAnchor(60, 60, 59, "y"),  # confirmed segment, printed 50-60, offset 0
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.segment_guidance.text()
    assert "Needs another verification anchor" in text
    assert "between printed pages 11 and 49" in text


def test_segment_guidance_is_open_ended_with_no_later_segment(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [MappingAnchor(10, 10, 9, "lone")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.segment_guidance.text()
    assert "anywhere after printed page 10" in text


def test_segment_selection_updates_guidance_without_a_full_rerender(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(10, 15, 14, "lone"),
        MappingAnchor(50, 50, 49, "x"), MappingAnchor(60, 60, 59, "y"),
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    assert "Needs another verification anchor" in screen.segment_guidance.text()

    screen.segments_table.setCurrentCell(1, 0)  # the confirmed segment
    assert "Confirmed" in screen.segment_guidance.text()


def test_adding_an_anchor_gives_acceptance_feedback_and_highlights_the_changed_rows(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    screen.printed.setValue(1); screen.physical.setValue(1)
    screen.add_anchor()
    assert "✓ Anchor accepted" in screen.anchor_feedback.text()
    assert "still needs one more anchor" in screen.anchor_feedback.text()
    assert screen.segments_table.item(0, 4).font().bold()
    assert screen.mapping_preview.item(0, 0).font().bold()  # Perspective, printed 1
    assert not screen.mapping_preview.item(1, 0).font().bold()  # Social Momentum, untouched

    screen.printed.setValue(2); screen.physical.setValue(2)
    screen.add_anchor()
    assert "Segment confirmed" in screen.anchor_feedback.text()
    assert screen.segments_table.item(0, 4).font().bold()  # merged 1-2 segment, still contains page 2
    assert not screen.mapping_preview.item(0, 0).font().bold()  # Perspective row no longer the latest change
    assert screen.mapping_preview.item(1, 0).font().bold()  # Social Momentum, printed 2, just anchored


def test_diagnostics_summary_shows_confirmed_warning_and_blocking_counts(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b"),  # confirmed segment, offset 0
        MappingAnchor(10, 15, 14, "lone"),  # unconfirmed, offset +5 -> a WARNING (segment_unconfirmed)
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.diagnostics_summary.text()
    assert "<b>Confirmed Segments</b><br>1" in text
    assert "<b>Warnings</b><br>1" in text
    assert "<b>Blocking Issues</b><br>0" in text
    assert screen.diagnostics_list.count() == 1
    assert "Unconfirmed anchor" in screen.diagnostics_list.item(0).text()


def test_conflict_diagnostic_explains_itself_and_highlights_both_anchors(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(5, 5, 4, "First reading"),
        MappingAnchor(5, 8, 7, "Second reading"),  # same printed page, disagreeing physical page
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    conflict_row = next(
        i for i in range(screen.diagnostics_list.count())
        if "Conflicting anchors" in screen.diagnostics_list.item(i).text()
    )
    screen.diagnostics_list.setCurrentRow(conflict_row)

    detail = screen.diagnostic_detail.text()
    assert "Conflict" in detail
    assert "disagree on which physical page" in detail
    assert "Suggested Action" in detail
    assert "Remove or mark one of the disagreeing anchors as an exception" in detail
    assert "First reading" in detail and "Second reading" in detail  # Affected Section

    assert screen.table.item(0, 0).font().bold()
    assert screen.table.item(1, 0).font().bold()

    # Selecting a different (or no) diagnostic clears the previous highlight.
    screen.diagnostics_list.clearSelection()
    assert not screen.table.item(0, 0).font().bold()
    assert not screen.table.item(1, 0).font().bold()
    assert screen.diagnostic_detail.text() == ""


def test_resolving_a_conflict_removes_it_from_diagnostics(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(5, 5, 4, "First reading"),
        MappingAnchor(5, 8, 7, "Second reading"),
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    assert any("Conflicting anchors" in screen.diagnostics_list.item(i).text() for i in range(screen.diagnostics_list.count()))

    screen.table.selectRow(1)  # the second, disagreeing anchor
    screen.remove_anchor()

    assert not any("Conflicting anchors" in screen.diagnostics_list.item(i).text() for i in range(screen.diagnostics_list.count()))


def test_approval_blocked_message_is_structured_with_reason_action_and_affected_section(app, tmp_path):
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"placeholder")
    book = BookRecord("book-gap", "book.pdf", str(pdf_path), "deadbeef", pdf_path.stat().st_size, 200, "text-extractable")
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1),
        OutlineEntry(sno=2, title="Between Bit", kind="chapter", printed_start=50),
        OutlineEntry(sno=3, title="Later Chapter", kind="chapter", printed_start=100),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    # Two confirmed segments with different offsets, and an entry (printed 50) that
    # falls in the gap between them -- unresolvable without a new anchor there.
    mapping = PageMapping(book.book_id, [
        MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b"),
        MappingAnchor(100, 150, 149, "c"), MappingAnchor(101, 151, 150, "d"),
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    with pytest.raises(AssertionError) as excinfo:
        screen.approve()

    message = str(excinfo.value)
    assert "Approval Blocked" in message
    assert "Reason" in message
    assert "doesn't fall inside any confirmed segment" in message
    assert "Action Required" in message
    assert "Add an anchor near this printed page." in message
    assert "Affected Section" in message
    assert "Between Bit" in message


def test_dashboard_shows_action_required_before_verification_is_complete(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1)]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.dashboard_summary.text()
    assert "<b>Verification Anchors</b><br>0" in text
    assert "<b>Confirmed Segments</b><br>0" in text
    assert "<b>Outline Entries</b><br>0 / 1" in text
    assert "ACTION REQUIRED" in text
    assert "READY FOR APPROVAL" not in text


def test_dashboard_shows_ready_for_approval_once_everything_resolves(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    text = screen.dashboard_summary.text()
    assert "<b>Verification Anchors</b><br>2" in text
    assert "<b>Confirmed Segments</b><br>1" in text
    assert "<b>Outline Entries</b><br>2 / 2" in text
    assert "<b>Blocking Issues</b><br>0" in text
    assert "READY FOR APPROVAL" in text


def test_dashboard_shows_success_summary_after_approval(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1, source="manual"),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2, source="manual"),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    screen.approve()

    text = screen.dashboard_summary.text()
    assert "<b>Mapping Approved</b>" in text
    assert "<b>Book</b><br>book.pdf" in text
    assert "<b>Verified Segments</b><br>1" in text
    assert "<b>Outline Entries</b><br>2" in text
    assert "READY FOR EXTRACTION" in text


def test_workflow_progress_reflects_lifecycle_state(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1, source="manual"),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2, source="manual"),
    ]
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, entries)
    window.services.outlines.approve(book, entries)

    screen = _panel(window)
    screen.selection_changed()
    text = screen.workflow_summary.text()
    assert "✓ Outline Approved" in text
    assert "□ Anchors Added" in text
    assert "□ Segments Confirmed" in text
    assert "□ Mapping Approved" in text

    screen.printed.setValue(1); screen.physical.setValue(1); screen.add_anchor()
    screen.printed.setValue(2); screen.physical.setValue(2); screen.add_anchor()
    text = screen.workflow_summary.text()
    assert "✓ Anchors Added" in text
    assert "✓ Segments Confirmed" in text
    assert "✓ Outline Fully Resolved" in text
    assert "✓ Diagnostics Clear" in text
    assert "□ Mapping Approved" in text

    screen.approve()
    assert "✓ Mapping Approved" in screen.workflow_summary.text()


def test_segments_table_confirmed_and_unconfirmed_rows_get_distinct_icons_and_shading(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(1, 3, 2, "a"), MappingAnchor(2, 4, 3, "b"),  # confirmed segment
        MappingAnchor(500, 550, 549, "c"),  # isolated, unconfirmed
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()

    confirmed_row = next(row for row in range(2) if screen.segments_table.item(row, 4).text() == "confirmed")
    unconfirmed_row = 1 - confirmed_row

    assert not screen.segments_table.item(confirmed_row, 0).icon().isNull()
    assert not screen.segments_table.item(unconfirmed_row, 0).icon().isNull()
    confirmed_bg = screen.segments_table.item(confirmed_row, 0).background().color().name()
    unconfirmed_bg = screen.segments_table.item(unconfirmed_row, 0).background().color().name()
    assert confirmed_bg != unconfirmed_bg
    assert confirmed_bg == RESOLUTION_COLORS["segment"]


def test_enter_in_the_printed_field_adds_the_anchor(app, tmp_path):
    """Sprint 14, requirement #2 ("Add Anchor ... -> Add"): pressing Enter in either
    page field should submit, matching Browser's existing search-field convention,
    instead of requiring a mouse click on "Add verification anchor" every time."""
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    screen = _panel(window)
    screen.selection_changed()

    screen.printed.setValue(5)
    screen.physical.setValue(7)
    screen.printed.lineEdit().returnPressed.emit()

    assert len(screen.mapping.anchors) == 1
    assert screen.mapping.anchors[0].printed_page == 5
    assert screen.mapping.anchors[0].physical_page_number == 7


def test_enter_in_the_physical_field_also_adds_the_anchor(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    screen = _panel(window)
    screen.selection_changed()

    screen.printed.setValue(2)
    screen.physical.setValue(3)
    screen.physical.lineEdit().returnPressed.emit()

    assert len(screen.mapping.anchors) == 1


def test_remove_anchor_selects_the_next_logical_row_and_reclaims_focus(app, tmp_path):
    """Sprint 14, requirement #5: remove_anchor() previously left both selection and
    keyboard focus wherever they happened to be after the table was rebuilt."""
    from PySide6.QtWidgets import QPushButton

    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [
        MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b"), MappingAnchor(3, 3, 2, "c"),
    ])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    screen.table.selectRow(1)

    remove_button = next(b for b in screen.findChildren(QPushButton) if b.text() == "Remove selected anchor")
    remove_button.setFocus()
    assert screen.focusWidget() is remove_button

    screen.remove_anchor()

    assert len(screen.mapping.anchors) == 2
    assert screen.table.currentRow() == 1  # the anchor that followed the removed one
    assert screen.focusWidget() is screen.table


def test_remove_last_anchor_leaves_no_selection_but_still_returns_focus(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a")])
    MappingService(tmp_path / "outlines").save_draft(mapping)

    screen = _panel(window)
    screen.selection_changed()
    screen.table.selectRow(0)

    screen.remove_anchor()

    assert len(screen.mapping.anchors) == 0
    assert screen.focusWidget() is screen.table

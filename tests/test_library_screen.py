import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QListWidget

from bookcorpusbuilder.gui.main_window import CURRENT_STATUS_LABELS, LibraryScreen
from bookcorpusbuilder.gui.models import OutlineEntry, RunRecord
from bookcorpusbuilder.gui.services.history import HistoryService
from bookcorpusbuilder.gui.services.library import LibraryService
from bookcorpusbuilder.gui.services.mapping import MappingService
from bookcorpusbuilder.gui.services.outlines import OutlineService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeWindow:
    def __init__(self, root: Path):
        self.selected_book = None
        self.services = SimpleNamespace(
            library=LibraryService(root / "input", root / "outlines" / "book_library.json"),
            outlines=OutlineService(root / "outlines"),
            mappings=MappingService(root / "outlines"),
            history=HistoryService(root / "output" / "run_history"),
        )
        self.errors = []
        self.notices = []
        # Mirrors the exact navigation/screens shape ExtractScreen's and HistoryScreen's own
        # tests already use for the same navigate-and-preselect pattern.
        self.navigation = QListWidget()
        self.navigation.addItems(["1", "2", "3", "4", "5", "6"])
        self.structure_builder = SimpleNamespace(tabs=SimpleNamespace(setCurrentIndex=lambda index: None))
        self.browser = SimpleNamespace(run_filter=QComboBox())
        self.screens = [None, self.structure_builder, None, self.browser]

    def show_error(self, title, message, details=""):
        self.errors.append((title, message, details))

    def show_notice(self, title, message):
        self.notices.append((title, message))

    def set_book(self, book):
        self.selected_book = book

    def run_task(self, function, callback, *args, **kwargs):
        callback(function(*args, **kwargs))


def _run_record(book_id: str, status: str = "completed", run_id: str = "run-1") -> RunRecord:
    return RunRecord(
        run_id=run_id, started_at="2026-08-05T10:00:00", completed_at="2026-08-05T10:05:00",
        status=status, book_id=book_id, source_pdf_hash="deadbeef", outline_hash="deadbeef",
        page_mapping_hash="deadbeef", tool_version="test", expected_count=3, written_count=3,
        skipped_count=0, failed_count=0, output_location=str(Path("runs") / run_id),
    )


def _select_files(paths):
    return patch(
        "bookcorpusbuilder.gui.main_window.QFileDialog.getOpenFileNames",
        return_value=([str(p) for p in paths], ""),
    )


def test_normal_pdf_import_is_copied_registered_and_selected(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert not window.notices
    assert (tmp_path / "input" / "book.pdf").exists()
    assert len(screen.records) == 1
    assert window.selected_book is not None
    assert window.selected_book.filename == "book.pdf"
    assert [i.row() for i in screen.table.selectionModel().selectedRows()] == [0]


def test_scanned_pdf_import_registers_despite_no_extractable_text(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with patch.object(window.services.library, "_inspect_pdf", return_value=(12, "likely-scanned")):
        with _select_files([source]):
            screen.add_pdfs()

    assert not window.errors
    assert len(screen.records) == 1
    assert screen.records[0].text_status == "likely-scanned"
    assert window.selected_book.filename == "scanned.pdf"


def test_filename_with_underscore_imports_cleanly(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "complete_book_DIR.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert (tmp_path / "input" / "complete_book_DIR.pdf").exists()
    assert window.selected_book.filename == "complete_book_DIR.pdf"


def test_filename_with_spaces_and_punctuation_imports_cleanly(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "My Book (Vol. 2) - draft!.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert (tmp_path / "input" / "My Book (Vol. 2) - draft!.pdf").exists()
    assert window.selected_book.filename == "My Book (Vol. 2) - draft!.pdf"


def test_duplicate_import_shows_persistent_notice_not_a_toast(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()
    with _select_files([source]):
        screen.add_pdfs()

    assert len(window.notices) == 1
    title, message = window.notices[0]
    assert "already" in message.lower()
    assert "book.pdf" in message
    assert not window.errors
    # still exactly one registered row -- the duplicate did not create a second entry
    assert len(screen.records) == 1


def test_readding_a_hidden_book_restores_it_instead_of_silently_failing(app, tmp_path):
    # This is the exact production scenario: a book is imported, then its
    # registration is removed (hidden). Re-selecting the same source file
    # through Add PDFs must bring it back, not silently do nothing.
    window = FakeWindow(tmp_path)
    source = tmp_path / "completebook_DIR.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()
    book_id = screen.records[0].book_id

    window.services.library.remove_registration(book_id)
    screen.refresh()
    assert screen.records == []  # hidden: no longer visible, matching the reported symptom

    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert not window.notices
    assert len(screen.records) == 1
    assert screen.records[0].book_id == book_id
    assert window.selected_book.book_id == book_id


def test_destination_already_exists_with_same_content_still_registers(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    (tmp_path / "input").mkdir(parents=True, exist_ok=True)
    (tmp_path / "input" / "book.pdf").write_bytes(source.read_bytes())

    screen = LibraryScreen(window)
    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert len(screen.records) == 1
    assert screen.records[0].filename == "book.pdf"


def test_destination_already_exists_with_different_content_is_disambiguated(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\nsource\n%%EOF\n")
    (tmp_path / "input").mkdir(parents=True, exist_ok=True)
    (tmp_path / "input" / "book.pdf").write_bytes(b"%PDF-1.4\nunrelated existing file\n%%EOF\n")

    # LibraryScreen's own construction triggers LibraryService.books(), which
    # self-heals by auto-registering any untracked *.pdf already sitting in
    # input_dir -- so the pre-placed "unrelated existing file" becomes its
    # own record before add_pdfs() ever runs. The two files never collide.
    screen = LibraryScreen(window)
    preexisting_id = screen.records[0].book_id
    with _select_files([source]):
        screen.add_pdfs()

    assert not window.errors
    assert (tmp_path / "input" / "book.pdf").exists()  # untouched
    assert len(screen.records) == 2
    imported = next(book for book in screen.records if book.book_id != preexisting_id)
    assert imported.filename == "book.pdf"
    assert imported.book_id in imported.pdf_path
    assert window.selected_book.book_id == imported.book_id


def test_copy_failure_shows_persistent_error_dialog_with_stage_and_filename(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with patch("bookcorpusbuilder.gui.services.library.shutil.copy2", side_effect=OSError("disk full")):
        with _select_files([source]):
            screen.add_pdfs()

    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert title == "Could not add PDF"
    assert "book.pdf" in message
    assert "copying into library" in details
    assert "disk full" in details
    assert not (tmp_path / "input" / "book.pdf").exists()
    assert not list((tmp_path / "input").glob(".*.importing"))
    assert screen.records == []


def test_copy_failure_error_dialog_includes_reason_and_recovery_guidance(app, tmp_path):
    """Sprint 15: the LibraryImportError branch's dialog message must carry the shared
    Reason/What-you-can-do structure, not just the bare "could not be added" sentence."""
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with patch("bookcorpusbuilder.gui.services.library.shutil.copy2", side_effect=OSError("disk full")):
        with _select_files([source]):
            screen.add_pdfs()

    assert len(window.errors) == 1
    _, message, details = window.errors[0]
    assert "<b>Reason</b>" in message
    assert "book.pdf could not be added to the library." in message
    assert "<b>What you can do</b>" in message
    assert "valid, readable PDF" in message
    # the technical diagnostics (failure stage, traceback) still live only in details
    assert "copying into library" in details
    assert "disk full" in details


def test_unexpected_failure_shows_reason_and_recovery_guidance(app, tmp_path):
    """Sprint 15: the bare `except Exception:` branch (no LibraryImportError stage
    info available) must still give the operator a Reason and next step, not just
    dump a raw exception."""
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with patch.object(window.services.library, "add", side_effect=RuntimeError("totally unexpected")):
        with _select_files([source]):
            screen.add_pdfs()

    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert title == "Could not add PDF"
    assert "<b>Reason</b>" in message
    assert "book.pdf could not be added to the library." in message
    assert "<b>What you can do</b>" in message
    assert "valid, readable PDF" in message
    assert "totally unexpected" in details


def test_registry_write_failure_leaves_no_orphan_pdf_or_partial_record(app, tmp_path):
    window = FakeWindow(tmp_path)
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")

    screen = LibraryScreen(window)
    with patch.object(window.services.library, "_save", side_effect=OSError("permission denied")):
        with _select_files([source]):
            screen.add_pdfs()

    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert "saving registry" in details
    assert not (tmp_path / "input" / "book.pdf").exists()
    assert not list((tmp_path / "input").glob(".*.importing"))
    registry_path = tmp_path / "outlines" / "book_library.json"
    assert not registry_path.exists()
    screen.refresh()
    assert screen.records == []


def test_unreadable_source_shows_persistent_error_dialog(app, tmp_path):
    window = FakeWindow(tmp_path)
    missing = tmp_path / "does-not-exist.pdf"

    screen = LibraryScreen(window)
    with _select_files([missing]):
        screen.add_pdfs()

    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert title == "Could not add PDF"
    assert "does-not-exist.pdf" in message
    assert "validating source" in details
    assert "Exists: False" in details


def _registered_book(window: FakeWindow, tmp_path: Path, name: str = "book.pdf"):
    source = tmp_path / name
    source.write_bytes(f"%PDF-1.4\n{name}\n%%EOF\n".encode())  # unique content -> unique book_id
    return window.services.library.add(source)


def _column(screen, row: int, label: str) -> str:
    headers = [screen.table.horizontalHeaderItem(i).text() for i in range(screen.table.columnCount())]
    return screen.table.item(row, headers.index(label)).text()


def test_project_status_and_next_action_for_a_freshly_registered_book(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    _registered_book(window, tmp_path)
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Registered"
    assert _column(screen, 0, "Next Action") == "Create Structure"
    assert _column(screen, 0, "Approved") == "No"


def test_next_action_distinguishes_drafted_from_never_started(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    draft, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(draft, [OutlineEntry(1, "Perspective", "chapter", 1)])
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Registered"  # still coarse-grained "Registered"
    assert _column(screen, 0, "Next Action") == "Approve Outline"  # but the action is now specific


def test_project_status_after_outline_approved(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Outline Ready"
    assert _column(screen, 0, "Next Action") == "Verify Mapping"
    assert _column(screen, 0, "Approved") == "Yes"


def test_approved_column_reflects_real_approval_not_stale_clean_file(app, tmp_path):
    """Regression test: revoke() never deletes the clean CSV, so the old 'Approved' column
    (driven by clean.exists()) kept showing Yes after a revoke. It must now track the real
    ApprovalMetadata.approved flag instead."""
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    window.services.outlines.revoke(book.book_id)
    screen.refresh()

    _, clean, _ = window.services.outlines.paths(book.book_id)
    assert clean.exists()  # the stale signal the old column used -- still there
    assert _column(screen, 0, "Approved") == "No"  # but the column now reports the truth
    assert _column(screen, 0, "Project Status") == "Registered"
    assert _column(screen, 0, "Next Action") == "Approve Outline"


def test_project_status_after_mapping_approved(app, tmp_path):
    from bookcorpusbuilder.gui.models import MappingAnchor, PageMapping

    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    window.services.mappings.approve(mapping, book.page_count, "", entries)
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Mapping Ready"
    assert _column(screen, 0, "Next Action") == "Run Extraction"
    assert _column(screen, 0, "Mapping") == "Verified"


def test_project_status_after_extraction_completed(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    window.services.history.save(_run_record(book.book_id))
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Extracted"
    assert _column(screen, 0, "Next Action") == "Browse Corpus"
    assert _column(screen, 0, "Extraction") == "Yes"


def test_a_failed_run_alone_does_not_count_as_extracted(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    window.services.history.save(_run_record(book.book_id, status="failed", run_id="run-failed"))
    screen.refresh()

    assert _column(screen, 0, "Project Status") == "Registered"
    assert _column(screen, 0, "Extraction") == "No"


def test_book_summary_panel_reflects_the_selected_books_full_lifecycle(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    screen.refresh()
    screen.table.selectRow(0)

    text = screen.summary.text()
    assert "book.pdf" in text
    assert "<b>Outline</b><br>Approved" in text
    assert "<b>Mapping</b><br>Unresolved" in text
    assert "✓ Registered" in text
    assert "✓ Outline" in text
    assert "✗ Mapping" in text
    assert "✗ Extracted" in text
    assert CURRENT_STATUS_LABELS["Verify Mapping"] in text
    assert "Next Action</b><br>Verify Mapping" in text


def test_summary_shows_placeholder_when_nothing_is_selected(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    assert "Select a book" in screen.summary.text()


def test_double_click_navigates_to_structure_builder_for_a_fresh_book(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    _registered_book(window, tmp_path)
    screen.refresh()
    screen.table.selectRow(0)

    screen.open_relevant_workspace(0, 0)

    assert window.navigation.currentRow() == 1  # Workspace 2: Structure Builder


def test_double_click_navigates_to_structure_builder_page_mapping_tab_once_outline_is_approved(app, tmp_path):
    """Page Alignment used to be its own workspace; it's now Structure Builder's
    "C. Page Mapping" tab, so a fresh outline approval should land on that tab
    within Structure Builder instead of navigating to a separate workspace row."""
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    screen.refresh()
    screen.table.selectRow(0)

    selected_tabs = []
    window.structure_builder.tabs.setCurrentIndex = selected_tabs.append

    screen.open_relevant_workspace(0, 0)

    assert window.navigation.currentRow() == 1  # Workspace 2: Structure Builder
    assert selected_tabs == [2]  # C. Page Mapping


def test_double_click_navigates_to_extract_once_mapping_is_approved(app, tmp_path):
    from bookcorpusbuilder.gui.models import MappingAnchor, PageMapping

    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    window.services.mappings.approve(mapping, book.page_count, "", entries)
    screen.refresh()
    screen.table.selectRow(0)

    screen.open_relevant_workspace(0, 0)

    assert window.navigation.currentRow() == 2  # Workspace 3: Extract


def test_double_click_navigates_to_browser_and_preselects_the_completed_run(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    window.services.history.save(_run_record(book.book_id, run_id="the-run"))
    window.browser.run_filter.addItem("the-run (completed)", "the-run")
    screen.refresh()
    screen.table.selectRow(0)

    screen.open_relevant_workspace(0, 0)

    assert window.navigation.currentRow() == 3  # Workspace 4: Corpus Browser
    assert window.browser.run_filter.currentData() == "the-run"


def test_empty_state_guidance_when_no_books_are_registered(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)

    assert "No books registered" in screen.empty_label.text()
    assert "Next Step" in screen.empty_label.text()
    assert "Add PDFs" in screen.empty_label.text()
    assert not screen.empty_label.isHidden()


def test_selection_changed_refreshes_the_cockpit_on_return_to_library(app, tmp_path):
    """The Library must reflect a change made in another workspace as soon as the operator
    switches back, not only after an explicit manual Refresh click."""
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    book = _registered_book(window, tmp_path)
    screen.refresh()
    assert _column(screen, 0, "Project Status") == "Registered"

    # Simulate an approval happening while the operator was in another workspace.
    entries = [OutlineEntry(1, "Perspective", "chapter", 1, source="manual")]
    window.services.outlines.approve(book, entries)

    screen.selection_changed()  # what MainWindow.navigate() calls on tab switch

    assert _column(screen, 0, "Project Status") == "Outline Ready"


def test_selection_persists_across_a_refresh(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = LibraryScreen(window)
    _registered_book(window, tmp_path, "a.pdf")
    _registered_book(window, tmp_path, "b.pdf")
    screen.refresh()
    screen.table.selectRow(1)
    selected_book = window.selected_book
    assert selected_book is not None

    screen.refresh()  # e.g. triggered by selection_changed() on tab re-entry

    assert window.selected_book.book_id == selected_book.book_id
    assert [i.row() for i in screen.table.selectionModel().selectedRows()] == [
        next(row for row, book in enumerate(screen.records) if book.book_id == selected_book.book_id)
    ]

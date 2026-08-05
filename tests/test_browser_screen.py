import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from bookcorpusbuilder.gui.main_window import BrowserScreen
from bookcorpusbuilder.gui.models import BookRecord
from bookcorpusbuilder.gui.services.history import HistoryService
from bookcorpusbuilder.gui.services.library import LibraryService
from bookcorpusbuilder.gui.services.search import CorpusSearchService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeWindow:
    def __init__(self, root: Path):
        self.selected_book = None
        self.services = SimpleNamespace(
            library=LibraryService(root / "input", root / "outlines" / "book_library.json"),
            search=CorpusSearchService(root / "output"),
            history=HistoryService(root / "output" / "run_history"),
        )

    def show_error(self, title, message, details=""):
        raise AssertionError(f"{title}: {message}\n{details}")


def _seed_corpus(root: Path, book_id: str):
    jsonl_dir = root / "output" / "runs" / "run-1" / "jsonl"
    jsonl_dir.mkdir(parents=True)
    record = {
        "book_id": book_id, "sno": 1, "title": "Chapter One", "kind": "chapter",
        "printed_start": 5, "physical_start": 7, "physical_end": 9,
        "source_pdf_hash": "deadbeef", "run_id": "run-1",
        "text": "the sovereignty of nations was tested",
    }
    (jsonl_dir / "book_sections.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")


def test_selecting_a_result_jumps_the_preview_to_its_source_page(app, tmp_path):
    window = FakeWindow(tmp_path)
    pdf_path = tmp_path / "original.pdf"
    pdf_path.write_bytes(b"placeholder pdf bytes")
    # A real page count matters here: PdfTextPreview.jump_to() clamps to it, so a
    # placeholder file's real (unreadable -> 0) page count would mask the feature
    # under test. Stub library.get() with a realistic BookRecord instead of relying
    # on PDF inspection of a non-PDF fixture.
    book = BookRecord("book-1", "original.pdf", str(pdf_path), "deadbeef", 10, 40, "text-extractable")
    _seed_corpus(tmp_path, book.book_id)

    screen = BrowserScreen(window)
    screen.query.setText("sovereignty")
    with patch.object(window.services.library, "get", return_value=book):
        screen.search()
        assert len(screen.items) == 1
        screen.results.setCurrentRow(0)

    assert screen.preview.pdf_path == book.path
    assert screen.preview.page.value() == 7
    assert "Chapter One" in screen.preview.context.text()


def test_missing_book_shows_a_graceful_message_instead_of_crashing(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_corpus(tmp_path, "book-does-not-exist")

    screen = BrowserScreen(window)
    screen.query.setText("sovereignty")
    screen.search()
    screen.results.setCurrentRow(0)

    assert "unavailable" in screen.preview.context.text()


def _seed_multi_section_run(root: Path, book_id: str, run_id: str = "run-1", n: int = 3):
    jsonl_dir = root / "output" / "runs" / run_id / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(1, n + 1):
        lines.append(json.dumps({
            "book_id": book_id, "pdf": "completebook_DIR.pdf", "sno": i, "title": f"Section {i}",
            "kind": "chapter", "printed_start": 10 * i, "printed_end": 10 * i + 5,
            "physical_start": 10 * i + 2, "physical_end": 10 * i + 7,
            "source_pdf_hash": "deadbeef", "run_id": run_id,
            "text": f"First paragraph of section {i}.\n\nSecond paragraph of section {i} has more words in it.",
        }))
    (jsonl_dir / "book_sections.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _history_run_record(book_id: str, run_id: str = "run-1", status: str = "completed"):
    from bookcorpusbuilder.gui.models import RunRecord
    return RunRecord(
        run_id=run_id, started_at="2026-08-05T18:42:00", completed_at="2026-08-05T18:45:00",
        status=status, book_id=book_id, source_pdf_hash="deadbeef", outline_hash="deadbeef",
        page_mapping_hash="deadbeef", tool_version="test", expected_count=3,
        written_count=3, skipped_count=0, failed_count=0, output_location=str(Path("runs") / run_id),
    )


def test_reading_header_shows_structured_fields_from_existing_metadata(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)
    window.services.history.save(_history_run_record("book-1"))

    screen = BrowserScreen(window)
    screen.search()

    text = screen.metadata.text()
    assert "<b>Book</b><br>completebook_DIR.pdf" in text
    assert "<b>Run</b><br>2026-08-05 18:42:00" in text
    assert "<b>Section</b><br>Section 1" in text
    assert "<b>Printed Pages</b><br>10–15" in text
    assert "<b>Physical Pages</b><br>12–17" in text
    assert "<b>Kind</b><br>chapter" in text
    assert "<b>Source Hash</b><br>deadbeef" in text


def test_word_count_is_computed_from_the_already_loaded_section_text(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)

    screen = BrowserScreen(window)
    screen.search()

    expected = len(screen.items[0]["text"].split())
    assert f"<b>Words</b><br>{expected}" in screen.metadata.text()


def test_copy_text_still_returns_the_full_plain_text_after_html_rendering(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)

    screen = BrowserScreen(window)
    screen.search()

    original = screen.items[0]["text"]
    copied = screen.text.toPlainText()
    # Paragraph breaks may render as blank lines, but no words are lost or altered.
    assert copied.split() == original.split()


def test_previous_next_navigation_moves_through_results_and_disables_at_the_edges(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)

    screen = BrowserScreen(window)
    screen.search()

    assert len(screen.items) == 3
    assert screen.results.currentRow() == 0
    assert not screen.prev_button.isEnabled()
    assert screen.next_button.isEnabled()
    assert "Section 1 of 3" in screen.reading_status.text()

    screen.next_button.click()
    assert screen.results.currentRow() == 1
    assert "Section 2 of 3" in screen.reading_status.text()
    assert "Section 2" in screen.metadata.text()
    assert screen.prev_button.isEnabled()
    assert screen.next_button.isEnabled()

    screen.next_button.click()
    assert screen.results.currentRow() == 2
    assert "Section 3 of 3" in screen.reading_status.text()
    assert not screen.next_button.isEnabled()  # last section -- nothing further to move to
    assert screen.prev_button.isEnabled()

    screen.prev_button.click()
    assert screen.results.currentRow() == 1
    assert "Section 2 of 3" in screen.reading_status.text()


def test_reading_status_shows_the_selected_runs_status(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)
    window.services.history.save(_history_run_record("book-1", status="completed"))

    screen = BrowserScreen(window)
    screen.search()

    assert "Run: Completed" in screen.reading_status.text()


def test_navigation_status_and_buttons_clear_when_there_are_no_results(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = BrowserScreen(window)
    screen.query.setText("nothing will match this")
    screen.search()

    assert screen.reading_status.text() == ""
    assert not screen.prev_button.isEnabled()
    assert not screen.next_button.isEnabled()


def test_empty_state_when_no_extractions_exist_at_all(app, tmp_path):
    window = FakeWindow(tmp_path)
    screen = BrowserScreen(window)

    screen.search()

    assert "No completed extractions yet" in screen.metadata.text()


def test_empty_state_when_the_run_has_no_sections(app, tmp_path):
    window = FakeWindow(tmp_path)
    run_dir = tmp_path / "output" / "runs" / "run-empty" / "jsonl"
    run_dir.mkdir(parents=True)
    (run_dir / "book_sections.jsonl").write_text("", encoding="utf-8")

    screen = BrowserScreen(window)
    # Populate/select the run filter without going through _run_selected() (which also
    # persists browser.last_run via a settings service this FakeWindow doesn't provide,
    # matching the existing tests' convention of stubbing only what's under test).
    screen.run_filter.blockSignals(True)
    screen.run_filter.addItem("run-empty", "run-empty")
    screen.run_filter.setCurrentIndex(screen.run_filter.count() - 1)
    screen.run_filter.blockSignals(False)
    screen.search()

    assert "This run has no extracted sections" in screen.metadata.text()


def test_empty_state_when_filters_match_nothing(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)

    screen = BrowserScreen(window)
    # has_runs (the branch this empty state depends on) is driven by run_filter's contents,
    # which selection_changed() normally populates; seed it directly here since this
    # FakeWindow (matching the file's existing convention) doesn't provide a settings
    # service for selection_changed()'s browser.last_run persistence.
    screen.run_filter.blockSignals(True)
    screen.run_filter.addItem("run-1", "run-1")
    screen.run_filter.blockSignals(False)
    screen.query.setText("a phrase that does not appear anywhere")
    screen.search()

    assert "No sections match the current search and filters" in screen.metadata.text()


def _history_run_record_with_count(written_count: int):
    from bookcorpusbuilder.gui.models import RunRecord
    return RunRecord(
        run_id="run-1", started_at="2026-08-05T18:42:00", completed_at="2026-08-05T18:45:00",
        status="completed", book_id="book-1", source_pdf_hash="deadbeef", outline_hash="deadbeef",
        page_mapping_hash="deadbeef", tool_version="test", expected_count=written_count,
        written_count=written_count, skipped_count=0, failed_count=0, output_location="runs/run-1",
    )


def test_search_summary_shows_matching_count_and_query(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)
    # No run selected (no RunRecord.written_count available) -- exercises the generic
    # "N matching sections" line rather than the "Showing X of Y" branch, which has its
    # own dedicated test below.
    screen = BrowserScreen(window)
    screen.query.setText("Section 1")
    screen.search()

    text = screen.search_summary.text()
    assert "Search Results" in text
    assert "matching section" in text
    assert "“Section 1”" in text


def test_search_summary_shows_showing_x_of_y_when_narrowed_by_a_filter(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)
    window.services.history.save(_history_run_record_with_count(3))

    screen = BrowserScreen(window)
    screen.run_filter.blockSignals(True); screen.run_filter.addItem("run-1", "run-1"); screen.run_filter.setCurrentIndex(1); screen.run_filter.blockSignals(False)
    screen.query.setText("Section 1")  # matches only 1 of the 3 real sections
    screen.search()

    assert len(screen.items) == 1
    assert "Showing <b>1</b> of 3 sections" in screen.search_summary.text()


def test_search_summary_shows_run_date_when_a_run_is_selected(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=1)
    window.services.history.save(_history_run_record("book-1"))

    screen = BrowserScreen(window)
    screen.run_filter.blockSignals(True); screen.run_filter.addItem("run-1", "run-1"); screen.run_filter.setCurrentIndex(1); screen.run_filter.blockSignals(False)
    screen.search()

    assert "<b>Run</b><br>2026-08-05 18:42:00" in screen.search_summary.text()


def test_search_summary_flags_filter_active_only_when_a_filter_is_set(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)

    screen = BrowserScreen(window)
    screen.search()
    assert "Filter Active" not in screen.search_summary.text()

    screen.query.setText("Section 1")
    screen.search()
    assert "Filter Active" in screen.search_summary.text()


def test_clear_search_restores_the_full_list_and_resets_filters(app, tmp_path):
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)

    screen = BrowserScreen(window)
    screen.query.setText("Section 1")
    screen.kind.setCurrentIndex(screen.kind.findData("chapter"))
    screen.search()
    assert len(screen.items) == 1

    screen.clear_search()

    assert screen.query.text() == ""
    assert screen.kind.currentData() == ""
    assert len(screen.items) == 3
    assert "Filter Active" not in screen.search_summary.text()


def test_selecting_a_different_section_does_not_clear_the_active_search(app, tmp_path):
    """Requirement #5 (Search State Preservation): this already worked before Sprint 11 --
    show_result()/Previous/Next never call search() -- verified here as a regression test
    rather than changed, per the brief's own Engineering Guidance."""
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)

    screen = BrowserScreen(window)
    screen.query.setText("Section")  # matches all 3 -- keeps the scenario simple
    screen.search()
    assert len(screen.items) == 3

    screen.next_button.click()
    screen.next_button.click()

    assert screen.query.text() == "Section"
    assert len(screen.items) == 3
    assert screen.results.currentRow() == 2


def test_current_result_position_already_matches_the_filtered_set_not_the_full_corpus(app, tmp_path):
    """Requirement #2 (Search Context): Sprint 10's reading_status already reports position
    within self.items, the current (possibly filtered) result set -- so a search narrowing
    to 1 of 3 sections correctly shows "1 of 1", not "1 of 3". Documented via regression
    test rather than adding a duplicate "Current Result" widget."""
    window = FakeWindow(tmp_path)
    _seed_multi_section_run(tmp_path, "book-1", n=3)

    screen = BrowserScreen(window)
    screen.query.setText("Section 1")
    screen.search()

    assert len(screen.items) == 1
    assert "Section 1 of 1" in screen.reading_status.text()


def test_printed_page_range_labels_have_explicit_buddies(app, tmp_path):
    """Sprint 14, requirement #8: QFormLayout.addRow(str, widget) auto-sets a label's
    buddy, but these two labels sit in a plain QHBoxLayout instead, so the accessibility
    association has to be set explicitly."""
    window = FakeWindow(tmp_path)
    screen = BrowserScreen(window)

    from PySide6.QtWidgets import QLabel
    printed_from = next(label for label in screen.findChildren(QLabel) if label.text() == "Printed from")
    printed_to = next(label for label in screen.findChildren(QLabel) if label.text() == "to")

    assert printed_from.buddy() is screen.page_from
    assert printed_to.buddy() is screen.page_to

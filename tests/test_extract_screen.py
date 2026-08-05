import os
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QListWidget

from bookcorpusbuilder.gui.main_window import ExtractScreen
from bookcorpusbuilder.gui.models import BookRecord, MappingAnchor, OutlineEntry, PageMapping
from bookcorpusbuilder.gui.services.common import sha256_file
from bookcorpusbuilder.gui.services.extraction import ExtractionService
from bookcorpusbuilder.gui.services.history import HistoryService
from bookcorpusbuilder.gui.services.mapping import MappingService
from bookcorpusbuilder.gui.services.outlines import OutlineService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeWindow:
    def __init__(self, root: Path, book: BookRecord):
        self.selected_book = book
        outlines = OutlineService(root / "outlines")
        mappings = MappingService(root / "outlines")
        history = HistoryService(root / "output" / "run_history")
        self.services = SimpleNamespace(
            settings=SimpleNamespace(minimum_chars=1, output_dir=str(root / "output")),
            outlines=outlines,
            mappings=mappings,
            history=history,
            extraction=ExtractionService(root / "output", history, outlines, mappings),
        )
        self.navigation = QListWidget()
        self.navigation.addItems(["1", "2", "3", "4", "5", "6"])
        self.structure_builder = SimpleNamespace(tabs=SimpleNamespace(setCurrentIndex=lambda index: None))
        self.browser = SimpleNamespace(run_filter=QComboBox())
        self.screens = [None, self.structure_builder, None, self.browser]
        self.errors = []

    def show_error(self, title, message, details=""):
        self.errors.append((title, message, details))

    def run_task(self, function, callback, *args, with_progress=False, progress_slot=None, on_failure=None, **kwargs):
        """Mirrors the real MainWindow.run_task()'s try/except/on_failure dispatch
        (Sprint 13) synchronously, so failure-path tests exercise the same contract
        without needing a real QThread."""
        if with_progress:
            kwargs["progress"] = progress_slot
        try:
            result = function(*args, **kwargs)
        except Exception as exc:
            details = traceback.format_exc()
            if on_failure:
                on_failure(str(exc), details)
            self.show_error(
                "Task Failed",
                f"<b>Reason</b><br>{exc}<br><br><b>What you can do</b><br>Review the reason above, then try again.",
                details,
            )
            return
        callback(result)


def _book(tmp_path: Path, page_count: int = 2) -> BookRecord:
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"not a real pdf, only used as a path placeholder")
    return BookRecord("book-extract", "book.pdf", str(pdf_path), sha256_file(pdf_path), pdf_path.stat().st_size, page_count, "text-extractable")


def _approved_context(tmp_path, book):
    entries = [
        OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1, source="manual"),
        OutlineEntry(sno=2, title="Social Momentum", kind="chapter", printed_start=2, source="manual"),
    ]
    window = FakeWindow(tmp_path, book)
    window.services.outlines.approve(book, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(2, 2, 1, "b")])
    window.services.mappings.approve(mapping, book.page_count, "", entries)
    return window


def _fake_pdfplumber_module(page_texts):
    pages = [SimpleNamespace(extract_text=lambda t=text: t) for text in page_texts]

    class _Pdf:
        def __enter__(self_inner):
            return SimpleNamespace(pages=pages)

        def __exit__(self_inner, *_args):
            return False

    return SimpleNamespace(open=lambda *_args, **_kwargs: _Pdf())


def test_readiness_panel_shows_ready_for_extraction_when_dry_run_passes(app, tmp_path):
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)

    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()

    text = screen.readiness.text()
    assert "READY FOR EXTRACTION" in text
    assert "SAFE TO EXTRACT" in text
    assert "Approved" in text
    assert screen.readiness_output.text().startswith("Output folder:")
    assert screen.extract.isEnabled()


def test_readiness_panel_shows_warnings_without_blocking_extraction(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    # An unrecognized "kind" is a WARNING (outline_service.validate), not BLOCKING,
    # so approval and the dry run should both still succeed.
    entries = [OutlineEntry(sno=1, title="Perspective", kind="unusual", printed_start=1)]
    window.services.outlines.approve(book, entries)
    mapping = PageMapping(book.book_id, [MappingAnchor(1, 1, 0, "a"), MappingAnchor(1, 1, 0, "b")])
    window.services.mappings.approve(mapping, book.page_count, "", entries)

    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()

    text = screen.readiness.text()
    assert "READY FOR EXTRACTION" in text
    assert "SAFE TO EXTRACT" in text
    assert "Warnings" in text
    assert "unknown kind" in text
    assert screen.extract.isEnabled()


def test_readiness_panel_shows_blocked_state_when_mapping_is_not_approved(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    entries = [OutlineEntry(sno=1, title="Perspective", kind="chapter", printed_start=1)]
    window.services.outlines.approve(book, entries)
    # Mapping intentionally left unapproved.

    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()

    text = screen.readiness.text()
    assert "NOT READY" in text
    assert "BLOCKED" in text
    assert not screen.extract.isEnabled()


def test_progress_checklist_and_completion_summary_after_extraction(app, tmp_path):
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()

    fake_module = _fake_pdfplumber_module(["Perspective text", "Social Momentum text"])
    with patch.dict(sys.modules, {"pdfplumber": fake_module}):
        screen.start()

    assert not window.errors, window.errors
    checklist_items = [screen.checklist.item(i).text() for i in range(screen.checklist.count())]
    assert checklist_items == ["✓ Perspective", "✓ Social Momentum"]
    assert screen.progress_state.text() == "✓ Extraction Complete"

    summary = screen.summary.text()
    for expected in ("Extraction Completed", "Sections expected", "Sections written", "Elapsed time", "COMPLETED"):
        assert expected in summary
    assert screen.summary_output.text().startswith("Run output:")
    assert screen.summary_output.toolTip() == screen._last_record.output_location
    assert all(button.isEnabled() for button in screen.next_step_buttons)
    assert not screen.cancel_button.isEnabled()


def test_skipped_sections_are_marked_distinctly_in_the_checklist(app, tmp_path):
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.minimum.setValue(50)  # both fake pages are shorter than this, so both are skipped
    screen.dry_run()

    fake_module = _fake_pdfplumber_module(["short", "text"])
    with patch.dict(sys.modules, {"pdfplumber": fake_module}):
        screen.start()

    checklist_items = [screen.checklist.item(i).text() for i in range(screen.checklist.count())]
    assert checklist_items == ["⊘ Perspective", "⊘ Social Momentum"]
    assert screen._last_record.skipped_count == 2


def test_open_in_browser_navigates_and_preselects_the_run_just_extracted(app, tmp_path):
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()
    fake_module = _fake_pdfplumber_module(["Perspective text", "Social Momentum text"])
    with patch.dict(sys.modules, {"pdfplumber": fake_module}):
        screen.start()
    window.browser.run_filter.addItem("run label", screen._last_record.run_id)

    screen.open_in_browser()

    assert window.navigation.currentRow() == 3
    assert window.browser.run_filter.currentData() == screen._last_record.run_id


def test_open_output_and_run_folder_target_the_right_paths(app, tmp_path):
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()
    fake_module = _fake_pdfplumber_module(["Perspective text", "Social Momentum text"])
    with patch.dict(sys.modules, {"pdfplumber": fake_module}):
        screen.start()

    with patch("bookcorpusbuilder.gui.main_window.open_path") as opened:
        screen.open_output_folder()
        screen.open_run_folder()

    assert opened.call_count == 2
    first_call, second_call = opened.call_args_list
    assert first_call.args[0] == Path(tmp_path / "output")
    assert second_call.args[0] == Path(screen._last_record.output_location)


def test_progress_state_starts_as_ready_using_the_shared_task_vocabulary(app, tmp_path):
    book = _book(tmp_path)
    window = FakeWindow(tmp_path, book)
    screen = ExtractScreen(window)

    assert screen.progress_state.text() == "Ready"


def _failing_pdfplumber_module(message: str):
    def _raise(*_args, **_kwargs):
        raise RuntimeError(message)
    return SimpleNamespace(open=_raise)


def test_a_real_extraction_failure_resets_the_screens_stuck_ui_state(app, tmp_path):
    """Sprint 13 regression test for the bug Sprint 3 identified and deferred: a failed
    background task used to bypass the workspace's own callback entirely (only the
    generic error dialog fired via worker.failed), leaving Extract's Cancel button,
    progress state, and Completion Summary stuck in their mid-run state forever. Now
    MainWindow.run_task()'s on_failure hook lets the screen reset itself too."""
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()
    assert screen.extract.isEnabled()

    fake_module = _failing_pdfplumber_module("simulated PDF read failure")
    with patch.dict(sys.modules, {"pdfplumber": fake_module}):
        screen.start()

    # The shared, centralized dialog fired with the real exception message...
    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert title == "Task Failed"
    assert "simulated PDF read failure" in message
    assert "What you can do" in message
    assert details  # the traceback is preserved, not suppressed

    # ...and the screen's own in-progress UI state was reset, not left stuck mid-run.
    assert not screen.cancel_button.isEnabled()
    assert screen.progress_state.text() == "✗ Task Failed"
    summary = screen.summary.text()
    assert "Task Failed" in summary
    assert "simulated PDF read failure" in summary
    assert "Nothing was written to your output folder" in summary
    assert not any(button.isEnabled() for button in screen.next_step_buttons)

    # The real, existing transactional guarantee this message relies on: a failed run
    # never promotes a temporary directory to the real run output.
    assert list((tmp_path / "output" / "runs").glob("*")) == []

    # A real run-history record was still written for the failed attempt (existing
    # ExtractionService behaviour, untouched) -- this sprint didn't change that.
    records = window.services.history.records(book.book_id)
    assert len(records) == 1
    assert records[0].status == "failed"
    assert "simulated PDF read failure" in records[0].error_summary


def test_start_without_a_selected_book_shows_reason_and_recovery_guidance(app, tmp_path):
    """Sprint 15: start()'s own pre-flight guard (context() raising before the
    background task is even started) must give the same Reason/What-you-can-do
    structure as every other error path, reusing the screen's existing idle-state
    guidance as the recovery step."""
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    window.selected_book = None  # simulates calling start() before context() can succeed

    screen.start()

    assert len(window.errors) == 1
    title, message, details = window.errors[0]
    assert title == "Extraction could not start"
    assert "<b>Reason</b>" in message
    assert "Select a book first." in message
    assert "<b>What you can do</b>" in message
    assert screen.IDLE_MESSAGE in message
    assert details  # traceback preserved, not suppressed


def test_a_second_attempt_after_a_failure_can_still_succeed(app, tmp_path):
    """Confirms the failure path doesn't strand the screen -- a fresh dry run + start
    after a failure completes normally, exactly like any first attempt would."""
    book = _book(tmp_path)
    window = _approved_context(tmp_path, book)
    screen = ExtractScreen(window)
    screen.output.setText(str(tmp_path / "output"))
    screen.dry_run()

    with patch.dict(sys.modules, {"pdfplumber": _failing_pdfplumber_module("first attempt fails")}):
        screen.start()
    assert screen.progress_state.text() == "✗ Task Failed"

    screen.dry_run()  # the existing, required re-validation step before retrying
    assert screen.extract.isEnabled()
    with patch.dict(sys.modules, {"pdfplumber": _fake_pdfplumber_module(["Perspective text", "Social Momentum text"])}):
        screen.start()

    assert screen.progress_state.text() == "✓ Extraction Complete"
    assert "COMPLETED" in screen.summary.text()
    assert all(button.isEnabled() for button in screen.next_step_buttons)

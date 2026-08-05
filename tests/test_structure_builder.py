import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QStatusBar,
)

from bookcorpusbuilder.gui.models import BookRecord, OutlineEntry
from bookcorpusbuilder.gui.services.common import sha256_file, stable_book_id
from bookcorpusbuilder.gui.services.mapping import MappingService
from bookcorpusbuilder.gui.services.outlines import KINDS, OutlineService
from bookcorpusbuilder.gui.widgets.structure_builder import StructureBuilder


class FakeWindow:
    def __init__(self, root):
        self.selected_book = None
        self.services = SimpleNamespace(
            outlines=OutlineService(root / "outlines"),
            mappings=MappingService(root / "outlines"),
        )
        self._status = QStatusBar()
        self.navigation = SimpleNamespace(setCurrentRow=lambda _row: None)

    def statusBar(self):
        return self._status

    def show_error(self, title, message, details=""):
        raise AssertionError(f"{title}: {message}\n{details}")

    def run_task(self, function, callback, *args, **kwargs):
        callback(function(*args, **kwargs))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def builder_context(app):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "book.pdf"
        source.write_bytes(b"disposable widget test pdf")
        digest = sha256_file(source)
        book = BookRecord(
            stable_book_id(digest), "book.pdf", str(source), digest,
            source.stat().st_size, 100, "text-extractable",
        )
        window = FakeWindow(root)
        builder = StructureBuilder(window)
        yield builder, window, book
        builder.deleteLater()


def test_paste_panel_empty_state_and_parse_preview(builder_context):
    builder, window, book = builder_context
    assert builder.paste_text.objectName() == "pasteOutlineEditor"
    assert "Import JSON…" in [button.text() for button in builder.findChildren(QPushButton)]
    assert "Generate with Ollama…" in [button.text() for button in builder.findChildren(QPushButton)]
    assert "No book selected" in builder.candidate_empty.text()
    window.selected_book = book
    builder.selection_changed()
    builder.paste_text.setPlainText("Chapter One\nPerspective ........ 1")
    builder.parse_preview()
    assert builder.candidate_table.rowCount() == 1
    assert builder.candidate_records[0].title == "Chapter One Perspective"
    assert builder.table.rowCount() == 0


def test_accept_creates_draft_without_bypassing_preview(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.selection_changed()
    builder.paste_text.setPlainText("Perspective ........ 1")
    builder.parse_preview()
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        builder.create_new_outline()
    draft, clean, _ = window.services.outlines.paths(book.book_id)
    assert draft.exists()
    assert not clean.exists()
    assert builder.table.rowCount() == 1
    assert window.services.outlines.load(draft)[0].source == "pasted_outline"
    provenance = window.services.outlines.candidate_provenance_path(book.book_id)
    assert provenance.exists()
    assert "Perspective ........ 1" in provenance.read_text(encoding="utf-8")


def test_merge_conflict_keeps_draft_by_default(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    draft_path, _, _ = window.services.outlines.paths(book.book_id)
    window.services.outlines.save(
        draft_path, [OutlineEntry(1, "Perspective", "chapter", 4)]
    )
    builder.selection_changed()
    builder.paste_text.setPlainText("Perspective 1")
    builder.parse_preview()
    with patch.object(builder, "merge_preview_dialog", return_value={}):
        builder.merge_into_draft()
    assert builder.entries()[0].printed_start == 4


def test_editing_approved_row_invalidates_approval(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)
    builder.table.item(0, 2).setText("Edited Perspective")
    assert window.services.outlines.approval(book.book_id).approved is False


def test_editing_an_approved_row_shows_positive_invalidation_feedback(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)
    builder.table.item(0, 2).setText("Edited Perspective")
    message = window.statusBar().currentMessage()
    assert "Approval has been cleared" in message
    assert "approve again" in message


def test_duplicate_row_preserves_fields_and_selects_the_new_row(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", printed_start=1, level=2),
        OutlineEntry(2, "Social Momentum", "chapter", printed_start=2),
    ]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    builder.duplicate_row()

    assert builder.table.rowCount() == 3
    assert builder.table.currentRow() == 1  # the operator lands on the new duplicate, not the original
    duplicated = builder.entries()[1]
    assert duplicated.title == "Perspective"
    assert duplicated.kind == "chapter"
    assert duplicated.level == 2
    assert duplicated.printed_start == 1
    assert duplicated.sno != entries[0].sno  # new row, not an alias of the original
    # the row that followed the original is still present, just shifted down
    assert builder.entries()[2].title == "Social Momentum"


def test_duplicating_an_approved_outline_invalidates_approval(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)
    builder.table.selectRow(0)

    builder.duplicate_row()

    assert window.services.outlines.approval(book.book_id).approved is False
    assert "Approval has been cleared" in window.statusBar().currentMessage()


def test_delete_row_selects_the_next_logical_row(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", 1),
        OutlineEntry(2, "Social Momentum", "chapter", 2),
        OutlineEntry(3, "Closing Word", "chapter", 3),
    ]
    builder.set_entries(entries)
    builder.table.selectRow(1)

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=True):
        builder.delete_row()

    assert builder.table.rowCount() == 2
    assert builder.table.currentRow() == 1  # "Closing Word" now occupies row 1
    assert builder.entries()[1].title == "Closing Word"


def test_deleting_the_last_row_selects_the_new_last_row(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", 1),
        OutlineEntry(2, "Social Momentum", "chapter", 2),
    ]
    builder.set_entries(entries)
    builder.table.selectRow(1)

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=True):
        builder.delete_row()

    assert builder.table.rowCount() == 1
    assert builder.table.currentRow() == 0


def test_move_row_keeps_the_moved_row_selected(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", 1),
        OutlineEntry(2, "Social Momentum", "chapter", 2),
    ]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    builder.move(1)

    assert builder.table.currentRow() == 1
    assert builder.entries()[1].title == "Perspective"


def test_add_row_invalidates_approval(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)

    builder.add_row()

    assert window.services.outlines.approval(book.book_id).approved is False
    assert builder.table.currentRow() == 1
    assert "Approval has been cleared" in window.statusBar().currentMessage()


def test_editing_status_reflects_entries_modified_and_approved_state(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", 1),
        OutlineEntry(2, "Social Momentum", "chapter", 2),
    ]
    builder.set_entries(entries)

    text = builder.editing_status.text()
    assert "Entries 2" in text
    assert "Modified No" in text
    assert "Approved No" in text

    builder.table.selectRow(0)
    builder.duplicate_row()
    text = builder.editing_status.text()
    assert "Entries 3" in text
    assert "Modified Yes" in text  # duplicate_row marks the new row edited_by_user

    window.services.outlines.approve(book, builder.entries(), "widget test")
    builder.validate()
    assert "Approved Yes" in builder.editing_status.text()


def test_review_empty_state_gives_a_next_step_when_no_outline_exists(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.selection_changed()

    assert builder.table.rowCount() == 0
    assert "No outline has been generated" in builder.review_empty.text()
    assert "Next Step" in builder.review_empty.text()
    assert "A. Create Structure" in builder.review_empty.text()


def test_keyboard_shortcuts_move_and_delete_the_review_table_row(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "Perspective", "chapter", 1),
        OutlineEntry(2, "Social Momentum", "chapter", 2),
    ]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    shortcuts = builder.table.findChildren(QShortcut)
    move_down = next(s for s in shortcuts if s.key() == QKeySequence("Alt+Down"))
    move_up = next(s for s in shortcuts if s.key() == QKeySequence("Alt+Up"))
    delete = next(s for s in shortcuts if s.key() == QKeySequence(QKeySequence.StandardKey.Delete))

    move_down.activated.emit()
    assert builder.entries()[1].title == "Perspective"
    assert builder.table.currentRow() == 1

    move_up.activated.emit()
    assert builder.entries()[0].title == "Perspective"
    assert builder.table.currentRow() == 0

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=True):
        delete.activated.emit()
    assert builder.table.rowCount() == 1
    assert builder.entries()[0].title == "Social Momentum"


def test_json_pasted_into_free_form_box_offers_structured_preview(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.selection_changed()
    builder.paste_text.setPlainText(json.dumps({
        "book": {"title": "Metadata, not an outline row"},
        "outline": [{
            "sno": "1", "title": "Perspective", "kind": "chapter",
            "printed_start": 1, "level": 1, "parent_sno": None,
        }],
    }))

    with patch.object(builder.parser, "parse", side_effect=AssertionError("free-form parser called")):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as question:
            builder.parse_preview()

    assert question.call_args.args[2] == "This appears to be JSON. Import it as structured JSON?"
    assert [row.title for row in builder.candidate_records] == ["Perspective"]
    assert builder.table.rowCount() == 0
    assert not builder.import_diagnostics.isHidden()
    assert "Import SHA-256" in builder.import_diagnostics.toPlainText()


def test_json_paste_decline_does_not_parse_or_import(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.selection_changed()
    builder.paste_text.setPlainText('[{"parent_sno":"1"}]')

    with patch.object(builder.parser, "parse", side_effect=AssertionError("free-form parser called")):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            builder.parse_preview()

    assert builder.candidate_records == []


def test_json_null_page_cannot_be_selected_until_page_is_supplied(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    result = builder.import_json_text(json.dumps([{
        "sno": "1", "title": "Metadata", "kind": "notes",
        "printed_start": None, "level": 1, "include": True,
    }]))

    assert result is not None
    include_item = builder.candidate_table.item(0, 0)
    include_item.setCheckState(Qt.CheckState.Checked)
    assert include_item.checkState() == Qt.CheckState.Unchecked
    builder.candidate_table.item(0, 4).setText("12")
    include_item.setCheckState(Qt.CheckState.Checked)
    assert include_item.checkState() == Qt.CheckState.Checked


def test_json_provenance_hierarchy_hash_and_user_edit_survive_preview_acceptance(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    result = builder.import_json_text(json.dumps({"outline": [{
        "sno": "1", "title": "Part", "kind": "part", "printed_start": 1,
        "level": 1, "children": [{
            "sno": "1.1", "title": "Child", "kind": "chapter",
            "printed_start": 2, "level": 2,
        }],
    }]}))
    builder.candidate_table.item(1, 2).setText("Edited Child")

    entries = builder.selected_candidate_entries()
    assert entries[1].source_sno == "1.1"
    assert entries[1].parent_sno == "1"
    assert entries[1].raw_import_hash == result.import_hash
    assert entries[1].edited_by_user is True


def test_kind_column_is_a_controlled_selector_limited_to_existing_kinds(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.set_entries([OutlineEntry(1, "Perspective", "chapter", 1)])

    combo = builder.table.cellWidget(0, 3)
    assert isinstance(combo, QComboBox)
    offered = {combo.itemData(i) for i in range(combo.count())}
    assert offered == KINDS  # no schema value invented, nothing valid left out
    assert combo.currentData() == "chapter"  # preselected to the entry's current kind


def test_unknown_kind_shows_needs_review_placeholder_and_status(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.set_entries([OutlineEntry(1, "Postscript", "postscript", 1)])

    combo = builder.table.cellWidget(0, 3)
    assert combo.currentData() == "postscript"
    assert "needs review" in combo.currentText().lower()
    assert builder.table.item(0, 10).text() == "Review Needed"
    assert not builder.table.item(0, 10).icon().isNull()


def test_known_kind_shows_classified_status(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.set_entries([OutlineEntry(1, "Perspective", "chapter", 1)])

    assert builder.table.item(0, 10).text() == "Classified"


def test_changing_kind_via_combo_updates_entry_but_never_touches_title(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.set_entries([OutlineEntry(1, "Postscript", "postscript", 1)])

    combo = builder.table.cellWidget(0, 3)
    combo.setCurrentIndex(combo.findData("chapter"))

    entry = builder.entries()[0]
    assert entry.kind == "chapter"
    assert entry.title == "Postscript"  # title is never modified by a semantic-type change
    assert builder.table.item(0, 10).text() == "Classified"


def test_changing_kind_on_an_approved_outline_shows_semantic_specific_feedback(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)

    combo = builder.table.cellWidget(0, 3)
    combo.setCurrentIndex(combo.findData("appendix"))

    assert window.services.outlines.approval(book.book_id).approved is False
    message = window.statusBar().currentMessage()
    assert "Semantic classification updated" in message
    assert "Outline approval has been cleared" in message
    assert "Review and approve again" in message


def test_editing_title_still_shows_the_generic_invalidation_message_not_the_semantic_one(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1)]
    window.services.outlines.approve(book, entries, "widget test")
    builder.set_entries(entries)

    builder.table.item(0, 2).setText("Edited Perspective")

    message = window.statusBar().currentMessage()
    assert "Semantic classification updated" not in message
    assert "Approval has been cleared" in message


def test_dry_review_distinguishes_title_from_recommended_semantic_type(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    builder.set_entries([OutlineEntry(1, "Postscript", "postscript", 1)])

    text = builder.validation.toPlainText()
    assert "Semantic type requires review" in text
    assert "Title: Postscript" in text
    assert "Current classification: postscript" in text
    assert "Recommended classification: Section" in text
    # the raw "unknown kind '...'" wording is replaced, not duplicated alongside the advisory
    assert "has unknown kind" not in text


def test_clear_paste_uses_the_shared_safe_by_default_confirmation(builder_context):
    """Sprint 14: Clear pasted text is a data-loss risk, so it goes through
    confirm_destructive() (Enter does not confirm by accident), not the plain
    QMessageBox.question() convenience call every other Yes/No question here uses."""
    builder, window, book = builder_context
    window.selected_book = book
    builder.paste_text.setPlainText("some pasted text")

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=False) as mocked:
        builder.clear_paste()
    mocked.assert_called_once()
    assert builder.paste_text.toPlainText() == "some pasted text"  # declining leaves it untouched

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=True):
        builder.clear_paste()
    assert builder.paste_text.toPlainText() == ""


def test_delete_row_declining_the_confirmation_leaves_the_row_in_place(builder_context):
    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1), OutlineEntry(2, "Social Momentum", "chapter", 2)]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=False):
        builder.delete_row()

    assert builder.table.rowCount() == 2  # declining the (now safe-by-default) confirmation deletes nothing


def test_delete_row_returns_keyboard_focus_to_the_table(builder_context):
    """Sprint 14, requirement #5: a button click leaves keyboard focus on the button,
    not the table -- confirmed empirically before this fix that selectRow() alone does
    not move input focus. delete_row() must now explicitly reclaim it so the operator
    can keep working the table by keyboard without an extra Tab press."""
    from PySide6.QtWidgets import QPushButton

    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1), OutlineEntry(2, "Social Momentum", "chapter", 2)]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    delete_button = next(b for b in builder.findChildren(QPushButton) if b.text() == "Delete")
    delete_button.setFocus()
    assert builder.focusWidget() is delete_button

    with patch("bookcorpusbuilder.gui.widgets.structure_builder.confirm_destructive", return_value=True):
        builder.delete_row()

    assert builder.focusWidget() is builder.table


def test_move_row_returns_keyboard_focus_to_the_table(builder_context):
    from PySide6.QtWidgets import QPushButton

    builder, window, book = builder_context
    window.selected_book = book
    entries = [OutlineEntry(1, "Perspective", "chapter", 1), OutlineEntry(2, "Social Momentum", "chapter", 2)]
    builder.set_entries(entries)
    builder.table.selectRow(0)

    move_down_button = next(b for b in builder.findChildren(QPushButton) if b.text() == "Move Down")
    move_down_button.setFocus()
    assert builder.focusWidget() is move_down_button

    builder.move(1)

    assert builder.focusWidget() is builder.table


def test_csv_import_failure_shows_reason_and_recovery_guidance(builder_context):
    """Sprint 15: previously the raw exception text (str(exc)) was the entire dialog
    message, with no recovery guidance and no separate technical-details pane."""
    builder, window, book = builder_context
    window.selected_book = book

    from PySide6.QtWidgets import QFileDialog
    with patch.object(QFileDialog, "getOpenFileName", return_value=("/nonexistent/fake.csv", "")), \
         patch.object(window.services.outlines, "load", side_effect=ValueError("boom: bad csv")):
        with pytest.raises(AssertionError) as excinfo:
            builder.import_csv()

    text = str(excinfo.value)
    assert "Outline Import Failed" in text
    assert "Reason" in text
    assert "The selected file could not be read as an outline." in text
    assert "What you can do" in text
    assert "try importing again" in text
    assert "boom: bad csv" in text  # the real exception text is preserved, just relocated


def test_json_file_read_failure_shows_reason_and_recovery_guidance(builder_context):
    builder, window, book = builder_context
    window.selected_book = book

    from PySide6.QtWidgets import QFileDialog
    with patch.object(QFileDialog, "getOpenFileName", return_value=("/nonexistent/fake.json", "")):
        with pytest.raises(AssertionError) as excinfo:
            builder.import_json()

    text = str(excinfo.value)
    assert "JSON Outline Import Failed" in text
    assert "Reason" in text
    assert "The selected file could not be read." in text
    assert "What you can do" in text
    assert "UTF-8 encoded text" in text


def test_malformed_json_import_shows_schema_guidance_and_keeps_diagnostics_panel(builder_context):
    builder, window, book = builder_context
    window.selected_book = book

    with pytest.raises(AssertionError) as excinfo:
        builder.import_json_text("not valid json at all")

    text = str(excinfo.value)
    assert "JSON Outline Import Failed" in text
    assert "Reason" in text
    assert "What you can do" in text
    assert "outline schema" in text
    # the existing inline diagnostics panel is still populated too (Sprint 5-era
    # behaviour, untouched) -- the dialog complements it, doesn't replace it.
    assert "malformed_json" in builder.import_diagnostics.toPlainText()


def test_approve_blocked_shows_bulleted_reasons_and_recovery_guidance(builder_context):
    """Sprint 15: OutlineService.approve()'s single semicolon-joined ValueError is now
    split into one bullet per blocking issue, still using its own operator-language
    messages (not exception jargon), plus explicit recovery guidance."""
    builder, window, book = builder_context
    window.selected_book = book
    entries = [
        OutlineEntry(1, "", "chapter", None),  # no title, no printed page -> 2 blocking issues
    ]
    builder.set_entries(entries)

    with patch.object(QInputDialog, "getMultiLineText", return_value=("note", True)):
        with pytest.raises(AssertionError) as excinfo:
            builder.approve()

    text = str(excinfo.value)
    assert "Outline Approval Blocked" in text
    assert "Reason" in text
    assert "•" in text  # split into a bulleted list, not one run-on sentence
    assert "What you can do" in text
    assert "Review Outline table" in text

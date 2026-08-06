from __future__ import annotations

import csv
import html
import json
import logging
import os
import stat
import traceback
from base64 import b64decode, b64encode
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QDialog, QDialogButtonBox, QGroupBox, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QListWidgetItem, QInputDialog,
    QSpinBox, QSplitter, QStackedWidget, QStyle, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..paths import INPUT_PDF_DIR, OUTLINE_DIR, OUTPUT_DIR, PROJECT_ROOT
from .models import MappingAnchor, OutlineCandidate, OutlineEntry, PageMapping, Severity
from .services.assistance import TocIndexService
from .services.common import sha256_file
from .services.extraction import ExtractionService
from .services.history import HistoryService
from .services.library import DuplicateBookError, LibraryImportError, LibraryService
from .services.mapping import MappingService, suggested_action
from .services.outline_text_parser import OutlineMergeService, OutlineTextParser
from .services.outlines import FIELDS, KINDS, OutlineService
from .services.search import CorpusSearchService
from .services.settings import AppSettings, SettingsService
from .widgets import PdfTextPreview, StructureBuilder, format_operator_error
from .widgets.table_usability import best_fit_button, configure_splitter, configure_table
from .workers import FunctionWorker


logger = logging.getLogger(__name__)


def open_path(path: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))


def reveal_path(path: Path):
    target = path if path.is_dir() else path.parent
    open_path(target)


def format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return value


def short_output_path(path: Path) -> str:
    """Last two path components, e.g. '.../runs/20260804-abcd'. Full path stays available as a tooltip."""
    parts = path.parts
    return str(Path(*parts[-2:])) if len(parts) >= 2 else str(path)


def format_elapsed(started_at: str, completed_at: str) -> str:
    try:
        seconds = max(0, (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds())
    except (ValueError, TypeError):
        return "—"
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def source_diagnostics(source: Path) -> str:
    """Best-effort facts about a source file for an error dialog's details pane.

    Must never itself raise -- it runs while we're already reporting a
    failure, so a second exception here would re-introduce the silent
    failure this is meant to fix.
    """
    lines = [f"Source path: {source}"]
    try:
        exists = source.exists()
        lines.append(f"Exists: {exists}")
        if exists:
            info = source.stat()
            lines.append(f"Permissions: {oct(stat.S_IMODE(info.st_mode))}")
            lines.append(f"Size: {info.st_size} bytes")
        if source.is_file():
            lines.append(f"SHA-256: {sha256_file(source)}")
    except OSError as exc:
        lines.append(f"(diagnostics incomplete: {exc})")
    return "\n".join(lines)


class Services:
    def __init__(self):
        self.settings_service = SettingsService()
        self.settings = self.settings_service.load()
        self.rebuild()

    def rebuild(self):
        self.input_dir = Path(self.settings.input_pdf_dir)
        self.outline_dir = Path(self.settings.outline_dir)
        self.output_dir = Path(self.settings.output_dir)
        self.library = LibraryService(self.input_dir, self.outline_dir / "book_library.json")
        self.outlines = OutlineService(self.outline_dir)
        self.mappings = MappingService(self.outline_dir)
        self.history = HistoryService(self.output_dir / "run_history")
        self.extraction = ExtractionService(self.output_dir, self.history, self.outlines, self.mappings)
        self.search = CorpusSearchService(self.output_dir)
        self.assistance = TocIndexService()


class Screen(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.window = window

    @property
    def book(self):
        return self.window.selected_book

    def selection_changed(self):
        pass


class LibraryScreen(Screen):
    def __init__(self, window):
        super().__init__(window)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search books…")
        self.search.textChanged.connect(self.refresh)
        add = QPushButton("Add PDFs…")
        add.clicked.connect(self.add_pdfs)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(lambda: self.window.run_task(self.window.services.library.books, self.loaded, True))
        open_pdf = QPushButton("Open Source PDF")
        open_pdf.clicked.connect(lambda: open_path(self.book.path) if self.book else None)
        reveal = QPushButton("Reveal Source PDF")
        reveal.clicked.connect(lambda: reveal_path(self.book.path) if self.book else None)
        remove = QPushButton("Hide from Library")
        remove.clicked.connect(self.remove)
        bar = QHBoxLayout()
        for widget in (self.search, add, refresh, open_pdf, reveal, remove):
            bar.addWidget(widget)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            ["Filename", "Size", "Pages", "Text", "Draft", "Approved", "Mapping", "Extraction", "Last Run",
             "Project Status", "Next Action"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        configure_table(
            self.table, self.window, "library.books",
            default_widths={0: 500, 1: 90, 2: 75, 3: 130, 4: 80, 5: 90, 6: 115, 7: 100, 8: 130, 9: 130, 10: 150},
            frozen_columns=(0,), content_caps={0: 760},
        )
        bar.addWidget(best_fit_button(self.table))
        self.table.itemSelectionChanged.connect(self.select)
        self.table.cellDoubleClicked.connect(self.open_relevant_workspace)
        self.empty_label = QLabel("No books registered.\n\nNext Step\nUse \"Add PDFs…\" above to register your first book.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary = QLabel("Select a book to see its status.")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        summary_box = QGroupBox("Book Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary)
        summary_layout.addStretch()
        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(summary_box)
        configure_splitter(split, self.window, "library.main", [980, 320])
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.empty_label)
        layout.addWidget(split)
        self.records = []
        self.refresh()

    def selection_changed(self):
        # The Library is the operator's cockpit -- it must reflect state changed in any other
        # workspace (an approval, a mapping, an extraction run) as soon as the operator returns
        # here, not only after an explicit manual "Refresh" click.
        self.refresh()

    def refresh(self):
        self.loaded(self.window.services.library.books(False))

    def _lifecycle(self, book):
        """Single source of truth for a book's pipeline stage.

        Reuses exactly the signals already computed elsewhere on this screen (outline
        approval, mapping approval, run history) -- no new persistence, no new detection
        logic. Feeds the Project Status / Next Action columns, the Book Summary panel, and
        double-click navigation, so all three always agree with each other.
        """
        draft, _, _ = self.window.services.outlines.paths(book.book_id)
        approval = self.window.services.outlines.approval(book.book_id)
        outline_approved = bool(approval and approval.approved)
        mapping = self.window.services.mappings.load(book.book_id)
        runs = self.window.services.history.records(book.book_id)
        completed_runs = [run for run in runs if run.status == "completed"]
        # "target" is a navigation.setCurrentRow() index; "tab" is which Structure Builder tab
        # to additionally select (A=0 create, B=1 review, C=2 page mapping) when target points
        # there, or None for screens that aren't Structure Builder. Page Alignment used to be
        # its own navigation row -- it's now Structure Builder's "C. Page Mapping" tab.
        if completed_runs:
            status, action, target, tab = "Extracted", "Browse Corpus", 3, None
        elif mapping.approved:
            status, action, target, tab = "Mapping Ready", "Run Extraction", 2, None
        elif outline_approved:
            status, action, target, tab = "Outline Ready", "Verify Mapping", 1, 2
        elif draft.exists():
            status, action, target, tab = "Registered", "Approve Outline", 1, 1
        else:
            status, action, target, tab = "Registered", "Create Structure", 1, 0
        return {
            "status": status, "action": action, "target": target, "tab": tab,
            "draft_exists": draft.exists(), "outline_approved": outline_approved,
            "mapping_approved": mapping.approved, "runs": runs, "completed_runs": completed_runs,
        }

    def loaded(self, books):
        needle = self.search.text().casefold()
        self.records = [book for book in books if needle in book.filename.casefold()]
        self.table.setRowCount(len(self.records))
        self.empty_label.setVisible(not self.records)
        for row, book in enumerate(self.records):
            lifecycle = self._lifecycle(book)
            values = [
                book.filename, f"{book.size_bytes / 1048576:.1f} MB", book.page_count or "—", book.text_status,
                "Yes" if lifecycle["draft_exists"] else "No", "Yes" if lifecycle["outline_approved"] else "No",
                "Verified" if lifecycle["mapping_approved"] else "Unresolved",
                "Yes" if lifecycle["completed_runs"] else "No",
                lifecycle["runs"][0].status if lifecycle["runs"] else "—",
                lifecycle["status"], lifecycle["action"],
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        if self.book:
            # select_book_id() re-selects the same row when the index didn't move, which
            # Qt does not treat as a selection change -- so update_summary() must be called
            # unconditionally here, not left to itemSelectionChanged, or the summary panel
            # would show stale data whenever a refresh changes the selected book's
            # underlying state without moving its row.
            self.select_book_id(self.book.book_id)
        self.update_summary()

    def select(self):
        selected = self.table.selectionModel().selectedRows()
        if selected:
            record = self.records[selected[0].row()]
            if record.page_count == 0:
                self.window.run_task(self.window.services.library.books, lambda books, book_id=record.book_id: self.select_inspected(books, book_id), True)
            else:
                self.window.set_book(record)
                self.update_summary()
        else:
            self.update_summary()

    def select_inspected(self, books, book_id):
        self.loaded(books)
        match = next((book for book in books if book.book_id == book_id), None)
        if match:
            self.window.set_book(match)
            self.update_summary()

    def update_summary(self):
        if not self.book:
            self.summary.setText("Select a book to see its status.")
            return
        lifecycle = self._lifecycle(self.book)

        def mark(ok: bool) -> str:
            return "✓" if ok else "✗"

        registered = format_timestamp(self.book.registered_at) if self.book.registered_at else "—"
        latest_run = lifecycle["runs"][0] if lifecycle["runs"] else None
        latest_run_text = f"{format_timestamp(latest_run.started_at)} · {latest_run.status}" if latest_run else "—"
        status_color = "#287a3d" if lifecycle["action"] == "Browse Corpus" else "#9a5a00"
        lines = [
            f"<b>Book</b><br>{self.book.filename}",
            f"<br><b>Registered</b><br>{registered}",
            f"<br><b>Outline</b><br>{'Approved' if lifecycle['outline_approved'] else ('Drafted' if lifecycle['draft_exists'] else 'Not started')}",
            f"<br><b>Mapping</b><br>{'Approved' if lifecycle['mapping_approved'] else 'Unresolved'}",
            f"<br><b>Extractions</b><br>{len(lifecycle['completed_runs'])}",
            f"<br><b>Latest Run</b><br>{latest_run_text}",
            "<br><b>Lifecycle</b>",
            f"{mark(True)} Registered",
            f"{mark(lifecycle['outline_approved'])} Outline",
            f"{mark(lifecycle['mapping_approved'])} Mapping",
            f"{mark(bool(lifecycle['completed_runs']))} Extracted",
            f"<br><b>Current Status</b><br><b style='color:{status_color}'>{CURRENT_STATUS_LABELS[lifecycle['action']]}</b>",
            f"<br><b>Next Action</b><br>{lifecycle['action']}",
        ]
        self.summary.setText("<br>".join(lines))

    def open_relevant_workspace(self, *_args):
        """Double-click a book to jump straight to the workspace its current stage needs.

        Reuses the exact navigate-and-preselect pattern already established by
        HistoryScreen.open_run() and ExtractScreen.open_in_browser() -- set the row's
        book (already done via the click's selection change), switch workspaces, and
        for the "browse" stage, preselect its most recent completed run the same way.
        """
        if not self.book:
            return
        lifecycle = self._lifecycle(self.book)
        self.window.navigation.setCurrentRow(lifecycle["target"])
        if lifecycle["tab"] is not None:
            self.window.screens[1].tabs.setCurrentIndex(lifecycle["tab"])
        if lifecycle["action"] == "Browse Corpus" and lifecycle["completed_runs"]:
            browser = self.window.screens[3]
            index = browser.run_filter.findData(lifecycle["completed_runs"][0].run_id)
            if index >= 0:
                browser.run_filter.setCurrentIndex(index)

    def add_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add PDFs", str(Path.home()), "PDF files (*.pdf)")
        last_added_book_id = None
        for filename in files:
            source = Path(filename)
            try:
                record = self.window.services.library.add(source)
                last_added_book_id = record.book_id
            except DuplicateBookError as exc:
                self.window.show_notice("Already in Library", f"{source.name} is already registered as {exc.record.filename}.")
            except LibraryImportError as exc:
                logger.exception("Failed to add %s at stage %r", source.name, exc.stage)
                self.window.show_error(
                    "Could not add PDF",
                    format_operator_error(
                        f"{source.name} could not be added to the library.",
                        "Check that the file is a valid, readable PDF and try adding it again.",
                    ),
                    f"Failure stage: {exc.stage}\n{source_diagnostics(source)}\n\n{traceback.format_exc()}",
                )
            except Exception:
                logger.exception("Unexpected failure adding %s", source.name)
                self.window.show_error(
                    "Could not add PDF",
                    format_operator_error(
                        f"{source.name} could not be added to the library.",
                        "Check that the file is a valid, readable PDF and try adding it again.",
                    ),
                    f"{source_diagnostics(source)}\n\n{traceback.format_exc()}",
                )
        self.refresh()
        if last_added_book_id:
            self.select_book_id(last_added_book_id)

    def select_book_id(self, book_id):
        for row, book in enumerate(self.records):
            if book.book_id == book_id:
                self.table.selectRow(row)
                return

    def remove(self):
        if not self.book:
            return
        answer = QMessageBox.question(self, "Hide from Library", "Hide this book from the library? The imported PDF and its original source will not be deleted. Re-adding the same PDF later restores it.")
        if answer == QMessageBox.StandardButton.Yes:
            self.window.services.library.remove_registration(self.book.book_id)
            self.window.set_book(None)
            self.refresh()


class OutlineScreen(Screen):
    columns = ["Sno", "title", "kind", "printed_start", "physical_start", "pdf_page_index", "confidence", "source", "review_status", "include"]

    def __init__(self, window):
        super().__init__(window)
        self.preview = PdfTextPreview()
        open_pdf = QPushButton("Open PDF externally")
        open_pdf.clicked.connect(lambda: open_path(self.book.path) if self.book else None)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Book pages — select and copy TOC text"))
        preview_header.addStretch()
        preview_header.addWidget(open_pdf)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.preview)

        self.paste_text = QPlainTextEdit()
        self.paste_text.setPlaceholderText(
            "Paste a table of contents here. Each entry should end with its printed page number.\n\n"
            "Chapter 1  Beginnings ........ 3\nMethods and materials          18"
        )
        self.paste_text.setMaximumHeight(155)
        self.paste_text.textChanged.connect(self.update_actions)
        clipboard = QPushButton("Paste from clipboard")
        clipboard.clicked.connect(self.paste_from_clipboard)
        self.parse_button = QPushButton("Parse into outline")
        self.parse_button.setObjectName("primaryAction")
        self.parse_button.clicked.connect(self.parse_paste)
        paste_actions = QHBoxLayout()
        paste_actions.addWidget(clipboard)
        paste_actions.addStretch()
        paste_actions.addWidget(QLabel("Parsing replaces the rows below."))
        paste_actions.addWidget(self.parse_button)
        self.paste_feedback = QLabel("Printed pages are captured now; physical PDF pages are aligned in the next workspace.")
        self.paste_feedback.setWordWrap(True)
        paste_group = QGroupBox("1 · Paste an outline")
        paste_layout = QVBoxLayout(paste_group)
        paste_layout.addWidget(self.paste_text)
        paste_layout.addLayout(paste_actions)
        paste_layout.addWidget(self.paste_feedback)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(["#", "Title", "Type", "Printed page", "Physical page", "PDF index", "Confidence", "Source", "Review", "Use"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        configure_table(
            self.table, self.window, "legacy_outline.rows",
            default_widths={0: 70, 1: 500, 2: 120, 3: 110, 4: 110, 5: 95, 6: 110, 7: 140, 8: 110, 9: 70},
            frozen_columns=(0, 1), content_caps={1: 760},
        )
        self.table.itemSelectionChanged.connect(self.jump)
        self.table.itemChanged.connect(lambda _item: self.validate())
        for column in (4, 5, 6, 7, 8):
            self.table.setColumnHidden(column, True)

        add = QPushButton("Add row")
        add.clicked.connect(self.add_row)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_row)
        duplicate = QPushButton("Duplicate")
        duplicate.clicked.connect(self.duplicate_row)
        up = QPushButton("Move up")
        up.clicked.connect(lambda: self.move(-1))
        down = QPushButton("Move down")
        down.clicked.connect(lambda: self.move(1))
        row_actions = QHBoxLayout()
        row_actions.addWidget(QLabel("2 · Review and correct the parsed rows"))
        row_actions.addWidget(best_fit_button(self.table))
        row_actions.addStretch()
        for button in (add, delete, duplicate, up, down):
            row_actions.addWidget(button)

        self.validation = QPlainTextEdit()
        self.validation.setReadOnly(True)
        self.validation.setMaximumHeight(88)
        self.candidates = QListWidget()
        self.candidates.setMaximumHeight(100)
        self.candidates.currentRowChanged.connect(self.candidate_selected)
        self.candidate_pages = []

        self.more_button = QPushButton("Other ways to create an outline…")
        self.more_button.setCheckable(True)
        self.more_button.toggled.connect(self.toggle_more_options)
        self.more_panel = QWidget()
        more_layout = QVBoxLayout(self.more_panel)
        more_layout.setContentsMargins(0, 0, 0, 0)
        more_buttons = QHBoxLayout()
        secondary_actions = [
            ("Detect from PDF", self.generate),
            ("Import CSV…", self.import_csv),
            ("Reload saved draft", self.load_draft),
            ("Find TOC/index pages", self.scan_candidates),
            ("Add selected TOC pages", self.merge_toc),
            ("Export scan data…", self.export_candidates),
        ]
        for label, callback in secondary_actions:
            button = QPushButton(label)
            button.clicked.connect(callback)
            more_buttons.addWidget(button)
        more_buttons.addStretch()
        more_layout.addLayout(more_buttons)
        more_layout.addWidget(self.candidates)
        self.more_panel.setVisible(False)

        self.save_button = QPushButton("Save draft")
        self.save_button.clicked.connect(self.save_draft)
        self.approve_button = QPushButton("Approve outline & continue")
        self.approve_button.setObjectName("primaryAction")
        self.approve_button.clicked.connect(self.approve)
        finish_actions = QHBoxLayout()
        finish_actions.addWidget(QLabel("3 · When the rows match the book, approve the outline"))
        finish_actions.addStretch()
        finish_actions.addWidget(self.save_button)
        finish_actions.addWidget(self.approve_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(paste_group)
        right_layout.addLayout(row_actions)
        right_layout.addWidget(self.table, 1)
        right_layout.addWidget(self.validation)
        right_layout.addWidget(self.more_button)
        right_layout.addWidget(self.more_panel)
        right_layout.addLayout(finish_actions)

        split = QSplitter()
        split.addWidget(preview_panel)
        split.addWidget(right)
        configure_splitter(split, self.window, "legacy_outline.main", [500, 940])

        workflow = QLabel("OPEN BOOK   →   PASTE CONTENTS   →   REVIEW OUTLINE   →   APPROVE   →   ALIGN PAGES")
        workflow.setObjectName("workflow")
        workflow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(workflow)
        layout.addWidget(split)
        self.validate()

    def selection_changed(self):
        self.preview.set_pdf(self.book.path if self.book else None, self.book.page_count if self.book else 0)
        self.load_draft()
        self.update_actions()

    def paste_from_clipboard(self):
        self.paste_text.setPlainText(QApplication.clipboard().text())

    def parse_paste(self):
        result = parse_pasted_outline(self.paste_text.toPlainText())
        if result.entries:
            self.set_entries(result.entries)
        summary = f"Parsed {len(result.entries)} outline row(s)."
        if result.warnings:
            summary += " " + " ".join(result.warnings)
        if result.ignored_lines:
            examples = "; ".join(repr(line) for line in result.ignored_lines[:3])
            summary += f" Review skipped text: {examples}"
        self.paste_feedback.setText(summary)
        self.window.statusBar().showMessage(summary, 7000)

    def toggle_more_options(self, visible):
        self.more_panel.setVisible(visible)
        self.more_button.setText("Hide other outline options" if visible else "Other ways to create an outline…")

    def entries(self):
        result = []
        for row in range(self.table.rowCount()):
            value = lambda col: self.table.item(row, col).text().strip() if self.table.item(row, col) else ""
            def integer(col):
                try:
                    return int(value(col)) if value(col) else None
                except ValueError:
                    return None
            try:
                confidence = float(value(6)) if value(6) else None
            except ValueError:
                confidence = None
            include_item = self.table.item(row, 9)
            result.append(OutlineEntry(
                sno=row + 1, title=value(1), kind=value(2).casefold() or "section",
                printed_start=integer(3), physical_start=integer(4), pdf_page_index=integer(5),
                confidence=confidence, source=value(7) or "manual",
                review_status=value(8) or "draft",
                include=include_item.checkState() == Qt.CheckState.Checked if include_item else True,
            ))
        return result

    def set_entries(self, entries):
        self.table.blockSignals(True)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = list(entry.to_csv_row().values())
            values[0] = row + 1
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 9:
                    item.setText("")
                    item.setFlags((item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
                    item.setCheckState(Qt.CheckState.Checked if entry.include else Qt.CheckState.Unchecked)
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        self.validate()

    def generate(self):
        if self.book:
            self.window.run_task(self.window.services.outlines.generate, self.set_entries, self.book)

    def load_draft(self):
        if not self.book:
            self.set_entries([])
            return
        draft, clean, _ = self.window.services.outlines.paths(self.book.book_id)
        path = draft if draft.exists() else clean
        self.set_entries(self.window.services.outlines.load(path) if path.exists() else [])

    def import_csv(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import outline", str(Path.home()), "CSV (*.csv)")
        if filename:
            try:
                self.set_entries(self.window.services.outlines.load(Path(filename)))
            except Exception as exc:
                self.window.show_error("Outline import failed", str(exc))

    def add_row(self):
        entries = self.entries()
        entries.append(OutlineEntry(len(entries) + 1, "New section", source="manual"))
        self.set_entries(entries)
        self.table.selectRow(len(entries) - 1)
        self.table.editItem(self.table.item(len(entries) - 1, 1))

    def delete_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.renumber_rows()
            self.validate()

    def renumber_rows(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setText(str(row + 1))

    def duplicate_row(self):
        row = self.table.currentRow()
        entries = self.entries()
        if row >= 0:
            copy = OutlineEntry(**asdict(entries[row]))
            copy.sno = max((entry.sno for entry in entries), default=0) + 1
            copy.review_status = "draft"
            entries.insert(row + 1, copy)
            self.set_entries(entries)

    def move(self, direction):
        row = self.table.currentRow()
        target = row + direction
        entries = self.entries()
        if row >= 0 and 0 <= target < len(entries):
            entries[row], entries[target] = entries[target], entries[row]
            self.set_entries(entries)
            self.table.selectRow(target)

    def save_draft(self):
        if not self.book:
            return
        approval = self.window.services.outlines.approval(self.book.book_id)
        if approval and approval.approved:
            QMessageBox.warning(self, "Approved outline protected", "Revoke approval before replacing an approved outline. Saving a revised draft is allowed and will not alter the clean outline.")
        draft, _, _ = self.window.services.outlines.paths(self.book.book_id)
        self.window.services.outlines.save(draft, self.entries())
        self.window.statusBar().showMessage("Outline draft saved.", 5000)
        self.validate()

    def approve(self):
        if not self.book:
            return
        try:
            note, accepted = QInputDialog.getMultiLineText(self, "Approve clean outline", "Reviewer note")
            if not accepted:
                return
            draft, _, _ = self.window.services.outlines.paths(self.book.book_id)
            self.window.services.outlines.save(draft, self.entries())
            self.window.services.outlines.approve(self.book, self.entries(), note)
            self.window.statusBar().showMessage("Outline approved and hash-bound to the source PDF.", 5000)
            self.validate()
            self.window.navigation.setCurrentRow(2)
        except FileExistsError:
            answer = QMessageBox.question(self, "Revoke existing approval?", "An approved outline exists. Revoke it and approve the current table?")
            if answer == QMessageBox.StandardButton.Yes:
                self.window.services.outlines.revoke(self.book.book_id)
                self.approve()
        except Exception as exc:
            self.window.show_error("Outline approval blocked", str(exc))

    def validate(self):
        if not self.book:
            self.validation.setPlainText("Select a book to review or create an outline.")
            self.update_actions()
            return
        issues = self.window.services.outlines.validate(self.entries(), self.book.page_count)
        self.validation.setPlainText("\n".join(f"{item.severity.value.upper()} · {item.message}" for item in issues))
        self.update_actions(issues)

    def update_actions(self, issues=None):
        has_book = self.book is not None
        has_rows = self.table.rowCount() > 0
        if issues is None and has_book:
            issues = self.window.services.outlines.validate(self.entries(), self.book.page_count)
        blocking = any(item.severity == Severity.BLOCKING for item in (issues or []))
        self.parse_button.setEnabled(has_book and bool(self.paste_text.toPlainText().strip()))
        self.save_button.setEnabled(has_book and has_rows)
        self.approve_button.setEnabled(has_book and has_rows and not blocking)

    def jump(self):
        row = self.table.currentRow()
        if row >= 0:
            value = self.table.item(row, 4)
            if value and value.text().isdigit():
                self.preview.jump_to(int(value.text()))

    def scan_candidates(self):
        if self.book:
            settings = self.window.services.settings
            self.window.run_task(self.window.services.assistance.scan, self.show_candidates, self.book.path, settings.toc_scan_pages, settings.index_scan_pages)

    def show_candidates(self, pages):
        self.candidate_pages = pages
        self.candidates.clear()
        for page in pages:
            item = QListWidgetItem(f"{page.source.upper()} · physical {page.physical_page_number} · {page.confidence:.0%}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.candidates.addItem(item)

    def accepted_candidates(self):
        return [page for index, page in enumerate(self.candidate_pages) if self.candidates.item(index).checkState() == Qt.CheckState.Checked]

    def candidate_selected(self, index):
        if 0 <= index < len(self.candidate_pages):
            page = self.candidate_pages[index]
            self.preview.jump_to(page.physical_page_number)
            self.validation.setPlainText(f"{page.source.upper()} candidate · confidence {page.confidence:.0%}\n\n{page.raw_text}")

    def merge_toc(self):
        rows = self.window.services.assistance.parse_toc(self.accepted_candidates())
        entries = self.entries()
        start = max((entry.sno for entry in entries), default=0)
        entries.extend(OutlineEntry(start + index, row["title"], "section", row["printed_start"], source="toc", confidence=0.9) for index, row in enumerate(rows, 1))
        self.set_entries(entries)

    def export_candidates(self):
        if not self.candidate_pages:
            return
        destination = QFileDialog.getExistingDirectory(self, "Export candidate data")
        if destination:
            folder = Path(destination)
            accepted = self.accepted_candidates()
            self.window.services.assistance.export_raw(accepted, folder / "raw_toc.txt", "toc")
            self.window.services.assistance.export_raw(accepted, folder / "raw_index.txt", "index")
            self.window.services.assistance.export_entries(self.window.services.assistance.parse_toc(accepted), folder / "parsed_toc.csv")
            self.window.services.assistance.export_entries(self.window.services.assistance.parse_index(accepted), folder / "parsed_index.csv")


RUN_STATUS_COLORS = {
    "completed": "#c6efce",
    "running": "#ffeb9c",
    "failed": "#ffc7ce",
    "cancelled": "#e0e0e0",
}

CURRENT_STATUS_LABELS: dict[str, str] = {
    "Create Structure": "NEEDS STRUCTURE",
    "Approve Outline": "NEEDS OUTLINE APPROVAL",
    "Verify Mapping": "NEEDS PAGE MAPPING",
    "Run Extraction": "READY FOR EXTRACTION",
    "Browse Corpus": "READY TO BROWSE",
}


class ExtractScreen(Screen):
    IDLE_MESSAGE = "Select a book, approve its outline, and verify page alignment before extraction."

    def __init__(self, window):
        super().__init__(window)
        self._last_record = None
        self.minimum = QSpinBox(); self.minimum.setRange(1, 100000); self.minimum.setValue(window.services.settings.minimum_chars)
        self.output = QLineEdit(window.services.settings.output_dir)
        browse = QPushButton("Choose Output…"); browse.clicked.connect(self.choose_output)
        dry = QPushButton("Validate / Dry Run"); dry.clicked.connect(self.dry_run)
        self.extract = QPushButton("Extract Verified Corpus"); self.extract.clicked.connect(self.start)
        self.extract.setEnabled(False)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.cancel); self.cancel_button.setEnabled(False)
        form = QFormLayout(); form.addRow("Minimum characters", self.minimum); form.addRow("Output root", self.output)
        controls = QHBoxLayout()
        for widget in (browse, dry, self.extract, self.cancel_button): controls.addWidget(widget)

        self.readiness = QLabel(self.IDLE_MESSAGE); self.readiness.setWordWrap(True); self.readiness.setTextFormat(Qt.RichText)
        self.readiness.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.readiness_output = QLabel(""); self.readiness_output.setWordWrap(True)
        readiness_box = QGroupBox("Extraction Readiness")
        readiness_layout = QVBoxLayout(readiness_box); readiness_layout.addWidget(self.readiness); readiness_layout.addWidget(self.readiness_output); readiness_layout.addStretch()

        self.progress_state = QLabel("Ready")
        self.progress = QProgressBar()
        self.checklist = QListWidget()
        progress_box = QGroupBox("Extraction Progress")
        progress_layout = QVBoxLayout(progress_box)
        progress_layout.addWidget(self.progress_state); progress_layout.addWidget(self.progress); progress_layout.addWidget(self.checklist)

        splitter = QSplitter()
        splitter.addWidget(readiness_box); splitter.addWidget(progress_box)
        configure_splitter(splitter, self.window, "extract.readiness_progress", [520, 520])

        self.summary = QLabel("No extraction run yet in this session."); self.summary.setWordWrap(True); self.summary.setTextFormat(Qt.RichText)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.summary_output = QLabel(""); self.summary_output.setWordWrap(True)
        open_browser = QPushButton("Open Corpus Browser"); open_browser.clicked.connect(self.open_in_browser)
        open_output_folder = QPushButton("Open Output Folder"); open_output_folder.clicked.connect(self.open_output_folder)
        open_run_folder = QPushButton("Open Run Folder"); open_run_folder.clicked.connect(self.open_run_folder)
        self.next_step_buttons = [open_browser, open_output_folder, open_run_folder]
        for button in self.next_step_buttons: button.setEnabled(False)
        next_steps = QHBoxLayout()
        for button in self.next_step_buttons: next_steps.addWidget(button)
        next_steps.addStretch()
        summary_box = QGroupBox("Completion Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary); summary_layout.addWidget(self.summary_output); summary_layout.addLayout(next_steps)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(140)
        log_box = QGroupBox("Detailed Log")
        log_layout = QVBoxLayout(log_box); log_layout.addWidget(self.log)

        layout = QVBoxLayout(self)
        layout.addLayout(form); layout.addLayout(controls)
        layout.addWidget(splitter, 1)
        layout.addWidget(summary_box)
        layout.addWidget(log_box)
        self.cancel_event = Event()
        self.log.setPlainText(self.IDLE_MESSAGE)

    def selection_changed(self):
        if not self.book:
            self.extract.setEnabled(False)
            self.readiness.setText(self.IDLE_MESSAGE)
            self.readiness_output.setText("")
            self.log.setPlainText(self.IDLE_MESSAGE)

    def choose_output(self):
        value = QFileDialog.getExistingDirectory(self, "Output root", self.output.text())
        if value: self.output.setText(value)

    def context(self):
        if not self.book:
            raise ValueError("Select a book first.")
        _, clean, _ = self.window.services.outlines.paths(self.book.book_id)
        entries = self.window.services.outlines.load(clean) if clean.exists() else []
        return entries, self.window.services.outlines.approval(self.book.book_id), self.window.services.mappings.load(self.book.book_id)

    def dry_run(self):
        try:
            entries, approval, mapping = self.context()
            self.window.services.extraction.output_root = Path(self.output.text())
            issues = self.window.services.extraction.dry_run(self.book, entries, approval, mapping)
            self.render_readiness(issues, approval, mapping)
            self.log.setPlainText("\n".join(f"{issue.severity.value.upper()}: {issue.message}" for issue in issues))
            self.extract.setEnabled(not any(issue.severity == Severity.BLOCKING for issue in issues))
        except Exception as exc:
            self.readiness.setText(f"<b style='color:#a33'>NOT READY</b><br>{exc}")
            self.readiness_output.setText("")
            self.log.setPlainText(f"BLOCKING: {exc}"); self.extract.setEnabled(False)

    def render_readiness(self, issues, approval, mapping):
        blocking = [item for item in issues if item.severity == Severity.BLOCKING]
        warnings = [item for item in issues if item.severity == Severity.WARNING]
        outline_state = "Approved" if approval and getattr(approval, "approved", False) else "Not approved"
        mapping_state = "Approved" if mapping and mapping.approved else "Not approved"
        validation_state = "Blocked" if blocking else ("Passed, with warnings" if warnings else "Passed")
        header = "NOT READY" if blocking else "READY FOR EXTRACTION"
        color = "#a33" if blocking else "#287a3d"
        lines = [
            f"<b style='color:{color}'>{header}</b>",
            f"<br><b>Book</b><br>{self.book.filename}",
            f"<br><b>Outline</b><br>{outline_state}",
            f"<br><b>Page Mapping</b><br>{mapping_state}",
            f"<br><b>Validation</b><br>{validation_state}",
        ]
        if warnings:
            lines.append("<br><b style='color:#9a5a00'>Warnings</b>")
            lines.extend(f"⚠ {item.message}" for item in warnings)
        if blocking:
            lines.append("<br><b style='color:#a33'>Blocking issues</b>")
            lines.extend(f"✗ {item.message}" for item in blocking)
        lines.append(f"<br><b>Status</b><br><b style='color:{color}'>{'BLOCKED' if blocking else 'SAFE TO EXTRACT'}</b>")
        self.readiness.setText("<br>".join(lines))
        output_root = Path(self.output.text())
        self.readiness_output.setText(f"Output folder: {short_output_path(output_root)}")
        self.readiness_output.setToolTip(str(output_root))

    def start(self):
        try:
            entries, approval, mapping = self.context()
            self.cancel_event = Event(); self.cancel_button.setEnabled(True); self.extract.setEnabled(False)
            self.window.services.extraction.output_root = Path(self.output.text())
            self.checklist.clear(); self.progress.setValue(0); self.progress_state.setText("Extraction in progress…")
            self._set_next_steps_enabled(False)
            self.window.run_task(self.window.services.extraction.run, self.completed, self.book, entries, approval, mapping,
                                 min_chars=self.minimum.value(), cancel=self.cancel_event, with_progress=True,
                                 progress_slot=self.on_progress, on_failure=self.failed)
        except Exception as exc:
            self.window.show_error(
                "Extraction could not start",
                format_operator_error(str(exc), self.IDLE_MESSAGE),
                traceback.format_exc(),
            )

    def on_progress(self, done, total, title):
        self.progress.setMaximum(total); self.progress.setValue(done)
        skipped = title.startswith("Skipped: ")
        label = title[len("Skipped: "):] if skipped else title
        self.checklist.addItem(f"{'⊘' if skipped else '✓'} {label}")
        self.log.appendPlainText(f"{done}/{total}: {title}")
        if total and done >= total:
            self.progress_state.setText("✓ Extraction Complete")

    def cancel(self):
        self.cancel_event.set(); self.log.appendPlainText("Cancellation requested; temporary output will not be promoted.")

    def _set_next_steps_enabled(self, enabled: bool):
        for button in self.next_step_buttons: button.setEnabled(enabled)

    def failed(self, message: str, details: str) -> None:
        """Sprint 13: the workspace-specific half of the shared failure lifecycle --
        MainWindow.run_task() already shows the generic "Task Failed" dialog; this resets
        the screen's own in-progress state (buttons, progress bar) instead of leaving it
        stuck mid-run, and mirrors completed()'s panel structure for the failure case.
        `ExtractionService.run()` writes to a temporary directory and only replaces the
        real output on full success (see extraction.py) -- so it's accurate, not assumed,
        that nothing in the output folder was touched by a failed run.
        """
        self.cancel_button.setEnabled(False)
        self.progress_state.setText("✗ Task Failed")
        self.summary.setText(
            "<b style='color:#a33'>Task Failed</b><br>"
            + format_operator_error(
                message,
                "Nothing was written to your output folder — review the reason above, then try again.",
            )
        )
        self.summary_output.setText(""); self.summary_output.setToolTip("")
        self._set_next_steps_enabled(False)
        self.log.appendPlainText(f"FAILED: {message}")

    def completed(self, result):
        record = result.record
        self._last_record = record
        self.cancel_button.setEnabled(False)
        status_ok = record.status == "completed"
        state_text = {"completed": "✓ Extraction Complete", "cancelled": "Extraction cancelled", "failed": "Extraction failed"}
        self.progress_state.setText(state_text.get(record.status, record.status))
        color = "#287a3d" if status_ok else ("#9a5a00" if record.status == "cancelled" else "#a33")
        lines = [
            f"<b>Extraction {'Completed' if status_ok else record.status.title()}</b>",
            f"<br><b>Book</b><br>{self.book.filename if self.book else record.book_id}",
            f"<br><b>Sections expected</b><br>{record.expected_count}",
            f"<br><b>Sections written</b><br>{record.written_count}",
            f"<br><b>Skipped</b><br>{record.skipped_count}",
            f"<br><b>Failed</b><br>{record.failed_count}",
            f"<br><b>Elapsed time</b><br>{format_elapsed(record.started_at, record.completed_at)}",
        ]
        if record.error_summary:
            lines.append(f"<br><b style='color:#a33'>Error</b><br>{record.error_summary}")
        lines.append(f"<br><b>Status</b><br><b style='color:{color}'>{record.status.upper()}</b>")
        self.summary.setText("<br>".join(lines))
        if status_ok and record.output_location:
            output_path = Path(record.output_location)
            self.summary_output.setText(f"Run output: {short_output_path(output_path)}")
            self.summary_output.setToolTip(record.output_location)
        else:
            self.summary_output.setText("")
            self.summary_output.setToolTip("")
        self._set_next_steps_enabled(status_ok)
        self.log.appendPlainText(f"{record.status.upper()} · expected {record.expected_count}, written {record.written_count}, skipped {record.skipped_count}, failed {record.failed_count}\n{record.output_location}")

    def open_in_browser(self):
        if not self._last_record or self._last_record.status != "completed":
            return
        self.window.navigation.setCurrentRow(3)
        browser = self.window.screens[3]
        index = browser.run_filter.findData(self._last_record.run_id)
        if index >= 0:
            browser.run_filter.setCurrentIndex(index)

    def open_output_folder(self):
        output_root = Path(self.output.text())
        if output_root.exists():
            open_path(output_root)

    def open_run_folder(self):
        if self._last_record and self._last_record.output_location:
            open_path(Path(self._last_record.output_location))


class BrowserScreen(Screen):
    def __init__(self, window):
        super().__init__(window)
        # ---- shared run selector: run metadata lives outside both the outline tree and
        # the search results list, since neither one is "per run" (the outline is the
        # book's approved structure; the run only decides which extraction fills it in).
        self.run_filter = QComboBox(); self.run_filter.addItem("All runs", "")
        self.run_filter.currentIndexChanged.connect(self._run_selected)
        run_label = QLabel("Run"); run_label.setBuddy(self.run_filter)
        run_row = QHBoxLayout(); run_row.addWidget(run_label); run_row.addWidget(self.run_filter, 1)

        # ---- Outline tab: a pure sno+title tree over the approved outline records.
        self.outline_filter = QLineEdit(); self.outline_filter.setPlaceholderText("Filter outline titles…")
        self.outline_filter.textChanged.connect(self._apply_outline_filter)
        self.outline_tree = QTreeWidget()
        self.outline_tree.setColumnCount(2)
        self.outline_tree.setHeaderLabels(["Sno", "Title"])
        self.outline_tree.setColumnWidth(0, 56)
        self.outline_tree.header().setStretchLastSection(True)
        self.outline_tree.currentItemChanged.connect(self._outline_selection_changed)
        self.outline_tree.itemExpanded.connect(lambda item: self._set_expand_state(item, True))
        self.outline_tree.itemCollapsed.connect(lambda item: self._set_expand_state(item, False))
        self.outline_empty_label = QLabel("Select a book with an approved outline to browse its structure.")
        self.outline_empty_label.setWordWrap(True)
        self.outline_empty_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        outline_tab = QWidget(); outline_layout = QVBoxLayout(outline_tab); outline_layout.setContentsMargins(0, 0, 0, 0)
        outline_layout.addWidget(self.outline_filter); outline_layout.addWidget(self.outline_empty_label); outline_layout.addWidget(self.outline_tree)

        # ---- Full-text Search tab: unchanged text/kind/page search over extracted JSONL.
        self.query = QLineEdit(); self.query.setPlaceholderText("Search section titles and full text…"); self.query.returnPressed.connect(self.search)
        self.kind = QComboBox(); self.kind.addItem("All kinds", "")
        for entry_kind in sorted(KINDS): self.kind.addItem(entry_kind.title(), entry_kind)
        self.page_from = QSpinBox(); self.page_from.setRange(0, 100000); self.page_from.setSpecialValueText("Any page")
        self.page_to = QSpinBox(); self.page_to.setRange(0, 100000); self.page_to.setSpecialValueText("Any page")
        button = QPushButton("Search"); button.clicked.connect(self.search)
        clear_search = QPushButton("Clear Search"); clear_search.clicked.connect(self.clear_search)
        self.results = QListWidget(); self.results.currentRowChanged.connect(self.show_result)
        filters = QHBoxLayout()
        # QFormLayout.addRow(str, widget) auto-assigns a label's buddy; these two labels
        # sit in a plain QHBoxLayout instead, so the buddy has to be set explicitly for
        # the same keyboard/screen-reader association (Sprint 14, requirement #8).
        printed_from_label = QLabel("Printed from"); printed_from_label.setBuddy(self.page_from)
        printed_to_label = QLabel("to"); printed_to_label.setBuddy(self.page_to)
        for widget in (self.query, self.kind, printed_from_label, self.page_from, printed_to_label, self.page_to, button, clear_search): filters.addWidget(widget)
        self.empty_label = QLabel("No completed extractions yet. Extract a book from Workspace 4 — its corpus will appear here automatically.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.search_summary = QLabel(""); self.search_summary.setWordWrap(True); self.search_summary.setTextFormat(Qt.RichText)
        search_tab = QWidget(); search_layout = QVBoxLayout(search_tab); search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addLayout(filters); search_layout.addWidget(self.search_summary)
        search_layout.addWidget(self.empty_label); search_layout.addWidget(self.results)

        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(outline_tab, "Outline")
        self.left_tabs.addTab(search_tab, "Full-text Search")
        self.left_tabs.currentChanged.connect(self._tab_changed)

        # ---- shared centre/right panels: whichever tab is active drives these.
        copy = QPushButton("Copy Text"); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.text.toPlainText()))
        self.text = QTextEdit(); self.text.setReadOnly(True)
        self.text.document().setDocumentMargin(28)
        self.text.setFont(QFont(self.text.font().family(), 12))
        self.metadata = QLabel(); self.metadata.setWordWrap(True); self.metadata.setTextFormat(Qt.RichText)
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.clicked.connect(self._nav_prev)
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self._nav_next)
        self.reading_status = QLabel("")
        self.reading_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row = QHBoxLayout()
        nav_row.addWidget(self.prev_button); nav_row.addWidget(self.reading_status, 1); nav_row.addWidget(self.next_button)
        open_text = QPushButton("Open Section TXT"); open_text.clicked.connect(self.open_text)
        open_jsonl = QPushButton("Open JSONL"); open_jsonl.clicked.connect(self.open_jsonl)
        open_manifest = QPushButton("Open Manifest"); open_manifest.clicked.connect(self.open_manifest)
        export = QPushButton("Export Results"); export.clicked.connect(self.export_results)
        open_pdf = QPushButton("Open Source PDF"); open_pdf.clicked.connect(lambda: open_path(self.book.path) if self.book else None)
        reveal = QPushButton("Reveal Output"); reveal.clicked.connect(self.reveal)
        actions = QHBoxLayout()
        for widget in (copy, open_text, open_jsonl, open_manifest, open_pdf, export, reveal): actions.addWidget(widget)

        left = QWidget(); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(run_row); left_layout.addWidget(self.left_tabs)
        split = QSplitter(); split.addWidget(left)
        right = QWidget(); right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.metadata); right_layout.addLayout(nav_row); right_layout.addWidget(self.text)
        split.addWidget(right)
        self.preview = PdfTextPreview()
        split.addWidget(self.preview)
        configure_splitter(split, self.window, "browser.results", [380, 700, 700])
        layout = QVBoxLayout(self); layout.addLayout(actions); layout.addWidget(split)

        self.items = []
        self.outline_entries: list[OutlineEntry] = []
        self._sno_to_item: dict[int, QTreeWidgetItem] = {}
        self._sno_to_record: dict[int, dict] = {}
        self._expand_state: dict[str, dict[int, bool]] = {}
        self.current_entry: OutlineEntry | None = None
        self.current_content: dict | None = None
        self._preview_book_id = None

    def selection_changed(self):
        self.run_filter.blockSignals(True)
        self.run_filter.clear(); self.run_filter.addItem("All runs", "")
        records = self.window.services.history.records(self.book.book_id if self.book else None)
        completed = [record for record in records if record.status == "completed"]
        for record in completed:
            self.run_filter.addItem(record.run_id, record.run_id)
        saved_run_id = self.window.services.settings.ui_layouts.get("browser.last_run", "")
        default_run_id = saved_run_id if any(r.run_id == saved_run_id for r in completed) else (completed[0].run_id if completed else "")
        index = self.run_filter.findData(default_run_id) if default_run_id else 0
        self.run_filter.setCurrentIndex(index if index >= 0 else 0)
        self.run_filter.blockSignals(False)
        if not self.book:
            self.metadata.setText("Showing completed extractions across all books.")
        self._load_run_sections()
        self._populate_outline()
        self.search()

    def _run_selected(self):
        self.window.services.settings.ui_layouts["browser.last_run"] = self.run_filter.currentData() or ""
        self.window.services.settings_service.save(self.window.services.settings)
        self._load_run_sections()
        self.search()
        if self.current_entry is not None:
            self.current_content = self._sno_to_record.get(self.current_entry.sno)
            if self.left_tabs.currentIndex() == 0:
                self._render_outline_current()

    def _load_run_sections(self) -> None:
        """Looks up the currently selected run's extracted JSONL for the current book, keyed
        by sno, so the outline tree can show each node's extracted text without itself being
        built from (or duplicating) any search/extraction record."""
        self._sno_to_record = {}
        run_id = self.run_filter.currentData()
        book = self.book
        if not run_id or not book:
            return
        jsonl_path = self.window.services.output_dir / "runs" / run_id / "jsonl" / f"{book.book_id}_sections.jsonl"
        if not jsonl_path.exists():
            return
        section_dir = jsonl_path.parents[1] / "sections" / book.book_id
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            record["jsonl_path"] = str(jsonl_path)
            matches = list(section_dir.glob(f"{int(record.get('sno', 0)):03d}_*.txt"))
            record["txt_path"] = str(matches[0]) if matches else ""
            self._sno_to_record[record.get("sno")] = record

    # ---- Outline tab -------------------------------------------------------------

    def _populate_outline(self) -> None:
        """Builds the outline tree exclusively from the book's approved outline records
        (never from search/extraction results), nesting level 1/2/3 entries in source
        order via a level-stack -- the same nesting rule a table of contents uses, and
        the one field (`level`) every outline-creation path already fills in."""
        self.outline_tree.blockSignals(True)
        self.outline_tree.clear()
        self._sno_to_item = {}
        self.outline_entries = []
        book = self.book
        if book:
            approval = self.window.services.outlines.approval(book.book_id)
            if approval and approval.approved:
                _, clean, _ = self.window.services.outlines.paths(book.book_id)
                if clean.exists():
                    self.outline_entries = self.window.services.outlines.load(clean)
        stack: list[tuple[int, QTreeWidgetItem]] = []
        for entry in self.outline_entries:
            level = max(1, min(entry.level or 1, 3))
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_item = stack[-1][1] if stack else self.outline_tree.invisibleRootItem()
            item = QTreeWidgetItem()
            item.setText(0, str(entry.sno)); item.setText(1, entry.title)
            item.setToolTip(1, entry.title)
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            parent_item.addChild(item)
            self._sno_to_item[entry.sno] = item
            stack.append((level, item))
        self.outline_tree.blockSignals(False)
        self._apply_expand_state()
        if self.outline_entries:
            self.outline_empty_label.setVisible(False)
            self.outline_tree.setCurrentItem(self.outline_tree.topLevelItem(0))
        else:
            self.outline_empty_label.setText(
                "Select a book with an approved outline to browse its structure."
                if not book else "This book has no approved outline yet."
            )
            self.outline_empty_label.setVisible(True)
            self.outline_tree.setCurrentItem(None)
            self.current_entry = None; self.current_content = None
            if self.left_tabs.currentIndex() == 0:
                self._render_outline_current()

    def _apply_expand_state(self) -> None:
        book_id = self.book.book_id if self.book else None
        state = self._expand_state.get(book_id, {}) if book_id else {}

        def recurse(item):
            for index in range(item.childCount()):
                child = item.child(index)
                entry = child.data(0, Qt.ItemDataRole.UserRole)
                default_expanded = bool(entry and entry.level <= 1)
                child.setExpanded(state.get(entry.sno, default_expanded) if entry else default_expanded)
                recurse(child)

        recurse(self.outline_tree.invisibleRootItem())

    def _set_expand_state(self, item, expanded: bool) -> None:
        entry = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry or not self.book:
            return
        self._expand_state.setdefault(self.book.book_id, {})[entry.sno] = expanded

    def _apply_outline_filter(self) -> None:
        needle = self.outline_filter.text().casefold().strip()
        self.outline_tree.blockSignals(True)
        self._filter_item(self.outline_tree.invisibleRootItem(), needle)
        self.outline_tree.blockSignals(False)
        if not needle:
            self._apply_expand_state()

    def _filter_item(self, item, needle: str) -> bool:
        """Hides rows whose title doesn't match, but keeps ancestors of any surviving
        descendant visible (and expanded) so the match stays reachable in its outline
        context -- title-only filtering that never has to touch the extracted text."""
        any_visible_child = False
        for index in range(item.childCount()):
            child = item.child(index)
            entry = child.data(0, Qt.ItemDataRole.UserRole)
            self_match = (not needle) or bool(entry and needle in entry.title.casefold())
            descendant_visible = self._filter_item(child, needle)
            child_visible = self_match or descendant_visible
            child.setHidden(not child_visible)
            if needle and descendant_visible:
                child.setExpanded(True)
            any_visible_child = any_visible_child or child_visible
        return any_visible_child

    def _outline_selection_changed(self, current, _previous) -> None:
        entry = current.data(0, Qt.ItemDataRole.UserRole) if current else None
        self.current_entry = entry
        self.current_content = self._sno_to_record.get(entry.sno) if entry else None
        if self.left_tabs.currentIndex() == 0:
            self._render_outline_current()

    def _render_outline_current(self) -> None:
        entry = self.current_entry
        if entry is None:
            self.text.setPlainText("")
            self.metadata.setText("Select an outline entry to preview its extracted content.")
            self.preview.set_context("", "")
            self.reading_status.setText("")
            self.prev_button.setEnabled(False); self.next_button.setEnabled(False)
            return
        record = self.current_content
        if record:
            self._render_text(record.get("text", ""))
            self._render_reading_header(record)
            self._show_source_page(record)
        else:
            self._render_text("")
            self._render_entry_only_header(entry)
            self._show_source_page_for_entry(entry)
        self._render_outline_navigation_status(entry)

    def _render_entry_only_header(self, entry: OutlineEntry) -> None:
        book = self.book
        run = self._run_record_for_id(self.run_filter.currentData())
        run_started = format_timestamp(run.started_at) if run else "—"
        physical = self._resolved_physical_page(entry)
        lines = [
            f"<b>Book</b><br>{book.filename if book else '—'}",
            f"<br><b>Run</b><br>{run_started}",
            f"<br><b>Section</b><br>{entry.title}",
            f"<br><b>Printed Page</b><br>{entry.printed_start or '—'}",
            f"<br><b>Kind</b><br>{entry.kind}",
            f"<br><b>Physical Page</b><br>{physical or '—'}",
            "<br><b style='color:#9a5a00'>Not extracted in the selected run</b>",
        ]
        self.metadata.setText("<br>".join(lines))

    def _resolved_physical_page(self, entry: OutlineEntry) -> int | None:
        if not self.book:
            return entry.physical_start
        mapping = self.window.services.mappings.load(self.book.book_id)
        return mapping.resolve_entry(entry).physical_page

    def _show_source_page_for_entry(self, entry: OutlineEntry) -> None:
        book = self.book
        if not book or not book.path.exists():
            self.preview.set_context(entry.title, "source PDF unavailable")
            return
        physical = self._resolved_physical_page(entry)
        if self._preview_book_id != book.book_id:
            self.preview.set_pdf(book.path, book.page_count)
            self._preview_book_id = book.book_id
        if physical:
            self.preview.jump_to(physical)
        self.preview.set_context(entry.title, f"printed {entry.printed_start or '—'} · physical {physical or 'not mapped'}")

    def _render_outline_navigation_status(self, entry: OutlineEntry) -> None:
        total = len(self.outline_entries)
        index = next((i for i, item in enumerate(self.outline_entries) if item.sno == entry.sno), None)
        if index is not None:
            run = self._run_record_for_id(self.run_filter.currentData())
            run_status = run.status.title() if run else "—"
            self.reading_status.setText(f"Entry {index + 1} of {total} · Run: {run_status}")
            self.prev_button.setEnabled(index > 0)
            self.next_button.setEnabled(index < total - 1)
        else:
            self.reading_status.setText("")
            self.prev_button.setEnabled(False); self.next_button.setEnabled(False)

    def _outline_step(self, delta: int) -> None:
        if not self.outline_entries or self.current_entry is None:
            return
        index = next((i for i, e in enumerate(self.outline_entries) if e.sno == self.current_entry.sno), None)
        if index is None:
            return
        target = index + delta
        if 0 <= target < len(self.outline_entries):
            item = self._sno_to_item.get(self.outline_entries[target].sno)
            if item:
                self.outline_tree.setCurrentItem(item)

    # ---- Full-text Search tab -----------------------------------------------------

    def search(self):
        self.items = self.window.services.search.search(
            self.query.text(), self.book.book_id if self.book else None,
            self.run_filter.currentData() or None, self.kind.currentData() or None,
            self.page_from.value() or None, self.page_to.value() or None,
        )
        self.results.blockSignals(True)
        self.results.clear()
        for item in self.items:
            self.results.addItem(item["title"])
        self.results.setCurrentRow(0 if self.items else -1)
        self.results.blockSignals(False)
        self.empty_label.setVisible(not self.items)
        self._render_search_summary()
        if self.left_tabs.currentIndex() == 1:
            self._render_search_result(self.results.currentRow())

    def clear_search(self):
        """Reuses the existing search() exactly as-is -- just resets the query/kind/page
        filters to their defaults first. Run selection is left alone: which run you're
        browsing isn't a "search filter" to clear, it's the corpus you're in."""
        self.query.clear()
        self.kind.setCurrentIndex(0)
        self.page_from.setValue(0)
        self.page_to.setValue(0)
        self.search()

    def _run_record_for_id(self, run_id: str):
        if not run_id:
            return None
        records = self.window.services.history.records(self.book.book_id if self.book else None)
        return next((record for record in records if record.run_id == run_id), None)

    def _render_search_summary(self) -> None:
        """Consolidates Sprint 11's "Search Summary" (#1) and "Filter Awareness" (#6) into
        one panel -- their brief examples overlap (both describe result counts and active
        filters), so this avoids two near-duplicate widgets, matching Sprint 10's precedent
        of consolidating overlapping requirements into a single control."""
        count = len(self.items)
        run = self._run_record_for_id(self.run_filter.currentData())
        filters_active = bool(
            self.query.text() or self.kind.currentData() or self.page_from.value() or self.page_to.value()
        )
        lines = ["<b>Search Results</b>"]
        if run and run.written_count and count < run.written_count:
            lines.append(f"<br>Showing <b>{count}</b> of {run.written_count} sections")
        else:
            plural = "" if count == 1 else "s"
            lines.append(f"<br><b>{count}</b> matching section{plural}")
        if self.query.text():
            lines.append(f"<br><b>Search</b><br>“{html.escape(self.query.text())}”")
        if run:
            lines.append(f"<br><b>Run</b><br>{format_timestamp(run.started_at)}")
        if filters_active:
            lines.append("<br><b style='color:#9a5a00'>Filter Active</b>")
        self.search_summary.setText("".join(lines))

    def show_result(self, row):
        self._render_search_result(row)

    def _render_search_result(self, row: int) -> None:
        if 0 <= row < len(self.items):
            item = self.items[row]
            self._render_text(item.get("text", ""))
            self._render_reading_header(item)
            self._show_source_page(item)
        else:
            self.text.setPlainText("")
            has_runs = self.run_filter.count() > 1
            if not has_runs:
                self.metadata.setText("No completed extractions yet. Extract a book from Workspace 4 — its corpus will appear here automatically.")
            elif self.query.text() or self.kind.currentData() or self.page_from.value() or self.page_to.value():
                self.metadata.setText("No sections match the current search and filters. Clear a filter or choose a different run.")
            else:
                self.metadata.setText("This run has no extracted sections.")
        self._render_navigation_status(row)

    def _run_record_for(self, item: dict):
        run_id = item.get("run_id")
        if not run_id:
            return None
        records = self.window.services.history.records(item.get("book_id"))
        return next((record for record in records if record.run_id == run_id), None)

    def _render_reading_header(self, item: dict) -> None:
        """Structured "reading header" -- the same facts the old dense one-liner showed
        (kind, printed/physical pages, run, source hash), just labeled and reused, plus
        the book filename and run timestamp (both already present on the item/RunRecord)
        and a word count computed from the section text already loaded for display."""
        word_count = len(item.get("text", "").split())
        run = self._run_record_for(item)
        run_started = format_timestamp(run.started_at) if run else "—"
        lines = [
            f"<b>Book</b><br>{item.get('pdf', '—')}",
            f"<br><b>Run</b><br>{run_started}",
            f"<br><b>Section</b><br>{item.get('title', '—')}",
            f"<br><b>Printed Pages</b><br>{item.get('printed_start', '—')}–{item.get('printed_end', '—')}",
            f"<br><b>Words</b><br>{word_count:,}",
            f"<br><b>Kind</b><br>{item.get('kind', '—')}",
            f"<br><b>Physical Pages</b><br>{item.get('physical_start', '—')}–{item.get('physical_end', '—')}",
            f"<br><b>Source Hash</b><br>{item.get('source_pdf_hash', '—')}",
        ]
        self.metadata.setText("<br>".join(lines))

    def _render_text(self, text: str) -> None:
        """Render section text as HTML paragraphs purely for typography (margins, line and
        paragraph spacing) -- still read-only, no editing affordances added. Copy text keeps
        working unchanged since QTextEdit.toPlainText() already strips markup correctly."""
        paragraphs = [html.escape(part).replace("\n", "<br>") for part in text.split("\n\n") if part.strip()]
        body = "".join(f"<p style='margin:0 0 1em 0; line-height:1.6;'>{part}</p>" for part in paragraphs)
        self.text.setHtml(body)

    def _render_navigation_status(self, row: int) -> None:
        total = len(self.items)
        if 0 <= row < total:
            run = self._run_record_for(self.items[row])
            run_status = run.status.title() if run else "—"
            self.reading_status.setText(f"Section {row + 1} of {total} · Run: {run_status}")
        else:
            self.reading_status.setText("")
        self.prev_button.setEnabled(row > 0)
        self.next_button.setEnabled(0 <= row < total - 1)

    def _show_source_page(self, item: dict) -> None:
        book_id = item.get("book_id")
        physical_start = item.get("physical_start")
        try:
            book = self.window.services.library.get(book_id) if book_id else None
        except KeyError:
            book = None
        if not book or not book.path.exists():
            self.preview.set_context(item.get("title", ""), "source PDF unavailable")
            return
        if self._preview_book_id != book_id:
            self.preview.set_pdf(book.path, book.page_count)
            self._preview_book_id = book_id
        if physical_start:
            self.preview.jump_to(physical_start)
        self.preview.set_context(item.get("title", ""), f"printed {item.get('printed_start')} · physical {physical_start}")

    # ---- Shared navigation + actions (act on whichever tab is active) ------------

    def _tab_changed(self, index: int) -> None:
        if index == 0:
            self._render_outline_current()
        else:
            self._render_search_result(self.results.currentRow())

    def _nav_prev(self):
        if self.left_tabs.currentIndex() == 0:
            self._outline_step(-1)
        else:
            self.results.setCurrentRow(self.results.currentRow() - 1)

    def _nav_next(self):
        if self.left_tabs.currentIndex() == 0:
            self._outline_step(1)
        else:
            self.results.setCurrentRow(self.results.currentRow() + 1)

    def _active_content(self) -> dict | None:
        if self.left_tabs.currentIndex() == 0:
            return self.current_content
        row = self.results.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def open_text(self):
        content = self._active_content()
        if content and content.get("txt_path"):
            open_path(Path(content["txt_path"]))

    def open_jsonl(self):
        content = self._active_content()
        if content and content.get("jsonl_path"):
            open_path(Path(content["jsonl_path"]))

    def open_manifest(self):
        content = self._active_content()
        if content and content.get("jsonl_path"):
            run_dir = Path(content["jsonl_path"]).parents[1]
            manifests = list((run_dir / "manifests").glob("*.csv"))
            if manifests: open_path(manifests[0])

    def export_results(self):
        if not self.items: return
        filename, _ = QFileDialog.getSaveFileName(self, "Export search results", "search_results.json", "JSON (*.json)")
        if filename:
            Path(filename).write_text(json.dumps(self.items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def reveal(self):
        content = self._active_content()
        if content and content.get("jsonl_path"):
            reveal_path(Path(content["jsonl_path"]).parents[1])


class HistoryScreen(Screen):
    def __init__(self, window):
        super().__init__(window)
        refresh = QPushButton("Refresh Run History"); refresh.clicked.connect(self.refresh)
        open_output = QPushButton("Open Run Folder"); open_output.clicked.connect(self.open_output)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Run ID", "Started", "Status", "Book", "Expected", "Written", "Skipped", "Failed", "Output"])
        self.table.cellDoubleClicked.connect(self.open_in_browser)
        controller = configure_table(
            self.table, self.window, "history.runs",
            default_widths={0: 210, 1: 160, 2: 105, 3: 260, 4: 95, 5: 90, 6: 90, 7: 80, 8: 260},
            frozen_columns=(0,), content_caps={8: 760},
        )
        # The frozen Run ID column is a separate overlay QTableView (see
        # TableLayoutController._create_frozen_view) that never routes
        # through self.table's own mouse signals, so double-clicks there
        # need their own connection or they silently do nothing.
        if controller.frozen is not None:
            controller.frozen.doubleClicked.connect(lambda index: self.open_in_browser(index.row(), index.column()))
        self.empty_label = QLabel(
            "No extraction runs recorded.\n\nNext Step\nRun an extraction from Workspace 4 to see it listed here."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self); bar = QHBoxLayout(); bar.addWidget(refresh); bar.addWidget(open_output); bar.addWidget(best_fit_button(self.table)); bar.addStretch(); layout.addLayout(bar); layout.addWidget(self.empty_label); layout.addWidget(self.table)
        self.records = []

    def selection_changed(self): self.refresh()

    def _book_label(self, book_id: str) -> str:
        try:
            return self.window.services.library.get(book_id).filename
        except KeyError:
            return book_id

    def refresh(self):
        self.records = self.window.services.history.records(self.book.book_id if self.book else None)
        self.empty_label.setVisible(not self.records)
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            values = [
                record.run_id, format_timestamp(record.started_at), record.status,
                self._book_label(record.book_id), record.expected_count, record.written_count,
                record.skipped_count, record.failed_count, record.output_location,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 2:
                    item.setBackground(QColor(RUN_STATUS_COLORS.get(record.status, "#e0e0e0")))
                    item.setForeground(QColor("#1a1a1a"))
                if column == 8 and record.output_location:
                    output_path = Path(record.output_location)
                    item.setText(str(Path(*output_path.parts[-2:])) if len(output_path.parts) >= 2 else str(output_path))
                    item.setToolTip(record.output_location)
                self.table.setItem(row, column, item)

    def open_output(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.records) and self.records[row].output_location:
            open_path(Path(self.records[row].output_location))

    def open_in_browser(self, row: int, _column: int) -> None:
        if not (0 <= row < len(self.records)):
            return
        record = self.records[row]
        if record.status != "completed":
            self.window.show_notice("Cannot Open Run", "Only completed runs can be opened in Corpus Browser.")
            return
        try:
            book = self.window.services.library.get(record.book_id)
        except KeyError:
            book = None
        self.window.set_book(book)
        self.window.navigation.setCurrentRow(3)
        browser = self.window.screens[3]
        index = browser.run_filter.findData(record.run_id)
        if index >= 0:
            browser.run_filter.setCurrentIndex(index)


SETTINGS_LABELS: dict[str, str] = {
    "project_root": "Project Root",
    "input_pdf_dir": "Library Folder",
    "outline_dir": "Outline Directory",
    "output_dir": "Output Directory",
    "pdf_viewer_command": "PDF Viewer Command",
    "toc_scan_pages": "TOC Scan Pages",
    "index_scan_pages": "Index Scan Pages",
    "minimum_chars": "Default Minimum Characters",
    "ocr_status": "OCR",
}

SETTINGS_DESCRIPTIONS: dict[str, str] = {
    "project_root": "The root folder for this project. The folders below are typically inside it.",
    "input_pdf_dir": "Where source PDFs are read from when you add books in the Library.",
    "outline_dir": "Where outlines, page mappings, and approval records are stored for each book.",
    "output_dir": "Where extracted corpus files (text, JSONL, and manifests) will be written.",
    "pdf_viewer_command": "Optional external command used to open a PDF. Leave blank to use your system's default viewer.",
    "toc_scan_pages": "How many pages from the start of a PDF are scanned when detecting a table of contents.",
    "index_scan_pages": "How many pages from the end of a PDF are scanned when detecting an index.",
    "minimum_chars": "The default minimum number of characters a section must have to be written during extraction.",
    "ocr_status": "Whether OCR (optical character recognition) is available on this machine, used for scanned PDFs.",
}

# The four folders required for the application to function -- used for both the per-field
# validation status (#3) and the coarser Configuration Summary (#4); the summary intentionally
# covers all four rather than just the three named in the brief's illustrative example, since
# Outline Directory is exactly as required for the app to work as the other three.
SETTINGS_PATH_FIELDS = ("project_root", "input_pdf_dir", "outline_dir", "output_dir")


class SettingsScreen(Screen):
    def __init__(self, window):
        super().__init__(window)
        self.fields = {name: QLineEdit() for name in ("project_root", "input_pdf_dir", "outline_dir", "output_dir", "pdf_viewer_command")}
        self.toc = QSpinBox(); self.toc.setRange(1, 100)
        self.index = QSpinBox(); self.index.setRange(1, 100)
        self.minimum = QSpinBox(); self.minimum.setRange(1, 100000)
        self.ocr = QLabel()
        self.path_status_labels: dict[str, QLabel] = {}

        self.config_banner = QLabel("")
        self.config_banner.setWordWrap(True)
        self.config_banner.setTextFormat(Qt.RichText)
        self.config_banner.setStyleSheet("background: #fdf0d5; color: #7a4a00; padding: 8px; border-radius: 4px;")
        self.config_banner.setVisible(False)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        summary_box = QGroupBox("Configuration Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary)

        project_group = self._group("Project", (
            ("project_root", True), ("input_pdf_dir", True), ("outline_dir", True), ("output_dir", True),
        ))
        parsing_group = self._group("Parsing & Detection", (("toc_scan_pages", False), ("index_scan_pages", False)))
        extraction_group = self._group("Extraction Defaults", (
            ("minimum_chars", False), ("pdf_viewer_command", False),
        ))
        diagnostics_group = self._group("Diagnostics", (("ocr_status", False),))

        save = QPushButton("Save Local Settings"); save.clicked.connect(self.save)
        layout = QVBoxLayout(self)
        layout.addWidget(self.config_banner)
        layout.addWidget(summary_box)
        layout.addWidget(project_group)
        layout.addWidget(parsing_group)
        layout.addWidget(extraction_group)
        layout.addWidget(diagnostics_group)
        layout.addWidget(save)
        layout.addStretch()
        self.load()

    def _group(self, title: str, items: tuple[tuple[str, bool], ...]) -> QGroupBox:
        """Build one logical settings group. `items` is (field_name, is_path) pairs; a path
        field gets a "Choose…" browse button and a live validation status label (#3) under it."""
        box = QGroupBox(title)
        form = QFormLayout(box)
        for name, is_path in items:
            widget = {
                "toc_scan_pages": self.toc, "index_scan_pages": self.index,
                "minimum_chars": self.minimum, "ocr_status": self.ocr,
            }.get(name, self.fields.get(name))
            label = SETTINGS_LABELS.get(name, name.replace("_", " ").title())
            if is_path:
                container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(widget)
                browse = QPushButton("Choose…")
                browse.clicked.connect(lambda _checked=False, target=widget: self.choose_folder(target))
                row.addWidget(browse)
                form.addRow(label, container)
                status = QLabel("")
                self.path_status_labels[name] = status
                form.addRow("", status)
                widget.textChanged.connect(self.update_status)
            else:
                form.addRow(label, widget)
            description = QLabel(SETTINGS_DESCRIPTIONS.get(name, ""))
            description.setWordWrap(True)
            description.setStyleSheet("color: #666; font-size: 11px;")
            form.addRow("", description)
        return box

    def load(self):
        settings = self.window.services.settings
        for name, widget in self.fields.items(): widget.setText(str(getattr(settings, name)))
        self.toc.setValue(settings.toc_scan_pages); self.index.setValue(settings.index_scan_pages); self.minimum.setValue(settings.minimum_chars); self.ocr.setText(settings.ocr_status)
        self.update_status()

    def save(self):
        settings = AppSettings(
            **{name: widget.text() for name, widget in self.fields.items()},
            toc_scan_pages=self.toc.value(), index_scan_pages=self.index.value(),
            minimum_chars=self.minimum.value(),
            ui_layouts=dict(self.window.services.settings.ui_layouts),
        )
        self.window.services.settings_service.save(settings); self.window.services.settings = settings; self.window.services.rebuild(); self.window.statusBar().showMessage("Local settings saved.", 5000)
        self.update_status()

    def choose_folder(self, field):
        value = QFileDialog.getExistingDirectory(self, "Choose folder", field.text())
        if value: field.setText(value)

    def _path_status(self, raw: str) -> tuple[str, str]:
        """Read-only, presentation-only path inspection -- no configuration logic, storage,
        or validation *rule* is introduced; it only reports filesystem facts about whatever
        the operator has already typed or saved. No pre-existing path-validation mechanism
        was found anywhere in the app to reuse (see Sprint 12 report)."""
        text = raw.strip()
        if not text:
            return "Not set", "#9a5a00"
        path = Path(text)
        if not path.exists():
            return "⚠ Directory not found", "#a33"
        if not path.is_dir():
            return "⚠ Not a directory", "#a33"
        if not os.access(path, os.W_OK):
            return "⚠ Not writable", "#a33"
        return "✓ Valid", "#287a3d"

    def update_status(self, *_args) -> None:
        """Refreshes both the per-field validation labels (#3) and the Configuration
        Summary + empty-state banner (#4/#5), all from the same per-path status computed
        once per field -- nothing is validated twice."""
        failing = []
        summary_lines = ["<b>Configuration Summary</b>"]
        for name in SETTINGS_PATH_FIELDS:
            status_text, color = self._path_status(self.fields[name].text())
            status_label = self.path_status_labels.get(name)
            if status_label is not None:
                status_label.setText(status_text)
                status_label.setStyleSheet(f"color: {color}")
            ok = status_text == "✓ Valid"
            if not ok:
                failing.append(SETTINGS_LABELS[name])
            state = "Configured" if ok else "Needs Attention"
            summary_lines.append(f"<br><b>{SETTINGS_LABELS[name]}</b><br><span style='color:{color}'>{state}</span>")
        ready = not failing
        status_color = "#287a3d" if ready else "#a33"
        summary_lines.append(f"<br><b>Status</b><br><b style='color:{status_color}'>{'READY' if ready else 'ACTION REQUIRED'}</b>")
        self.summary.setText("".join(summary_lines))
        if failing:
            self.config_banner.setText(
                "<b>Configuration Required</b><br>Choose a valid " + " / ".join(failing) + " to begin."
            )
        self.config_banner.setVisible(bool(failing))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.services = Services()
        self.selected_book = None
        self.threads: list[QThread] = []
        self.workers: list[FunctionWorker] = []
        self.threads: list[QThread] = []
        self.setWindowTitle("BOOKCORPUSBUILDER")
        self.resize(1440, 860)
        self.setMinimumSize(990, 580)
        self.book_label = QLabel("No book selected")
        self.stage_label = QLabel("Library")
        self.warning_label = QLabel("Select a book to begin")
        self.warning_label.setStyleSheet("color: #9a5a00")
        self.last_action = QLabel("Last action: —")
        # Shared, workspace-agnostic indeterminate task indicator (#2): run_task() shows
        # "<Task> running…" here for any task that doesn't have its own progress widget
        # (with_progress=False), and clears it on completion or failure. Lives in the
        # shared header, not inside any individual workspace, so it needs no changes to
        # frozen workspaces to give their background tasks *some* visible running state.
        self.task_indicator = QLabel("")
        self.task_indicator.setStyleSheet("color: #2457a6")
        header = QHBoxLayout(); header.addWidget(QLabel("BOOKCORPUSBUILDER")); header.addStretch(); header.addWidget(self.book_label); header.addWidget(self.stage_label); header.addWidget(self.warning_label); header.addWidget(self.task_indicator); header.addWidget(self.last_action)
        self.navigation = QListWidget(); self.navigation.addItems(["1. Library", "2. Structure Builder", "3. Extract", "4. Corpus Browser", "5. Run History", "6. Settings"]); self.navigation.setFixedWidth(175)
        self.stack = QStackedWidget()
        self.screens = [LibraryScreen(self), StructureBuilder(self), ExtractScreen(self), BrowserScreen(self), HistoryScreen(self), SettingsScreen(self)]
        for screen in self.screens: self.stack.addWidget(screen)
        self.navigation.currentRowChanged.connect(self.navigate); self.navigation.setCurrentRow(0)
        body = QHBoxLayout(); body.addWidget(self.navigation); body.addWidget(self.stack)
        root = QWidget(); layout = QVBoxLayout(root); layout.addLayout(header); layout.addLayout(body); self.setCentralWidget(root)
        self.setStyleSheet("""
            QWidget { font-size: 13px; }
            QPushButton { padding: 7px 10px; }
            QPushButton#primaryAction { background: #2457a6; color: white; font-weight: 600; padding: 9px 14px; }
            QPushButton#primaryAction:disabled { background: #9da8b8; color: #e9edf2; }
            QPushButton#sourceChoice { min-height: 30px; padding: 5px; font-size: 12px; font-weight: 600; }
            QPushButton#destructiveAction { color: #8b2525; border: 1px solid #c7a1a1; }
            QLabel#workflow { background: #edf3fb; color: #27415f; font-weight: 600; padding: 9px; border-radius: 4px; }
            QLabel#emptyState { background: #f5f7fa; color: #52606d; padding: 14px; border: 1px dashed #aab4bf; }
            QLabel#warningText { color: #8a4b08; font-weight: 600; }
            QGroupBox { font-weight: 600; margin-top: 8px; padding-top: 8px; }
            QHeaderView::section { padding: 6px 9px; border-right: 3px solid #8f9aa8; border-bottom: 1px solid #778392; }
            QHeaderView::section:hover { border-right: 5px solid #4f8edc; }
            QTableView, QTableWidget { gridline-color: #778392; }
            QSplitter::handle { background: #8f9aa8; }
            QSplitter::handle:hover { background: #4f8edc; }
            QListWidget { padding: 4px; }
        """)
        geometry = self.services.settings.ui_layouts.get("window/main")
        if geometry:
            try:
                self.restoreGeometry(b64decode(geometry))
            except (ValueError, TypeError):
                geometry = ""
        if not geometry:
            available = self.screen().availableGeometry()
            self.resize(max(1100, int(available.width() * 0.86)), max(700, int(available.height() * 0.86)))

    def closeEvent(self, event):
        self.services.settings.ui_layouts["window/main"] = b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        self.services.settings_service.save(self.services.settings)
        super().closeEvent(event)

    def navigate(self, index):
        if index < 0: return
        self.stack.setCurrentIndex(index); self.stage_label.setText(self.navigation.item(index).text()); self.screens[index].selection_changed()

    def set_book(self, book):
        self.selected_book = book; self.book_label.setText(book.filename if book else "No book selected")
        if book:
            approval = self.services.outlines.approval(book.book_id); mapping = self.services.mappings.load(book.book_id)
            self.warning_label.setText("Ready for extraction" if approval and approval.approved and mapping.approved else "Review outline and verify page mapping")
        else: self.warning_label.setText("Select a book to begin")
        for screen in self.screens[1:]: screen.selection_changed()

    def show_error(self, title, message, details=""):
        box = QMessageBox(QMessageBox.Icon.Critical, title, message, parent=self)
        if details: box.setDetailedText(details)
        box.exec()

    def show_notice(self, title, message):
        box = QMessageBox(QMessageBox.Icon.Information, title, message, parent=self)
        box.exec()

    def run_task(self, function, callback, *args, with_progress=False, progress_slot=None, on_failure=None, **kwargs):
        """Shared task lifecycle for every background operation in the app (Sprint 13).

        Every task moves through READY -> RUNNING -> COMPLETED/CANCELLED (both reach
        `callback` via `worker.finished`, unchanged) or FAILED (`worker.failed`). Before
        this sprint, a FAILED task only ever reached the generic error dialog -- the
        calling workspace's own `callback` was never invoked, so any in-progress UI state
        it had set (disabled buttons, a progress bar, a checklist) was left stuck. Fixed
        once here, centrally: `on_failure(message, details)` -- optional, since most
        existing callers have no visible "in progress" state to reset -- lets a workspace
        opt into resetting its own state, in addition to (not instead of) the shared
        dialog every caller already gets.
        """
        thread = QThread(self); worker = FunctionWorker(function, *args, with_progress=with_progress, **kwargs); worker.moveToThread(thread)
        task_title = function.__name__.replace("_", " ")
        if not with_progress:
            self.task_indicator.setText(f"⏳ {task_title} running…")
        thread.started.connect(worker.run)
        worker.finished.connect(callback)
        worker.finished.connect(lambda _result: self.last_action.setText(f"Last action: {function.__name__} succeeded"))
        worker.finished.connect(lambda _result: self.task_indicator.setText(""))
        worker.finished.connect(thread.quit)
        worker.failed.connect(lambda message, details: self.show_error(
            "Task Failed",
            format_operator_error(message, "Review the reason above, then try again."),
            details,
        ))
        worker.failed.connect(lambda _message, _details: self.last_action.setText(f"Last action: {function.__name__} failed"))
        worker.failed.connect(lambda _message, _details: self.task_indicator.setText(""))
        if on_failure: worker.failed.connect(on_failure)
        worker.failed.connect(thread.quit)
        if progress_slot: worker.progress.connect(progress_slot)
        thread.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self.threads.remove(thread) if thread in self.threads else None)
        thread.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        self.threads.append(thread); self.workers.append(worker); thread.start()

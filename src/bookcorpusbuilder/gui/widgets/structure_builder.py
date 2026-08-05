from __future__ import annotations

import csv
import json
import re
import traceback
from dataclasses import asdict
from io import StringIO
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...ollama_outline_generator import generate_outline_with_ollama
from ...outline_contract_repository import OutlineContractRepository
from ..models import OutlineCandidate, OutlineEntry, Severity
from ..services.json_outline_importer import JsonOutlineImportError, JsonOutlineImporter
from ..services.outline_text_parser import OutlineMergeService, OutlineTextParser
from ..services.outlines import FIELDS, KINDS
from .dialogs import confirm_destructive, format_operator_error
from .page_mapping import PageMappingPanel
from .pdf_preview import PdfTextPreview
from .table_usability import best_fit_button, configure_splitter, configure_table

# Kind options for the "3 · Parsing preview" candidate table's Kind column (Tab A,
# "A. Create Structure"). Derived from services.outlines.KINDS rather than a separately
# maintained list -- four independently-drifted kind lists across the codebase (this one,
# KINDS, the EntryKind contract enum, and json_outline_importer's ACCEPTED_KINDS) were
# reconciled into one inclusive set; deriving this tuple from KINDS keeps it that way.
CANDIDATE_KIND_OPTIONS = tuple(sorted(KINDS))


class StructureBuilder(QWidget):
    """Paste-first source intake followed by authoritative outline review."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.parser = OutlineTextParser()
        self.json_importer = JsonOutlineImporter()
        self.merger = OutlineMergeService()
        self.candidate_records: list[OutlineCandidate] = []
        self.active_contract = None
        self._loading_candidates = False
        self._loading_outline = False

        self.preview = PdfTextPreview()
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_bar = QHBoxLayout()
        preview_bar.addWidget(QLabel("PDF / text reference"))
        preview_bar.addStretch()
        open_pdf = QPushButton("Open Source PDF")
        open_pdf.clicked.connect(self.open_pdf)
        preview_bar.addWidget(open_pdf)
        preview_layout.addLayout(preview_bar)
        preview_layout.addWidget(self.preview)

        self.stage = QLabel()
        self.stage.setObjectName("workflow")
        self.stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage.setWordWrap(True)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tab(), "A. Create Structure")
        self.tabs.addTab(self._review_tab(), "B. Review Outline")
        # Page Alignment used to be its own top-level workspace; every outline node's
        # structural identity and its printed/physical page location are now reviewed in one
        # workspace instead of two. This only relocates the UI into a tab -- PageMapping,
        # MappingAnchor, and MappingService (the mapping algorithm and its book-scoped
        # persistence) are untouched.
        self.page_mapping = PageMappingPanel(self.window, self.preview)
        self.tabs.addTab(self.page_mapping, "C. Page Mapping")
        self.tabs.currentChanged.connect(self.update_stage)

        split = QSplitter()
        split.addWidget(preview_panel)
        split.addWidget(self.tabs)
        configure_splitter(split, self.window, "structure.main", [480, 960])
        layout = QVBoxLayout(self)
        layout.addWidget(self.stage)
        layout.addWidget(split)

        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self.save_draft)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.parse_preview)
        QShortcut(QKeySequence.StandardKey.Delete, self.candidate_table).activated.connect(self.delete_candidate)
        QShortcut(QKeySequence("Alt+Up"), self.candidate_table).activated.connect(lambda: self.move_candidate(-1))
        QShortcut(QKeySequence("Alt+Down"), self.candidate_table).activated.connect(lambda: self.move_candidate(1))
        # Same Alt+Up/Down/Delete convention as the candidate table above, mirrored onto the
        # canonical outline table — Move Up/Down and Delete previously had no keyboard path here.
        QShortcut(QKeySequence.StandardKey.Delete, self.table).activated.connect(self.delete_row)
        QShortcut(QKeySequence("Alt+Up"), self.table).activated.connect(lambda: self.move(-1))
        QShortcut(QKeySequence("Alt+Down"), self.table).activated.connect(lambda: self.move(1))
        self.update_stage()
        self.selection_changed()

    @property
    def book(self):
        return self.window.selected_book

    def _create_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        source_group = QGroupBox("1 · Choose a structure source")
        source_layout = QHBoxLayout(source_group)
        actions = (
            ("Paste outline", lambda: self.paste_text.setFocus()),
            ("Detect from PDF", self.detect_from_pdf),
            ("Import CSV…", self.import_csv),
            ("Import JSON…", self.import_json),
            ("Generate with Ollama…", self.generate_with_ollama),
            ("Build manually", self.manual_candidate),
        )
        for label, callback in actions:
            button = QPushButton(label)
            button.setObjectName("sourceChoice")
            button.clicked.connect(callback)
            source_layout.addWidget(button)
        layout.addWidget(source_group)

        paste_group = QGroupBox("2 · Pasted TOC / outline")
        paste_layout = QVBoxLayout(paste_group)
        self.paste_text = QPlainTextEdit()
        self.paste_text.setObjectName("pasteOutlineEditor")
        self.paste_text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.paste_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.paste_text.setMaximumHeight(92)
        self.paste_text.setPlaceholderText(
            "Paste a TOC, spreadsheet rows, or a manually prepared outline.\n"
            "Chapter One\nPerspective ........ 1\n\n1,The Seaman's Point of View,24"
        )
        self.paste_text.textChanged.connect(self.update_actions)
        paste_layout.addWidget(self.paste_text)
        paste_buttons = QHBoxLayout()
        clear = QPushButton("Clear")
        clear.setObjectName("destructiveAction")
        clear.clicked.connect(self.clear_paste)
        clipboard = QPushButton("Paste from Clipboard")
        clipboard.clicked.connect(self.paste_from_clipboard)
        self.parse_button = QPushButton("Parse Preview")
        self.parse_button.setObjectName("primaryAction")
        self.parse_button.clicked.connect(self.parse_preview)
        paste_buttons.addWidget(clear)
        paste_buttons.addWidget(clipboard)
        paste_buttons.addStretch()
        paste_buttons.addWidget(self.parse_button)
        paste_layout.addLayout(paste_buttons)
        layout.addWidget(paste_group, 1)

        candidate_group = QGroupBox("3 · Parsing preview — edits here do not alter the draft")
        candidate_layout = QVBoxLayout(candidate_group)
        self.candidate_empty = QLabel()
        self.candidate_empty.setObjectName("emptyState")
        self.candidate_empty.setWordWrap(True)
        candidate_layout.addWidget(self.candidate_empty)
        self.import_diagnostics = QPlainTextEdit()
        self.import_diagnostics.setObjectName("jsonImportDiagnostics")
        self.import_diagnostics.setReadOnly(True)
        self.import_diagnostics.setMaximumHeight(76)
        self.import_diagnostics.setVisible(False)
        candidate_layout.addWidget(self.import_diagnostics)
        self.candidate_table = QTableWidget(0, 11)
        self.candidate_table.setObjectName("candidateTable")
        self.candidate_table.setHorizontalHeaderLabels(
            ["Include", "Sno", "Title", "Kind", "Printed Page", "Physical Start", "PDF Index",
             "Level", "Source", "Confidence", "Warning"]
        )
        self.candidate_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidate_table.setMinimumHeight(92)
        configure_table(
            self.candidate_table, self.window, "structure.candidates",
            default_widths={0: 70, 1: 90, 2: 500, 3: 130, 4: 110, 5: 100, 6: 100, 7: 70, 8: 150, 9: 105, 10: 280},
            frozen_columns=(0, 1, 2), content_caps={2: 760, 10: 440},
        )
        self.candidate_table.itemChanged.connect(self.candidate_edited)
        self.candidate_table.itemSelectionChanged.connect(self.show_candidate_detail)
        candidate_layout.addWidget(self.candidate_table, 1)
        tools = QHBoxLayout()
        tools.addWidget(best_fit_button(self.candidate_table))
        for label, callback in (
            ("Delete", self.delete_candidate),
            ("Up", lambda: self.move_candidate(-1)),
            ("Down", lambda: self.move_candidate(1)),
            ("Copy", self.copy_candidates),
            ("Inspect", self.inspect_candidate),
            ("Export…", self.export_candidate_preview),
        ):
            button = QPushButton(label)
            if label == "Delete":
                button.setObjectName("destructiveAction")
            button.clicked.connect(callback)
            tools.addWidget(button)
        tools.addStretch()
        candidate_layout.addLayout(tools)
        self.candidate_detail = QPlainTextEdit()
        self.candidate_detail.setReadOnly(True)
        self.candidate_detail.setMaximumHeight(48)
        self.candidate_detail.setPlaceholderText(
            "Select a candidate to inspect its original text, parser rule, and warnings."
        )
        accept = QHBoxLayout()
        self.merge_button = QPushButton("Merge into Current Draft")
        self.merge_button.clicked.connect(self.merge_into_draft)
        self.create_button = QPushButton("Create New Outline")
        self.create_button.setObjectName("primaryAction")
        self.create_button.clicked.connect(self.create_new_outline)
        accept.addStretch()
        accept.addWidget(self.merge_button)
        accept.addWidget(self.create_button)
        candidate_layout.addLayout(accept)
        layout.addWidget(candidate_group, 2)
        return tab

    def _review_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        source_group = QGroupBox("Source")
        source_row = QHBoxLayout(source_group)
        load = QPushButton("Load Existing Draft")
        load.clicked.connect(self.load_draft)
        another = QPushButton("Add from Another Source")
        another.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        source_row.addWidget(load)
        source_row.addWidget(another)
        source_row.addStretch()
        layout.addWidget(source_group)

        self.editing_status = QLabel()
        self.editing_status.setWordWrap(True)
        layout.addWidget(self.editing_status)

        self.review_empty = QLabel()
        self.review_empty.setObjectName("emptyState")
        self.review_empty.setWordWrap(True)
        layout.addWidget(self.review_empty)
        self.table = QTableWidget(0, 11)
        self.table.setObjectName("canonicalOutlineTable")
        self.table.setHorizontalHeaderLabels(
            ["Include", "Sno", "Title", "Kind", "Printed Start", "Physical Start", "PDF Index", "Level", "Source",
             "Review Status", "Semantic Status"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        configure_table(
            self.table, self.window, "structure.outline",
            default_widths={0: 70, 1: 90, 2: 500, 3: 160, 4: 110, 5: 110, 6: 100, 7: 70, 8: 155, 9: 120, 10: 150},
            frozen_columns=(0, 1, 2), content_caps={2: 760},
        )
        self.table.itemChanged.connect(self.outline_edited)
        self.table.itemSelectionChanged.connect(self.jump)
        self.validation = QPlainTextEdit()
        self.validation.setObjectName("outlineValidation")
        self.validation.setReadOnly(True)
        self.validation.setMinimumWidth(245)
        review_split = QSplitter()
        review_split.addWidget(self.table)
        review_split.addWidget(self.validation)
        configure_splitter(review_split, self.window, "structure.review", [760, 300])
        layout.addWidget(review_split, 1)

        edit_tools_row = QHBoxLayout()
        edit_tools_row.addWidget(best_fit_button(self.table))
        edit_tools_row.addStretch()
        layout.addLayout(edit_tools_row)

        row_ops_group = QGroupBox("Row Operations")
        row_ops_row = QHBoxLayout(row_ops_group)
        for label, callback in (
            ("Add", self.add_row),
            ("Duplicate", self.duplicate_row),
            ("Delete", self.delete_row),
            ("Move Up", lambda: self.move(-1)),
            ("Move Down", lambda: self.move(1)),
        ):
            button = QPushButton(label)
            if label == "Delete":
                button.setObjectName("destructiveAction")
            button.clicked.connect(callback)
            row_ops_row.addWidget(button)
        row_ops_row.addStretch()

        structure_group = QGroupBox("Structure")
        structure_row = QHBoxLayout(structure_group)
        sort_button = QPushButton("Sort")
        sort_button.clicked.connect(self.sort_printed)
        structure_row.addWidget(sort_button)
        structure_row.addStretch()

        edit_groups_row = QHBoxLayout()
        edit_groups_row.addWidget(row_ops_group, 2)
        edit_groups_row.addWidget(structure_group, 1)
        layout.addLayout(edit_groups_row)

        save_group = QGroupBox("Save and Continue")
        save_row = QHBoxLayout(save_group)
        copy_csv = QPushButton("Copy CSV")
        copy_csv.clicked.connect(lambda: self.copy_outline("csv"))
        copy_text = QPushButton("Copy Text")
        copy_text.clicked.connect(lambda: self.copy_outline("text"))
        self.save_button = QPushButton("Save Draft")
        self.save_button.setObjectName("primaryAction")
        self.save_button.clicked.connect(self.save_draft)
        self.approve_button = QPushButton("Approve Outline")
        self.approve_button.setObjectName("primaryAction")
        self.approve_button.clicked.connect(self.approve)
        save_row.addWidget(copy_csv)
        save_row.addWidget(copy_text)
        save_row.addStretch()
        save_row.addWidget(self.save_button)
        save_row.addWidget(self.approve_button)
        layout.addWidget(save_group)
        return tab

    def selection_changed(self):
        self.preview.set_pdf(self.book.path if self.book else None, self.book.page_count if self.book else 0)
        self.set_candidate_records([])
        self.set_import_diagnostics("")
        self.active_contract = None
        self.load_draft()
        self.update_empty_states()
        self.update_actions()
        self.page_mapping.selection_changed()

    def open_pdf(self):
        if not self.book:
            self.no_book_error()
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.book.path.resolve())))

    def no_book_error(self):
        QMessageBox.information(
            self, "No book selected", "Open Library, add or select a PDF, then return to Structure Builder."
        )

    def clear_paste(self):
        if self.paste_text.toPlainText() and not confirm_destructive(
            self, "Clear pasted text?", "Clear the pasted outline text?"
        ):
            return
        self.paste_text.clear()

    def paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        if not text:
            QMessageBox.information(self, "Clipboard is empty", "Copy outline text locally, then try again.")
            return
        self.paste_text.insertPlainText(text)

    def parse_preview(self):
        if not self.book:
            self.no_book_error()
            return
        if not self.paste_text.toPlainText().strip():
            QMessageBox.information(self, "Nothing pasted", "Paste a Table of Contents or outline before parsing.")
            return
        pasted = self.paste_text.toPlainText()
        if pasted.lstrip().startswith(("{", "[")):
            answer = QMessageBox.question(
                self,
                "Structured JSON detected",
                "This appears to be JSON. Import it as structured JSON?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.import_json_text(pasted)
            else:
                self.window.statusBar().showMessage(
                    "JSON was not imported and was not sent to the free-form parser.", 7000
                )
            return
        self.set_import_diagnostics("")
        self.active_contract = None
        result = self.parser.parse(pasted)
        self.set_candidate_records(result.candidates)
        if not result.usable_count:
            self.candidate_empty.setText(
                "No structured entries were detected. Review the pasted text, import another format, or build manually."
            )
            self.candidate_empty.setVisible(True)
        self.update_stage()

    def set_candidate_records(self, candidates):
        self._loading_candidates = True
        self.candidate_records = list(candidates)
        self.candidate_table.setRowCount(len(candidates))
        for row, candidate in enumerate(candidates):
            values = [
                "", candidate.source_sno or candidate.sno or "", candidate.title, candidate.kind,
                candidate.printed_page_label or candidate.printed_page or "",
                "" if candidate.physical_start is None else candidate.physical_start,
                "" if candidate.pdf_page_index is None else candidate.pdf_page_index,
                candidate.level, candidate.source, f"{candidate.confidence:.0%}",
                ", ".join(candidate.warning_codes) or "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setFlags((item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
                    item.setCheckState(Qt.CheckState.Checked if candidate.include else Qt.CheckState.Unchecked)
                if column in (3, 8, 9, 10):
                    # Column 3 (Kind) is edited exclusively through the combo box set below;
                    # this item just holds the raw stored value for candidate_edited() to read back.
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.candidate_table.setItem(row, column, item)
            self.candidate_table.setCellWidget(row, 3, self._build_candidate_kind_combo(row, candidate.kind))
        self._loading_candidates = False
        self.update_empty_states()
        self.update_actions()

    def _build_candidate_kind_combo(self, row: int, kind: str) -> QComboBox:
        combo = QComboBox()
        if kind not in CANDIDATE_KIND_OPTIONS:
            combo.addItem(f"⚠ {kind or '(blank)'} — needs review", kind)
        for option in CANDIDATE_KIND_OPTIONS:
            combo.addItem(option.replace("_", " ").title(), option)
        index = combo.findData(kind)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(lambda _index, r=row: self._candidate_kind_changed(r))
        return combo

    def _candidate_kind_changed(self, row: int):
        if self._loading_candidates:
            return
        combo = self.candidate_table.cellWidget(row, 3)
        kind_item = self.candidate_table.item(row, 3)
        if combo is None or kind_item is None:
            return
        kind_item.setText(combo.currentData())  # triggers itemChanged -> candidate_edited()

    def candidate_edited(self, item):
        if self._loading_candidates or not (0 <= item.row() < len(self.candidate_records)):
            return
        candidate = self.candidate_records[item.row()]
        value = lambda column: self.candidate_table.item(item.row(), column).text().strip()
        candidate.include = self.candidate_table.item(item.row(), 0).checkState() == Qt.CheckState.Checked
        old_source_sno = candidate.source_sno
        candidate.source_sno = value(1)
        candidate.sno = int(value(1)) if value(1).isdigit() and int(value(1)) > 0 else item.row() + 1
        if old_source_sno and old_source_sno != candidate.source_sno:
            for child in self.candidate_records:
                if child.parent_sno == old_source_sno:
                    child.parent_sno = candidate.source_sno
        candidate.title = value(2)
        candidate.kind = value(3).casefold() or "section"
        page = value(4)
        candidate.printed_page = int(page) if page.isdigit() else None
        candidate.printed_page_label = page
        physical = value(5)
        candidate.physical_start = int(physical) if physical.isdigit() and int(physical) >= 1 else None
        pdf_index = value(6)
        candidate.pdf_page_index = int(pdf_index) if pdf_index.lstrip("-").isdigit() and int(pdf_index) >= 0 else None
        candidate.warning_codes = [
            code for code in candidate.warning_codes
            if code not in {
                "missing_page", "missing_printed_page", "ambiguous_page", "roman_page",
                "invalid_physical_start", "invalid_pdf_index", "pdf_index_mismatch",
            }
        ]
        if not page:
            candidate.warning_codes.append(
                "missing_printed_page" if candidate.parser_rule == "json_import" else "missing_page"
            )
        elif not page.isdigit():
            candidate.warning_codes.append(
                "roman_page" if re.fullmatch(r"[ivxlcdm]+", page, re.IGNORECASE) else "ambiguous_page"
            )
        if physical and candidate.physical_start is None:
            candidate.warning_codes.append("invalid_physical_start")
        if pdf_index and candidate.pdf_page_index is None:
            candidate.warning_codes.append("invalid_pdf_index")
        if (
            candidate.physical_start is not None and candidate.pdf_page_index is not None
            and candidate.pdf_page_index != candidate.physical_start - 1
        ):
            candidate.warning_codes.append("pdf_index_mismatch")
        candidate.level = max(1, int(value(7))) if value(7).isdigit() else 1
        if "missing_printed_page" in candidate.warning_codes or not candidate.allow_extraction:
            candidate.include = False
            self._loading_candidates = True
            self.candidate_table.item(item.row(), 0).setCheckState(Qt.CheckState.Unchecked)
            self._loading_candidates = False
        candidate.edited_by_user = True
        self._loading_candidates = True
        self.candidate_table.item(item.row(), 10).setText(
            ", ".join(candidate.warning_codes) or "—"
        )
        self._loading_candidates = False
        self.update_actions()

    def show_candidate_detail(self):
        row = self.candidate_table.currentRow()
        if 0 <= row < len(self.candidate_records):
            candidate = self.candidate_records[row]
            physical_note = (
                f"physical page {candidate.physical_start}" if candidate.physical_start is not None
                else "not mapped to a physical page"
            )
            self.preview.set_context(
                candidate.title,
                f"Printed page {candidate.printed_page_label or 'missing'} — {physical_note}",
            )
            if candidate.physical_start is not None:
                self.preview.jump_to(candidate.physical_start)
            self.candidate_detail.setPlainText(
                f"Parser rule: {candidate.parser_rule}\nWarnings: {', '.join(candidate.warning_codes) or 'none'}\n"
                f"Boundary: {candidate.boundary_status or 'legacy'} · "
                f"Extraction allowed: {'yes' if candidate.allow_extraction else 'no'}\n"
                f"Raw source: {candidate.raw_text}"
            )

    def inspect_candidate(self):
        row = self.candidate_table.currentRow()
        if 0 <= row < len(self.candidate_records):
            candidate = self.candidate_records[row]
            QMessageBox.information(
                self,
                "Candidate source",
                f"Parser rule: {candidate.parser_rule}\n"
                f"Warnings: {', '.join(candidate.warning_codes) or 'none'}\n\n"
                f"Original text:\n{candidate.raw_text}",
            )

    def delete_candidate(self):
        row = self.candidate_table.currentRow()
        if row >= 0:
            records = list(self.candidate_records)
            records.pop(row)
            self.set_candidate_records(records)

    def move_candidate(self, direction):
        row = self.candidate_table.currentRow()
        target = row + direction
        if row >= 0 and 0 <= target < len(self.candidate_records):
            records = list(self.candidate_records)
            records[row], records[target] = records[target], records[row]
            self.set_candidate_records(records)
            self.candidate_table.selectRow(target)

    def manual_candidate(self):
        if not self.book:
            self.no_book_error()
            return
        self.active_contract = None
        records = list(self.candidate_records)
        records.append(OutlineCandidate(
            raw_text="Manual row", sno=len(records) + 1, title="New section",
            source="manual", confidence=1.0, parser_rule="manual",
        ))
        self.set_candidate_records(records)
        self.candidate_table.selectRow(len(records) - 1)
        self.candidate_table.editItem(self.candidate_table.item(len(records) - 1, 2))

    def detect_from_pdf(self):
        if not self.book:
            self.no_book_error()
            return
        self.window.run_task(self.window.services.outlines.detect, self.detected_entries, self.book)

    def detected_entries(self, entries):
        self.active_contract = None
        candidates = []
        for entry in entries:
            candidates.append(OutlineCandidate(
                raw_text=entry.title, sno=entry.sno, title=entry.title, kind=entry.kind,
                printed_page=entry.printed_start,
                printed_page_label=str(entry.printed_start or ""), level=entry.level,
                source="pdf_toc" if entry.source == "toc" else "pdf_heading",
                confidence=entry.confidence or 0.5, parser_rule=entry.source,
                warning_codes=[] if entry.printed_start else ["missing_page"],
            ))
        self.set_candidate_records(candidates)

    def import_csv(self):
        if not self.book:
            self.no_book_error()
            return
        self.active_contract = None
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import outline candidates", str(Path.home()), "CSV (*.csv)"
        )
        if not filename:
            return
        try:
            entries = self.window.services.outlines.load(Path(filename))
            candidates = [
                OutlineCandidate(
                    raw_text=entry.title, sno=entry.sno, title=entry.title, kind=entry.kind,
                    printed_page=entry.printed_start,
                    printed_page_label=entry.printed_page_label or str(entry.printed_start or ""),
                    level=entry.level, source="csv_import", confidence=1.0,
                    include=entry.include, parser_rule="csv_import", sno_explicit=True,
                )
                for entry in entries
            ]
            self.set_candidate_records(candidates)
        except Exception as exc:
            self.window.show_error(
                "Outline Import Failed",
                format_operator_error(
                    "The selected file could not be read as an outline.",
                    "Check that the file exists and is a valid outline CSV, then try importing again.",
                ),
                f"{exc}\n\n{traceback.format_exc()}",
            )

    def import_json(self):
        if not self.book:
            self.no_book_error()
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import structured JSON outline", str(Path.home()),
            "JSON outlines (*.json);;All files (*)",
        )
        if not filename:
            return
        try:
            text = Path(filename).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.window.show_error(
                "JSON Outline Import Failed",
                format_operator_error(
                    "The selected file could not be read.",
                    "Check that the file exists, is readable, and is UTF-8 encoded text, then try importing again.",
                ),
                f"{exc}\n\n{traceback.format_exc()}",
            )
            return
        self.import_json_text(text)

    def generate_with_ollama(self):
        if not self.book:
            self.no_book_error()
            return
        source_text = self.paste_text.toPlainText().strip()
        if not source_text:
            QMessageBox.information(
                self, "Source text required",
                "Paste the source pages or extracted text first. Ollama only generates review candidates.",
            )
            return
        model, accepted = QInputDialog.getText(
            self, "Generate structured candidates with Ollama", "Local Ollama model:",
            text="qwen3:8b",
        )
        if not accepted or not model.strip():
            return
        self.window.statusBar().showMessage(
            "Ollama is generating an unapproved schema-constrained candidate…", 7000
        )
        self.window.run_task(
            generate_outline_with_ollama,
            self.ollama_generated,
            source_text,
            model.strip(),
            {
                "book_id": self.book.book_id,
                "pdf_filename": self.book.filename,
                "pdf_sha256": self.book.source_hash,
                "title": Path(self.book.filename).stem,
                "total_pdf_pages": self.book.page_count,
            },
        )

    def ollama_generated(self, contract):
        result = self.import_json_text(contract.model_dump_json(indent=2))
        if result is not None:
            self.window.statusBar().showMessage(
                "Ollama candidate loaded for deterministic validation and human review; nothing was approved.",
                9000,
            )

    def import_json_text(self, text: str):
        if not self.book:
            self.no_book_error()
            return None
        self.active_contract = None
        try:
            result = self.json_importer.import_text(
                text,
                expected_book_id=self.book.book_id,
                expected_pdf_sha256=self.book.source_hash,
                expected_pdf_pages=self.book.page_count,
            )
        except JsonOutlineImportError as exc:
            self.set_import_diagnostics(f"ERROR · malformed_json · {exc}")
            self.window.show_error(
                "JSON Outline Import Failed",
                format_operator_error(
                    str(exc),
                    "Review the JSON against the outline schema (see the diagnostics panel below), then try importing again.",
                ),
                traceback.format_exc(),
            )
            return None
        self.set_candidate_records(result.candidates)
        self.active_contract = result.contract
        lines = [f"Import SHA-256: {result.import_hash}"]
        if result.book_metadata:
            metadata = " · ".join(
                f"{key.title()}: {value}" for key, value in result.book_metadata.items()
            )
            lines.append(f"Book metadata: {metadata}")
        if result.contract:
            lines.append(
                f"Contract: {result.contract.schema_name} v{result.contract.schema_version} · "
                f"Lifecycle: {result.lifecycle_state}"
            )
        if result.diagnostics:
            lines.extend(
                f"{item.severity.upper()} · {item.code} · {item.path} · {item.message}"
                for item in result.diagnostics
            )
        else:
            lines.append("PASSED · No JSON import diagnostics.")
        self.set_import_diagnostics("\n".join(lines))
        self.window.statusBar().showMessage(
            f"JSON preview loaded: {len(result.candidates)} candidate row(s), "
            f"{result.error_count} validation error(s).",
            7000,
        )
        return result

    def set_import_diagnostics(self, text: str):
        self.import_diagnostics.setPlainText(text)
        self.import_diagnostics.setVisible(bool(text))

    def selected_candidate_entries(self):
        entries = [
            candidate.to_outline_entry(index)
            for index, candidate in enumerate(self.candidate_records, 1)
            if candidate.include or candidate.parser_rule == "book_outline_contract_v1"
        ]
        used: set[int] = set()
        for entry in entries:
            if entry.sno in used:
                entry.sno = max(used, default=0) + 1
            used.add(entry.sno)
        return entries

    def create_new_outline(self):
        if not self.book:
            self.no_book_error()
            return
        entries = self.selected_candidate_entries()
        if not entries:
            QMessageBox.information(
                self, "No usable outline entries detected", "Include at least one candidate before creating a draft."
            )
            return
        invalid = [
            candidate for candidate in self.candidate_records
            if candidate.include and "ambiguous_page" in candidate.warning_codes
        ]
        if invalid:
            QMessageBox.warning(
                self, "Invalid printed page",
                "Correct or exclude candidates whose printed page is ambiguous before creating a draft.",
            )
            return
        draft, _, _ = self.window.services.outlines.paths(self.book.book_id)
        approval = self.window.services.outlines.approval(self.book.book_id)
        if approval and approval.approved:
            message = (
                "An approved clean outline is protected. Create a separate revised draft without "
                "overwriting the approved outline?"
            )
        elif draft.exists():
            message = "An unapproved draft already exists. Replace that draft with the selected candidates?"
        else:
            message = "Create a new draft from the selected candidates?"
        if QMessageBox.question(self, "Create New Outline", message) != QMessageBox.StandardButton.Yes:
            return
        self.window.services.outlines.save(draft, entries)
        self.window.services.outlines.save_candidate_provenance(
            self.book.book_id, self.candidate_records, "create_new_outline"
        )
        if self.active_contract is not None:
            OutlineContractRepository(self.window.services.outlines.outline_dir).save(
                self.active_contract, "candidate"
            )
        self.set_entries(entries)
        self.tabs.setCurrentIndex(1)
        self.window.statusBar().showMessage("Draft created from reviewed candidates.", 6000)

    def merge_into_draft(self):
        if not self.book:
            self.no_book_error()
            return
        if not self.candidate_records:
            QMessageBox.information(self, "No candidates", "Parse, detect, import, or add candidates before merging.")
            return
        draft = self.entries()
        analysis = self.merger.analyse(draft, self.candidate_records)
        resolutions = self.merge_preview_dialog(analysis)
        if resolutions is None:
            return
        merged = self.merger.apply(draft, analysis, resolutions)
        draft_path, _, _ = self.window.services.outlines.paths(self.book.book_id)
        self.window.services.outlines.save(draft_path, merged)
        self.window.services.outlines.save_candidate_provenance(
            self.book.book_id, self.candidate_records, "merge_into_draft"
        )
        self.set_entries(merged)
        self.tabs.setCurrentIndex(1)

    def merge_preview_dialog(self, analysis):
        dialog = QDialog(self)
        dialog.setWindowTitle("Merge preview")
        dialog.resize(900, 480)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            f"New rows: {len(analysis.new_rows)}   ·   Matching rows: {len(analysis.matching_rows)}   ·   "
            f"Conflicting rows: {len(analysis.conflicting_rows)}   ·   Ignored rows: {len(analysis.ignored_rows)}"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        if analysis.has_conflicts:
            warning = QLabel(
                "Conflicts are never replaced automatically. The conservative default is Keep draft."
            )
            warning.setObjectName("warningText")
            layout.addWidget(warning)
        rows = analysis.new_rows + analysis.matching_rows + analysis.conflicting_rows + analysis.ignored_rows
        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["Category", "Candidate", "Draft", "Reason", "Resolution"])
        configure_table(
            table, self.window, "structure.merge_preview",
            default_widths={0: 100, 1: 360, 2: 300, 3: 280, 4: 160},
            frozen_columns=(0, 1), content_caps={1: 520, 2: 460, 3: 420},
        )
        combos = {}
        for row, item in enumerate(rows):
            values = [
                item.category.upper(),
                f"{item.candidate.title} — {item.candidate.printed_page_label or 'no page'}",
                f"{item.draft.title} — {item.draft.printed_start}" if item.draft else "—",
                item.reason,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, cell)
            if item.category == "conflict":
                combo = QComboBox()
                combo.addItem("Keep draft", "keep_draft")
                combo.addItem("Use candidate", "use_candidate")
                combo.addItem("Keep both", "keep_both")
                combo.addItem("Exclude candidate", "exclude")
                table.setCellWidget(row, 4, combo)
                combos[item.candidate.candidate_id] = combo
            else:
                table.setItem(row, 4, QTableWidgetItem("Add" if item.category == "new" else "No change"))
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm merge")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return {candidate_id: combo.currentData() for candidate_id, combo in combos.items()}

    def entries(self):
        result = []
        for row in range(self.table.rowCount()):
            value = lambda column: self.table.item(row, column).text().strip() if self.table.item(row, column) else ""
            def number(column):
                return int(value(column)) if value(column).isdigit() else None
            printed = value(4)
            result.append(OutlineEntry(
                sno=number(1) or row + 1, title=value(2), kind=value(3).casefold() or "section",
                printed_start=int(printed) if printed.isdigit() else None,
                physical_start=number(5), pdf_page_index=number(6), source=value(8) or "manual",
                review_status=value(9) or "draft",
                include=self.table.item(row, 0).checkState() == Qt.CheckState.Checked,
                printed_page_label=printed, level=number(7) or 1,
                edited_by_user=bool((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("edited")),
                source_sno=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("source_sno", "")),
                parent_sno=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("parent_sno", "")),
                raw_import_hash=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("raw_import_hash", "")),
                entry_id=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("entry_id", "")),
                parent_entry_id=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("parent_entry_id", "")),
                provenance_source_type=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("provenance_source_type", "")),
                analytical_or_verbatim=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("analytical_or_verbatim", "")),
                boundary_status=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("boundary_status", "")),
                boundary_basis=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("boundary_basis", "")),
                allow_extraction=bool((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("allow_extraction", True)),
                notes=str((self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or {}).get("notes", "")),
            ))
        return result

    def set_entries(self, entries):
        self._loading_outline = True
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                "", entry.sno, entry.title, entry.kind,
                entry.printed_page_label or entry.printed_start or "",
                entry.physical_start or "", "" if entry.pdf_page_index is None else entry.pdf_page_index,
                entry.level, entry.source, entry.review_status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setFlags((item.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
                    item.setCheckState(Qt.CheckState.Checked if entry.include else Qt.CheckState.Unchecked)
                if column in (3, 8, 9):
                    # Column 3 (Kind) is edited exclusively through the combo box set below;
                    # this item just holds the raw stored value for entries() to read back.
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, {
                        "edited": entry.edited_by_user,
                        "source_sno": entry.source_sno,
                        "parent_sno": entry.parent_sno,
                        "raw_import_hash": entry.raw_import_hash,
                        "entry_id": entry.entry_id,
                        "parent_entry_id": entry.parent_entry_id,
                        "provenance_source_type": entry.provenance_source_type,
                        "analytical_or_verbatim": entry.analytical_or_verbatim,
                        "boundary_status": entry.boundary_status,
                        "boundary_basis": entry.boundary_basis,
                        "allow_extraction": entry.allow_extraction,
                        "notes": entry.notes,
                    })
                self.table.setItem(row, column, item)
            self.table.setCellWidget(row, 3, self._build_kind_combo(row, entry.kind))
            status_item = QTableWidgetItem(self._semantic_status_text(entry.kind))
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status_item.setIcon(self._semantic_status_icon(entry.kind))
            self.table.setItem(row, 10, status_item)
        self._loading_outline = False
        self.update_empty_states()
        self.validate()

    def _semantic_status_text(self, kind: str) -> str:
        return "Classified" if kind in KINDS else "Review Needed"

    def _semantic_status_icon(self, kind: str):
        symbol = QStyle.StandardPixmap.SP_DialogApplyButton if kind in KINDS else QStyle.StandardPixmap.SP_MessageBoxWarning
        return self.style().standardIcon(symbol)

    def _build_kind_combo(self, row: int, kind: str) -> QComboBox:
        combo = QComboBox()
        if kind not in KINDS:
            combo.addItem(f"⚠ {kind or '(blank)'} — needs review", kind)
        for option in sorted(KINDS):
            combo.addItem(option.replace("_", " ").title(), option)
        index = combo.findData(kind)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(lambda _index, r=row: self._kind_changed(r))
        return combo

    def _kind_changed(self, row: int):
        if self._loading_outline:
            return
        combo = self.table.cellWidget(row, 3)
        kind_item = self.table.item(row, 3)
        if combo is None or kind_item is None:
            return
        new_kind = combo.currentData()
        kind_item.setText(new_kind)  # triggers itemChanged -> outline_edited() (existing invalidation path)
        status_item = self.table.item(row, 10)
        if status_item is not None:
            # Purely derived/presentational -- block signals so this doesn't re-enter
            # outline_edited() via itemChanged for a column entries() never reads.
            self.table.blockSignals(True)
            status_item.setText(self._semantic_status_text(new_kind))
            status_item.setIcon(self._semantic_status_icon(new_kind))
            self.table.blockSignals(False)

    def _unknown_kind_advisory(self, entry: OutlineEntry) -> str:
        return (
            "• Semantic type requires review\n"
            f"  Title: {entry.title}\n"
            f"  Current classification: {entry.kind or '(blank)'}\n"
            "  Recommended classification: Section\n"
            "  Choose another semantic type from the Kind column if 'Section' isn't right.\n"
            "  Code: unknown_kind"
        )

    def load_draft(self):
        if not self.book:
            self.set_entries([])
            return
        draft, clean, _ = self.window.services.outlines.paths(self.book.book_id)
        path = draft if draft.exists() else clean
        self.set_entries(self.window.services.outlines.load(path) if path.exists() else [])

    def outline_edited(self, item):
        if self._loading_outline:
            return
        # Decide and show the invalidation message (revoking approval as a side effect) before
        # the edited-metadata bookkeeping below, whose setData() call re-enters this same slot
        # for the title item (column 2) -- running invalidation first means that re-entrant call
        # finds approval already revoked and is a harmless no-op, instead of racing to overwrite
        # this column's more specific message with the generic one.
        if item.column() == 3:
            self.invalidate_approval(
                "Semantic classification updated. Outline approval has been cleared. Review and approve again."
            )
        else:
            self.invalidate_approval()
        if item.column() in (1, 2, 3, 4, 7):
            title_item = self.table.item(item.row(), 2)
            metadata = dict(title_item.data(Qt.ItemDataRole.UserRole) or {})
            metadata["edited"] = True
            title_item.setData(Qt.ItemDataRole.UserRole, metadata)
        self.validate()

    def add_row(self):
        entries = self.entries()
        entries.append(OutlineEntry(
            max((entry.sno for entry in entries), default=0) + 1,
            "New section", source="manual", edited_by_user=True,
        ))
        self.set_entries(entries)
        self.table.selectRow(len(entries) - 1)
        self.table.editItem(self.table.item(len(entries) - 1, 2))
        self.invalidate_approval()

    def delete_row(self):
        row = self.table.currentRow()
        if row >= 0 and confirm_destructive(
            self, "Delete outline row?", "Remove the selected row from the current review table?"
        ):
            entries = self.entries()
            entries.pop(row)
            self.set_entries(entries)
            if entries:
                self.table.selectRow(min(row, len(entries) - 1))
            # Selecting a row moves the highlight but not keyboard input focus, which a
            # button click leaves on the button that was just clicked -- explicitly
            # returning focus to the table lets the operator continue navigating/deleting
            # by keyboard immediately, without an extra Tab press (Sprint 14, requirement #5).
            self.table.setFocus()
            self.invalidate_approval()

    def duplicate_row(self):
        row = self.table.currentRow()
        entries = self.entries()
        if row >= 0:
            copy = OutlineEntry(**asdict(entries[row]))
            copy.sno = max((entry.sno for entry in entries), default=0) + 1
            copy.review_status = "draft"
            copy.edited_by_user = True
            entries.insert(row + 1, copy)
            self.set_entries(entries)
            self.table.selectRow(row + 1)
            self.table.editItem(self.table.item(row + 1, 2))
            self.invalidate_approval()

    def move(self, direction):
        row = self.table.currentRow()
        target = row + direction
        entries = self.entries()
        if row >= 0 and 0 <= target < len(entries):
            entries[row], entries[target] = entries[target], entries[row]
            self.set_entries(entries)
            self.table.selectRow(target)
            self.table.setFocus()  # see delete_row()'s comment (Sprint 14, requirement #5)
            self.invalidate_approval()

    def sort_printed(self):
        entries = self.entries()
        entries.sort(key=lambda entry: (entry.printed_start is None, entry.printed_start or 0, entry.sno))
        self.set_entries(entries)
        self.invalidate_approval()

    def invalidate_approval(self, message: str | None = None):
        if self.book:
            approval = self.window.services.outlines.approval(self.book.book_id)
            if approval and approval.approved:
                self.window.services.outlines.revoke(self.book.book_id)
                self.window.statusBar().showMessage(
                    message or "Outline modified. Approval has been cleared — review changes and approve again.",
                    7000,
                )
        self.update_editing_status()

    def save_draft(self):
        if not self.book:
            self.no_book_error()
            return
        if not self.entries():
            QMessageBox.information(self, "No outline exists", "Create or load an outline before saving.")
            return
        self.invalidate_approval()
        draft, _, _ = self.window.services.outlines.paths(self.book.book_id)
        self.window.services.outlines.save(draft, self.entries())
        self.window.statusBar().showMessage("Draft saved. Review validation before approval.", 5000)
        self.validate()

    def approve(self):
        if not self.book:
            self.no_book_error()
            return
        try:
            note, accepted = QInputDialog.getMultiLineText(self, "Approve Outline", "Reviewer note")
            if not accepted:
                return
            draft, _, _ = self.window.services.outlines.paths(self.book.book_id)
            self.window.services.outlines.save(draft, self.entries())
            self.window.services.outlines.approve(self.book, self.entries(), note)
            self.window.statusBar().showMessage(
                "Outline approved. Continue by verifying page mapping.", 6000
            )
            self.validate()
            # Page mapping is now the "C. Page Mapping" tab of this same screen, not a
            # separate top-level workspace -- switch tabs instead of navigating away.
            self.tabs.setCurrentIndex(2)
        except FileExistsError:
            if QMessageBox.question(
                self, "Revoke Existing Approval",
                "An approved outline exists. Revoke it and approve the current reviewed outline?",
            ) == QMessageBox.StandardButton.Yes:
                self.window.services.outlines.revoke(self.book.book_id)
                self.approve()
        except Exception as exc:
            # OutlineService.approve() raises a single ValueError joining every blocking
            # ValidationIssue.message with "; " -- already operator language (e.g. "Section
            # 3 has no title."), not exception jargon, so it's shown directly as the
            # Reason (split into a bullet per issue), not hidden in technical details.
            reasons = [part.strip() for part in str(exc).split(";") if part.strip()]
            reason_text = "<br>".join(f"• {reason}" for reason in reasons) if reasons else str(exc)
            self.window.show_error(
                "Outline Approval Blocked",
                format_operator_error(
                    reason_text,
                    "Correct the listed section(s) in the Review Outline table, then approve again.",
                ),
                traceback.format_exc(),
            )

    def validate(self):
        self.update_editing_status()
        if not self.book:
            self.validation.setPlainText(
                "NO BOOK SELECTED\n\n1. Open Library\n2. Add or select a PDF\n"
                "3. Return here to create its structure"
            )
            self.update_actions()
            return
        entries = self.entries()
        issues = self.window.services.outlines.validate(entries, self.book.page_count)
        groups = {Severity.BLOCKING: [], Severity.WARNING: [], Severity.PASSED: []}
        for issue in issues:
            if issue.code == "unknown_kind":
                continue  # replaced below with a title-vs-semantic-type advisory, per entry
            groups[issue.severity].append(f"• {issue.message}\n  Code: {issue.code}")
        for entry in entries:
            if entry.include and entry.kind not in KINDS:
                groups[Severity.WARNING].append(self._unknown_kind_advisory(entry))
        mapping = self.window.services.mappings.load(self.book.book_id)
        if not mapping.approved:
            groups[Severity.WARNING].append(
                "• Page mapping is unresolved; printed pages are not physical pages.\n"
                "  Code: mapping_unresolved"
            )
        sections = []
        for severity, heading in (
            (Severity.BLOCKING, "BLOCKING ERRORS"),
            (Severity.WARNING, "WARNINGS"),
            (Severity.PASSED, "PASSED CHECKS"),
        ):
            sections.append(
                heading + "\n" + ("\n".join(groups[severity]) if groups[severity] else "• None")
            )
        self.validation.setPlainText("\n\n".join(sections))
        self.update_actions(issues)

    def update_actions(self, issues=None):
        has_book = self.book is not None
        has_candidates = bool(self.candidate_records)
        has_rows = self.table.rowCount() > 0
        if issues is None and has_book:
            issues = self.window.services.outlines.validate(self.entries(), self.book.page_count)
        blocking = any(issue.severity == Severity.BLOCKING for issue in (issues or []))
        self.parse_button.setEnabled(has_book and bool(self.paste_text.toPlainText().strip()))
        self.create_button.setEnabled(has_book and has_candidates)
        self.merge_button.setEnabled(has_book and has_candidates)
        self.save_button.setEnabled(has_book and has_rows)
        self.approve_button.setEnabled(has_book and has_rows and not blocking)

    def update_editing_status(self):
        if not self.book:
            self.editing_status.setText("")
            return
        entries = self.entries()
        approval = self.window.services.outlines.approval(self.book.book_id)
        modified = "Yes" if any(entry.edited_by_user for entry in entries) else "No"
        approved = "Yes" if approval and approval.approved else "No"
        self.editing_status.setText(
            f"Entries {len(entries)}   ·   Modified {modified}   ·   Approved {approved}"
        )

    def update_empty_states(self):
        if not self.book:
            message = (
                "No book selected\n\n1. Open Library\n2. Add or select a PDF\n"
                "3. Return here to create its structure"
            )
            self.candidate_empty.setText(message)
            self.review_empty.setText(message)
        else:
            self.candidate_empty.setText(
                "Paste a Table of Contents or outline above, then select Parse Preview."
            )
            self.review_empty.setText(
                "No outline has been generated for this book yet.\n\n"
                "Next Step\n"
                "Switch to the \"A. Create Structure\" tab (paste a TOC, detect from the PDF, or import "
                "CSV/JSON) — or use \"Add from Another Source\" above — then return here to review."
            )
        self.candidate_empty.setVisible(not self.candidate_records)
        self.candidate_table.setVisible(bool(self.candidate_records))
        self.review_empty.setVisible(self.table.rowCount() == 0)
        self.table.parentWidget().setVisible(self.table.rowCount() > 0)

    def update_stage(self, *_):
        if self.tabs.currentIndex() == 2:
            current = "6. MAP PAGES"
        elif self.tabs.currentIndex() == 1:
            current = "3. REVIEW"
        elif self.candidate_records:
            current = "2. PARSE"
        else:
            current = "1. CHOOSE SOURCE"
        self.stage.setText(
            "1. CHOOSE SOURCE → 2. PARSE → 3. REVIEW → 4. SAVE DRAFT → "
            f"5. APPROVE → 6. MAP PAGES     ·     Current: {current}"
        )

    def jump(self):
        row = self.table.currentRow()
        if row >= 0:
            entry = self.entries()[row]
            self.preview.set_context(
                entry.title,
                f"Printed page {entry.printed_page_label or 'missing'} — see the C. Page Mapping tab to verify",
            )
            if entry.physical_start:
                self.preview.jump_to(entry.physical_start)

    def copy_candidates(self):
        rows = sorted(index.row() for index in self.candidate_table.selectionModel().selectedRows())
        if rows:
            QApplication.clipboard().setText("\n".join(
                "\t".join(self.candidate_table.item(row, column).text() for column in range(1, 8))
                for row in rows
            ))

    def copy_outline(self, mode):
        entries = self.entries()
        if mode == "text":
            text = "\n".join(
                f"{entry.title} | {entry.printed_page_label or entry.printed_start or ''}"
                for entry in entries
            )
        else:
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(entry.to_csv_row() for entry in entries)
            text = output.getvalue()
        QApplication.clipboard().setText(text)

    def export_candidate_preview(self):
        if not self.candidate_records:
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Export candidate preview", "outline_candidates.csv",
            "CSV (*.csv);;JSON (*.json);;Plain text (*.txt)",
        )
        if not filename:
            return
        path = Path(filename)
        rows = [asdict(candidate) for candidate in self.candidate_records]
        if "JSON" in selected_filter or path.suffix.casefold() == ".json":
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif "Plain" in selected_filter or path.suffix.casefold() == ".txt":
            path.write_text(
                "\n".join(
                    f"{candidate.title} | {candidate.printed_page_label}"
                    for candidate in self.candidate_records
                ) + "\n",
                encoding="utf-8",
            )
        else:
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

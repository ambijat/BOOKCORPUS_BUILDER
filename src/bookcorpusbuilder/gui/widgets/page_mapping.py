from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import MappingAnchor, OutlineEntry, PageMapping, Severity
from ..services.mapping import suggested_action
from .pdf_preview import PdfTextPreview
from .table_usability import configure_table

RESOLUTION_COLORS = {
    "supplied": "#c6efce", "anchor": "#c6efce", "segment": "#c6efce",
    "extrapolated": "#ffeb9c",
    "unresolved": "#ffc7ce",
    "physical_only": "#e0e0e0", "no_printed_page": "#e0e0e0",
}

DIAGNOSTIC_LABELS: dict[str, str] = {
    "offset_conflict": "Conflicting anchors",
    "segment_unconfirmed": "Unconfirmed anchor",
    "two_anchors_required": "Not enough anchors",
    "offset_unresolved": "No confirmed segment yet",
    "uncovered_entry": "Section not covered",
    "invalid_anchor": "Invalid anchor",
    "index_mismatch": "PDF index mismatch",
    "anchor_out_of_range": "Anchor beyond PDF length",
}

DIAGNOSTIC_EXPLANATIONS: dict[str, str] = {
    "offset_conflict": (
        "Two anchors target the same printed page but disagree on which physical page it maps to. "
        "This segment cannot be confirmed until the disagreement is resolved."
    ),
    "segment_unconfirmed": "This anchor is alone at its offset — nothing else agrees with it yet, so its segment can't be confirmed.",
    "two_anchors_required": "At least two agreeing anchors are needed before any part of the book can be resolved.",
    "offset_unresolved": "No confirmed segment exists yet, so printed pages can't be translated into physical pages.",
    "uncovered_entry": "This section's printed page doesn't fall inside any confirmed segment, so its physical page is unknown.",
    "invalid_anchor": "This anchor's printed or physical page number isn't valid — both must be 1 or greater.",
    "index_mismatch": "This anchor's PDF index doesn't match physical page minus one — it was likely edited by hand instead of set from the preview.",
    "anchor_out_of_range": "This anchor's physical page is beyond the end of the PDF.",
}


class PageMappingPanel(QWidget):
    """Page-mapping verification, embedded as Structure Builder's "C. Page Mapping" tab.

    Formerly the standalone Page Alignment workspace (AlignmentScreen); moved here so every
    outline node's structural identity and its printed/physical page location are reviewed in
    one workspace instead of two. PageMapping/MappingAnchor and MappingService are untouched --
    this only relocates the UI, not the mapping algorithm or its book-scoped persistence.
    """

    def __init__(self, window, preview: PdfTextPreview):
        super().__init__()
        self.window = window
        # Shared with Structure Builder's own "A"/"B" tabs (the same PdfTextPreview instance,
        # not a second one) -- one PDF preview per book across all three tabs instead of two
        # independent ones that could drift out of sync with each other's page position. This
        # also removes a second, redundant preview+splitter pane that used to double up with
        # Structure Builder's own outer splitter and starve this tab's own content of width
        # and height when nested two splitters deep.
        self.preview = preview
        self.entry_combo = QComboBox()
        self.entry_combo.currentIndexChanged.connect(self.select_entry)
        self.printed = QSpinBox(); self.printed.setRange(1, 100000)
        self.physical = QSpinBox(); self.physical.setRange(1, 100000)
        self.exception = QCheckBox("Irregular exception")
        use = QPushButton("Use preview page as physical start")
        use.clicked.connect(lambda: self.physical.setValue(self.preview.page.value()))
        add = QPushButton("Add verification anchor")
        add.clicked.connect(self.add_anchor)
        # Enter in either page field adds the anchor directly (Sprint 14, requirement #2 --
        # "Add Anchor ... -> Add"), matching Browser's existing search-field convention
        # instead of requiring a mouse click on "Add verification anchor" every time.
        self.printed.lineEdit().returnPressed.connect(self.add_anchor)
        self.physical.lineEdit().returnPressed.connect(self.add_anchor)
        remove = QPushButton("Remove selected anchor")
        remove.clicked.connect(self.remove_anchor)
        self.anchor_feedback = QLabel(""); self.anchor_feedback.setWordWrap(True); self.anchor_feedback.setTextFormat(Qt.RichText)
        self.suggest_button = QPushButton("Suggest Next Anchor")
        self.suggest_button.clicked.connect(self.suggest_next)
        self.suggestion_label = QLabel("")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setTextFormat(Qt.RichText)
        verify = QPushButton("Verify and approve mapping")
        verify.clicked.connect(self.approve)
        self.dashboard_summary = QLabel(""); self.dashboard_summary.setWordWrap(True); self.dashboard_summary.setTextFormat(Qt.RichText)
        self.workflow_summary = QLabel(""); self.workflow_summary.setWordWrap(True); self.workflow_summary.setTextFormat(Qt.RichText)
        self.status = QLabel("Page mapping unresolved — extraction is blocked.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.RichText)
        self.diagnostics_summary = QLabel(""); self.diagnostics_summary.setWordWrap(True); self.diagnostics_summary.setTextFormat(Qt.RichText)
        self.diagnostics_list = QListWidget(); self.diagnostics_list.setMaximumHeight(140)
        self.diagnostics_list.itemSelectionChanged.connect(self.on_diagnostic_selected)
        self.diagnostic_detail = QLabel(""); self.diagnostic_detail.setWordWrap(True); self.diagnostic_detail.setTextFormat(Qt.RichText)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Label", "Printed", "Physical", "PDF Index", "Exception"])
        self.table.setMinimumHeight(120)
        configure_table(
            self.table, self.window, "alignment.anchors",
            default_widths={0: 300, 1: 95, 2: 95, 3: 100, 4: 105},
            frozen_columns=(0,), content_caps={0: 500},
        )
        self.segments_table = QTableWidget(0, 5)
        self.segments_table.setHorizontalHeaderLabels(["Printed Range", "Physical Range", "Offset", "Anchors", "Status"])
        self.segments_table.setMinimumHeight(100)
        configure_table(
            self.segments_table, self.window, "alignment.segments",
            default_widths={0: 140, 1: 140, 2: 80, 3: 80, 4: 200},
            frozen_columns=(), content_caps={4: 220},
        )
        self.segments_table.itemSelectionChanged.connect(self.on_segment_selected)
        self.segment_guidance = QLabel(""); self.segment_guidance.setWordWrap(True); self.segment_guidance.setTextFormat(Qt.RichText)
        self.mapping_preview = QTableWidget(0, 5)
        self.mapping_preview.setHorizontalHeaderLabels(["Section", "Printed", "Mapped Physical", "PDF Index", "Resolution"])
        self.mapping_preview.setMinimumHeight(120)
        configure_table(
            self.mapping_preview, self.window, "alignment.preview",
            default_widths={0: 500, 1: 100, 2: 145, 3: 105, 4: 260},
            frozen_columns=(0,), content_caps={0: 760, 4: 400},
        )
        self.entry_combo.setMinimumWidth(240)
        self.entry_combo.setMinimumHeight(26)
        self.printed.setMinimumHeight(26)
        self.physical.setMinimumHeight(26)
        self.exception.setMinimumHeight(22)
        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.addRow("Outline entry", self.entry_combo)
        form.addRow("Printed page", self.printed)
        form.addRow("Physical page", self.physical)
        form.addRow("", self.exception)
        # A plain addLayout(form) lets the surrounding QVBoxLayout shrink this block's row
        # pitch below each row's own minimum height when the whole page is starved for
        # vertical space (rows visibly overlapping instead of the deficit landing on a
        # flexible sibling). A Fixed vertical size policy makes this block's height
        # non-negotiable, so any such shortfall is absorbed elsewhere instead.
        form_widget = QWidget()
        form_widget.setLayout(form)
        form_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        right = QWidget(); right_layout = QVBoxLayout(right)
        fit_all = QPushButton("Best Fit Columns")
        fit_all.clicked.connect(lambda: (
            self.table._layout_controller.best_fit_all(),
            self.segments_table._layout_controller.best_fit_all(),
            self.mapping_preview._layout_controller.best_fit_all(),
        ))
        fit_row = QHBoxLayout(); fit_row.addWidget(fit_all); fit_row.addStretch()
        dashboard_box = QGroupBox("Verification Status")
        dashboard_box_layout = QVBoxLayout(dashboard_box); dashboard_box_layout.addWidget(self.dashboard_summary)
        workflow_box = QGroupBox("Verification Workflow")
        workflow_box_layout = QVBoxLayout(workflow_box); workflow_box_layout.addWidget(self.workflow_summary)
        top_row = QHBoxLayout(); top_row.addWidget(dashboard_box, 1); top_row.addWidget(workflow_box, 1)
        # This status/diagnostics block's combined content (dashboard, workflow, the free-form
        # status label, and the diagnostics list/detail) has no natural height ceiling. Capping
        # it in its own fixed-height scroll area keeps its growth from eating the space the
        # form block below it needs, which is what previously caused the form rows to overlap.
        diagnostics_block = QWidget()
        diagnostics_block_layout = QVBoxLayout(diagnostics_block)
        diagnostics_block_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_block_layout.addLayout(top_row)
        diagnostics_block_layout.addWidget(self.status)
        diagnostics_block_layout.addWidget(QLabel("Mapping Diagnostics"))
        diagnostics_block_layout.addWidget(self.diagnostics_summary)
        diagnostics_block_layout.addWidget(self.diagnostics_list)
        diagnostics_block_layout.addWidget(self.diagnostic_detail)
        diagnostics_scroll = QScrollArea()
        diagnostics_scroll.setWidget(diagnostics_block)
        diagnostics_scroll.setWidgetResizable(True)
        diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        diagnostics_scroll.setFixedHeight(320)
        right_layout.addWidget(diagnostics_scroll)
        right_layout.addWidget(form_widget); right_layout.addWidget(use); right_layout.addWidget(add); right_layout.addWidget(remove)
        right_layout.addWidget(self.anchor_feedback)
        right_layout.addWidget(self.suggest_button); right_layout.addWidget(self.suggestion_label)
        right_layout.addLayout(fit_row); right_layout.addWidget(self.table, 2)
        right_layout.addWidget(QLabel("Segments")); right_layout.addWidget(self.segments_table, 1)
        right_layout.addWidget(self.segment_guidance)
        right_layout.addWidget(QLabel("Mapping preview")); right_layout.addWidget(self.mapping_preview, 2); right_layout.addWidget(verify)
        # Even with the diagnostics block capped above, the anchors/segments/mapping-preview
        # tables plus their action rows still add up to more mandatory height than fits at
        # common laptop resolutions (e.g. 1366x768) once this panel is nested inside Structure
        # Builder's own "stage" banner and tab bar. Wrapping the whole tab in a vertical-only
        # scroll area is what keeps rows from being squeezed into overlapping each other, the
        # same fix that resolved this for the standalone Page Alignment workspace.
        scroll = QScrollArea()
        scroll.setWidget(right)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self); layout.addWidget(scroll)
        self.mapping = PageMapping("")
        self.outline_entries = []
        self._segments_cache = []
        self._changed_printed_page = None
        self._diagnostic_highlight_rows = {"anchors": [], "segments": [], "preview": []}

    @property
    def book(self):
        return self.window.selected_book

    def selection_changed(self):
        self.preview.set_pdf(self.book.path if self.book else None, self.book.page_count if self.book else 0)
        self.mapping = self.window.services.mappings.load(self.book.book_id) if self.book else PageMapping("")
        self.outline_entries = []
        self.entry_combo.clear()
        self.anchor_feedback.setText("")
        if self.book:
            draft, clean, _ = self.window.services.outlines.paths(self.book.book_id)
            source = clean if clean.exists() else draft
            if source.exists():
                self.outline_entries = [entry for entry in self.window.services.outlines.load(source) if entry.include]
                for entry in self.outline_entries:
                    label = f"printed {entry.printed_start}" if entry.printed_start else f"physical {entry.physical_start} (no printed page read yet)"
                    self.entry_combo.addItem(f"{entry.sno}. {entry.title} · {label}", entry.sno)
        self.render()

    def select_entry(self, index):
        if 0 <= index < len(self.outline_entries):
            entry = self.outline_entries[index]
            self.printed.setValue(entry.printed_start or 1)
            physical = self.mapping.resolve_entry(entry).physical_page
            if physical:
                self.physical.setValue(physical)
                self.preview.jump_to(physical)
            # No printed_start on record (heading-detected entry): jump to its known
            # physical page so the operator can read the printed number off the page
            # and type it in before adding the anchor.

    def add_anchor(self):
        if not self.book:
            return
        physical = self.physical.value()
        printed_value = self.printed.value()
        is_exception = self.exception.isChecked()
        self.mapping.anchors.append(MappingAnchor(printed_value, physical, physical - 1, f"Check {len(self.mapping.anchors) + 1}", is_exception))
        if is_exception:
            self.mapping.exceptions[str(printed_value)] = physical
        self.mapping.approved = False
        self.window.services.mappings.save_draft(self.mapping)
        self._changed_printed_page = printed_value
        self.render()
        self.update_anchor_feedback(printed_value)

    def remove_anchor(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.mapping.anchors):
            removed = self.mapping.anchors.pop(row)
            self.mapping.exceptions.pop(str(removed.printed_page), None)
            self.window.services.mappings.save_draft(self.mapping)
            self.anchor_feedback.setText("")
            self.render()
            # render() rebuilds the table from scratch, so selection/focus recovery
            # (Sprint 14, requirement #5) has to happen after it, not before.
            if self.mapping.anchors:
                self.table.selectRow(min(row, len(self.mapping.anchors) - 1))
            self.table.setFocus()

    def suggest_next(self):
        suggestion = self.window.services.mappings.suggest_next_anchor(self.mapping, self.outline_entries)
        if not suggestion:
            return
        index = next((i for i, entry in enumerate(self.outline_entries) if entry.sno == suggestion.sno), -1)
        if index >= 0:
            self.entry_combo.setCurrentIndex(index)
            self.select_entry(index)

    def update_anchor_feedback(self, printed_value: int) -> None:
        segment = next((s for s in self.mapping.segments() if s.printed_start <= printed_value <= s.printed_end), None)
        confirmed = bool(segment and segment.confirmed)
        lines = [
            "<b style='color:#287a3d'>✓ Anchor accepted</b>",
            f"<br>Segment {'confirmed' if confirmed else 'still needs one more anchor'} (printed page {printed_value}).",
        ]
        suggestion = self.window.services.mappings.suggest_next_anchor(self.mapping, self.outline_entries)
        if suggestion:
            lines.append(f"<br><b>Next recommended anchor</b><br>{suggestion.title} · printed {suggestion.printed_start}")
        else:
            lines.append("<br>No further unresolved entries — every section is covered.")
        self.anchor_feedback.setText("<br>".join(lines))

    def _segment_action_text(self, segment, index: int, segments: list) -> str:
        lower = segment.printed_end + 1
        upper = segments[index + 1].printed_start - 1 if index + 1 < len(segments) else None
        if upper is not None and upper >= lower:
            return f"Add one more anchor anywhere between printed pages {lower} and {upper} to confirm this offset."
        return f"Add one more agreeing anchor anywhere after printed page {segment.printed_end} to confirm this offset."

    def _describe_segment(self, segment, index: int, segments: list) -> str:
        printed_desc = (
            str(segment.printed_start) if segment.printed_start == segment.printed_end
            else f"{segment.printed_start}–{segment.printed_end}"
        )
        lines = [f"<b>Segment</b><br>Printed page(s)<br>{printed_desc}"]
        if segment.confirmed:
            lines.append("<br><b>Status</b><br>Confirmed")
        else:
            lines.append("<br><b>Status</b><br>Needs another verification anchor")
            lines.append(f"<br><b>Action</b><br>{self._segment_action_text(segment, index, segments)}")
        return "<br>".join(lines)

    def _suggestion_reason(self, confirmed_segments: list) -> str:
        if not self.mapping.anchors:
            return "No verification anchors exist yet — this is the best section to start with."
        if not confirmed_segments:
            return "Confirming this section's physical page will help establish your first confirmed offset segment."
        return "This section isn't covered by any confirmed segment yet and needs its own anchor."

    def on_segment_selected(self):
        segments = self._segments_cache
        row = self.segments_table.currentRow()
        if 0 <= row < len(segments):
            self.segment_guidance.setText(self._describe_segment(segments[row], row, segments))

    def _diagnostic_entries(self, diagnostics: list, segments: list) -> list[dict]:
        """Cross-reference the existing ValidationIssue list back to concrete rows.

        Reuses the exact same source data and iteration order MappingService.validate()
        already builds its issues from (conflicting_anchor_pairs(), unconfirmed_anchors(),
        the per-anchor loop, the per-entry loop), so each issue lines up with the anchor,
        segment, or outline entry it actually came from -- no new detection logic, just
        associating existing facts with existing table rows for presentation.
        """
        def anchor_index(anchor) -> int | None:
            return next((i for i, candidate in enumerate(self.mapping.anchors) if candidate is anchor), None)

        def segment_index_for_page(page: int) -> int | None:
            return next((i for i, segment in enumerate(segments) if segment.printed_start <= page <= segment.printed_end), None)

        def entry_index_for(entry) -> int | None:
            return next((i for i, candidate in enumerate(self.outline_entries) if candidate is entry), None)

        conflict_iter = iter(self.mapping.conflicting_anchor_pairs())
        unconfirmed_iter = iter(self.mapping.unconfirmed_anchors())
        uncovered_iter = iter(
            entry for entry in self.outline_entries
            if entry.include and entry.printed_start and self.mapping.resolve_entry(entry).physical_page is None
        )
        invalid_iter = iter(i for i, a in enumerate(self.mapping.anchors) if a.printed_page < 1 or a.physical_page_number < 1)
        mismatch_iter = iter(i for i, a in enumerate(self.mapping.anchors) if a.pdf_page_index != a.physical_page_number - 1)
        page_count = self.book.page_count if self.book else 0
        out_of_range_iter = iter(i for i, a in enumerate(self.mapping.anchors) if page_count and a.physical_page_number > page_count)

        entries: list[dict] = []
        for issue in diagnostics:
            if issue.severity == Severity.PASSED:
                continue
            anchor_indices: list[int] = []
            segment_index: int | None = None
            entry_index: int | None = None
            if issue.code == "offset_conflict":
                pair = next(conflict_iter, None)
                if pair:
                    anchor_indices = [index for index in (anchor_index(pair[0]), anchor_index(pair[1])) if index is not None]
                    segment_index = segment_index_for_page(pair[0].printed_page)
            elif issue.code == "segment_unconfirmed":
                anchor = next(unconfirmed_iter, None)
                if anchor:
                    index = anchor_index(anchor)
                    anchor_indices = [index] if index is not None else []
                    segment_index = segment_index_for_page(anchor.printed_page)
            elif issue.code == "uncovered_entry":
                entry = next(uncovered_iter, None)
                if entry:
                    entry_index = entry_index_for(entry)
            elif issue.code == "invalid_anchor":
                index = next(invalid_iter, None)
                anchor_indices = [index] if index is not None else []
            elif issue.code == "index_mismatch":
                index = next(mismatch_iter, None)
                anchor_indices = [index] if index is not None else []
            elif issue.code == "anchor_out_of_range":
                index = next(out_of_range_iter, None)
                anchor_indices = [index] if index is not None else []
            entries.append({
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "explanation": DIAGNOSTIC_EXPLANATIONS.get(issue.code, issue.message),
                "action": suggested_action(issue),
                "anchor_indices": anchor_indices,
                "segment_index": segment_index,
                "entry_index": entry_index,
            })
        return entries

    def _affected_section_text(self, entry: dict) -> str:
        if entry["entry_index"] is not None and entry["entry_index"] < len(self.outline_entries):
            outline_entry = self.outline_entries[entry["entry_index"]]
            return f"{outline_entry.title} (printed {outline_entry.printed_start})"
        if entry["anchor_indices"]:
            labels = [self.mapping.anchors[i].label for i in entry["anchor_indices"] if i < len(self.mapping.anchors)]
            if labels:
                return ", ".join(labels)
        if entry["segment_index"] is not None:
            segments = self.mapping.segments()
            if entry["segment_index"] < len(segments):
                segment = segments[entry["segment_index"]]
                return f"Printed pages {segment.printed_start}-{segment.printed_end}"
        return ""

    def _format_diagnostic_detail(self, entry: dict) -> str:
        heading = "Conflict" if entry["code"] == "offset_conflict" else DIAGNOSTIC_LABELS.get(entry["code"], entry["code"])
        lines = [f"<b>{heading}</b>", entry["explanation"]]
        if entry["action"]:
            lines.append("<br><b>Suggested Action</b>")
            lines.append(entry["action"])
        affected = self._affected_section_text(entry)
        if affected:
            lines.append("<br><b>Affected</b>")
            lines.append(affected)
        return "<br>".join(lines)

    def _clear_diagnostic_highlight(self) -> None:
        bold_font = QFont(); bold_font.setBold(False)
        for row in self._diagnostic_highlight_rows["anchors"]:
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item: item.setFont(bold_font)
        for row in self._diagnostic_highlight_rows["segments"]:
            for column in range(self.segments_table.columnCount()):
                item = self.segments_table.item(row, column)
                if item: item.setFont(bold_font)
        for row in self._diagnostic_highlight_rows["preview"]:
            for column in range(self.mapping_preview.columnCount()):
                item = self.mapping_preview.item(row, column)
                if item: item.setFont(bold_font)
        self._diagnostic_highlight_rows = {"anchors": [], "segments": [], "preview": []}

    def _apply_diagnostic_highlight(self, entry: dict) -> None:
        bold_font = QFont(); bold_font.setBold(True)
        if entry["anchor_indices"]:
            for row in entry["anchor_indices"]:
                if 0 <= row < self.table.rowCount():
                    for column in range(self.table.columnCount()):
                        item = self.table.item(row, column)
                        if item: item.setFont(bold_font)
            self._diagnostic_highlight_rows["anchors"] = list(entry["anchor_indices"])
            first_row = entry["anchor_indices"][0]
            self.table.selectRow(first_row)
            if self.table.item(first_row, 0):
                self.table.scrollToItem(self.table.item(first_row, 0))
        if entry["segment_index"] is not None and 0 <= entry["segment_index"] < self.segments_table.rowCount():
            row = entry["segment_index"]
            for column in range(self.segments_table.columnCount()):
                item = self.segments_table.item(row, column)
                if item: item.setFont(bold_font)
            self._diagnostic_highlight_rows["segments"] = [row]
            self.segments_table.selectRow(row)
            if self.segments_table.item(row, 0):
                self.segments_table.scrollToItem(self.segments_table.item(row, 0))
        if entry["entry_index"] is not None and 0 <= entry["entry_index"] < self.mapping_preview.rowCount():
            row = entry["entry_index"]
            for column in range(self.mapping_preview.columnCount()):
                item = self.mapping_preview.item(row, column)
                if item: item.setFont(bold_font)
            self._diagnostic_highlight_rows["preview"] = [row]
            self.mapping_preview.selectRow(row)
            if self.mapping_preview.item(row, 0):
                self.mapping_preview.scrollToItem(self.mapping_preview.item(row, 0))

    def on_diagnostic_selected(self):
        self._clear_diagnostic_highlight()
        selected = self.diagnostics_list.selectedItems()
        if not selected:
            self.diagnostic_detail.setText("")
            return
        entry = selected[0].data(Qt.ItemDataRole.UserRole)
        self.diagnostic_detail.setText(self._format_diagnostic_detail(entry))
        self._apply_diagnostic_highlight(entry)

    def _outline_approved(self) -> bool:
        if not self.book:
            return False
        approval = self.window.services.outlines.approval(self.book.book_id)
        return bool(approval and approval.approved)

    def render_dashboard(self, confirmed: list, total_entries: int, resolved_count: int, blocking_count: int) -> None:
        if self.mapping.approved:
            lines = [
                "<b>Mapping Approved</b>",
                f"<br><b>Book</b><br>{self.book.filename if self.book else '—'}",
                f"<br><b>Verified Segments</b><br>{len(confirmed)}",
                f"<br><b>Outline Entries</b><br>{total_entries}",
                "<br><b>Status</b><br><b style='color:#287a3d'>READY FOR EXTRACTION</b>",
            ]
        else:
            ready = blocking_count == 0
            status_text = "READY FOR APPROVAL" if ready else "ACTION REQUIRED"
            status_color = "#287a3d" if ready else "#a33"
            lines = [
                f"<b>Verification Anchors</b><br>{len(self.mapping.anchors)}",
                f"<br><b>Confirmed Segments</b><br>{len(confirmed)}",
                f"<br><b>Outline Entries</b><br>{resolved_count} / {total_entries}",
                f"<br><b>Blocking Issues</b><br>{blocking_count}",
                f"<br><b>Status</b><br><b style='color:{status_color}'>{status_text}</b>",
            ]
        self.dashboard_summary.setText("<br>".join(lines))

    def render_workflow(self, confirmed: list, total_entries: int, resolved_count: int, blocking_count: int) -> None:
        def mark(ok: bool) -> str:
            return "✓" if ok else "□"

        steps = [
            (self._outline_approved(), "Outline Approved"),
            (bool(self.mapping.anchors), "Anchors Added"),
            (bool(confirmed), "Segments Confirmed"),
            (bool(total_entries) and resolved_count == total_entries, "Outline Fully Resolved"),
            (blocking_count == 0, "Diagnostics Clear"),
            (self.mapping.approved, "Mapping Approved"),
        ]
        self.workflow_summary.setText("<br>".join(f"{mark(ok)} {label}" for ok, label in steps))

    def render(self):
        self.table.setRowCount(len(self.mapping.anchors))
        for row, anchor in enumerate(self.mapping.anchors):
            for column, value in enumerate([anchor.label, anchor.printed_page, anchor.physical_page_number, anchor.pdf_page_index, anchor.exception]):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

        changed_page = self._changed_printed_page
        bold_font = QFont(); bold_font.setBold(True)

        segments = self.mapping.segments()
        self._segments_cache = segments
        self.segments_table.setRowCount(len(segments))
        confirmed_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        unconfirmed_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        for row, segment in enumerate(segments):
            physical_range = f"{segment.printed_start + segment.offset}-{segment.printed_end + segment.offset}"
            status = "confirmed" if segment.confirmed else "needs a second anchor"
            values = [f"{segment.printed_start}-{segment.printed_end}", physical_range, f"{segment.offset:+d}", len(segment.anchors), status]
            changed = changed_page is not None and segment.printed_start <= changed_page <= segment.printed_end
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setBackground(QColor(RESOLUTION_COLORS["segment"] if segment.confirmed else RESOLUTION_COLORS["extrapolated"]))
                item.setForeground(QColor("#1a1a1a"))
                if column == 0:
                    item.setIcon(confirmed_icon if segment.confirmed else unconfirmed_icon)
                if changed:
                    item.setFont(bold_font)
                self.segments_table.setItem(row, column, item)

        diagnostics = self.window.services.mappings.validate(self.mapping, self.book.page_count if self.book else 0, self.outline_entries)
        confirmed = self.mapping.confirmed_segments()
        unconfirmed = [segment for segment in segments if not segment.confirmed]
        total_entries = len(self.outline_entries)
        def is_resolved(entry: OutlineEntry) -> bool:
            return self.mapping.resolve_entry(entry).physical_page is not None

        resolved_count = sum(1 for entry in self.outline_entries if is_resolved(entry))

        def mark(ok: bool) -> str:
            return "✓" if ok else "✗"

        lines = []
        # Only prompt for a first anchor when entries actually need one -- an outline
        # that arrived with its own resolved physical_start/pdf_index for every entry
        # (JSON import) needs no anchors at all, and telling the operator to add one
        # anyway would be actively wrong, not just unnecessary.
        if not self.mapping.anchors and not (total_entries and resolved_count == total_entries):
            if self.outline_entries:
                lines.append("<b>Begin by selecting the first chapter and adding your first verification anchor.</b>")
            else:
                lines.append("<b>No outline entries yet — build and approve the outline in the Review Outline tab before verifying page alignment.</b>")
            lines.append("<br>")
        lines.append("<b>PAGE MAPPING STATUS</b>")
        lines.append(f"{mark(len(self.mapping.anchors) >= 2)} {len(self.mapping.anchors)} verification anchor(s)")
        lines.append(f"{mark(bool(confirmed))} {len(confirmed)} confirmed segment(s)")
        if unconfirmed:
            lines.append(f"✗ {len(unconfirmed)} segment(s) still need confirmation")
        lines.append(f"{mark(resolved_count == total_entries)} {resolved_count} / {total_entries} outline entries resolved")

        conflicts = [item for item in diagnostics if item.code == "offset_conflict"]
        blocking = [item for item in diagnostics if item.severity == Severity.BLOCKING and item.code != "offset_conflict"]
        passed = [item for item in diagnostics if item.severity == Severity.PASSED]

        if conflicts:
            lines.append("<br><b style='color:#a33'>CONFLICT</b>")
            lines.extend(f"• {item.message} <i>({suggested_action(item)})</i>" for item in conflicts)
        if blocking:
            lines.append("<br><b style='color:#a33'>BLOCKING</b>")
            lines.extend(f"• {item.message} <i>({suggested_action(item)})</i>" for item in blocking)
        if self.mapping.approved and not blocking and not conflicts:
            lines.append("<br><b style='color:#287a3d'>APPROVED</b>")
        elif passed and not blocking and not conflicts:
            if not unconfirmed and total_entries and resolved_count == total_entries:
                lines.append("<br><b style='color:#287a3d'>✓ All segments confirmed</b>")
                lines.append("<b style='color:#287a3d'>✓ All outline entries resolved</b>")
                lines.append("<br><b>Next Step</b><br>Verify and approve mapping")
            else:
                lines.append("<br><b style='color:#287a3d'>PASSED</b>")
                lines.extend(f"• {item.message}" for item in passed)

        self.status.setText("<br>".join(lines))

        self.mapping_preview.setRowCount(len(self.outline_entries))
        for row, entry in enumerate(self.outline_entries):
            resolution = self.mapping.resolve_entry(entry)
            physical = resolution.physical_page
            method = resolution.method
            detail = resolution.detail if resolution.physical_page is None else ""
            values = [
                entry.title, entry.printed_start or "—", physical or "—",
                (physical - 1) if physical else "—", f"{method}{': ' + detail if detail else ''}",
            ]
            changed = changed_page is not None and entry.printed_start == changed_page
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 4:
                    item.setBackground(QColor(RESOLUTION_COLORS.get(method, "#e0e0e0")))
                    item.setForeground(QColor("#1a1a1a"))
                if changed:
                    item.setFont(bold_font)
                self.mapping_preview.setItem(row, column, item)

        diagnostic_entries = self._diagnostic_entries(diagnostics, segments)
        blocking_count = sum(1 for entry in diagnostic_entries if entry["severity"] == Severity.BLOCKING)
        warning_count = sum(1 for entry in diagnostic_entries if entry["severity"] == Severity.WARNING)
        self.diagnostics_summary.setText(
            f"<b>Confirmed Segments</b><br>{len(confirmed)}"
            f"<br><b>Warnings</b><br>{warning_count}"
            f"<br><b>Blocking Issues</b><br>{blocking_count}"
        )
        self.render_dashboard(confirmed, total_entries, resolved_count, blocking_count)
        self.render_workflow(confirmed, total_entries, resolved_count, blocking_count)
        self.diagnostics_list.clear()
        for entry in diagnostic_entries:
            marker = "✗" if entry["severity"] == Severity.BLOCKING else "⚠"
            label = DIAGNOSTIC_LABELS.get(entry["code"], entry["code"])
            list_item = QListWidgetItem(f"{marker} {label}")
            list_item.setData(Qt.ItemDataRole.UserRole, entry)
            list_item.setForeground(QColor("#a33" if entry["severity"] == Severity.BLOCKING else "#9a5a00"))
            self.diagnostics_list.addItem(list_item)

        unconfirmed_index = next((i for i, segment in enumerate(segments) if not segment.confirmed), None)
        selected_row = self.segments_table.currentRow()
        guidance_index = selected_row if 0 <= selected_row < len(segments) else unconfirmed_index
        if not segments:
            self.segment_guidance.setText(
                "No segments yet — add verification anchors to create one." if self.mapping.anchors else ""
            )
        elif guidance_index is None:
            self.segment_guidance.setText("<b style='color:#287a3d'>✓ All segments confirmed</b>")
        else:
            self.segment_guidance.setText(self._describe_segment(segments[guidance_index], guidance_index, segments))

        suggestion = self.window.services.mappings.suggest_next_anchor(self.mapping, self.outline_entries)
        if suggestion:
            reason = self._suggestion_reason(confirmed)
            self.suggestion_label.setText(
                "<b>Next Recommended Verification</b>"
                f"<br><b>Section</b><br>{suggestion.title}"
                f"<br><b>Printed page</b><br>{suggestion.printed_start}"
                f"<br><b>Reason</b><br>{reason}"
                "<br><b>Next action</b><br>Navigate to this page in the preview and verify its physical page, then add the anchor."
            )
            self.suggest_button.setEnabled(True)
        else:
            self.suggestion_label.setText("No unresolved entries — nothing to suggest." if self.outline_entries else "")
            self.suggest_button.setEnabled(False)

        self._changed_printed_page = None

    def approve(self):
        if not self.book:
            return
        try:
            self.window.services.mappings.approve(
                self.mapping, self.book.page_count, "Verified in desktop GUI", self.outline_entries,
            )
            self.anchor_feedback.setText("")
            self.render()
        except Exception as exc:
            diagnostics = self.window.services.mappings.validate(self.mapping, self.book.page_count, self.outline_entries)
            segments = self.mapping.segments()
            blocking_entries = [entry for entry in self._diagnostic_entries(diagnostics, segments) if entry["severity"] == Severity.BLOCKING]
            self.window.show_error("Approval Blocked", self._format_approval_blocked(blocking_entries), str(exc))

    def _format_approval_blocked(self, blocking_entries: list[dict]) -> str:
        if not blocking_entries:
            return "The mapping could not be approved."
        multiple = len(blocking_entries) > 1
        sections = []
        for index, entry in enumerate(blocking_entries, start=1):
            prefix = f"{index}. " if multiple else ""
            block = [f"{prefix}Reason", entry["explanation"], "", "Action Required", entry["action"] or "Review this issue in the Mapping Diagnostics panel."]
            affected = self._affected_section_text(entry)
            if affected:
                block.extend(["", "Affected Section", affected])
            sections.append("\n".join(block))
        return "\n\n".join(sections)

from __future__ import annotations

from base64 import b64decode, b64encode

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
)


def _layout_store(window):
    services = getattr(window, "services", None)
    settings = getattr(services, "settings", None)
    service = getattr(services, "settings_service", None)
    layouts = getattr(settings, "ui_layouts", None)
    if settings is None or service is None or layouts is None:
        return None
    return settings, service, layouts


class TableLayoutController(QObject):
    """Spreadsheet-like table headers with persistent, operator-owned layouts."""

    def __init__(
        self,
        table: QTableWidget,
        window,
        key: str,
        *,
        default_widths: dict[int, int] | None = None,
        frozen_columns: tuple[int, ...] = (),
        content_caps: dict[int, int] | None = None,
    ):
        super().__init__(table)
        self.table = table
        self.window = window
        self.key = f"table/{key}"
        self.default_widths = default_widths or {}
        self.frozen_columns = frozen_columns
        self.content_caps = content_caps or {}
        self._loading = True
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self.save)
        self.frozen: QTableView | None = None

        header = table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(36)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_menu)
        header.sectionHandleDoubleClicked.connect(self.best_fit_column)
        header.sectionResized.connect(self._section_resized)
        header.sectionMoved.connect(lambda *_args: self.schedule_save())
        header.geometriesChanged.connect(self.schedule_save)

        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        # Must match the frozen QTableView's vertical scroll mode below: both
        # scrollbars are wired value-to-value (see _create_frozen_view), so if
        # one is ScrollPerItem (row index) and the other ScrollPerPixel (pixel
        # offset) the same raw value means a different position on each side,
        # and the frozen column's rows desync from the main table's rows on
        # every vertical scroll.
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.viewport().installEventFilter(self)
        table.installEventFilter(self)

        restored = self.restore()
        if not restored:
            self.apply_defaults()
        for column in frozen_columns:
            table.setColumnHidden(column, False)
        if frozen_columns:
            self._create_frozen_view()
        self._loading = False

    def apply_defaults(self):
        for column, width in self.default_widths.items():
            if 0 <= column < self.table.columnCount():
                self.table.setColumnWidth(column, width)

    def _state(self) -> str:
        return b64encode(bytes(self.table.horizontalHeader().saveState())).decode("ascii")

    def restore(self) -> bool:
        store = _layout_store(self.window)
        if not store:
            return False
        encoded = store[2].get(self.key)
        if not encoded:
            return False
        try:
            return self.table.horizontalHeader().restoreState(b64decode(encoded))
        except (ValueError, TypeError):
            return False

    def schedule_save(self, *_args):
        if not self._loading:
            self._save_timer.start()

    def save(self):
        store = _layout_store(self.window)
        if not store:
            return
        settings, service, layouts = store
        layouts[self.key] = self._state()
        service.save(settings)

    def reset(self):
        header = self.table.horizontalHeader()
        for visual in range(header.count()):
            logical = header.logicalIndex(visual)
            header.moveSection(header.visualIndex(logical), logical)
            self.table.setColumnHidden(logical, False)
        self.apply_defaults()
        self.schedule_save()
        self._update_frozen_geometry()

    def best_fit_column(self, logical: int):
        if not (0 <= logical < self.table.columnCount()):
            return
        self.table.resizeColumnToContents(logical)
        minimum = self.default_widths.get(logical, 56)
        maximum = self.content_caps.get(logical, 700 if logical in self.frozen_columns else 320)
        self.table.setColumnWidth(logical, max(minimum, min(self.table.columnWidth(logical), maximum)))
        self.schedule_save()

    def best_fit_all(self):
        for logical in range(self.table.columnCount()):
            if not self.table.isColumnHidden(logical):
                self.best_fit_column(logical)

    def show_header_menu(self, position: QPoint, source_header=None):
        menu = QMenu(self.table)
        header = self.table.horizontalHeader()
        for logical in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(logical)
            label = item.text() if item else f"Column {logical + 1}"
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(logical))
            action.setEnabled(logical not in self.frozen_columns)
            action.toggled.connect(
                lambda visible, column=logical: self._set_column_visible(column, visible)
            )
            menu.addAction(action)
        menu.addSeparator()
        fit = menu.addAction("Best Fit Columns")
        fit.triggered.connect(self.best_fit_all)
        reset = menu.addAction("Reset Column Layout")
        reset.triggered.connect(self.reset)
        menu.exec((source_header or header).mapToGlobal(position))

    def _set_column_visible(self, logical: int, visible: bool):
        self.table.setColumnHidden(logical, not visible)
        self.schedule_save()
        self._update_frozen_geometry()

    def _section_resized(self, logical: int, _old: int, width: int):
        if self.frozen and logical in self.frozen_columns:
            self.frozen.setColumnWidth(logical, width)
            self._update_frozen_geometry()
        self.schedule_save()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self._update_frozen_geometry()
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = event.angleDelta().y() or event.angleDelta().x()
            bar = self.table.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            return True
        return super().eventFilter(watched, event)

    def _create_frozen_view(self):
        frozen = QTableView(self.table)
        self.frozen = frozen
        frozen.setObjectName(f"{self.table.objectName()}FrozenColumns")
        frozen.setModel(self.table.model())
        frozen.setSelectionModel(self.table.selectionModel())
        frozen.setSelectionBehavior(self.table.selectionBehavior())
        frozen.setEditTriggers(self.table.editTriggers())
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.verticalHeader().hide()
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen_header = frozen.horizontalHeader()
        frozen_header.setSectionsMovable(False)
        frozen_header.setSectionsClickable(True)
        frozen_header.setStretchLastSection(False)
        frozen_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        frozen_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        frozen_header.customContextMenuRequested.connect(
            lambda position: self.show_header_menu(position, frozen_header)
        )
        frozen_header.sectionHandleDoubleClicked.connect(self.best_fit_column)
        frozen_header.sectionResized.connect(
            lambda logical, _old, width: self.table.setColumnWidth(logical, width)
            if logical in self.frozen_columns else None
        )
        for logical in range(self.table.columnCount()):
            frozen.setColumnHidden(logical, logical not in self.frozen_columns)
        for logical in self.frozen_columns:
            frozen.setColumnWidth(logical, self.table.columnWidth(logical))
        self.table.verticalScrollBar().valueChanged.connect(frozen.verticalScrollBar().setValue)
        frozen.verticalScrollBar().valueChanged.connect(self.table.verticalScrollBar().setValue)
        frozen.show()
        frozen.raise_()
        self._update_frozen_geometry()

    def _update_frozen_geometry(self):
        if not self.frozen:
            return
        width = sum(
            self.table.columnWidth(column)
            for column in self.frozen_columns
            if not self.table.isColumnHidden(column)
        )
        frame = self.table.frameWidth()
        x = self.table.verticalHeader().width() + frame
        self.frozen.setGeometry(
            x,
            frame,
            width,
            self.table.viewport().height() + self.table.horizontalHeader().height(),
        )


class SplitterLayoutController(QObject):
    def __init__(self, splitter: QSplitter, window, key: str, default_sizes: list[int]):
        super().__init__(splitter)
        self.splitter = splitter
        self.window = window
        self.key = f"splitter/{key}"
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self.save)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)
        splitter.setOpaqueResize(True)
        splitter.setSizes(default_sizes)
        self.restore()
        splitter.splitterMoved.connect(lambda *_args: self._save_timer.start())

    def restore(self):
        store = _layout_store(self.window)
        if not store:
            return False
        encoded = store[2].get(self.key)
        if not encoded:
            return False
        try:
            return self.splitter.restoreState(b64decode(encoded))
        except (ValueError, TypeError):
            return False

    def save(self):
        store = _layout_store(self.window)
        if not store:
            return
        settings, service, layouts = store
        layouts[self.key] = b64encode(bytes(self.splitter.saveState())).decode("ascii")
        service.save(settings)


def configure_table(
    table: QTableWidget,
    window,
    key: str,
    *,
    default_widths: dict[int, int] | None = None,
    frozen_columns: tuple[int, ...] = (),
    content_caps: dict[int, int] | None = None,
) -> TableLayoutController:
    controller = TableLayoutController(
        table, window, key,
        default_widths=default_widths,
        frozen_columns=frozen_columns,
        content_caps=content_caps,
    )
    table._layout_controller = controller
    return controller


def configure_splitter(
    splitter: QSplitter,
    window,
    key: str,
    default_sizes: list[int],
) -> SplitterLayoutController:
    controller = SplitterLayoutController(splitter, window, key, default_sizes)
    splitter._layout_controller = controller
    return controller


def best_fit_button(table: QTableWidget) -> QPushButton:
    button = QPushButton("Best Fit Columns")
    button.setToolTip("Resize visible columns to their current contents. Double-click a header divider to fit one column.")
    button.clicked.connect(table._layout_controller.best_fit_all)
    return button

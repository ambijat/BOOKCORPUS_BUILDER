import json
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QHeaderView, QSplitter, QTableWidget, QTableWidgetItem, QWidget

from bookcorpusbuilder.gui.services.settings import SettingsService
from bookcorpusbuilder.gui.widgets.table_usability import configure_splitter, configure_table


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def fake_window(tmp_path):
    service = SettingsService(tmp_path / "settings.json")
    return SimpleNamespace(services=SimpleNamespace(settings_service=service, settings=service.load()))


def make_table():
    table = QTableWidget(2, 5)
    table.setHorizontalHeaderLabels(["Include", "Sno", "Title", "Printed", "Warning"])
    for column, value in enumerate(["yes", "1", "A deliberately long title", "12", "review warning"]):
        table.setItem(0, column, QTableWidgetItem(value))
    return table


def test_interactive_header_frozen_columns_and_persistent_state(app, tmp_path):
    window = fake_window(tmp_path)
    table = make_table()
    controller = configure_table(
        table, window, "test.outline",
        default_widths={0: 70, 1: 90, 2: 500, 3: 100, 4: 260},
        frozen_columns=(0, 1, 2), content_caps={2: 700, 4: 400},
    )
    header = table.horizontalHeader()

    assert header.sectionsMovable()
    assert header.sectionsClickable()
    assert not header.stretchLastSection()
    assert all(
        header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
        for column in range(table.columnCount())
    )
    assert table.columnWidth(2) == 500
    assert controller.frozen is not None
    assert not controller.frozen.isColumnHidden(0)
    assert controller.frozen.isColumnHidden(4)
    assert controller.frozen.horizontalHeader().sectionResizeMode(2) == QHeaderView.ResizeMode.Interactive
    controller.frozen.setColumnWidth(2, 610)
    assert table.columnWidth(2) == 610

    table.setColumnWidth(2, 620)
    table.setColumnHidden(4, True)
    header.moveSection(header.visualIndex(3), 0)
    controller.save()
    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "table/test.outline" in stored["ui_layouts"]

    restored = make_table()
    configure_table(
        restored, window, "test.outline",
        default_widths={0: 70, 1: 90, 2: 500, 3: 100, 4: 260},
        frozen_columns=(0, 1, 2),
    )
    assert restored.columnWidth(2) == 620
    assert restored.isColumnHidden(4)
    assert restored.horizontalHeader().visualIndex(3) == 0


def test_best_fit_is_bounded_and_shift_wheel_scrolls_horizontally(app, tmp_path):
    window = fake_window(tmp_path)
    table = make_table()
    table.resize(320, 180)
    controller = configure_table(
        table, window, "test.wheel",
        default_widths={0: 70, 1: 90, 2: 500, 3: 100, 4: 260},
        content_caps={2: 540},
    )
    table.show()
    app.processEvents()
    controller.best_fit_column(2)
    assert 500 <= table.columnWidth(2) <= 540

    bar = table.horizontalScrollBar()
    bar.setValue(min(100, bar.maximum()))
    before = bar.value()

    class ShiftWheel:
        def type(self):
            from PySide6.QtCore import QEvent
            return QEvent.Type.Wheel

        def modifiers(self):
            return Qt.KeyboardModifier.ShiftModifier

        def angleDelta(self):
            return QPoint(0, -120)

    assert controller.eventFilter(table.viewport(), ShiftWheel()) is True
    assert bar.value() > before


def test_splitter_sizes_are_persistent(app, tmp_path):
    window = fake_window(tmp_path)
    splitter = QSplitter()
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.resize(900, 300)
    controller = configure_splitter(splitter, window, "test.panes", [300, 600])
    splitter.show()
    app.processEvents()
    splitter.setSizes([240, 660])
    controller.save()

    restored = QSplitter()
    restored.addWidget(QWidget())
    restored.addWidget(QWidget())
    restored.resize(900, 300)
    configure_splitter(restored, window, "test.panes", [450, 450])
    restored.show()
    app.processEvents()
    left, right = restored.sizes()
    assert left < right
    assert restored.handleWidth() == 7
    assert not restored.childrenCollapsible()


def test_frozen_view_vertical_scroll_stays_in_sync_with_many_rows(app, tmp_path):
    # Regression: the frozen overlay defaulted to per-pixel vertical scrolling
    # while the main table defaulted to Qt's per-row default, so the two
    # scrollbars -- wired value-to-value in _create_frozen_view -- used
    # incompatible units even though the raw numbers looked the same. "Row 19"
    # on the main table became "19 pixels" on the frozen view, so after any
    # vertical scroll the frozen column showed a different row than the one
    # its row-number gutter (owned by the main table) claimed to be showing.
    window = fake_window(tmp_path)
    table = QTableWidget(60, 5)
    table.setHorizontalHeaderLabels(["Include", "Sno", "Title", "Printed", "Warning"])
    for row in range(60):
        for column in range(5):
            table.setItem(row, column, QTableWidgetItem(f"r{row}c{column}"))
    table.resize(320, 180)
    controller = configure_table(
        table, window, "test.manyrows",
        default_widths={0: 70, 1: 90, 2: 500, 3: 100, 4: 260},
        frozen_columns=(0, 1, 2),
    )
    table.show()
    app.processEvents()

    frozen_bar = controller.frozen.verticalScrollBar()
    main_bar = table.verticalScrollBar()
    assert table.verticalScrollMode() == controller.frozen.verticalScrollMode()
    # A few pixels of slack is expected: the frozen view permanently hides its
    # own scrollbars (ScrollBarAlwaysOff) while the main table reserves space
    # for one, so their viewports aren't pixel-identical. What must hold is
    # the units matching (asserted above) and same-row-on-top after a scroll
    # (asserted below) -- that's the actual, operator-visible contract.
    assert abs(main_bar.maximum() - frozen_bar.maximum()) <= 10

    main_bar.setValue(main_bar.maximum() // 2)
    app.processEvents()
    assert frozen_bar.value() == main_bar.value()
    assert controller.frozen.rowAt(0) == table.rowAt(0)

    main_bar.setValue(main_bar.maximum())
    app.processEvents()
    assert controller.frozen.rowAt(0) == table.rowAt(0)


def test_all_main_workspace_tables_and_splitters_are_configured(app, tmp_path, monkeypatch):
    config = tmp_path / "app-settings.json"
    config.write_text(
        json.dumps({
            "project_root": str(tmp_path),
            "input_pdf_dir": str(tmp_path / "input"),
            "outline_dir": str(tmp_path / "outlines"),
            "output_dir": str(tmp_path / "output"),
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("BOOKCORPUSBUILDER_CONFIG", str(config))
    from bookcorpusbuilder.gui.main_window import MainWindow

    window = MainWindow()
    tables = window.findChildren(QTableWidget)
    splitters = window.findChildren(QSplitter)
    assert len(tables) >= 6
    assert all(hasattr(table, "_layout_controller") for table in tables)
    assert len(splitters) >= 4
    assert all(hasattr(splitter, "_layout_controller") for splitter in splitters)
    assert "border-right: 3px" in window.styleSheet()
    window.services.settings.ui_layouts["test/preserved"] = "state"
    window.screens[-1].save()
    assert window.services.settings.ui_layouts["test/preserved"] == "state"
    window.close()

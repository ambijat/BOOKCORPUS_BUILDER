import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QStatusBar

from bookcorpusbuilder.gui.main_window import SETTINGS_PATH_FIELDS, SettingsScreen
from bookcorpusbuilder.gui.services.settings import AppSettings, SettingsService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeWindow:
    def __init__(self, root: Path, settings: AppSettings):
        self.services = SimpleNamespace(
            settings=settings,
            settings_service=SettingsService(root / "settings.json"),
            rebuild=lambda: None,
        )
        self._status = QStatusBar()
        self.rebuilt = False

    def statusBar(self):
        return self._status


def _settings(tmp_path: Path, **overrides) -> AppSettings:
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    base = dict(
        project_root=str(tmp_path), input_pdf_dir=str(valid_dir),
        outline_dir=str(valid_dir), output_dir=str(valid_dir),
    )
    base.update(overrides)
    return AppSettings(**base)


def test_settings_grouped_into_logical_sections(app, tmp_path):
    from PySide6.QtWidgets import QGroupBox
    window = FakeWindow(tmp_path, _settings(tmp_path))
    screen = SettingsScreen(window)

    titles = [box.title() for box in screen.findChildren(QGroupBox)]
    assert "Project" in titles
    assert "Parsing & Detection" in titles
    assert "Extraction Defaults" in titles
    assert "Diagnostics" in titles


def test_each_field_shows_an_operator_language_description(app, tmp_path):
    from PySide6.QtWidgets import QLabel
    window = FakeWindow(tmp_path, _settings(tmp_path))
    screen = SettingsScreen(window)

    all_text = " ".join(label.text() for label in screen.findChildren(QLabel))
    assert "Where extracted corpus files" in all_text  # output_dir description
    assert "Where source PDFs are read from" in all_text  # input_pdf_dir description


def test_valid_paths_show_a_checkmark_status(app, tmp_path):
    window = FakeWindow(tmp_path, _settings(tmp_path))
    screen = SettingsScreen(window)

    for name in SETTINGS_PATH_FIELDS:
        assert screen.path_status_labels[name].text() == "✓ Valid"
    assert "READY" in screen.summary.text()
    assert screen.config_banner.isHidden()


def test_missing_directory_shows_a_warning_status(app, tmp_path):
    missing = str(tmp_path / "does-not-exist")
    window = FakeWindow(tmp_path, _settings(tmp_path, output_dir=missing))
    screen = SettingsScreen(window)

    assert screen.path_status_labels["output_dir"].text() == "⚠ Directory not found"
    assert "ACTION REQUIRED" in screen.summary.text()
    assert not screen.config_banner.isHidden()
    assert "Configuration Required" in screen.config_banner.text()
    assert "Output Directory" in screen.config_banner.text()


def test_file_instead_of_directory_shows_a_distinct_warning(app, tmp_path):
    a_file = tmp_path / "not_a_folder.txt"
    a_file.write_text("x")
    window = FakeWindow(tmp_path, _settings(tmp_path, outline_dir=str(a_file)))
    screen = SettingsScreen(window)

    assert screen.path_status_labels["outline_dir"].text() == "⚠ Not a directory"


def test_unwritable_directory_shows_a_not_writable_warning(app, tmp_path):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o500)  # read + execute, no write
    try:
        window = FakeWindow(tmp_path, _settings(tmp_path, outline_dir=str(readonly)))
        screen = SettingsScreen(window)
        assert screen.path_status_labels["outline_dir"].text() == "⚠ Not writable"
    finally:
        readonly.chmod(0o700)  # restore so tmp_path cleanup can remove it


def test_blank_path_shows_not_set_rather_than_a_directory_error(app, tmp_path):
    window = FakeWindow(tmp_path, _settings(tmp_path, project_root=""))
    screen = SettingsScreen(window)

    assert screen.path_status_labels["project_root"].text() == "Not set"


def test_validation_updates_live_when_a_field_is_edited(app, tmp_path):
    window = FakeWindow(tmp_path, _settings(tmp_path))
    screen = SettingsScreen(window)
    assert screen.path_status_labels["output_dir"].text() == "✓ Valid"

    screen.fields["output_dir"].setText(str(tmp_path / "brand-new-missing-folder"))

    assert screen.path_status_labels["output_dir"].text() == "⚠ Directory not found"
    assert not screen.config_banner.isHidden()

    screen.fields["output_dir"].setText(str(tmp_path))  # tmp_path itself always exists

    assert screen.path_status_labels["output_dir"].text() == "✓ Valid"
    assert screen.config_banner.isHidden()


def test_choosing_a_folder_refreshes_validation_without_a_manual_save(app, tmp_path, monkeypatch):
    from unittest.mock import patch
    from PySide6.QtWidgets import QFileDialog

    window = FakeWindow(tmp_path, _settings(tmp_path, output_dir=str(tmp_path / "missing")))
    screen = SettingsScreen(window)
    assert screen.path_status_labels["output_dir"].text() == "⚠ Directory not found"

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(tmp_path)):
        screen.choose_folder(screen.fields["output_dir"])

    assert screen.path_status_labels["output_dir"].text() == "✓ Valid"


def test_save_persists_exactly_as_before_and_reuses_existing_behaviour(app, tmp_path):
    window = FakeWindow(tmp_path, _settings(tmp_path))
    screen = SettingsScreen(window)
    screen.fields["pdf_viewer_command"].setText("xdg-open")
    screen.minimum.setValue(42)

    screen.save()

    reloaded = window.services.settings_service.load()
    assert reloaded.pdf_viewer_command == "xdg-open"
    assert reloaded.minimum_chars == 42
    assert window.statusBar().currentMessage() == "Local settings saved."


def test_load_populates_all_fields_from_settings_unchanged(app, tmp_path):
    settings = _settings(tmp_path, toc_scan_pages=7, index_scan_pages=9, minimum_chars=123)
    window = FakeWindow(tmp_path, settings)
    screen = SettingsScreen(window)

    assert screen.toc.value() == 7
    assert screen.index.value() == 9
    assert screen.minimum.value() == 123
    assert screen.fields["project_root"].text() == settings.project_root

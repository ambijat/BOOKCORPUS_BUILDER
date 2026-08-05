"""Sprint 14 (Operator Navigation & Keyboard Workflow) and Sprint 15 (Error Reporting
& Recovery): tests for the shared dialogs.py helpers."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from bookcorpusbuilder.gui.widgets.dialogs import confirm_destructive, format_operator_error


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_confirm_destructive_defaults_to_no_not_yes(app):
    """The whole point of this helper: unlike the plain QMessageBox.question()
    convenience call (which defaults Enter to Yes), a reflexive Enter here must not
    confirm the destructive action."""
    box_holder = {}
    real_init = QMessageBox.__init__

    def capturing_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        box_holder["box"] = self

    with patch.object(QMessageBox, "__init__", capturing_init), \
         patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
        confirm_destructive(None, "Delete outline row?", "Remove the selected row?")

    box = box_holder["box"]
    assert box.defaultButton() == box.button(QMessageBox.StandardButton.No)
    assert box.standardButtons() == (QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)


def test_confirm_destructive_returns_true_only_on_an_explicit_yes(app):
    with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Yes):
        assert confirm_destructive(None, "title", "text") is True
    with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No):
        assert confirm_destructive(None, "title", "text") is False


def test_confirm_destructive_shows_the_real_title_and_text(app):
    seen = {}

    def fake_exec(self):
        seen["title"] = self.windowTitle()
        seen["text"] = self.text()
        return QMessageBox.StandardButton.No

    with patch.object(QMessageBox, "exec", fake_exec):
        confirm_destructive(None, "Delete outline row?", "Remove the selected row from the current review table?")

    assert seen["title"] == "Delete outline row?"
    assert seen["text"] == "Remove the selected row from the current review table?"


def test_format_operator_error_shows_reason_and_next_steps(app):
    text = format_operator_error("Two conflicting anchors were found.", "Remove one of them and try again.")
    assert "<b>Reason</b>" in text
    assert "Two conflicting anchors were found." in text
    assert "<b>What you can do</b>" in text
    assert "Remove one of them and try again." in text
    # Reason comes first, guidance second -- not the other way around.
    assert text.index("Reason") < text.index("Two conflicting")
    assert text.index("Two conflicting") < text.index("What you can do")


def test_format_operator_error_never_invents_a_reason_or_guidance(app):
    """The helper only assembles what it's given -- it must never substitute a generic
    placeholder, since that would silently discard the real reason (requirement #6)."""
    text = format_operator_error("exact reason text", "exact next step text")
    assert "exact reason text" in text
    assert "exact next step text" in text

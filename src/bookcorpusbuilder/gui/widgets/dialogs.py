from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_destructive(parent: QWidget, title: str, text: str) -> bool:
    """Shared Yes/No confirmation for hard-to-undo actions (Sprint 14).

    Identical in appearance to the plain ``QMessageBox.question(parent, title, text)``
    call used throughout this app, except the default button is No, not Yes: pressing
    Enter without deliberately choosing a button does not confirm the destructive
    action. Reversible or purely informational Yes/No questions (e.g. "Import as
    JSON?") should keep using the plain call -- this helper is only for actions that
    lose operator work if confirmed by accident (deleting a row, clearing pasted text).
    """
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


def format_operator_error(reason: str, next_steps: str) -> str:
    """Shared "Reason / What you can do" structure for operator-facing error dialogs
    (Sprint 15), generalizing the exact wording ``MainWindow.run_task()``'s generic
    Task Failed dialog already used (Sprint 13) so every ``show_error()`` call built
    from a caught exception reads the same way. ``reason`` should be plain operator
    language describing what went wrong -- never a bare exception class name or
    traceback; those belong only in ``show_error()``'s existing ``details`` parameter
    (its "Show Details" expandable pane), never suppressed.
    """
    return f"<b>Reason</b><br>{reason}<br><br><b>What you can do</b><br>{next_steps}"

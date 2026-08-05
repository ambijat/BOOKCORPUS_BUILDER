"""Sprint 13 (Product Refinement — Shared Task Lifecycle): regression tests for the
centralized, cross-workspace fix in MainWindow.run_task() itself, using the real,
threaded MainWindow (not a synchronous FakeWindow) so the actual QThread/signal
plumbing is exercised, matching this project's established convention for
infrastructure-level tests (see tests/test_table_usability.py)."""

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _real_window(tmp_path, monkeypatch):
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({
        "project_root": str(tmp_path),
        "input_pdf_dir": str(tmp_path / "input"),
        "outline_dir": str(tmp_path / "outlines"),
        "output_dir": str(tmp_path / "output"),
    }), encoding="utf-8")
    monkeypatch.setenv("BOOKCORPUSBUILDER_CONFIG", str(config))
    from bookcorpusbuilder.gui.main_window import MainWindow
    return MainWindow()


def _wait_until(condition, timeout_ms: int = 2000) -> None:
    """Waits on the actual, directly-observable outcome of a task (a callback firing, a
    label changing) rather than on MainWindow's internal self.threads/self.workers
    bookkeeping lists -- those are cleaned up via deleteLater() on a timing that proved
    flaky to poll directly under heavy same-process test load, independent of anything
    this sprint changed."""
    deadline = time.monotonic() + timeout_ms / 1000
    while not condition() and time.monotonic() < deadline:
        QApplication.processEvents()
    assert condition(), "task did not complete within the timeout"
    # Give the thread/worker's deleteLater() cleanup (queued once thread.finished fires)
    # a few more event-loop turns to actually run now, rather than leaving it pending
    # until interpreter shutdown.
    for _ in range(5):
        QApplication.processEvents()


def _succeeding_task():
    return "ok"


def _failing_task():
    raise RuntimeError("kaboom")


def test_successful_task_updates_last_action_and_clears_the_task_indicator(app, tmp_path, monkeypatch):
    window = _real_window(tmp_path, monkeypatch)
    results = []

    window.run_task(_succeeding_task, results.append)
    # Set synchronously in run_task() itself, before the thread starts -- observable
    # immediately, regardless of how fast the task itself completes.
    assert "running" in window.task_indicator.text().lower()

    _wait_until(lambda: bool(results))

    assert results == ["ok"]
    assert window.last_action.text() == "Last action: _succeeding_task succeeded"
    _wait_until(lambda: window.task_indicator.text() == "")


def test_failed_task_shows_a_structured_dialog_and_updates_last_action(app, tmp_path, monkeypatch):
    window = _real_window(tmp_path, monkeypatch)
    calls = []
    window.show_error = lambda title, message, details="": calls.append((title, message, details))

    window.run_task(_failing_task, lambda _result: None)
    _wait_until(lambda: bool(calls))

    title, message, details = calls[0]
    assert title == "Task Failed"
    assert "kaboom" in message
    assert "Reason" in message
    assert "What you can do" in message
    assert "kaboom" in details  # traceback is preserved, not suppressed (requirement #3)
    _wait_until(lambda: window.last_action.text() == "Last action: _failing_task failed")
    _wait_until(lambda: window.task_indicator.text() == "")


def test_failed_task_calls_the_workspace_supplied_on_failure_hook(app, tmp_path, monkeypatch):
    """This is the centralized half of the Sprint 3 fix: a workspace that opts in via
    on_failure gets a chance to reset its own in-progress state, in addition to (not
    instead of) the shared dialog every caller already receives."""
    window = _real_window(tmp_path, monkeypatch)
    window.show_error = lambda *_args, **_kwargs: None
    received = []

    window.run_task(_failing_task, lambda _result: None, on_failure=lambda message, details: received.append((message, details)))
    _wait_until(lambda: bool(received))

    message, details = received[0]
    assert "kaboom" in message
    assert details


def test_a_task_without_on_failure_behaves_exactly_as_before_sprint_13(app, tmp_path, monkeypatch):
    """Backward compatibility: every pre-existing run_task() call site (Library,
    Structure Builder) doesn't pass on_failure at all -- confirms that's still valid
    and doesn't raise just because the hook wasn't supplied."""
    window = _real_window(tmp_path, monkeypatch)
    window.show_error = lambda *_args, **_kwargs: None

    window.run_task(_failing_task, lambda _result: None)  # no on_failure kwarg
    _wait_until(lambda: window.last_action.text() == "Last action: _failing_task failed")


def test_progress_reporting_tasks_do_not_use_the_generic_indicator(app, tmp_path, monkeypatch):
    """Reuses existing progress widgets (#2) rather than showing a redundant, competing
    indicator: with_progress=True tasks (currently only Extract) have their own
    dedicated progress bar, so the shared header indicator stays out of the way."""
    window = _real_window(tmp_path, monkeypatch)
    results = []

    def _with_progress(progress=None):
        if progress:
            progress(1, 1, "done")
        return "ok"

    window.run_task(_with_progress, results.append, with_progress=True, progress_slot=lambda *_a: None)
    assert window.task_indicator.text() == ""
    _wait_until(lambda: bool(results))
    assert window.task_indicator.text() == ""

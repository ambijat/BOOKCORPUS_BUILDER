from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal, Slot


class FunctionWorker(QObject):
    finished = Signal(object)
    failed = Signal(str, str)
    progress = Signal(int, int, str)

    def __init__(self, function, *args, with_progress: bool = False, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.with_progress = with_progress

    @Slot()
    def run(self):
        try:
            if self.with_progress:
                self.kwargs["progress"] = self.progress.emit
            self.finished.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())

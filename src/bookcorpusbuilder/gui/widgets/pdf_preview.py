from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget


class PdfTextPreview(QWidget):
    pageChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.pdf_path: Path | None = None
        self.page_count = 0
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.valueChanged.connect(self.load_page)
        previous = QPushButton("Previous")
        following = QPushButton("Next")
        previous.clicked.connect(lambda: self.page.setValue(max(1, self.page.value() - 1)))
        following.clicked.connect(lambda: self.page.setValue(min(self.page_count, self.page.value() + 1)))
        controls = QHBoxLayout()
        controls.addWidget(previous)
        controls.addWidget(QLabel("Physical page"))
        controls.addWidget(self.page)
        controls.addWidget(following)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.context = QLabel("No outline candidate selected.")
        self.context.setWordWrap(True)
        self.metadata = QLabel("Book: — · PDF index: — · Native text status: —")
        self.metadata.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.context)
        layout.addWidget(self.metadata)
        layout.addLayout(controls)
        layout.addWidget(self.text)

    def set_pdf(self, path: Path | None, page_count: int = 0):
        self.pdf_path = path
        self.page_count = page_count
        self.page.setMaximum(max(1, page_count))
        self.metadata.setText(
            f"Book: {path.name if path else '—'} · Physical page: 1 · PDF index: 0 · "
            "Printed page: not mapped"
        )
        self.load_page(1)

    def set_context(self, title: str = "", reference: str = ""):
        self.context.setText(
            f"Selected: {title} · {reference}" if title else "No outline candidate selected."
        )

    def jump_to(self, physical_page: int):
        self.page.setValue(max(1, min(physical_page, max(1, self.page_count))))

    def load_page(self, physical_page: int):
        if not self.pdf_path:
            self.text.setPlainText("Select a book to preview its pages.")
            return
        try:
            import pdfplumber
            with pdfplumber.open(self.pdf_path) as pdf:
                self.page_count = len(pdf.pages)
                self.page.setMaximum(max(1, self.page_count))
                extracted = pdf.pages[physical_page - 1].extract_text() or ""
            self.text.setPlainText(extracted or "No native text found on this page. OCR may be required.")
            self.metadata.setText(
                f"Book: {self.pdf_path.name} · Physical page: {physical_page} · "
                f"PDF index: {physical_page - 1} · Printed page: not mapped · "
                f"Native text: {'available' if extracted else 'empty / likely scanned'}"
            )
            self.pageChanged.emit(physical_page)
        except Exception as exc:
            self.text.setPlainText(f"Preview unavailable: {exc}")

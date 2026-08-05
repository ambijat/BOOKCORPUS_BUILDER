from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ...paths import INPUT_PDF_DIR, OUTLINE_DIR, OUTPUT_DIR, PROJECT_ROOT
from .common import atomic_write_json, read_json


@dataclass
class AppSettings:
    project_root: str = str(PROJECT_ROOT)
    input_pdf_dir: str = str(INPUT_PDF_DIR)
    outline_dir: str = str(OUTLINE_DIR)
    output_dir: str = str(OUTPUT_DIR)
    toc_scan_pages: int = 12
    index_scan_pages: int = 12
    minimum_chars: int = 1
    pdf_viewer_command: str = ""
    ui_layouts: dict[str, str] = field(default_factory=dict)

    @property
    def ocr_status(self) -> str:
        return "available" if shutil.which("tesseract") else "unavailable"


class SettingsService:
    def __init__(self, path: Path | None = None):
        configured = os.environ.get("BOOKCORPUSBUILDER_CONFIG")
        self.path = path or (Path(configured) if configured else PROJECT_ROOT / ".bookcorpusbuilder.local.json")

    def load(self) -> AppSettings:
        value = read_json(self.path)
        return AppSettings(**value) if value else AppSettings()

    def save(self, settings: AppSettings) -> None:
        atomic_write_json(self.path, asdict(settings))

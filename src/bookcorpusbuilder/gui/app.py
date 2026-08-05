import logging
import sys
from pathlib import Path

def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is required. Install with: pip install -e '.[gui]'", file=sys.stderr)
        return 2
    from .services.settings import SettingsService

    output_dir = Path(SettingsService().load().output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=output_dir / "bookcorpusbuilder.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from .main_window import MainWindow

    application = QApplication(sys.argv)
    application.setApplicationName("BOOKCORPUSBUILDER")
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
LED Placement Studio – entry point
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.version import APP_NAME, APP_ORG, APP_VERSION
from ui.main_window import MainWindow


def _resource(*parts: str) -> Path:
    """Resolve asset path (works from source and PyInstaller bundle)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = ROOT
    return base.joinpath(*parts)


def _excepthook(exc_type, exc, tb):
    err = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        QMessageBox.critical(
            None,
            f"{APP_NAME} – unexpected error",
            f"Something went wrong.\n\n{exc_type.__name__}: {exc}\n\n"
            "Details have been printed to the console.",
        )
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc, tb)
    print(err, file=sys.stderr)


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    app.setStyle("Fusion")

    icon_path = _resource("assets", "icon.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    font = QFont("Segoe UI", 10)
    if not font.exactMatch():
        font = QFont("Arial", 10)
    app.setFont(font)

    sys.excepthook = _excepthook

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

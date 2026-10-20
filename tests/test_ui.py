"""Lightweight UI smoke tests (no keyboard injection or Windows desktop required)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_typing.core import TypingMode
from auto_typing.ui import MainWindow


def test_default_workspace_and_telex_preview() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.windowTitle() == "Auto Typing"
        assert window.mode.currentData() == TypingMode.TELEX
        assert window.preview.text() == "Chaof banj"
        assert window.start_button.isEnabled()
        assert not window.stop_button.isEnabled()
    finally:
        window.close()


def test_preview_updates_when_switching_modes() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.editor.setPlainText("Tiếng Việt")
        assert window.preview.text() == "Tieengs Vieetj"
        window.mode.setCurrentIndex(1)
        assert window.preview.text() == "Tiếng Việt"
        window.mode.setCurrentIndex(0)
        assert window.preview.text() == "(Clipboard paste: original Unicode text)"
    finally:
        window.close()

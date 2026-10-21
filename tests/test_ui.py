"""Lightweight UI smoke tests (no keyboard injection or Windows desktop required)."""

import os

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from auto_typing.core import TypingMode
from auto_typing.ui import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_default_workspace_and_telex_preview() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.windowTitle() == "Auto Typing"
        assert window.mode.currentData() == TypingMode.TELEX
        assert window.preview.text() == "[Keys] Chaof banj"
        assert window.start_button.isEnabled()
        assert not window.stop_button.isEnabled()
    finally:
        window.close()
        app.processEvents()


def test_preview_updates_when_switching_modes() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.editor.setPlainText("Tiếng Việt")
        assert window.preview.text() == "[Keys] Tieengs Vieetj"
        window.mode.setCurrentIndex(1)
        assert window.preview.text() == "Tiếng Việt"
        window.mode.setCurrentIndex(0)
        assert window.preview.text() == "(Clipboard paste: original Unicode text)"
    finally:
        window.close()
        app.processEvents()


def _rect_in(widget, ancestor) -> QRect:
    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())


@pytest.mark.parametrize("size", [(970, 700), (790, 620), (700, 500)])
def test_timing_controls_remain_accessible_without_overlap(size: tuple[int, int]) -> None:
    """No timing row is lost behind Start/Stop on small window sizes."""
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.resize(*size)
        window.show()
        app.processEvents()

        scroll = window.settings_scroll
        panel = scroll.parentWidget()
        viewport = scroll.viewport()
        scroll_rect = _rect_in(scroll, panel)
        start_rect = _rect_in(window.start_button, panel)
        stop_rect = _rect_in(window.stop_button, panel)

        assert scroll.isVisibleTo(window)
        assert window.start_button.isVisibleTo(window)
        assert window.stop_button.isVisibleTo(window)
        assert viewport.height() > 0
        assert start_rect.top() >= scroll_rect.bottom()
        assert not start_rect.intersects(scroll_rect)
        assert not stop_rect.intersects(scroll_rect)

        for field in (window.delay, window.interval, window.hold):
            scroll.ensureWidgetVisible(field, 0, 0)
            app.processEvents()
            assert viewport.rect().intersects(_rect_in(field, viewport))
    finally:
        window.close()
        app.processEvents()


def test_normalize_button_repairs_pasted_text() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.editor.setPlainText("“Chào\u00a0bạn”")
        window.show()
        app.processEvents()

        assert window.normalize_button.isVisible()
        assert window.start_button.isEnabled()
        window.normalize_button.click()
        app.processEvents()

        assert window.editor.toPlainText() == '"Chào bạn"'
        assert window.preview.text() == '[Keys] "Chaof banj"'
        assert window.start_button.isEnabled()
        assert not window.normalize_button.isVisible()
    finally:
        window.close()
        app.processEvents()


def test_invalid_physical_input_offers_lossless_unicode_mode() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.mode.setCurrentIndex(2)  # Physical-only mode
        window.editor.setPlainText("Xin chào 😊")
        window.show()
        app.processEvents()

        assert not window.start_button.isEnabled()
        assert window.unicode_button.isVisible()
        window.unicode_button.click()
        app.processEvents()

        assert window.mode.currentData() == TypingMode.UNICODE
        assert window.editor.toPlainText() == "Xin chào 😊"
        assert window.start_button.isEnabled()
        assert not window.unicode_button.isVisible()
    finally:
        window.close()
        app.processEvents()



def test_hybrid_preview_shows_physical_and_unicode_actions_for_mixed_text() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.editor.setPlainText("as Chào dd 😊")
        window.show()
        app.processEvents()

        preview = window.preview.text()
        assert preview.startswith("[Unicode] as")
        assert "[Keys]  Chaof " in preview
        assert "[Unicode] dd" in preview
        assert "[Unicode] 😊" in preview
        assert window.start_button.isEnabled()
        assert not window.unicode_button.isVisible()
    finally:
        window.close()
        app.processEvents()

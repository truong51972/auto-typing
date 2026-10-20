"""Polished, compact PySide6 interface for Windows auto typing."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .core import TypingMode, build_plan, to_telex
from .worker import TypingWorker


STYLE_SHEET = """
QMainWindow, QWidget#appBody {
    background: #0b1020;
    color: #e9eefc;
    font-family: "Segoe UI", "Arial";
    font-size: 13px;
}
QLabel { color: #e9eefc; background: transparent; }
QLabel#eyebrow {
    color: #8b9bb8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#title {
    font-size: 28px;
    font-weight: 700;
    color: #f5f7ff;
}
QLabel#subtitle, QLabel#secondary, QLabel#count {
    color: #95a5c2;
}
QLabel#badge {
    color: #bec9ff;
    background: #222d54;
    border: 1px solid #34467f;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#panelTitle {
    font-weight: 700;
    font-size: 15px;
    color: #f1f4fd;
}
QLabel#modeHint { color: #9baed0; font-size: 12px; }
QLabel#preview {
    color: #c8d8ff;
    background: #0e1629;
    border: 1px solid #2b3a58;
    border-radius: 10px;
    padding: 12px 14px;
}
QLabel#status { color: #95a5c2; font-weight: 600; }
QLabel#status[state="ok"] { color: #6dddb4; }
QLabel#status[state="error"] { color: #ff999b; }
QLabel#status[state="stopped"] { color: #ffd18a; }
QFrame#panel {
    background: #151e31;
    border: 1px solid #2b3750;
    border-radius: 16px;
}
QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0d1628;
    border: 1px solid #33415e;
    border-radius: 9px;
    color: #eff3ff;
    padding: 9px 11px;
    selection-background-color: #506dd1;
}
QPlainTextEdit {
    font-family: "Cascadia Code", "Consolas", "Segoe UI";
    font-size: 13px;
    line-height: 1.25;
    padding: 13px 14px;
}
QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #798bff;
}
QPlainTextEdit:read-only { color: #9ba9c4; }
QComboBox { min-height: 21px; padding-right: 30px; }
QComboBox::drop-down { width: 28px; border: 0; }
QComboBox QAbstractItemView {
    background: #1b2840;
    color: #f1f4ff;
    border: 1px solid #405173;
    selection-background-color: #405eb0;
    padding: 5px;
    outline: none;
}
QSpinBox, QDoubleSpinBox { min-height: 22px; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 18px; }
QPushButton {
    padding: 11px 18px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#startButton {
    background: #7086ff;
    color: #09132b;
    border: 1px solid #889aff;
}
QPushButton#startButton:hover { background: #90a0ff; }
QPushButton#stopButton {
    background: #273550;
    color: #e8edff;
    border: 1px solid #3d4c69;
}
QPushButton#stopButton:hover { background: #36486a; }
QPushButton:disabled {
    background: #253047;
    color: #7383a1;
    border-color: #344158;
}
QProgressBar {
    background: #0e172a;
    border: 1px solid #2c3b58;
    border-radius: 7px;
    height: 13px;
    color: #eaf0ff;
    text-align: center;
    font-size: 10px;
}
QProgressBar::chunk {
    background: #7a91ff;
    border-radius: 6px;
}
QScrollBar:vertical { background: #111b2c; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: #394967;
    border-radius: 4px;
    min-height: 22px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


_MODE_HINTS = {
    TypingMode.PASTE: "Fast insert via Ctrl+V. Your clipboard is replaced.",
    TypingMode.UNICODE: "Enter Unicode characters directly; UniKey is not required.",
    TypingMode.PHYSICAL: "Simulate real ASCII keystrokes using the target keyboard layout.",
    TypingMode.TELEX: "Send physical Telex keys. Enable UniKey Vietnamese / Telex first.",
}


def _eyebrow(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("eyebrow")
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Typing")
        self.resize(970, 700)
        self.setMinimumSize(790, 620)
        self.setStyleSheet(STYLE_SHEET)
        self.worker: TypingWorker | None = None

        body = QWidget()
        body.setObjectName("appBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(28, 24, 28, 26)
        root.setSpacing(18)
        self.setCentralWidget(body)

        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        heading.addWidget(_eyebrow("KEYBOARD AUTOMATION"))
        title = QLabel("Auto Typing")
        title.setObjectName("title")
        heading.addWidget(title)
        subtitle = QLabel("Compose once. Type naturally into any Windows app.")
        subtitle.setObjectName("subtitle")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        badge = QLabel("LOCAL  ·  WINDOWS")
        badge.setObjectName("badge")
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        root.addLayout(workspace, 1)

        editor_panel = QFrame()
        editor_panel.setObjectName("panel")
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(20, 18, 20, 20)
        editor_layout.setSpacing(12)
        editor_header = QHBoxLayout()
        editor_heading = QLabel("Source text")
        editor_heading.setObjectName("panelTitle")
        editor_header.addWidget(editor_heading)
        editor_header.addStretch()
        self.char_count = QLabel("0 characters")
        self.char_count.setObjectName("count")
        editor_header.addWidget(self.char_count)
        editor_layout.addLayout(editor_header)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Enter the text to type into another application...")
        self.editor.setPlainText("Chào bạn")
        editor_layout.addWidget(self.editor, 1)
        editor_tip = QLabel("Tip: switch to the target window during the countdown.")
        editor_tip.setObjectName("secondary")
        editor_tip.setWordWrap(True)
        editor_layout.addWidget(editor_tip)
        workspace.addWidget(editor_panel, 5)

        options_panel = QFrame()
        options_panel.setObjectName("panel")
        options_panel.setMinimumWidth(272)
        options_layout = QVBoxLayout(options_panel)
        options_layout.setContentsMargins(20, 18, 20, 20)
        options_layout.setSpacing(12)
        options_heading = QLabel("Typing settings")
        options_heading.setObjectName("panelTitle")
        options_layout.addWidget(options_heading)
        options_layout.addWidget(_eyebrow("OUTPUT MODE"))

        self.mode = QComboBox()
        self.mode.addItem("Clipboard Paste", TypingMode.PASTE)
        self.mode.addItem("Unicode Typing", TypingMode.UNICODE)
        self.mode.addItem("Physical Typing", TypingMode.PHYSICAL)
        self.mode.addItem("Telex Typing (UniKey)", TypingMode.TELEX)
        self.mode.setCurrentIndex(3)
        options_layout.addWidget(self.mode)
        self.mode_hint = QLabel()
        self.mode_hint.setObjectName("modeHint")
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setMinimumHeight(42)
        options_layout.addWidget(self.mode_hint)

        options_layout.addWidget(_eyebrow("TIMING"))
        timing = QFormLayout()
        timing.setVerticalSpacing(12)
        timing.setHorizontalSpacing(12)
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.5, 30)
        self.delay.setSingleStep(0.5)
        self.delay.setValue(3)
        self.delay.setSuffix(" s")
        timing.addRow("Start delay", self.delay)

        self.interval = QSpinBox()
        self.interval.setRange(10, 5000)
        self.interval.setValue(120)
        self.interval.setSuffix(" ms")
        timing.addRow("Key interval", self.interval)

        self.hold = QSpinBox()
        self.hold.setRange(1, 500)
        self.hold.setValue(20)
        self.hold.setSuffix(" ms")
        timing.addRow("Key hold", self.hold)
        options_layout.addLayout(timing)
        options_layout.addStretch(1)

        self.start_button = QPushButton("Start typing")
        self.start_button.setObjectName("startButton")
        self.stop_button = QPushButton("Stop  ·  F8")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        options_layout.addWidget(self.start_button)
        options_layout.addWidget(self.stop_button)
        workspace.addWidget(options_panel, 3)

        preview_panel = QFrame()
        preview_panel.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(20, 16, 20, 18)
        preview_layout.setSpacing(10)
        preview_header = QHBoxLayout()
        preview_header.addWidget(_eyebrow("KEYSTROKE PREVIEW"))
        preview_header.addStretch()
        preview_layout.addLayout(preview_header)
        self.preview = QLabel()
        self.preview.setObjectName("preview")
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setWordWrap(True)
        self.preview.setMinimumHeight(46)
        self.preview.setMaximumHeight(76)
        preview_layout.addWidget(self.preview)

        self.status = QLabel("Ready  ·  F8 stops an active session")
        self.status.setObjectName("status")
        preview_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        preview_layout.addWidget(self.progress)
        root.addWidget(preview_panel)

        self.editor.textChanged.connect(self._update_preview)
        self.mode.currentIndexChanged.connect(self._update_preview)
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        self._update_preview()

    def _update_preview(self) -> None:
        text = self.editor.toPlainText()
        mode = self.mode.currentData()
        self.char_count.setText(f"{len(text):,} characters")
        self.mode_hint.setText(_MODE_HINTS.get(mode, ""))
        try:
            if mode == TypingMode.TELEX:
                preview = to_telex(text)
            elif mode == TypingMode.PASTE:
                preview = "(Clipboard paste: original Unicode text)"
            else:
                preview = text
        except ValueError as error:
            preview = f"Invalid Telex input: {error}"
        self.preview.setText(preview[:240] + ("…" if len(preview) > 240 else ""))

    def _set_status(self, message: str, state: str = "") -> None:
        self.status.setText(message)
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _set_result(self, message: str) -> None:
        if message.startswith("Failed"):
            state = "error"
        elif message == "Stopped":
            state = "stopped"
        else:
            state = "ok"
        self._set_status(message, state)

    def _start(self) -> None:
        if self.worker is not None:
            return
        if sys.platform != "win32":
            QMessageBox.warning(self, "Unsupported platform", "Typing backend requires Windows.")
            return
        try:
            plan = build_plan(self.editor.toPlainText(), self.mode.currentData())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid input", str(error))
            return
        if self.hold.value() >= self.interval.value() and plan.count > 1:
            QMessageBox.warning(self, "Invalid timing", "Key hold must be shorter than interval.")
            return
        if "\n" in plan.payload and plan.mode != TypingMode.PASTE:
            answer = QMessageBox.question(
                self,
                "Enter can submit forms",
                "Newlines send Enter, which may submit a chat message or form. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if plan.mode == TypingMode.PASTE:
            from PySide6.QtGui import QGuiApplication

            QGuiApplication.clipboard().setText(plan.original_text)

        self.worker = TypingWorker(
            plan=plan,
            start_delay=self.delay.value(),
            interval_ms=self.interval.value(),
            hold_ms=self.hold.value(),
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.result.connect(self._set_result)
        self.worker.finished.connect(self._finished)
        self.progress.setMaximum(plan.count)
        self.progress.setValue(0)
        self._set_status(f"Switch to the destination app within {self.delay.value():g} s")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.editor.setReadOnly(True)
        self.mode.setEnabled(False)
        self.delay.setEnabled(False)
        self.interval.setEnabled(False)
        self.hold.setEnabled(False)
        self.worker.start()

    def _stop(self) -> None:
        if self.worker:
            self.worker.stop()
            self._set_status("Stopping...", "stopped")

    def _finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.editor.setReadOnly(False)
        self.mode.setEnabled(True)
        self.delay.setEnabled(True)
        self.interval.setEnabled(True)
        self.hold.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(2000):
                event.ignore()
                return
        super().closeEvent(event)

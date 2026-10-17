"""Compact PySide6 desktop interface for the Windows typing prototype."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Typing")
        self.resize(620, 520)
        self.worker: TypingWorker | None = None

        body = QWidget()
        layout = QVBoxLayout(body)
        self.setCentralWidget(body)

        layout.addWidget(QLabel("Input text"))
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Enter text to type into another window...")
        self.editor.setPlainText("Chào bạn")
        layout.addWidget(self.editor, stretch=1)

        self.mode = QComboBox()
        self.mode.addItem("Clipboard Paste", TypingMode.PASTE)
        self.mode.addItem("Unicode Typing", TypingMode.UNICODE)
        self.mode.addItem("Physical Typing", TypingMode.PHYSICAL)
        self.mode.addItem("Telex Typing (UniKey)", TypingMode.TELEX)
        self.mode.setCurrentIndex(3)
        layout.addWidget(self.mode)

        settings = QFormLayout()
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.5, 30)
        self.delay.setSingleStep(0.5)
        self.delay.setValue(3)
        self.delay.setSuffix(" s")
        settings.addRow("Start delay", self.delay)

        self.interval = QSpinBox()
        self.interval.setRange(10, 5000)
        self.interval.setValue(120)
        self.interval.setSuffix(" ms")
        settings.addRow("Key interval", self.interval)

        self.hold = QSpinBox()
        self.hold.setRange(1, 500)
        self.hold.setValue(20)
        self.hold.setSuffix(" ms")
        settings.addRow("Key hold", self.hold)
        layout.addLayout(settings)

        layout.addWidget(QLabel("Typing preview"))
        self.preview = QLabel()
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview.setWordWrap(True)
        self.preview.setMaximumHeight(74)
        layout.addWidget(self.preview)

        self.status = QLabel("Ready. F8 stops an active session.")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        layout.addLayout(actions)

        self.editor.textChanged.connect(self._update_preview)
        self.mode.currentIndexChanged.connect(self._update_preview)
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        self._update_preview()

    def _update_preview(self) -> None:
        text = self.editor.toPlainText()
        mode = self.mode.currentData()
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
        self.worker.result.connect(self.status.setText)
        self.worker.finished.connect(self._finished)
        self.progress.setMaximum(plan.count)
        self.progress.setValue(0)
        self.status.setText(f"Switch to the destination app within {self.delay.value():g} s")
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
            self.status.setText("Stopping...")

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

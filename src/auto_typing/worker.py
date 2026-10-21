"""Qt worker that drives a frozen plan without blocking the UI."""

from __future__ import annotations

import time
from threading import Event

from PySide6.QtCore import QThread, Signal

from .core import TypingActionKind, TypingPlan
from .win_keyboard import WindowsKeyboard


class _Stopped(Exception):
    pass


class TypingWorker(QThread):
    progress = Signal(int, int)
    result = Signal(str)

    def __init__(
        self,
        plan: TypingPlan,
        start_delay: float,
        interval_ms: int,
        hold_ms: int,
    ) -> None:
        super().__init__()
        self.plan = plan
        self.start_delay = start_delay
        self.interval_seconds = interval_ms / 1000.0
        self.hold_seconds = hold_ms / 1000.0
        self._stop_event = Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _check_cancelled(self, keyboard: WindowsKeyboard) -> None:
        if self._stop_event.is_set() or keyboard.stop_hotkey_pressed():
            raise _Stopped()

    def _wait(self, seconds: float, keyboard: WindowsKeyboard) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            self._check_cancelled(keyboard)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._stop_event.wait(min(remaining, 0.01))

    def run(self) -> None:
        try:
            keyboard = WindowsKeyboard()
            self._wait(self.start_delay, keyboard)
            target = keyboard.capture_foreground_target()
            total = self.plan.count

            for index, action in enumerate(self.plan.actions, start=1):
                self._check_cancelled(keyboard)
                keyboard.ensure_foreground(target)
                wait = lambda seconds: self._wait(seconds, keyboard)
                if action.kind == TypingActionKind.PASTE:
                    keyboard.paste(self.hold_seconds, wait)
                elif action.kind == TypingActionKind.UNICODE:
                    keyboard.type_unicode(action.value, self.hold_seconds, wait)
                else:
                    keyboard.type_physical(action.value, self.hold_seconds, wait)
                self.progress.emit(index, total)
                if index < total:
                    self._wait(max(0.0, self.interval_seconds - self.hold_seconds), keyboard)

            self.result.emit("Completed")
        except _Stopped:
            self.result.emit("Stopped")
        except Exception as error:  # noqa: BLE001 - worker must report unexpected failures
            self.result.emit(f"Failed: {error}")

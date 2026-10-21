"""Worker-level hybrid dispatch tests without a real Windows desktop."""

from __future__ import annotations

from auto_typing.core import TypingActionKind, TypingMode, build_plan
from auto_typing.worker import TypingWorker


class FakeKeyboard:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.targets: list[int] = []

    def stop_hotkey_pressed(self) -> bool:
        return False

    def capture_foreground_target(self) -> int:
        return 42

    def ensure_foreground(self, target: int) -> None:
        self.targets.append(target)

    def type_unicode(self, char: str, hold_seconds: float, wait) -> None:
        self.calls.append(("unicode", char))

    def type_physical(self, char: str, hold_seconds: float, wait) -> None:
        self.calls.append(("physical", char))

    def paste(self, hold_seconds: float, wait) -> None:
        self.calls.append(("paste", ""))


def _execute(monkeypatch, plan):
    keyboard = FakeKeyboard()
    monkeypatch.setattr("auto_typing.worker.WindowsKeyboard", lambda: keyboard)
    worker = TypingWorker(plan=plan, start_delay=0, interval_ms=1, hold_ms=1)
    progress = []
    results = []
    worker.progress.connect(lambda current, total: progress.append((current, total)))
    worker.result.connect(results.append)
    worker.run()
    return keyboard, progress, results


def test_hybrid_worker_dispatches_english_as_unicode_and_vietnamese_as_keys(
    monkeypatch,
) -> None:
    plan = build_plan("as Chào dd 😊", TypingMode.TELEX)
    keyboard, progress, results = _execute(monkeypatch, plan)

    assert keyboard.calls == [(action.kind.value, action.value) for action in plan.actions]
    assert keyboard.calls[:2] == [("unicode", "a"), ("unicode", "s")]
    assert keyboard.calls[3:8] == [("physical", c) for c in "Chaof"]
    assert keyboard.calls[-1] == ("unicode", "😊")
    assert all(hwnd == 42 for hwnd in keyboard.targets)
    assert len(keyboard.targets) == plan.count
    assert progress[-1] == (plan.count, plan.count)
    assert results == ["Completed"]


def test_paste_mode_remains_single_clipboard_action(monkeypatch) -> None:
    plan = build_plan("as Chào", TypingMode.PASTE)
    keyboard, progress, results = _execute(monkeypatch, plan)

    assert [action.kind for action in plan.actions] == [TypingActionKind.PASTE]
    assert keyboard.calls == [("paste", "")]
    assert progress == [(1, 1)]
    assert results == ["Completed"]

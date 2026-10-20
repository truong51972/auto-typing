"""Windows-only synthetic keyboard backend using documented Win32 SendInput."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import sys
from typing import Callable


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_V = 0x56
VK_F8 = 0x77


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    """Largest Win32 INPUT variant; required for the union's native ABI size."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    # Using only KEYBDINPUT produces an undersized INPUT (32 instead of 40
    # bytes on x64). SendInput rejects the wrong cbSize with WinError 87.
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


WaitFunction = Callable[[float], None]


class WindowsKeyboard:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Typing injection is currently supported on Windows only")

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.VkKeyScanExW.argtypes = (wintypes.WCHAR, wintypes.HKL)
        self.user32.VkKeyScanExW.restype = ctypes.c_short
        self.user32.GetKeyboardLayout.argtypes = (wintypes.DWORD,)
        self.user32.GetKeyboardLayout.restype = wintypes.HKL
        self._target_layout: int | None = None
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        )
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        self.user32.GetAsyncKeyState.restype = ctypes.c_short

    def _send(self, virtual_key: int, flags: int = 0, scan_code: int = 0) -> None:
        event = INPUT(
            type=INPUT_KEYBOARD,
            union=_INPUT_UNION(
                ki=KEYBDINPUT(
                    wVk=virtual_key, wScan=scan_code, dwFlags=flags, time=0, dwExtraInfo=0
                )
            ),
        )
        sent = self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        if sent != 1:
            raise OSError(ctypes.get_last_error(), "SendInput failed (target may be elevated)")

    def _tap_key(self, virtual_key: int, hold_seconds: float, wait: WaitFunction) -> None:
        key_is_down = False
        try:
            self._send(virtual_key)
            key_is_down = True
            wait(hold_seconds)
        finally:
            if key_is_down:
                self._send(virtual_key, KEYEVENTF_KEYUP)

    def type_physical(self, char: str, hold_seconds: float, wait: WaitFunction) -> None:
        """Type one ASCII key; honor the active Windows keyboard layout."""
        if char == "\n":
            self._tap_key(VK_RETURN, hold_seconds, wait)
            return

        translation = self.user32.VkKeyScanExW(char, self._target_layout)
        if translation == -1:
            raise ValueError(f"No physical key mapping for {char!r}")

        virtual_key = translation & 0xFF
        modifiers = (translation >> 8) & 0xFF
        if modifiers & ~1:
            raise ValueError(f"{char!r} requires Ctrl/Alt; use Unicode or Paste mode")

        shifted = bool(modifiers & 1)
        shift_is_down = False
        try:
            if shifted:
                self._send(VK_SHIFT)
                shift_is_down = True
            self._tap_key(virtual_key, hold_seconds, wait)
        finally:
            if shift_is_down:
                self._send(VK_SHIFT, KEYEVENTF_KEYUP)

    def type_unicode(self, char: str, hold_seconds: float, wait: WaitFunction) -> None:
        """Inject UTF-16 code units; non-BMP characters become a surrogate pair."""
        if char == "\n":
            self.type_physical(char, hold_seconds, wait)
            return

        raw = char.encode("utf-16-le")
        for offset in range(0, len(raw), 2):
            code_unit = int.from_bytes(raw[offset : offset + 2], byteorder="little")
            key_is_down = False
            try:
                self._send(0, KEYEVENTF_UNICODE, code_unit)
                key_is_down = True
                wait(hold_seconds / (len(raw) // 2))
            finally:
                if key_is_down:
                    self._send(0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, code_unit)

    def paste(self, hold_seconds: float, wait: WaitFunction) -> None:
        ctrl_is_down = False
        try:
            self._send(VK_CONTROL)
            ctrl_is_down = True
            self._tap_key(VK_V, hold_seconds, wait)
        finally:
            if ctrl_is_down:
                self._send(VK_CONTROL, KEYEVENTF_KEYUP)

    def capture_foreground_target(self) -> int:
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("No destination window is focused")
        pid = wintypes.DWORD()
        thread_id = self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            raise RuntimeError("Focus the destination app before the countdown ends")
        self._target_layout = self.user32.GetKeyboardLayout(thread_id)
        if not self._target_layout:
            raise RuntimeError("Could not detect destination keyboard layout")
        return int(hwnd)

    def ensure_foreground(self, expected_hwnd: int) -> None:
        if self.user32.GetForegroundWindow() != expected_hwnd:
            raise RuntimeError("Destination focus changed; typing stopped to avoid misdirected input")

    def stop_hotkey_pressed(self) -> bool:
        return bool(self.user32.GetAsyncKeyState(VK_F8) & 0x8000)

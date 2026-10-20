"""Regression tests for Win32 keyboard injection without a Windows desktop."""

import ctypes
from types import SimpleNamespace

from auto_typing.win_keyboard import (
    _INPUT_UNION,
    INPUT,
    KEYBDINPUT,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    MOUSEINPUT,
    VK_CONTROL,
    VK_SHIFT,
    VK_V,
    WindowsKeyboard,
)


def test_sendinput_struct_uses_correct_native_abi_size() -> None:
    # Windows requires cbSize=40 for x64, 28 for x86.
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(INPUT) == (40 if pointer_size == 8 else 28)
    assert INPUT.union.offset == (8 if pointer_size == 8 else 4)
    assert ctypes.sizeof(_INPUT_UNION) == ctypes.sizeof(MOUSEINPUT)
    assert ctypes.sizeof(KEYBDINPUT) == (24 if pointer_size == 8 else 16)


def test_send_passes_correct_size_and_key_event() -> None:
    calls = []

    def fake_send_input(count, pointer, size):
        event = ctypes.cast(pointer, ctypes.POINTER(INPUT)).contents
        calls.append((count, size, event.type, event.union.ki.wVk, event.union.ki.dwFlags))
        return 1

    keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
    keyboard.user32 = SimpleNamespace(SendInput=fake_send_input)
    keyboard._send(VK_V, KEYEVENTF_KEYUP)

    assert calls == [(1, ctypes.sizeof(INPUT), 1, VK_V, KEYEVENTF_KEYUP)]


def test_physical_keys_respect_shift_mapping() -> None:
    events = []
    keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
    keyboard.user32 = SimpleNamespace(VkKeyScanExW=lambda char, layout: ord("A") | 0x100)
    keyboard._target_layout = 1
    keyboard._send = lambda key, flags=0, scan_code=0: events.append((key, flags))

    keyboard.type_physical("A", 0.02, lambda seconds: None)
    assert events == [
        (VK_SHIFT, 0),
        (ord("A"), 0),
        (ord("A"), KEYEVENTF_KEYUP),
        (VK_SHIFT, KEYEVENTF_KEYUP),
    ]


def test_unicode_surrogate_pair_is_sent_as_two_utf16_units() -> None:
    events = []
    keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
    keyboard._send = lambda key, flags=0, scan_code=0: events.append(
        (key, flags, scan_code)
    )

    keyboard.type_unicode("😊", 0.02, lambda seconds: None)
    units = [int.from_bytes("😊".encode("utf-16-le")[i : i + 2], "little") for i in (0, 2)]
    assert events == [
        (0, KEYEVENTF_UNICODE, units[0]),
        (0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, units[0]),
        (0, KEYEVENTF_UNICODE, units[1]),
        (0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, units[1]),
    ]


def test_paste_releases_ctrl() -> None:
    events = []
    keyboard = WindowsKeyboard.__new__(WindowsKeyboard)
    keyboard._send = lambda key, flags=0, scan_code=0: events.append((key, flags))

    keyboard.paste(0.02, lambda seconds: None)
    assert events == [
        (VK_CONTROL, 0),
        (VK_V, 0),
        (VK_V, KEYEVENTF_KEYUP),
        (VK_CONTROL, KEYEVENTF_KEYUP),
    ]

"""Pure text conversion and typing-plan construction (no OS or Qt dependency)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum


class TypingMode(str, Enum):
    PASTE = "paste"
    UNICODE = "unicode"
    PHYSICAL = "physical"
    TELEX = "telex"


_TONE_MARKS = {
    "\u0301": "s",  # acute
    "\u0300": "f",  # grave
    "\u0309": "r",  # hook above
    "\u0303": "x",  # tilde
    "\u0323": "j",  # dot below
}
_VOWEL_MARKS = {
    "\u0302": {"a": "aa", "e": "ee", "o": "oo"},  # circumflex
    "\u0306": {"a": "aw"},  # breve
    "\u031b": {"o": "ow", "u": "uw"},  # horn
}


def _to_telex_word(word: str) -> str:
    result: list[str] = []
    tone: str | None = None

    for char in word:
        if char == "đ":
            result.append("dd")
            continue
        if char == "Đ":
            result.append("Dd")
            continue

        decomposed = unicodedata.normalize("NFD", char)
        base, marks = decomposed[0], decomposed[1:]
        if not (base.isascii() and base.isalpha()):
            raise ValueError(f"Cannot convert {char!r} to Telex; use Unicode/Paste mode")

        typed = base
        for mark in marks:
            if mark in _TONE_MARKS:
                if tone is not None:
                    raise ValueError(f"Multiple Vietnamese tone marks in {word!r}")
                tone = _TONE_MARKS[mark]
            elif mark in _VOWEL_MARKS and base.lower() in _VOWEL_MARKS[mark]:
                expanded = _VOWEL_MARKS[mark][base.lower()]
                typed = expanded.capitalize() if base.isupper() else expanded
            else:
                raise ValueError(f"Unsupported mark in {char!r}; use Unicode/Paste mode")
        result.append(typed)

    return "".join(result) + (tone or "")


def to_telex(text: str) -> str:
    """Convert Vietnamese words to Telex keystroke text, placing tone at word end.

    The result is a best-effort IME input sequence, not a universally reversible encoding.
    """
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    word: list[str] = []

    def flush_word() -> None:
        if word:
            out.append(_to_telex_word("".join(word)))
            word.clear()

    for char in text:
        if char.isalpha():
            word.append(char)
        else:
            flush_word()
            out.append(char)

    flush_word()
    return "".join(out)


@dataclass(frozen=True)
class TypingPlan:
    mode: TypingMode
    original_text: str
    payload: str
    keys: tuple[str, ...]

    @property
    def count(self) -> int:
        return 1 if self.mode == TypingMode.PASTE else len(self.keys)


def build_plan(text: str, mode: TypingMode) -> TypingPlan:
    """Validate and freeze the session before switching focus to the target window."""
    if not text:
        raise ValueError("Enter some text before starting")

    clean_text = text.replace("\r\n", "\n").replace("\r", "\n")
    payload = to_telex(clean_text) if mode == TypingMode.TELEX else clean_text
    keys = () if mode == TypingMode.PASTE else tuple(payload)

    for char in keys:
        if char == "\n":
            continue
        if char in ("\x00", "\t") or unicodedata.category(char).startswith("C"):
            raise ValueError("Control characters and tabs are unsupported in typing modes")
        if mode in (TypingMode.PHYSICAL, TypingMode.TELEX) and not (" " <= char <= "~"):
            raise ValueError(
                f"Physical/Telex mode cannot type {char!r}; use Unicode/Paste mode"
            )

    return TypingPlan(mode=mode, original_text=clean_text, payload=payload, keys=keys)
